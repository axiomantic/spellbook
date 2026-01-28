"""Integration tests for A/B test complete workflow."""

import pytest
from datetime import datetime
from spellbook_mcp.db import init_db, get_connection
from spellbook_mcp.skill_analyzer import (
    SkillOutcome,
    persist_outcome,
    OUTCOME_COMPLETED,
    OUTCOME_ABANDONED,
)


class TestABTestIntegrationWorkflow:
    """Test complete experiment lifecycle end-to-end."""

    def test_full_experiment_lifecycle(self, tmp_path):
        """Test complete flow: create -> start -> assign -> record -> pause -> complete -> results."""
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            experiment_pause,
            experiment_complete,
            experiment_status,
            experiment_results,
            get_skill_version_for_session,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # 1. Create experiment
        create_result = experiment_create(
            name="full-lifecycle-test",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            description="Full lifecycle integration test",
            db_path=db_path,
        )
        exp_id = create_result["experiment_id"]
        assert create_result["status"] == "created"

        # 2. Start experiment
        start_result = experiment_start(exp_id, db_path=db_path)
        assert start_result["status"] == "active"

        # 3. Assign sessions and record outcomes
        sessions_control = []
        sessions_treatment = []

        for i in range(20):
            session_id = f"session-{i}"
            _, variant_id, skill_version = get_skill_version_for_session(
                skill_name="debugging",
                session_id=session_id,
                db_path=db_path,
            )

            if skill_version is None:
                sessions_control.append((session_id, variant_id))
            else:
                sessions_treatment.append((session_id, variant_id))

            # Record outcome
            outcome = SkillOutcome(
                skill_name="debugging",
                session_id=session_id,
                project_encoded="test-project",
                start_time=datetime.now(),
                outcome=OUTCOME_COMPLETED if i % 3 != 0 else OUTCOME_ABANDONED,
                tokens_used=1000 + (i * 100),
            )
            persist_outcome(outcome, db_path=db_path, experiment_variant_id=variant_id)

        # 4. Check status
        status = experiment_status(exp_id, db_path=db_path)
        assert status["total_sessions"] == 20
        assert status["total_outcomes"] == 20

        # 5. Pause experiment
        pause_result = experiment_pause(exp_id, db_path=db_path)
        assert pause_result["status"] == "paused"

        # 6. Verify paused experiment doesn't assign new sessions
        _, variant_id_new, _ = get_skill_version_for_session(
            skill_name="debugging",
            session_id="session-new-after-pause",
            db_path=db_path,
        )
        assert variant_id_new is None

        # 7. Complete experiment
        complete_result = experiment_complete(exp_id, db_path=db_path)
        assert complete_result["status"] == "completed"

        # 8. Get results
        results = experiment_results(exp_id, db_path=db_path)
        assert results["success"] is True
        assert "control" in results["results"]
        assert "treatment" in results["results"]
        assert "comparison" in results

    def test_concurrent_experiment_prevention(self, tmp_path):
        """Test that concurrent experiments for same skill are blocked."""
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            ConcurrentExperimentError,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Create and start first experiment
        exp1 = experiment_create(
            name="exp-1",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(exp1["experiment_id"], db_path=db_path)

        # Create second experiment for same skill
        exp2 = experiment_create(
            name="exp-2",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v3", "weight": 50},
            ],
            db_path=db_path,
        )

        # Attempting to start should fail
        with pytest.raises(ConcurrentExperimentError):
            experiment_start(exp2["experiment_id"], db_path=db_path)

    def test_sticky_variant_assignment(self, tmp_path):
        """Test that sessions always get the same variant."""
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            get_skill_version_for_session,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="sticky-test",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(create_result["experiment_id"], db_path=db_path)

        # Get assignment multiple times
        results = []
        for _ in range(5):
            _, variant_id, skill_version = get_skill_version_for_session(
                skill_name="debugging",
                session_id="sticky-session",
                db_path=db_path,
            )
            results.append((variant_id, skill_version))

        # All should be identical
        assert all(r == results[0] for r in results)
