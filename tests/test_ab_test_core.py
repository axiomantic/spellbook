"""Tests for A/B test core logic functions."""

import pytest
from spellbook_mcp.db import init_db, get_connection


class TestExperimentCreate:
    """Test experiment_create function."""

    def test_creates_experiment_with_variants(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        result = experiment_create(
            name="test-experiment",
            skill_name="implementing-features",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            description="Test description",
            db_path=db_path,
        )

        assert result["success"] is True
        assert result["name"] == "test-experiment"
        assert result["skill_name"] == "implementing-features"
        assert result["status"] == "created"
        assert len(result["variants"]) == 2
        assert result["variants"][0]["name"] == "control"
        assert result["variants"][0]["skill_version"] is None
        assert result["variants"][1]["name"] == "treatment"
        assert result["variants"][1]["skill_version"] == "v2"

    def test_rejects_duplicate_name(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, ExperimentExistsError

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # First creation succeeds
        experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )

        # Second creation with same name fails
        with pytest.raises(ExperimentExistsError):
            experiment_create(
                name="test-experiment",
                skill_name="debugging",
                variants=[
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "skill_version": "v2", "weight": 50},
                ],
                db_path=db_path,
            )

    def test_rejects_invalid_weight_sum(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, InvalidVariantsError

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        with pytest.raises(InvalidVariantsError, match="must sum to 100"):
            experiment_create(
                name="test-experiment",
                skill_name="debugging",
                variants=[
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "skill_version": "v2", "weight": 40},
                ],
                db_path=db_path,
            )

    def test_rejects_no_control_variant(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, InvalidVariantsError

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        with pytest.raises(InvalidVariantsError, match="skill_version=None"):
            experiment_create(
                name="test-experiment",
                skill_name="debugging",
                variants=[
                    {"name": "v1", "skill_version": "v1", "weight": 50},
                    {"name": "v2", "skill_version": "v2", "weight": 50},
                ],
                db_path=db_path,
            )

    def test_rejects_single_variant(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, InvalidVariantsError

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        with pytest.raises(InvalidVariantsError, match="At least 2"):
            experiment_create(
                name="test-experiment",
                skill_name="debugging",
                variants=[{"name": "control", "weight": 100}],
                db_path=db_path,
            )


class TestExperimentStart:
    """Test experiment_start function."""

    def test_starts_created_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, experiment_start

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )

        result = experiment_start(create_result["experiment_id"], db_path=db_path)

        assert result["success"] is True
        assert result["status"] == "active"
        assert result["started_at"] is not None

    def test_rejects_starting_active_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            InvalidStatusTransitionError,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )

        experiment_start(create_result["experiment_id"], db_path=db_path)

        with pytest.raises(InvalidStatusTransitionError):
            experiment_start(create_result["experiment_id"], db_path=db_path)

    def test_rejects_concurrent_experiment_for_same_skill(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            ConcurrentExperimentError,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Create and start first experiment
        result1 = experiment_create(
            name="experiment-1",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(result1["experiment_id"], db_path=db_path)

        # Create second experiment for same skill
        result2 = experiment_create(
            name="experiment-2",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v3", "weight": 50},
            ],
            db_path=db_path,
        )

        # Starting second experiment should fail
        with pytest.raises(ConcurrentExperimentError):
            experiment_start(result2["experiment_id"], db_path=db_path)

    def test_rejects_nonexistent_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_start, ExperimentNotFoundError

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        with pytest.raises(ExperimentNotFoundError):
            experiment_start("nonexistent-id", db_path=db_path)


class TestExperimentPause:
    """Test experiment_pause function."""

    def test_pauses_active_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, experiment_start, experiment_pause

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(create_result["experiment_id"], db_path=db_path)

        result = experiment_pause(create_result["experiment_id"], db_path=db_path)

        assert result["success"] is True
        assert result["status"] == "paused"

    def test_rejects_pausing_created_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_pause,
            InvalidStatusTransitionError,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )

        with pytest.raises(InvalidStatusTransitionError):
            experiment_pause(create_result["experiment_id"], db_path=db_path)


class TestExperimentComplete:
    """Test experiment_complete function."""

    def test_completes_active_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            experiment_complete,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(create_result["experiment_id"], db_path=db_path)

        result = experiment_complete(create_result["experiment_id"], db_path=db_path)

        assert result["success"] is True
        assert result["status"] == "completed"
        assert result["completed_at"] is not None

    def test_completes_paused_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            experiment_pause,
            experiment_complete,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(create_result["experiment_id"], db_path=db_path)
        experiment_pause(create_result["experiment_id"], db_path=db_path)

        result = experiment_complete(create_result["experiment_id"], db_path=db_path)

        assert result["success"] is True
        assert result["status"] == "completed"

    def test_rejects_completing_created_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_complete,
            InvalidStatusTransitionError,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )

        with pytest.raises(InvalidStatusTransitionError):
            experiment_complete(create_result["experiment_id"], db_path=db_path)


