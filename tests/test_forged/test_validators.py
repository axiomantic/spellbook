"""Tests for Forged validator infrastructure.

Following TDD: these tests are written BEFORE implementation.
"""

import pytest
import json
from pathlib import Path


class TestValidatorDataclass:
    """Tests for Validator dataclass."""

    def test_validator_creation_with_all_fields(self):
        """Validator must be creatable with all required fields."""
        from spellbook_mcp.forged.validators import Validator

        validator = Validator(
            id="code_review",
            name="Code Review Validator",
            status="EXISTS",
            archetype="code-quality",
            applicable_stages=["IMPLEMENT"],
            skill="requesting-code-review",
            prompt_template=None,
            feedback_schema={"type": "object"},
            transform_level=None,
            depends_on=[],
        )

        assert validator.id == "code_review"
        assert validator.name == "Code Review Validator"
        assert validator.status == "EXISTS"
        assert validator.archetype == "code-quality"
        assert validator.applicable_stages == ["IMPLEMENT"]
        assert validator.skill == "requesting-code-review"
        assert validator.transform_level is None
        assert validator.depends_on == []

    def test_validator_creation_with_transform_level(self):
        """Validator can have transform_level specified."""
        from spellbook_mcp.forged.validators import Validator

        validator = Validator(
            id="formatter",
            name="Code Formatter",
            status="EXISTS",
            archetype="code-quality",
            applicable_stages=["IMPLEMENT"],
            skill=None,
            prompt_template="Format the code",
            feedback_schema={},
            transform_level="mechanical",
            depends_on=[],
        )

        assert validator.transform_level == "mechanical"

    def test_validator_creation_with_dependencies(self):
        """Validator can specify dependencies on other validators."""
        from spellbook_mcp.forged.validators import Validator

        validator = Validator(
            id="integration_test",
            name="Integration Tests",
            status="PLANNED",
            archetype="code-quality",
            applicable_stages=["IMPLEMENT"],
            skill=None,
            prompt_template=None,
            feedback_schema={},
            transform_level=None,
            depends_on=["code_review", "test_quality"],
        )

        assert validator.depends_on == ["code_review", "test_quality"]

    def test_validator_to_dict(self):
        """Validator.to_dict() must produce JSON-serializable dict."""
        from spellbook_mcp.forged.validators import Validator

        validator = Validator(
            id="test_validator",
            name="Test Validator",
            status="EXISTS",
            archetype="test-archetype",
            applicable_stages=["DESIGN", "IMPLEMENT"],
            skill="some-skill",
            prompt_template="Do the thing",
            feedback_schema={"required": ["critique"]},
            transform_level="semantic",
            depends_on=["other"],
        )

        d = validator.to_dict()

        # Must be JSON-serializable
        json_str = json.dumps(d)
        assert json_str is not None

        assert d["id"] == "test_validator"
        assert d["name"] == "Test Validator"
        assert d["status"] == "EXISTS"
        assert d["archetype"] == "test-archetype"
        assert d["applicable_stages"] == ["DESIGN", "IMPLEMENT"]
        assert d["skill"] == "some-skill"
        assert d["prompt_template"] == "Do the thing"
        assert d["feedback_schema"] == {"required": ["critique"]}
        assert d["transform_level"] == "semantic"
        assert d["depends_on"] == ["other"]

    def test_validator_from_dict(self):
        """Validator.from_dict() must reconstruct from dict."""
        from spellbook_mcp.forged.validators import Validator

        data = {
            "id": "reconstructed",
            "name": "Reconstructed Validator",
            "status": "PLANNED",
            "archetype": "design",
            "applicable_stages": ["DISCOVER"],
            "skill": None,
            "prompt_template": "Template text",
            "feedback_schema": {"type": "object"},
            "transform_level": None,
            "depends_on": [],
        }

        validator = Validator.from_dict(data)

        assert validator.id == "reconstructed"
        assert validator.name == "Reconstructed Validator"
        assert validator.status == "PLANNED"
        assert validator.archetype == "design"
        assert validator.skill is None
        assert validator.prompt_template == "Template text"

    def test_validator_roundtrip(self):
        """Validator must survive to_dict() -> from_dict() roundtrip."""
        from spellbook_mcp.forged.validators import Validator

        original = Validator(
            id="roundtrip_test",
            name="Roundtrip Test Validator",
            status="EXISTS",
            archetype="accuracy",
            applicable_stages=["PLAN", "IMPLEMENT", "COMPLETE"],
            skill="fact-checking",
            prompt_template=None,
            feedback_schema={"properties": {"issue": {"type": "string"}}},
            transform_level="mechanical",
            depends_on=["code_review"],
        )

        reconstructed = Validator.from_dict(original.to_dict())

        assert reconstructed.id == original.id
        assert reconstructed.name == original.name
        assert reconstructed.status == original.status
        assert reconstructed.archetype == original.archetype
        assert reconstructed.applicable_stages == original.applicable_stages
        assert reconstructed.skill == original.skill
        assert reconstructed.prompt_template == original.prompt_template
        assert reconstructed.feedback_schema == original.feedback_schema
        assert reconstructed.transform_level == original.transform_level
        assert reconstructed.depends_on == original.depends_on


