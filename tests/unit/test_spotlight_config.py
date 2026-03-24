"""Test spotlighting configuration defaults."""
import json
import os
from pathlib import Path


def test_config_defaults_include_spotlighting():
    """CONFIG_DEFAULTS must include security.spotlighting.enabled."""
    from spellbook.core.config import CONFIG_DEFAULTS
    assert "security.spotlighting.enabled" in CONFIG_DEFAULTS
    assert CONFIG_DEFAULTS["security.spotlighting.enabled"] is True


def test_config_defaults_include_spotlighting_tier():
    """CONFIG_DEFAULTS must include security.spotlighting.tier."""
    from spellbook.core.config import CONFIG_DEFAULTS
    assert "security.spotlighting.tier" in CONFIG_DEFAULTS
    assert CONFIG_DEFAULTS["security.spotlighting.tier"] == "standard"


def test_config_get_returns_default_when_key_missing(tmp_path):
    """config_get should return CONFIG_DEFAULTS value for unset keys."""
    from unittest.mock import patch
    from spellbook.core.config import config_get

    # Point config to a temp file with no spotlighting keys
    config_file = tmp_path / "spellbook.json"
    config_file.write_text(json.dumps({"some_other_key": "value"}))

    with patch("spellbook.core.config.get_config_path", return_value=config_file):
        result = config_get("security.spotlighting.enabled")
        assert result is True

        result = config_get("security.spotlighting.tier")
        assert result == "standard"


def test_config_get_user_override_takes_precedence(tmp_path):
    """User-set value should override CONFIG_DEFAULTS."""
    from unittest.mock import patch
    from spellbook.core.config import config_get

    config_file = tmp_path / "spellbook.json"
    config_file.write_text(json.dumps({"security.spotlighting.enabled": False}))

    with patch("spellbook.core.config.get_config_path", return_value=config_file):
        result = config_get("security.spotlighting.enabled")
        assert result is False


def test_config_get_no_file_returns_default(tmp_path):
    """When config file doesn't exist, return CONFIG_DEFAULTS."""
    from unittest.mock import patch
    from spellbook.core.config import config_get

    nonexistent = tmp_path / "nonexistent.json"

    with patch("spellbook.core.config.get_config_path", return_value=nonexistent):
        result = config_get("security.spotlighting.enabled")
        assert result is True
