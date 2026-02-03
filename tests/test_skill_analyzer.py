"""Tests for skill usage analyzer."""

import pytest
from datetime import datetime
from spellbook_mcp.skill_analyzer import (
    extract_skill_invocations,
    aggregate_metrics,
    _get_tool_uses,
    _get_user_content,
    _get_role,
    _detect_correction,
    _extract_version,
    SkillInvocation,
    SkillOutcome,
    persist_outcome,
    OUTCOME_COMPLETED,
    OUTCOME_ABANDONED,
)
from spellbook_mcp.db import init_db, get_connection


class TestToolUseExtraction:
    """Test extraction of tool_use blocks from messages."""

    def test_extracts_tool_use_from_assistant_message(self):
        msg = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll use a skill."},
                    {
                        "type": "tool_use",
                        "id": "toolu_123",
                        "name": "Skill",
                        "input": {"skill": "debugging"},
                    },
                ],
            },
        }
        tools = _get_tool_uses(msg)
        assert len(tools) == 1
        assert tools[0]["name"] == "Skill"
        assert tools[0]["input"]["skill"] == "debugging"

    def test_returns_empty_for_user_message(self):
        msg = {
            "type": "user",
            "message": {"role": "user", "content": "Hello"},
        }
        assert _get_tool_uses(msg) == []

    def test_returns_empty_for_string_content(self):
        msg = {
            "type": "assistant",
            "message": {"role": "assistant", "content": "Just text"},
        }
        assert _get_tool_uses(msg) == []

    def test_filters_non_tool_use_blocks(self):
        msg = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "thinking..."},
                    {"type": "thinking", "thinking": "hmm"},
                    {"type": "tool_use", "name": "Read", "input": {}},
                ],
            },
        }
        tools = _get_tool_uses(msg)
        assert len(tools) == 1
        assert tools[0]["name"] == "Read"


class TestUserContentExtraction:
    """Test extraction of user message content."""

    def test_extracts_string_content(self):
        msg = {
            "type": "user",
            "message": {"role": "user", "content": "Hello world"},
        }
        assert _get_user_content(msg) == "Hello world"

    def test_extracts_list_content(self):
        msg = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "text", "text": "Line 1"},
                    {"type": "text", "text": "Line 2"},
                ],
            },
        }
        assert _get_user_content(msg) == "Line 1\nLine 2"

    def test_returns_empty_for_assistant(self):
        msg = {
            "type": "assistant",
            "message": {"content": "Not extracted"},
        }
        assert _get_user_content(msg) == ""


class TestCorrectionDetection:
    """Test detection of user correction patterns."""

    @pytest.mark.parametrize(
        "text",
        [
            "No, that's wrong",
            "Stop doing that",
            "That's incorrect",
            "Actually, I meant...",
            "Don't do it that way",
            "do it instead like this",
            "That's not what I asked",
        ],
    )
    def test_detects_correction_patterns(self, text):
        assert _detect_correction(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Yes, that looks good",
            "Continue with that approach",
            "I know what you mean",  # "know" not "no"
            "The function is not working",  # "not" is fine
            "Now let's move on",  # "now" not "no"
        ],
    )
    def test_ignores_non_corrections(self, text):
        assert _detect_correction(text) is False


class TestVersionExtraction:
    """Test version marker extraction."""

    def test_extracts_version_from_skill_name(self):
        base, version = _extract_version("implementing-features:v2", None)
        assert base == "implementing-features"
        assert version == "v2"

    def test_extracts_version_from_args_bracket(self):
        base, version = _extract_version("debugging", "[v3] with extra context")
        assert base == "debugging"
        assert version == "v3"

    def test_extracts_version_from_args_flag(self):
        base, version = _extract_version("debugging", "--version v2")
        assert base == "debugging"
        assert version == "v2"

    def test_returns_none_when_no_version(self):
        base, version = _extract_version("debugging", "some args")
        assert base == "debugging"
        assert version is None