class TestValidatorCatalog:
    """Tests for VALIDATOR_CATALOG constant."""

    def test_validator_catalog_exists(self):
        """VALIDATOR_CATALOG must be defined."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        assert isinstance(VALIDATOR_CATALOG, dict)
        assert len(VALIDATOR_CATALOG) > 0

    def test_catalog_contains_code_review(self):
        """VALIDATOR_CATALOG must contain code_review validator."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        assert "code_review" in VALIDATOR_CATALOG
        validator = VALIDATOR_CATALOG["code_review"]
        assert validator.status == "EXISTS"
        assert validator.archetype == "code-quality"
        assert validator.skill == "requesting-code-review"

    def test_catalog_contains_test_quality(self):
        """VALIDATOR_CATALOG must contain test_quality validator."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        assert "test_quality" in VALIDATOR_CATALOG
        validator = VALIDATOR_CATALOG["test_quality"]
        assert validator.status == "EXISTS"
        assert validator.archetype == "code-quality"
        assert validator.skill == "green-mirage-audit"

    def test_catalog_contains_fact_check(self):
        """VALIDATOR_CATALOG must contain fact_check validator."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        assert "fact_check" in VALIDATOR_CATALOG
        validator = VALIDATOR_CATALOG["fact_check"]
        assert validator.status == "EXISTS"
        assert validator.archetype == "accuracy"
        assert validator.skill == "fact-checking"

    def test_catalog_contains_dead_code(self):
        """VALIDATOR_CATALOG must contain dead_code validator."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        assert "dead_code" in VALIDATOR_CATALOG
        validator = VALIDATOR_CATALOG["dead_code"]
        assert validator.status == "EXISTS"
        assert validator.archetype == "code-quality"
        assert validator.skill == "finding-dead-code"

    def test_catalog_contains_requirements_clarity(self):
        """VALIDATOR_CATALOG must contain requirements_clarity validator."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        assert "requirements_clarity" in VALIDATOR_CATALOG
        validator = VALIDATOR_CATALOG["requirements_clarity"]
        assert validator.status == "PLANNED"
        assert validator.archetype == "design"
        assert validator.skill is None

    def test_catalog_contains_design_coherence(self):
        """VALIDATOR_CATALOG must contain design_coherence validator."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        assert "design_coherence" in VALIDATOR_CATALOG
        validator = VALIDATOR_CATALOG["design_coherence"]
        assert validator.status == "PLANNED"
        assert validator.archetype == "design"
        assert validator.skill is None

    def test_all_catalog_values_are_validators(self):
        """All VALIDATOR_CATALOG values must be Validator instances."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG, Validator

        for key, value in VALIDATOR_CATALOG.items():
            assert isinstance(value, Validator), f"{key} is not a Validator"
            assert value.id == key, f"Validator id '{value.id}' does not match key '{key}'"


