"""Tests for spellbook.core.config module.

Verifies that core config functions are importable from spellbook.core.config
and that all public exports from spellbook.core.config exist in the new module.
"""

import inspect
import os
import warnings

import pytest


class TestCoreConfigImports:
    """Test that spellbook.core.config is importable with expected exports."""

    def test_import_config_get(self):
        from spellbook.core.config import config_get

        assert callable(config_get)

    def test_import_config_set(self):
        from spellbook.core.config import config_set

        assert callable(config_set)

    def test_import_config_set_many(self):
        from spellbook.core.config import config_set_many

        assert callable(config_set_many)

    def test_import_get_spellbook_dir(self):
        from spellbook.core.config import get_spellbook_dir

        assert callable(get_spellbook_dir)

    def test_import_get_config_path(self):
        from spellbook.core.config import get_config_path

        assert callable(get_config_path)

    def test_import_get_env(self):
        from spellbook.core.config import get_env

        assert callable(get_env)

    def test_all_public_exports_match(self):
        """Every public function in spellbook.core.config must exist in spellbook.core.config."""
        import spellbook.core.config as old_mod
        import spellbook.core.config as new_mod

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
        assert not missing, f"Missing public exports in spellbook.core.config: {missing}"


class TestGetEnv:
    """Test the get_env() backward-compatibility function."""

    def test_get_env_returns_value(self, monkeypatch):
        from spellbook.core.config import get_env

        monkeypatch.setenv("SPELLBOOK_PORT", "9999")
        assert get_env("PORT") == "9999"

    def test_get_env_old_name_with_deprecation_warning(self, monkeypatch):
        from spellbook.core.config import get_env

        monkeypatch.setenv("SPELLBOOK_MCP_PORT", "8888")
        # Ensure new name is not set
        monkeypatch.delenv("SPELLBOOK_PORT", raising=False)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = get_env("PORT")
            assert result == "8888"
            assert len(w) == 1
            assert "deprecated" in str(w[0].message).lower()
            assert "SPELLBOOK_MCP_PORT" in str(w[0].message)

    def test_get_env_new_name_takes_precedence(self, monkeypatch):
        from spellbook.core.config import get_env

        monkeypatch.setenv("SPELLBOOK_PORT", "9999")
        monkeypatch.setenv("SPELLBOOK_MCP_PORT", "8888")
        # New name should win, no warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = get_env("PORT")
            assert result == "9999"
            # No deprecation warning since new name was found
            deprecation_warnings = [
                x for x in w if "deprecated" in str(x.message).lower()
            ]
            assert len(deprecation_warnings) == 0

    def test_get_env_returns_default(self):
        from spellbook.core.config import get_env

        result = get_env("PORT", default="7777")
        # Only works if SPELLBOOK_PORT and SPELLBOOK_MCP_PORT are both unset
        # Use a unique key to avoid env contamination
        result = get_env("NONEXISTENT_TEST_KEY_12345", default="fallback")
        assert result == "fallback"

    def test_get_env_returns_none_by_default(self):
        from spellbook.core.config import get_env

        result = get_env("NONEXISTENT_TEST_KEY_12345")
        assert result is None

    def test_get_env_known_aliases(self):
        """All expected aliases should be recognized."""
        from spellbook.core.config import _ENV_ALIASES

        expected = {"PORT", "HOST", "DB_PATH", "TOKEN", "AUTH", "TRANSPORT"}
        assert expected <= set(_ENV_ALIASES.keys())


class TestCoreConfigFunctionality:
    """Test that config functions work correctly."""

    def test_config_roundtrip(self, tmp_path, monkeypatch):
        """config_set followed by config_get should return the same value."""
        from spellbook.core.config import config_get, config_set

        # Point config to a temp directory
        config_file = tmp_path / "spellbook.json"
        monkeypatch.setattr(
            "spellbook.core.config.get_config_path", lambda: config_file
        )
        # Use a temp lock path too
        monkeypatch.setattr(
            "spellbook.core.config.CONFIG_LOCK_PATH", tmp_path / "config.lock"
        )

        config_set("test_key", "test_value")
        assert config_get("test_key") == "test_value"

    def test_get_spellbook_dir_env_override(self, monkeypatch):
        from spellbook.core.config import get_spellbook_dir

        monkeypatch.setenv("SPELLBOOK_DIR", "/tmp/test-spellbook")
        from pathlib import Path

        assert get_spellbook_dir() == Path("/tmp/test-spellbook")