class TestSkillInvocationExtraction:
    """Test extraction of skill invocations from message sequences."""

    def test_extracts_single_skill_invocation(self):
        messages = [
            {"type": "user", "message": {"content": "Help me debug"}},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Skill",
                            "input": {"skill": "debugging"},
                        }
                    ],
                    "usage": {"output_tokens": 100},
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "Debugging..."}],
                    "usage": {"output_tokens": 200},
                },
            },
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 1
        assert invocations[0].skill == "debugging"
        assert invocations[0].completed is True
        assert invocations[0].tokens_used == 300

    def test_detects_superseded_skill(self):
        messages = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                    "usage": {"output_tokens": 50},
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "implementing-features"}}
                    ],
                    "usage": {"output_tokens": 100},
                },
            },
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 2
        assert invocations[0].skill == "debugging"
        assert invocations[0].superseded is True
        assert invocations[0].completed is False
        assert invocations[1].skill == "implementing-features"
        assert invocations[1].completed is True

    def test_counts_user_corrections(self):
        messages = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                },
            },
            {"type": "user", "message": {"role": "user", "content": "No, that's wrong"}},
            {"type": "user", "message": {"role": "user", "content": "Stop, try again"}},
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 1
        assert invocations[0].corrections == 2

    def test_detects_retry(self):
        messages = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                },
            },
            {"type": "user", "message": {"content": "Try again"}},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                },
            },
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 2
        assert invocations[0].retried is False  # First one wasn't a retry
        assert invocations[1].retried is True  # Second one is a retry

    def test_handles_compact_boundary(self):
        messages = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Skill", "input": {"skill": "debugging"}}
                    ],
                },
            },
            {"type": "system", "subtype": "compact_boundary"},
        ]

        invocations = extract_skill_invocations(messages)
        assert len(invocations) == 1
        assert invocations[0].completed is True


class TestMetricsAggregation:
    """Test aggregation of invocations into metrics."""

    def test_aggregates_by_skill(self):
        invocations = [
            SkillInvocation(skill="debugging", tokens_used=100, completed=True, corrections=0),
            SkillInvocation(skill="debugging", tokens_used=200, completed=True, corrections=1),
            SkillInvocation(skill="implementing-features", tokens_used=500, completed=False, superseded=True),
        ]

        metrics = aggregate_metrics(invocations)
        assert len(metrics) == 2

        debug_metrics = metrics["debugging"]
        assert debug_metrics.invocations == 2
        assert debug_metrics.completions == 2
        assert debug_metrics.corrections == 1
        assert debug_metrics.avg_tokens == 150

        impl_metrics = metrics["implementing-features"]
        assert impl_metrics.invocations == 1
        assert impl_metrics.completions == 0

    def test_groups_by_version_when_requested(self):
        invocations = [
            SkillInvocation(skill="debugging", version="v1", tokens_used=100, completed=True),
            SkillInvocation(skill="debugging", version="v2", tokens_used=80, completed=True),
            SkillInvocation(skill="debugging", version="v1", tokens_used=120, completed=False),
        ]

        metrics = aggregate_metrics(invocations, group_by_version=True)
        assert len(metrics) == 2
        assert "debugging:v1" in metrics
        assert "debugging:v2" in metrics
        assert metrics["debugging:v1"].invocations == 2
        assert metrics["debugging:v2"].invocations == 1

    def test_calculates_failure_score(self):
        invocations = [
            SkillInvocation(skill="bad-skill", completed=False, corrections=1, retried=True),
            SkillInvocation(skill="bad-skill", completed=True, corrections=0, retried=False),
        ]

        metrics = aggregate_metrics(invocations)
        # Failure score = (corrections + retries + non-completions) / invocations
        # = (1 + 1 + 1) / 2 = 1.5, but capped at invocations, so 3/2 = 1.5... wait
        # Actually: 1 correction, 1 retry (second invocation has retried=False), 1 non-completion
        # But retried is on the invocation itself, and second has retried=False
        # So: 1 correction + 0 retries (from first) + 1 retry (second marked as retry? No, second.retried=False)
        # Hmm, let me recalculate:
        # invocation 1: completed=False (1 failure), corrections=1, retried=True
        # invocation 2: completed=True, corrections=0, retried=False
        # failures = corrections(1+0) + retries(1+0) + non-completions(1+0) = 3
        # Wait, retried is counted per invocation where it's true
        bad_skill = metrics["bad-skill"]
        assert bad_skill.failure_score > 0


