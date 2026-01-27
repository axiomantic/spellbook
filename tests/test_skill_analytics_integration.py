"""Integration tests for skill analytics end-to-end flow."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch


class TestEndToEndSkillAnalytics:
    """Test complete flow from session monitoring to analytics query."""

    def test_full_analytics_flow(self, tmp_path, monkeypatch):
        """Test: session created -> watcher detects -> outcomes persisted -> analytics queried."""
        from spellbook_mcp.db import init_db, get_connection, close_all_connections
        from spellbook_mcp.watcher import SessionWatcher
        from spellbook_mcp.skill_analyzer import (
            get_analytics_summary,
            OUTCOME_COMPLETED,
        )

        # Setup
        db_path = tmp_path / "test.db"
        project_path = tmp_path / "project"
        project_path.mkdir()
        init_db(str(db_path))

        # Create session with multiple skills
        session_dir = tmp_path / ".claude" / "projects" / "-tmp-project"
        session_dir.mkdir(parents=True)
        session_file = session_dir / "integration-test.jsonl"

        messages = [
            # First skill: debugging (completed)
            {
                "type": "assistant",
                "timestamp": "2026-01-26T10:00:00",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                    "usage": {"output_tokens": 200},
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "Debug complete"}],
                    "usage": {"output_tokens": 100},
                },
            },
            # Second skill: implementing-features (supersedes debugging)
            {
                "type": "assistant",
                "timestamp": "2026-01-26T10:05:00",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "implementing-features:v2"}}
                    ],
                    "usage": {"output_tokens": 500},
                },
            },
        ]
        session_file.write_text("\n".join(json.dumps(m) for m in messages) + "\n")

        # Create watcher and run analysis
        watcher = SessionWatcher(str(db_path), project_path=str(project_path))

        with patch(
            "spellbook_mcp.compaction_detector._get_current_session_file",
            return_value=session_file,
        ):
            watcher._analyze_skills()

        # Query analytics
        project_encoded = str(project_path).replace("/", "-").lstrip("-")
        summary = get_analytics_summary(
            project_encoded=project_encoded,
            days=1,
            db_path=str(db_path),
        )

        # Verify results
        assert summary["total_outcomes"] >= 1
        assert "debugging" in summary["by_skill"] or "implementing-features" in summary["by_skill"]

        # Cleanup
        close_all_connections()

    def test_privacy_compliance(self, tmp_path):
        """Test that telemetry aggregates exclude sensitive data."""
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, anonymize_for_telemetry, OUTCOME_COMPLETED
        )

        # Create outcomes with sensitive data
        outcomes = [
            SkillOutcome(
                skill_name="debugging",
                session_id=f"secret-session-{i}",  # Sensitive
                project_encoded=f"users-alice-projects-secret-{i}",  # Sensitive
                start_time=datetime(2026, 1, 26, 10, i, 0),
                duration_seconds=120.0,
                outcome=OUTCOME_COMPLETED,
                tokens_used=2000,
                corrections=3,  # Sensitive
            )
            for i in range(5)
        ]

        aggregates = anonymize_for_telemetry(outcomes, min_count=5)

        assert len(aggregates) == 1
        agg = aggregates[0]

        # Verify NO sensitive fields are present
        # The TelemetryAggregate dataclass should not have these fields
        agg_dict = {
            "skill_name": agg.skill_name,
            "skill_version": agg.skill_version,
            "outcome": agg.outcome,
            "duration_bucket": agg.duration_bucket,
            "token_bucket": agg.token_bucket,
            "count": agg.count,
        }

        assert "session_id" not in str(agg_dict)
        assert "secret-session" not in str(agg_dict)
        assert "project_encoded" not in str(agg_dict)
        assert "alice" not in str(agg_dict)
        assert "corrections" not in str(agg_dict)

        # Verify bucketing happened
        assert agg.duration_bucket == "1-5m"  # 120s -> 1-5m
        assert agg.token_bucket == "1-5k"    # 2000 -> 1-5k

    def test_telemetry_min_count_enforcement(self, tmp_path):
        """Test that aggregates below min_count are excluded."""
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, anonymize_for_telemetry, OUTCOME_COMPLETED, OUTCOME_ABANDONED
        )

        # 4 completed (below threshold) and 5 abandoned (at threshold)
        outcomes = [
            SkillOutcome(
                skill_name="debugging",
                session_id=f"s{i}",
                project_encoded="p",
                start_time=datetime(2026, 1, 26, 10, i, 0),
                duration_seconds=60.0,
                outcome=OUTCOME_COMPLETED,
                tokens_used=1000,
            )
            for i in range(4)
        ] + [
            SkillOutcome(
                skill_name="debugging",
                session_id=f"s{i}",
                project_encoded="p",
                start_time=datetime(2026, 1, 26, 11, i, 0),
                duration_seconds=60.0,
                outcome=OUTCOME_ABANDONED,
                tokens_used=1000,
            )
            for i in range(5)
        ]

        aggregates = anonymize_for_telemetry(outcomes, min_count=5)

        # Only abandoned should be included (5 samples)
        assert len(aggregates) == 1
        assert aggregates[0].outcome == OUTCOME_ABANDONED
        assert aggregates[0].count == 5


class TestSessionInactivityHandling:
    """Test session inactivity detection and finalization."""

    def test_inactive_session_finalizes_open_skills(self, tmp_path):
        """Test that inactive sessions have their open skills finalized."""
        from spellbook_mcp.db import init_db, get_connection, close_all_connections
        from spellbook_mcp.watcher import SessionWatcher, SessionSkillState, SESSION_INACTIVE_THRESHOLD_SECONDS
        from spellbook_mcp.skill_analyzer import OUTCOME_SESSION_ENDED

        db_path = tmp_path / "test.db"
        project_path = tmp_path / "project"
        project_path.mkdir()
        init_db(str(db_path))

        session_dir = tmp_path / ".claude" / "projects" / "-tmp-project"
        session_dir.mkdir(parents=True)
        session_file = session_dir / "inactive-test.jsonl"

        # Create session with a skill that never completes
        messages = [
            {
                "type": "assistant",
                "timestamp": "2026-01-26T10:00:00",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                },
            },
        ]
        session_file.write_text("\n".join(json.dumps(m) for m in messages) + "\n")

        watcher = SessionWatcher(str(db_path), project_path=str(project_path))

        # First poll: detect skill
        with patch(
            "spellbook_mcp.compaction_detector._get_current_session_file",
            return_value=session_file,
        ):
            watcher._analyze_skills()

        # Simulate inactivity
        session_id = session_file.stem
        if session_id in watcher._skill_states:
            watcher._skill_states[session_id].last_activity = (
                datetime.now() - timedelta(seconds=SESSION_INACTIVE_THRESHOLD_SECONDS + 60)
            )

        # Insert a record with empty outcome to simulate open skill
        conn = get_connection(str(db_path))
        conn.execute("""
            INSERT OR REPLACE INTO skill_outcomes
            (skill_name, session_id, project_encoded, start_time, outcome)
            VALUES (?, ?, ?, ?, ?)
        """, ("debugging", session_id, "test", "2026-01-26T10:00:00", ""))
        conn.commit()

        # Second poll: should finalize
        with patch(
            "spellbook_mcp.compaction_detector._get_current_session_file",
            return_value=session_file,
        ):
            watcher._analyze_skills()

        # Verify finalization
        cursor = conn.cursor()
        cursor.execute(
            "SELECT outcome FROM skill_outcomes WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == OUTCOME_SESSION_ENDED

        # Session should be removed from tracking
        assert session_id not in watcher._skill_states

        # Cleanup
        close_all_connections()


class TestAnalyticsSummaryFiltering:
    """Test analytics summary filtering capabilities."""

    def test_filter_by_project(self, tmp_path):
        """Test that project_encoded filter works correctly."""
        from spellbook_mcp.db import init_db, get_connection, close_all_connections
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, persist_outcome, get_analytics_summary,
            OUTCOME_COMPLETED,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert outcomes for two different projects
        for project in ["project-a", "project-b"]:
            for i in range(3):
                outcome = SkillOutcome(
                    skill_name="debugging",
                    session_id=f"session-{project}-{i}",
                    project_encoded=project,
                    start_time=datetime(2026, 1, 26, 10, i, 0),
                    outcome=OUTCOME_COMPLETED,
                    tokens_used=1000,
                )
                persist_outcome(outcome, db_path)

        # Query for project-a only
        summary = get_analytics_summary(
            project_encoded="project-a",
            days=1,
            db_path=db_path,
        )

        assert summary["total_outcomes"] == 3
        assert "debugging" in summary["by_skill"]
        assert summary["by_skill"]["debugging"]["invocations"] == 3

        # Cleanup
        close_all_connections()

    def test_filter_by_skill(self, tmp_path):
        """Test that skill filter works correctly."""
        from spellbook_mcp.db import init_db, get_connection, close_all_connections
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, persist_outcome, get_analytics_summary,
            OUTCOME_COMPLETED,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert outcomes for two different skills
        for skill in ["debugging", "implementing-features"]:
            for i in range(3):
                outcome = SkillOutcome(
                    skill_name=skill,
                    session_id=f"session-{skill}-{i}",
                    project_encoded="project",
                    start_time=datetime(2026, 1, 26, 10, i, 0),
                    outcome=OUTCOME_COMPLETED,
                    tokens_used=1000,
                )
                persist_outcome(outcome, db_path)

        # Query for debugging only
        summary = get_analytics_summary(
            skill="debugging",
            days=1,
            db_path=db_path,
        )

        assert summary["total_outcomes"] == 3
        assert "debugging" in summary["by_skill"]
        assert "implementing-features" not in summary["by_skill"]

        # Cleanup
        close_all_connections()

    def test_filter_by_days(self, tmp_path):
        """Test that days filter works correctly."""
        from spellbook_mcp.db import init_db, get_connection, close_all_connections
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, persist_outcome, get_analytics_summary,
            OUTCOME_COMPLETED,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert outcomes - some recent, some old
        now = datetime.now()

        # Recent outcome
        recent = SkillOutcome(
            skill_name="debugging",
            session_id="recent-session",
            project_encoded="project",
            start_time=now - timedelta(hours=1),
            outcome=OUTCOME_COMPLETED,
            tokens_used=1000,
        )
        persist_outcome(recent, db_path)

        # Old outcome - manually insert with old created_at
        conn = get_connection(db_path)
        old_time = (now - timedelta(days=10)).isoformat()
        conn.execute("""
            INSERT INTO skill_outcomes
            (skill_name, session_id, project_encoded, start_time, outcome, tokens_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("debugging", "old-session", "project", old_time, OUTCOME_COMPLETED, 1000, old_time))
        conn.commit()

        # Query for last 5 days only
        summary = get_analytics_summary(
            days=5,
            db_path=db_path,
        )

        assert summary["total_outcomes"] == 1  # Only the recent one
        assert summary["period_days"] == 5

        # Cleanup
        close_all_connections()