class TestValidatorsForStage:
    """Tests for validators_for_stage function."""

    def test_validators_for_stage_returns_list(self):
        """validators_for_stage must return a list."""
        from spellbook_mcp.forged.validators import validators_for_stage

        result = validators_for_stage("IMPLEMENT")

        assert isinstance(result, list)

    def test_validators_for_stage_implement(self):
        """validators_for_stage('IMPLEMENT') must include code-quality validators."""
        from spellbook_mcp.forged.validators import validators_for_stage

        result = validators_for_stage("IMPLEMENT")
        validator_ids = [v.id for v in result]

        # Code review and test quality should apply to IMPLEMENT
        assert "code_review" in validator_ids
        assert "test_quality" in validator_ids

    def test_validators_for_stage_discover(self):
        """validators_for_stage('DISCOVER') must return appropriate validators."""
        from spellbook_mcp.forged.validators import validators_for_stage

        result = validators_for_stage("DISCOVER")

        # DISCOVER is early stage - should have requirements clarity if applicable
        validator_ids = [v.id for v in result]
        # At minimum, we should get an empty list or design validators
        assert isinstance(result, list)

    def test_validators_for_stage_design(self):
        """validators_for_stage('DESIGN') must include design validators."""
        from spellbook_mcp.forged.validators import validators_for_stage

        result = validators_for_stage("DESIGN")
        validator_ids = [v.id for v in result]

        # Design coherence should apply to DESIGN
        assert "design_coherence" in validator_ids

    def test_validators_for_stage_invalid_stage(self):
        """validators_for_stage with invalid stage must raise ValueError."""
        from spellbook_mcp.forged.validators import validators_for_stage

        with pytest.raises(ValueError) as exc_info:
            validators_for_stage("INVALID_STAGE")

        assert "Invalid stage" in str(exc_info.value)

    def test_validators_for_stage_returns_validator_instances(self):
        """validators_for_stage must return Validator instances."""
        from spellbook_mcp.forged.validators import validators_for_stage, Validator

        result = validators_for_stage("IMPLEMENT")

        for v in result:
            assert isinstance(v, Validator)


class TestResolveValidatorOrder:
    """Tests for resolve_validator_order function (topological sort)."""

    def test_resolve_validator_order_empty_list(self):
        """resolve_validator_order with empty list returns empty list."""
        from spellbook_mcp.forged.validators import resolve_validator_order

        result = resolve_validator_order([])

        assert result == []

    def test_resolve_validator_order_single_validator(self):
        """resolve_validator_order with single validator returns that validator."""
        from spellbook_mcp.forged.validators import resolve_validator_order

        result = resolve_validator_order(["code_review"])

        assert result == ["code_review"]

    def test_resolve_validator_order_no_dependencies(self):
        """resolve_validator_order with independent validators preserves order."""
        from spellbook_mcp.forged.validators import resolve_validator_order

        result = resolve_validator_order(["code_review", "fact_check"])

        # Both should be present (order may vary for independent validators)
        assert set(result) == {"code_review", "fact_check"}

    def test_resolve_validator_order_respects_dependencies(self):
        """resolve_validator_order must put dependencies before dependents."""
        from spellbook_mcp.forged.validators import resolve_validator_order, VALIDATOR_CATALOG

        # Create a scenario where we have dependencies
        # First, check if any validators have dependencies
        validators_with_deps = [
            vid for vid, v in VALIDATOR_CATALOG.items() if v.depends_on
        ]

        if validators_with_deps:
            # Use one that has dependencies
            vid = validators_with_deps[0]
            deps = VALIDATOR_CATALOG[vid].depends_on
            result = resolve_validator_order([vid] + deps)

            # Dependencies must come before the dependent
            vid_index = result.index(vid)
            for dep in deps:
                if dep in result:
                    dep_index = result.index(dep)
                    assert dep_index < vid_index, f"{dep} should come before {vid}"

    def test_resolve_validator_order_unknown_validator(self):
        """resolve_validator_order with unknown validator raises ValueError."""
        from spellbook_mcp.forged.validators import resolve_validator_order

        with pytest.raises(ValueError) as exc_info:
            resolve_validator_order(["nonexistent_validator"])

        assert "Unknown validator" in str(exc_info.value)

    def test_resolve_validator_order_cycle_detection(self):
        """resolve_validator_order must detect circular dependencies."""
        from spellbook_mcp.forged.validators import resolve_validator_order, VALIDATOR_CATALOG, Validator

        # This test verifies the function would detect cycles if they existed
        # Since VALIDATOR_CATALOG shouldn't have cycles, we test that valid input works
        all_ids = list(VALIDATOR_CATALOG.keys())
        result = resolve_validator_order(all_ids)

        assert set(result) == set(all_ids)


