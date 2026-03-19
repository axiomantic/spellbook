"""Tests for the spellbook.experiments domain module.

Verifies that key exports from spellbook.experiments.ab_test exist in
spellbook.experiments.ab_test.
"""

import pytest


class TestExperimentsABTest:
    """Verify spellbook.experiments.ab_test has key exports from spellbook.experiments.ab_test."""

    def test_ab_test_module_importable(self):
        import spellbook.experiments.ab_test

        assert hasattr(spellbook.experiments.ab_test, "__file__")

    @pytest.mark.parametrize(
        "name",
        [
            "ExperimentStatus",
            "OutcomeType",
            "ABTestError",
            "ABTestErrorCode",
            "ExperimentNotFoundError",
            "ExperimentExistsError",
            "InvalidStatusTransitionError",
            "ConcurrentExperimentError",
            "InvalidVariantsError",
            "ValidationError",
            "Variant",
            "Experiment",
            "Assignment",
            "VariantMetrics",
            "validate_status_transition",
            "experiment_create",
            "experiment_start",
            "experiment_pause",
            "experiment_complete",
            "experiment_status",
            "experiment_list",
            "experiment_results",
            "get_skill_version_for_session",
        ],
    )
    def test_ab_test_has_export(self, name):
        import spellbook.experiments.ab_test as ab_test

        assert hasattr(ab_test, name), f"spellbook.experiments.ab_test missing {name}"

    def test_ab_test_no_spellbook_mcp_imports(self):
        """Verify ab_test.py does not import from spellbook."""
        import ast
        import inspect

        import spellbook.experiments.ab_test as ab_test

        source = inspect.getsource(ab_test)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("spellbook"), (
                    f"spellbook.experiments.ab_test imports from "
                    f"spellbook: {node.module}"
                )
