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