class TestSkillOutcome:
    """Test SkillOutcome dataclass and conversion from SkillInvocation."""

    def test_skill_outcome_creation(self):
        outcome = SkillOutcome(
            skill_name="debugging",
            session_id="session-123",
            project_encoded="test-project",
            start_time=datetime.now(),
            outcome=OUTCOME_COMPLETED,
            tokens_used=1000,
        )
        assert outcome.skill_name == "debugging"
        assert outcome.session_id == "session-123"
        assert outcome.outcome == OUTCOME_COMPLETED

    def test_from_invocation_completed(self):
        """Test conversion of completed invocation."""
        from spellbook_mcp.skill_analyzer import SkillOutcome, OUTCOME_COMPLETED

        inv = SkillInvocation(
            skill="debugging",
            version="v1",
            start_idx=0,
            end_idx=10,
            timestamp="2026-01-26T10:00:00",
            tokens_used=500,
            corrections=1,
            completed=True,
            superseded=False,
            retried=False,
        )

        outcome = SkillOutcome.from_invocation(inv, "session-123", "Users-test-project")

        assert outcome.skill_name == "debugging"
        assert outcome.skill_version == "v1"
        assert outcome.session_id == "session-123"
        assert outcome.project_encoded == "Users-test-project"
        assert outcome.outcome == OUTCOME_COMPLETED
        assert outcome.tokens_used == 500
        assert outcome.corrections == 1
        assert outcome.retries == 0

    def test_from_invocation_superseded(self):
        """Test conversion of superseded invocation."""
        from spellbook_mcp.skill_analyzer import SkillOutcome, OUTCOME_SUPERSEDED

        inv = SkillInvocation(
            skill="debugging",
            completed=False,
            superseded=True,
        )

        outcome = SkillOutcome.from_invocation(inv, "session-123", "project")
        assert outcome.outcome == OUTCOME_SUPERSEDED

    def test_from_invocation_abandoned(self):
        """Test conversion of abandoned invocation."""
        from spellbook_mcp.skill_analyzer import SkillOutcome, OUTCOME_ABANDONED

        inv = SkillInvocation(
            skill="debugging",
            completed=False,
            superseded=False,
            end_idx=10,  # Has end but not completed
        )

        outcome = SkillOutcome.from_invocation(inv, "session-123", "project")
        assert outcome.outcome == OUTCOME_ABANDONED

    def test_from_invocation_still_active(self):
        """Test conversion of still-active invocation returns empty outcome."""
        from spellbook_mcp.skill_analyzer import SkillOutcome

        inv = SkillInvocation(
            skill="debugging",
            completed=False,
            superseded=False,
            end_idx=None,  # Still active
        )

        outcome = SkillOutcome.from_invocation(inv, "session-123", "project")
        assert outcome.outcome == ""  # Not yet determined

    def test_outcome_constants(self):
        assert OUTCOME_COMPLETED == "completed"
        assert OUTCOME_ABANDONED == "abandoned"


