"""Tests for telemetry and A/B test integration."""

import pytest
from datetime import datetime
from spellbook_mcp.db import init_db, get_connection


class TestTelemetryAggregate:
    """Test TelemetryAggregate dataclass."""

    def test_telemetry_aggregate_creation(self):
        from spellbook_mcp.telemetry_sync import TelemetryAggregate

        agg = TelemetryAggregate(
            skill_name="debugging",
            total_invocations=100,
            total_completions=80,
            total_abandonments=15,
            avg_tokens_used=1500,
            avg_corrections=0.2,
        )

        assert agg.skill_name == "debugging"
        assert agg.total_invocations == 100
        assert agg.completion_rate == 0.8

    def test_completion_rate_handles_zero(self):
        from spellbook_mcp.telemetry_sync import TelemetryAggregate

        agg = TelemetryAggregate(
            skill_name="debugging",
            total_invocations=0,
            total_completions=0,
            total_abandonments=0,
            avg_tokens_used=0,
            avg_corrections=0,
        )

        assert agg.completion_rate == 0.0


class TestSyncOutcomesToExperiments:
    """Test sync_outcomes_to_experiments function."""

    def test_links_outcomes_to_variants(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            get_skill_version_for_session,
        )
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome,
            persist_outcome,
            OUTCOME_COMPLETED,
        )
        from spellbook_mcp.telemetry_sync import sync_outcomes_to_experiments

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Create and start experiment
        result = experiment_create(
            name="test-exp",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(result["experiment_id"], db_path=db_path)

        # Get variant assignment for a session
        exp_id, variant_id, skill_version = get_skill_version_for_session(
            skill_name="debugging",
            session_id="session-123",
            db_path=db_path,
        )

        # Create outcome without experiment_variant_id
        outcome = SkillOutcome(
            skill_name="debugging",
            session_id="session-123",
            project_encoded="test-project",
            start_time=datetime.now(),
            outcome=OUTCOME_COMPLETED,
            tokens_used=1000,
        )
        persist_outcome(outcome, db_path=db_path)

        # Sync to link outcomes with experiment variants
        sync_outcomes_to_experiments(db_path=db_path)

        # Verify it's linked
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT experiment_variant_id FROM skill_outcomes WHERE session_id = ?",
            ("session-123",),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == variant_id

    def test_does_not_overwrite_existing_variant_id(self, tmp_path):
        from spellbook_mcp.skill_analyzer import (
            SkillOutcome,
            persist_outcome,
            OUTCOME_COMPLETED,
        )
        from spellbook_mcp.telemetry_sync import sync_outcomes_to_experiments

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Create outcome with explicit variant_id
        outcome = SkillOutcome(
            skill_name="debugging",
            session_id="session-456",
            project_encoded="test-project",
            start_time=datetime.now(),
            outcome=OUTCOME_COMPLETED,
            tokens_used=1000,
        )
        persist_outcome(outcome, db_path=db_path, experiment_variant_id="explicit-variant")

        # Sync
        sync_outcomes_to_experiments(db_path=db_path)

        # Verify it's NOT overwritten
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT experiment_variant_id FROM skill_outcomes WHERE session_id = ?",
            ("session-456",),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "explicit-variant"