class TestExperimentStatus:
    """Test experiment_status function."""

    def test_returns_experiment_with_variant_counts(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, experiment_start, experiment_status

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            description="Test description",
            db_path=db_path,
        )
        experiment_start(create_result["experiment_id"], db_path=db_path)

        result = experiment_status(create_result["experiment_id"], db_path=db_path)

        assert result["success"] is True
        assert result["experiment"]["name"] == "test-experiment"
        assert result["experiment"]["skill_name"] == "debugging"
        assert result["experiment"]["status"] == "active"
        assert result["experiment"]["description"] == "Test description"
        assert len(result["variants"]) == 2
        assert result["total_sessions"] == 0
        assert result["total_outcomes"] == 0

    def test_rejects_nonexistent_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_status, ExperimentNotFoundError

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        with pytest.raises(ExperimentNotFoundError):
            experiment_status("nonexistent-id", db_path=db_path)


class TestExperimentList:
    """Test experiment_list function."""

    def test_lists_all_experiments(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, experiment_start, experiment_list

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Create multiple experiments
        experiment_create(
            name="exp-1",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        result2 = experiment_create(
            name="exp-2",
            skill_name="implementing-features",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(result2["experiment_id"], db_path=db_path)

        result = experiment_list(db_path=db_path)

        assert result["success"] is True
        assert result["total"] == 2
        assert len(result["experiments"]) == 2

    def test_filters_by_status(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, experiment_start, experiment_list

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        experiment_create(
            name="exp-1",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        result2 = experiment_create(
            name="exp-2",
            skill_name="implementing-features",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(result2["experiment_id"], db_path=db_path)

        result = experiment_list(status="active", db_path=db_path)

        assert result["total"] == 1
        assert result["experiments"][0]["name"] == "exp-2"

    def test_filters_by_skill_name(self, tmp_path):
        from spellbook_mcp.ab_test import experiment_create, experiment_list

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        experiment_create(
            name="exp-1",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_create(
            name="exp-2",
            skill_name="implementing-features",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )

        result = experiment_list(skill_name="debugging", db_path=db_path)

        assert result["total"] == 1
        assert result["experiments"][0]["name"] == "exp-1"


class TestVariantAssignment:
    """Test variant assignment logic."""

    def test_assigns_variant_deterministically(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            get_skill_version_for_session,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(create_result["experiment_id"], db_path=db_path)

        # Get assignment for a session
        exp_id, variant_id, skill_version = get_skill_version_for_session(
            skill_name="debugging",
            session_id="session-123",
            db_path=db_path,
        )

        assert exp_id == create_result["experiment_id"]
        assert variant_id is not None

        # Same session gets same assignment
        exp_id2, variant_id2, skill_version2 = get_skill_version_for_session(
            skill_name="debugging",
            session_id="session-123",
            db_path=db_path,
        )

        assert exp_id2 == exp_id
        assert variant_id2 == variant_id
        assert skill_version2 == skill_version

    def test_returns_none_when_no_active_experiment(self, tmp_path):
        from spellbook_mcp.ab_test import get_skill_version_for_session

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        exp_id, variant_id, skill_version = get_skill_version_for_session(
            skill_name="debugging",
            session_id="session-123",
            db_path=db_path,
        )

        assert exp_id is None
        assert variant_id is None
        assert skill_version is None

    def test_paused_experiment_no_new_assignments(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            experiment_pause,
            get_skill_version_for_session,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 50},
                {"name": "treatment", "skill_version": "v2", "weight": 50},
            ],
            db_path=db_path,
        )
        experiment_start(create_result["experiment_id"], db_path=db_path)

        # Get assignment while active
        exp_id1, variant_id1, _ = get_skill_version_for_session(
            skill_name="debugging",
            session_id="session-existing",
            db_path=db_path,
        )
        assert exp_id1 is not None

        # Pause experiment
        experiment_pause(create_result["experiment_id"], db_path=db_path)

        # Existing session still gets its assignment
        exp_id2, variant_id2, _ = get_skill_version_for_session(
            skill_name="debugging",
            session_id="session-existing",
            db_path=db_path,
        )
        assert exp_id2 == exp_id1
        assert variant_id2 == variant_id1

        # New session gets no assignment
        exp_id3, variant_id3, _ = get_skill_version_for_session(
            skill_name="debugging",
            session_id="session-new",
            db_path=db_path,
        )
        assert exp_id3 is None
        assert variant_id3 is None

    def test_assignment_distribution_roughly_follows_weights(self, tmp_path):
        from spellbook_mcp.ab_test import (
            experiment_create,
            experiment_start,
            get_skill_version_for_session,
        )

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        create_result = experiment_create(
            name="test-experiment",
            skill_name="debugging",
            variants=[
                {"name": "control", "weight": 70},
                {"name": "treatment", "skill_version": "v2", "weight": 30},
            ],
            db_path=db_path,
        )
        experiment_start(create_result["experiment_id"], db_path=db_path)

        control_count = 0
        treatment_count = 0

        # Assign 100 sessions
        for i in range(100):
            _, _, skill_version = get_skill_version_for_session(
                skill_name="debugging",
                session_id=f"session-{i}",
                db_path=db_path,
            )
            if skill_version is None:
                control_count += 1
            else:
                treatment_count += 1

        # With 70/30 weights, expect roughly 70 control, 30 treatment
        # Allow 20% tolerance
        assert 50 <= control_count <= 90
        assert 10 <= treatment_count <= 50