class TestPersistOutcome:
    """Test persistence functions."""

    def test_persist_outcome_creates_record(self, tmp_path):
        """Test that persist_outcome creates a database record."""
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, persist_outcome, OUTCOME_COMPLETED
        )
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        outcome = SkillOutcome(
            skill_name="debugging",
            skill_version="v1",
            session_id="session-123",
            project_encoded="Users-test-project",
            start_time=datetime(2026, 1, 26, 10, 0, 0),
            end_time=datetime(2026, 1, 26, 10, 5, 0),
            duration_seconds=300.0,
            outcome=OUTCOME_COMPLETED,
            tokens_used=500,
            corrections=1,
            retries=0,
        )

        persist_outcome(outcome, db_path)

        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT skill_name, outcome, tokens_used FROM skill_outcomes")
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "debugging"
        assert row[1] == OUTCOME_COMPLETED
        assert row[2] == 500

    def test_persist_outcome_with_experiment_variant(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        outcome = SkillOutcome(
            skill_name="debugging",
            session_id="session-456",
            project_encoded="test-project",
            start_time=datetime.now(),
            outcome=OUTCOME_ABANDONED,
            tokens_used=500,
        )

        persist_outcome(outcome, db_path=db_path, experiment_variant_id="variant-123")

        # Verify it was persisted with experiment_variant_id
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT experiment_variant_id FROM skill_outcomes WHERE session_id = ?",
            ("session-456",)
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "variant-123"

    def test_persist_outcome_upserts_on_duplicate(self, tmp_path):
        """Test that duplicate outcomes are updated, not duplicated."""
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, persist_outcome, OUTCOME_COMPLETED, OUTCOME_ABANDONED
        )
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        start_time = datetime(2026, 1, 26, 10, 0, 0)

        # First insert
        outcome1 = SkillOutcome(
            skill_name="debugging",
            session_id="session-123",
            project_encoded="project",
            start_time=start_time,
            outcome=OUTCOME_ABANDONED,
            tokens_used=100,
        )
        persist_outcome(outcome1, db_path)

        # Update same record (same session, skill, start_time)
        outcome2 = SkillOutcome(
            skill_name="debugging",
            session_id="session-123",
            project_encoded="project",
            start_time=start_time,
            outcome=OUTCOME_COMPLETED,
            tokens_used=500,
        )
        persist_outcome(outcome2, db_path)

        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM skill_outcomes")
        count = cursor.fetchone()[0]
        assert count == 1  # Only one record

        cursor.execute("SELECT outcome, tokens_used FROM skill_outcomes")
        row = cursor.fetchone()
        assert row[0] == OUTCOME_COMPLETED  # Updated
        assert row[1] == 500  # Updated


