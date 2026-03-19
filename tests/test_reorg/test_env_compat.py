"""Verify backward compatibility for all 6 SPELLBOOK_MCP_* env var aliases."""

import warnings

import pytest

# (old_env_var, new_env_var, short_key_for_get_env)
ALIASES = [
    ("SPELLBOOK_MCP_TOKEN", "SPELLBOOK_TOKEN", "TOKEN"),
    ("SPELLBOOK_MCP_PORT", "SPELLBOOK_PORT", "PORT"),
    ("SPELLBOOK_MCP_HOST", "SPELLBOOK_HOST", "HOST"),
    ("SPELLBOOK_MCP_DB_PATH", "SPELLBOOK_DB_PATH", "DB_PATH"),
    ("SPELLBOOK_MCP_AUTH", "SPELLBOOK_AUTH", "AUTH"),
    ("SPELLBOOK_MCP_TRANSPORT", "SPELLBOOK_TRANSPORT", "TRANSPORT"),
]


@pytest.mark.parametrize("old_name,new_name,short_key", ALIASES)
def test_env_alias_works(monkeypatch, old_name, new_name, short_key):
    """Setting the old SPELLBOOK_MCP_* name should fall back with a warning."""
    monkeypatch.setenv(old_name, "test-value-123")
    # Clear the new name to ensure fallback
    monkeypatch.delenv(new_name, raising=False)
    from spellbook.core.config import get_env

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env(short_key)
        assert result == "test-value-123"
        assert len(w) == 1
        assert "deprecated" in str(w[0].message).lower()


@pytest.mark.parametrize("old_name,new_name,short_key", ALIASES)
def test_new_name_takes_precedence(monkeypatch, old_name, new_name, short_key):
    """When both old and new env vars are set, the new name wins silently."""
    monkeypatch.setenv(old_name, "old-value")
    monkeypatch.setenv(new_name, "new-value")
    from spellbook.core.config import get_env

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env(short_key)
        assert result == "new-value"  # new name wins
        # No deprecation warning when new name is set
        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) == 0