class TestWeakSkillDetection:
    """Test weak skill detection and ranking."""

    def test_weak_skills_ranked_by_failure_score(self, tmp_path):
        """Test that weak skills are correctly identified and ranked."""
        from spellbook_mcp.db import init_db, close_all_connections
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, persist_outcome, get_analytics_summary,
            OUTCOME_COMPLETED, OUTCOME_ABANDONED,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Good skill: high completion rate
        for i in range(10):
            outcome = SkillOutcome(
                skill_name="good-skill",
                session_id=f"session-good-{i}",
                project_encoded="project",
                start_time=datetime(2026, 1, 26, 10, i, 0),
                outcome=OUTCOME_COMPLETED,
                tokens_used=1000,
                corrections=0,
            )
            persist_outcome(outcome, db_path)

        # Bad skill: low completion rate, high corrections
        for i in range(10):
            outcome = SkillOutcome(
                skill_name="bad-skill",
                session_id=f"session-bad-{i}",
                project_encoded="project",
                start_time=datetime(2026, 1, 26, 11, i, 0),
                outcome=OUTCOME_ABANDONED if i < 7 else OUTCOME_COMPLETED,
                tokens_used=1000,
                corrections=3,
            )
            persist_outcome(outcome, db_path)

        summary = get_analytics_summary(days=1, db_path=db_path)

        # bad-skill should be in weak_skills, good-skill should not
        weak_skill_names = [s["skill"] for s in summary["weak_skills"]]
        assert "bad-skill" in weak_skill_names
        assert "good-skill" not in weak_skill_names

        # Verify bad-skill has higher failure score
        assert summary["by_skill"]["bad-skill"]["failure_score"] > summary["by_skill"]["good-skill"]["failure_score"]

        # Cleanup
        close_all_connections()
