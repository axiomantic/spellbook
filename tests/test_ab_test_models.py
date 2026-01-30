"""Tests for A/B test data models."""

import pytest
from datetime import datetime


class TestExperimentStatus:
    """Test ExperimentStatus enum."""

    def test_status_values(self):
        from spellbook_mcp.ab_test import ExperimentStatus

        assert ExperimentStatus.CREATED.value == "created"
        assert ExperimentStatus.ACTIVE.value == "active"
        assert ExperimentStatus.PAUSED.value == "paused"
        assert ExperimentStatus.COMPLETED.value == "completed"


class TestOutcomeType:
    """Test OutcomeType enum."""

    def test_outcome_values(self):
        from spellbook_mcp.ab_test import OutcomeType

        assert OutcomeType.COMPLETED.value == "completed"
        assert OutcomeType.ABANDONED.value == "abandoned"
        assert OutcomeType.SUPERSEDED.value == "superseded"
        assert OutcomeType.SESSION_ENDED.value == "session_ended"


class TestVariant:
    """Test Variant dataclass."""

    def test_variant_creation(self):
        from spellbook_mcp.ab_test import Variant

        v = Variant(
            id="variant-123",
            experiment_id="exp-456",
            variant_name="control",
            skill_version=None,
            weight=50,
        )

        assert v.id == "variant-123"
        assert v.experiment_id == "exp-456"
        assert v.variant_name == "control"
        assert v.skill_version is None
        assert v.weight == 50

    def test_variant_weight_validation_too_high(self):
        from spellbook_mcp.ab_test import Variant

        with pytest.raises(ValueError, match="weight must be 0-100"):
            Variant(
                id="v1",
                experiment_id="e1",
                variant_name="control",
                skill_version=None,
                weight=101,
            )

    def test_variant_weight_validation_negative(self):
        from spellbook_mcp.ab_test import Variant

        with pytest.raises(ValueError, match="weight must be 0-100"):
            Variant(
                id="v1",
                experiment_id="e1",
                variant_name="control",
                skill_version=None,
                weight=-1,
            )

    def test_variant_name_required(self):
        from spellbook_mcp.ab_test import Variant

        with pytest.raises(ValueError, match="variant_name cannot be empty"):
            Variant(
                id="v1",
                experiment_id="e1",
                variant_name="",
                skill_version=None,
                weight=50,
            )


class TestExperiment:
    """Test Experiment dataclass."""

    def test_experiment_creation(self):
        from spellbook_mcp.ab_test import Experiment, ExperimentStatus

        exp = Experiment(
            id="exp-123",
            name="test-experiment",
            skill_name="implementing-features",
            description="Test description",
        )

        assert exp.id == "exp-123"
        assert exp.name == "test-experiment"
        assert exp.skill_name == "implementing-features"
        assert exp.status == ExperimentStatus.CREATED
        assert exp.description == "Test description"
        assert exp.variants == []

    def test_experiment_name_required(self):
        from spellbook_mcp.ab_test import Experiment

        with pytest.raises(ValueError, match="name cannot be empty"):
            Experiment(id="e1", name="", skill_name="debugging")

    def test_experiment_skill_name_required(self):
        from spellbook_mcp.ab_test import Experiment

        with pytest.raises(ValueError, match="skill_name cannot be empty"):
            Experiment(id="e1", name="test", skill_name="")

    def test_validate_variants_requires_two(self):
        from spellbook_mcp.ab_test import Experiment, Variant, InvalidVariantsError

        exp = Experiment(id="e1", name="test", skill_name="debugging")
        exp.variants = [
            Variant(id="v1", experiment_id="e1", variant_name="control", skill_version=None, weight=100)
        ]

        with pytest.raises(InvalidVariantsError, match="At least 2 variants required"):
            exp.validate_variants()

    def test_validate_variants_requires_weight_sum_100(self):
        from spellbook_mcp.ab_test import Experiment, Variant, InvalidVariantsError

        exp = Experiment(id="e1", name="test", skill_name="debugging")
        exp.variants = [
            Variant(id="v1", experiment_id="e1", variant_name="control", skill_version=None, weight=50),
            Variant(id="v2", experiment_id="e1", variant_name="treatment", skill_version="v2", weight=40),
        ]

        with pytest.raises(InvalidVariantsError, match="must sum to 100"):
            exp.validate_variants()

    def test_validate_variants_requires_control(self):
        from spellbook_mcp.ab_test import Experiment, Variant, InvalidVariantsError

        exp = Experiment(id="e1", name="test", skill_name="debugging")
        exp.variants = [
            Variant(id="v1", experiment_id="e1", variant_name="v1", skill_version="v1", weight=50),
            Variant(id="v2", experiment_id="e1", variant_name="v2", skill_version="v2", weight=50),
        ]

        with pytest.raises(InvalidVariantsError, match="skill_version=None"):
            exp.validate_variants()

    def test_validate_variants_success(self):
        from spellbook_mcp.ab_test import Experiment, Variant

        exp = Experiment(id="e1", name="test", skill_name="debugging")
        exp.variants = [
            Variant(id="v1", experiment_id="e1", variant_name="control", skill_version=None, weight=50),
            Variant(id="v2", experiment_id="e1", variant_name="treatment", skill_version="v2", weight=50),
        ]

        # Should not raise
        exp.validate_variants()


class TestAssignment:
    """Test Assignment dataclass."""

    def test_assignment_creation(self):
        from spellbook_mcp.ab_test import Assignment

        a = Assignment(
            id=1,
            experiment_id="exp-123",
            session_id="session-456",
            variant_id="variant-789",
        )

        assert a.id == 1
        assert a.experiment_id == "exp-123"
        assert a.session_id == "session-456"
        assert a.variant_id == "variant-789"