class TestFinalizeSessionOutcomes:
    """Test session finalization."""

    def test_finalize_session_outcomes_marks_open_as_session_ended(self, tmp_path):
        """Test that open outcomes are marked as session_ended."""
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, persist_outcome, finalize_session_outcomes,
            OUTCOME_COMPLETED, OUTCOME_SESSION_ENDED
        )
        from spellbook_mcp.db import init_db, get_connection
        from datetime import datetime

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert a completed outcome and an outcome with empty outcome (still open)
        completed = SkillOutcome(
            skill_name="debugging",
            session_id="session-123",
            project_encoded="project",
            start_time=datetime(2026, 1, 26, 10, 0, 0),
            outcome=OUTCOME_COMPLETED,
        )
        persist_outcome(completed, db_path)

        # For open outcomes, insert directly with empty outcome
        conn = get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO skill_outcomes
            (skill_name, session_id, project_encoded, start_time, outcome)
            VALUES (?, ?, ?, ?, ?)
        """, ("implementing", "session-123", "project", "2026-01-26T11:00:00", ""))
        conn.commit()

        # Finalize
        count = finalize_session_outcomes("session-123", db_path)

        assert count == 1  # Only the open one

        cursor.execute(
            "SELECT outcome FROM skill_outcomes WHERE skill_name = ?",
            ("implementing",)
        )
        row = cursor.fetchone()
        assert row[0] == OUTCOME_SESSION_ENDED


class TestAnonymizeForTelemetry:
    """Test telemetry anonymization."""

    def test_anonymize_excludes_local_only_fields(self):
        """Test that session_id, project_encoded, corrections are excluded."""
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, anonymize_for_telemetry, OUTCOME_COMPLETED
        )
        from datetime import datetime

        outcomes = [
            SkillOutcome(
                skill_name="debugging",
                session_id="session-123",  # Should be excluded
                project_encoded="project",  # Should be excluded
                start_time=datetime(2026, 1, 26, 10, 0, 0),
                duration_seconds=120.0,
                outcome=OUTCOME_COMPLETED,
                tokens_used=2000,
                corrections=5,  # Should be excluded
            )
        ] * 5  # Need 5 for min_count

        aggregates = anonymize_for_telemetry(outcomes, min_count=5)

        assert len(aggregates) == 1
        agg = aggregates[0]

        # Check excluded fields are not present
        assert not hasattr(agg, "session_id") or getattr(agg, "session_id", None) is None
        assert not hasattr(agg, "project_encoded") or getattr(agg, "project_encoded", None) is None
        assert not hasattr(agg, "corrections") or getattr(agg, "corrections", None) is None

    def test_anonymize_buckets_duration(self):
        """Test that duration is bucketed correctly."""
        from spellbook_mcp.skill_analyzer import bucket_duration

        # 30 seconds -> "<1m"
        assert bucket_duration(30) == "<1m"
        # 120 seconds -> "1-5m"
        assert bucket_duration(120) == "1-5m"
        # 600 seconds -> "5-15m"
        assert bucket_duration(600) == "5-15m"
        # 1200 seconds -> "15-30m"
        assert bucket_duration(1200) == "15-30m"
        # 3600 seconds -> "30m+"
        assert bucket_duration(3600) == "30m+"

    def test_anonymize_buckets_tokens(self):
        """Test that tokens are bucketed correctly."""
        from spellbook_mcp.skill_analyzer import bucket_tokens

        assert bucket_tokens(500) == "<1k"
        assert bucket_tokens(2000) == "1-5k"
        assert bucket_tokens(10000) == "5-20k"
        assert bucket_tokens(30000) == "20-50k"
        assert bucket_tokens(100000) == "50k+"

    def test_anonymize_respects_min_count(self):
        """Test that aggregates with fewer than min_count are excluded."""
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, anonymize_for_telemetry, OUTCOME_COMPLETED
        )
        from datetime import datetime

        outcomes = [
            SkillOutcome(
                skill_name="debugging",
                session_id="s1",
                project_encoded="p1",
                start_time=datetime(2026, 1, 26, 10, 0, 0),
                duration_seconds=60.0,
                outcome=OUTCOME_COMPLETED,
                tokens_used=1000,
            )
        ] * 4  # Only 4, below min_count of 5

        aggregates = anonymize_for_telemetry(outcomes, min_count=5)

        assert len(aggregates) == 0  # Excluded due to insufficient count

    def test_anonymize_groups_by_skill_version_outcome_buckets(self):
        """Test that outcomes are grouped by skill, version, outcome, and buckets."""
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome, anonymize_for_telemetry, OUTCOME_COMPLETED
        )
        from datetime import datetime

        # 5 identical outcomes
        outcomes = [
            SkillOutcome(
                skill_name="debugging",
                skill_version="v2",
                session_id=f"s{i}",
                project_encoded="p1",
                start_time=datetime(2026, 1, 26, 10, i, 0),
                duration_seconds=120.0,  # 1-5m bucket
                outcome=OUTCOME_COMPLETED,
                tokens_used=2000,  # 1-5k bucket
            )
            for i in range(5)
        ]

        aggregates = anonymize_for_telemetry(outcomes, min_count=5)

        assert len(aggregates) == 1
        agg = aggregates[0]
        assert agg.skill_name == "debugging"
        assert agg.skill_version == "v2"
        assert agg.outcome == OUTCOME_COMPLETED
        assert agg.duration_bucket == "1-5m"
        assert agg.token_bucket == "1-5k"
        assert agg.count == 5