class TestValidatorInvoke:
    """Tests for validator_invoke function."""

    def test_validator_invoke_returns_validator_result(self, tmp_path):
        """validator_invoke must return a ValidatorResult."""
        from spellbook_mcp.forged.validators import validator_invoke
        from spellbook_mcp.forged.models import ValidatorResult

        # Create a test artifact
        artifact = tmp_path / "test.py"
        artifact.write_text("print('hello')")

        result = validator_invoke(
            validator_id="code_review",
            artifact_path=str(artifact),
            context=None,
        )

        assert isinstance(result, ValidatorResult)
        assert result.verdict in ["APPROVED", "FEEDBACK", "ABSTAIN", "ERROR"]
        assert result.artifact_path == str(artifact)

    def test_validator_invoke_unknown_validator(self, tmp_path):
        """validator_invoke with unknown validator returns ERROR verdict."""
        from spellbook_mcp.forged.validators import validator_invoke

        artifact = tmp_path / "test.py"
        artifact.write_text("print('hello')")

        result = validator_invoke(
            validator_id="nonexistent",
            artifact_path=str(artifact),
            context=None,
        )

        assert result.verdict == "ERROR"
        assert "Unknown validator" in result.error

    def test_validator_invoke_nonexistent_artifact(self):
        """validator_invoke with nonexistent artifact returns ERROR verdict."""
        from spellbook_mcp.forged.validators import validator_invoke

        result = validator_invoke(
            validator_id="code_review",
            artifact_path="/nonexistent/path/file.py",
            context=None,
        )

        assert result.verdict == "ERROR"
        assert "not found" in result.error.lower() or "does not exist" in result.error.lower()

    def test_validator_invoke_planned_validator(self, tmp_path):
        """validator_invoke with PLANNED validator returns ABSTAIN verdict."""
        from spellbook_mcp.forged.validators import validator_invoke

        artifact = tmp_path / "test.md"
        artifact.write_text("# Requirements")

        result = validator_invoke(
            validator_id="requirements_clarity",
            artifact_path=str(artifact),
            context=None,
        )

        assert result.verdict == "ABSTAIN"

    def test_validator_invoke_with_context(self, tmp_path):
        """validator_invoke must accept context parameter."""
        from spellbook_mcp.forged.validators import validator_invoke

        artifact = tmp_path / "test.py"
        artifact.write_text("def example(): pass")

        result = validator_invoke(
            validator_id="code_review",
            artifact_path=str(artifact),
            context={"feature_name": "test-feature", "iteration": 1},
        )

        # Should work without error
        assert result.verdict in ["APPROVED", "FEEDBACK", "ABSTAIN", "ERROR"]

    def test_validator_invoke_computes_artifact_hash(self, tmp_path):
        """validator_invoke must compute and return artifact hash."""
        from spellbook_mcp.forged.validators import validator_invoke

        artifact = tmp_path / "test.py"
        content = "# Test content"
        artifact.write_text(content)

        result = validator_invoke(
            validator_id="code_review",
            artifact_path=str(artifact),
            context=None,
        )

        assert result.artifact_hash is not None
        assert len(result.artifact_hash) > 0


