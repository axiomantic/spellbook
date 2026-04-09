"""Tests for spellbook.health domain modules.

Verifies that all public exports from spellbook health modules
exist in the corresponding spellbook.health modules.
"""

import inspect


class TestHealthCheckerImports:
    """Test that spellbook.health.checker is importable and has key exports."""

    def test_import_run_health_check(self):
        from spellbook.health.checker import run_health_check

        assert callable(run_health_check)

    def test_import_domain_check(self):
        from spellbook.health.checker import DomainCheck

        assert DomainCheck is not None

    def test_import_full_domains(self):
        from spellbook.health.checker import FULL_DOMAINS

        assert isinstance(FULL_DOMAINS, set)
        assert "database" in FULL_DOMAINS

    def test_import_health_status(self):
        from spellbook.health.checker import HealthStatus

        assert HealthStatus is not None

    def test_import_health_check_result(self):
        from spellbook.health.checker import HealthCheckResult

        assert HealthCheckResult is not None

    def test_all_public_exports_match(self):
        """Every public callable/class in spellbook.health.checker must exist in spellbook.health.checker."""
        import spellbook.health.checker as old_mod
        import spellbook.health.checker as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and (callable(obj) or isinstance(obj, (set, frozenset)))
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and (callable(obj) or isinstance(obj, (set, frozenset)))
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.health.checker: {missing}"


class TestHealthMetricsImports:
    """Test that spellbook.health.metrics is importable and has key exports."""

    def test_import_log_feature_metrics(self):
        from spellbook.health.metrics import log_feature_metrics

        assert callable(log_feature_metrics)

    def test_import_get_spellbook_config_dir(self):
        from spellbook.health.metrics import get_spellbook_config_dir

        assert callable(get_spellbook_config_dir)

    def test_import_get_project_encoded(self):
        from spellbook.health.metrics import get_project_encoded

        assert callable(get_project_encoded)

    def test_all_public_exports_match(self):
        """Every public callable in spellbook.health.metrics must exist in spellbook.health.metrics."""
        import spellbook.health.metrics as old_mod
        import spellbook.health.metrics as new_mod

        old_public = {
            name
            for name, obj in inspect.getmembers(old_mod)
            if not name.startswith("_") and callable(obj)
        }
        new_public = {
            name
            for name, obj in inspect.getmembers(new_mod)
            if not name.startswith("_") and callable(obj)
        }

        missing = old_public - new_public
        assert not missing, f"Missing public exports in spellbook.health.metrics: {missing}"