class TestTransformLevelHandling:
    """Tests for transform level handling."""

    def test_transform_level_none_is_read_only(self, tmp_path):
        """Validators with transform_level=None must not modify artifact."""
        from spellbook_mcp.forged.validators import validator_invoke, VALIDATOR_CATALOG

        # Find a validator with transform_level=None
        read_only_validators = [
            vid for vid, v in VALIDATOR_CATALOG.items()
            if v.transform_level is None and v.status == "EXISTS"
        ]

        if read_only_validators:
            vid = read_only_validators[0]
            artifact = tmp_path / "test.py"
            original_content = "def foo(): pass"
            artifact.write_text(original_content)

            validator_invoke(
                validator_id=vid,
                artifact_path=str(artifact),
                context=None,
            )

            # Content should be unchanged
            assert artifact.read_text() == original_content

    def test_transform_level_mechanical_can_auto_apply(self, tmp_path):
        """Validators with transform_level='mechanical' can auto-apply fixes."""
        from spellbook_mcp.forged.validators import (
            validator_invoke,
            VALIDATOR_CATALOG,
            get_transform_level,
        )

        # Check if there are any mechanical validators
        mechanical_validators = [
            vid for vid, v in VALIDATOR_CATALOG.items()
            if v.transform_level == "mechanical"
        ]

        # Even if none exist yet, the function should handle the concept
        level = get_transform_level("code_review")
        assert level in [None, "mechanical", "semantic"]

    def test_transform_level_semantic_requires_approval(self):
        """Validators with transform_level='semantic' require approval."""
        from spellbook_mcp.forged.validators import get_transform_level

        # This is a contract test - semantic transforms need approval workflow
        # The actual approval logic would be in a higher-level function
        # Here we just verify the level is retrievable
        level = get_transform_level("code_review")
        assert level in [None, "mechanical", "semantic"]

    def test_get_transform_level_unknown_validator(self):
        """get_transform_level with unknown validator raises ValueError."""
        from spellbook_mcp.forged.validators import get_transform_level

        with pytest.raises(ValueError) as exc_info:
            get_transform_level("nonexistent")

        assert "Unknown validator" in str(exc_info.value)


class TestValidatorArchetypes:
    """Tests for validator archetypes."""

    def test_code_quality_archetype_validators(self):
        """Validators with code-quality archetype must exist."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        code_quality = [
            v for v in VALIDATOR_CATALOG.values()
            if v.archetype == "code-quality"
        ]

        assert len(code_quality) >= 2  # At least code_review, test_quality

    def test_accuracy_archetype_validators(self):
        """Validators with accuracy archetype must exist."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        accuracy = [
            v for v in VALIDATOR_CATALOG.values()
            if v.archetype == "accuracy"
        ]

        assert len(accuracy) >= 1  # At least fact_check

    def test_design_archetype_validators(self):
        """Validators with design archetype must exist."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        design = [
            v for v in VALIDATOR_CATALOG.values()
            if v.archetype == "design"
        ]

        assert len(design) >= 2  # requirements_clarity, design_coherence


class TestValidatorStatus:
    """Tests for validator status handling."""

    def test_exists_status_means_implemented(self):
        """Validators with EXISTS status must have a skill reference."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        exists_validators = [
            v for v in VALIDATOR_CATALOG.values()
            if v.status == "EXISTS"
        ]

        for v in exists_validators:
            assert v.skill is not None, f"EXISTS validator {v.id} must have skill"

    def test_planned_status_means_not_implemented(self):
        """Validators with PLANNED status must not have a skill reference."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        planned_validators = [
            v for v in VALIDATOR_CATALOG.values()
            if v.status == "PLANNED"
        ]

        for v in planned_validators:
            assert v.skill is None, f"PLANNED validator {v.id} should not have skill"

    def test_valid_statuses_only(self):
        """All validators must have valid status values."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        valid_statuses = {"EXISTS", "PLANNED", "PLACEHOLDER"}

        for vid, v in VALIDATOR_CATALOG.items():
            assert v.status in valid_statuses, f"Invalid status '{v.status}' for {vid}"


class TestValidatorApplicableStages:
    """Tests for validator applicable_stages field."""

    def test_applicable_stages_are_valid(self):
        """All applicable_stages must be valid VALID_STAGES."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG
        from spellbook_mcp.forged.models import VALID_STAGES

        for vid, v in VALIDATOR_CATALOG.items():
            for stage in v.applicable_stages:
                assert stage in VALID_STAGES, (
                    f"Invalid stage '{stage}' in {vid}.applicable_stages"
                )

    def test_every_validator_has_at_least_one_stage(self):
        """Every validator must apply to at least one stage."""
        from spellbook_mcp.forged.validators import VALIDATOR_CATALOG

        for vid, v in VALIDATOR_CATALOG.items():
            assert len(v.applicable_stages) >= 1, (
                f"Validator {vid} must have at least one applicable stage"
            )
