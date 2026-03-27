"""Test spotlighting configuration defaults."""
import json

import bigfoot

from spellbook.core.config import CONFIG_DEFAULTS, config_get


def test_config_defaults_include_spotlighting():
    """CONFIG_DEFAULTS must include security.spotlighting.enabled."""
    assert "security.spotlighting.enabled" in CONFIG_DEFAULTS
    assert CONFIG_DEFAULTS["security.spotlighting.enabled"] is True


def test_config_defaults_include_spotlighting_tier():
    """CONFIG_DEFAULTS must include security.spotlighting.tier."""
    assert "security.spotlighting.tier" in CONFIG_DEFAULTS
    assert CONFIG_DEFAULTS["security.spotlighting.tier"] == "standard"


def test_config_get_returns_default_when_key_missing(tmp_path):
    """config_get should return CONFIG_DEFAULTS value for unset keys."""
    # Point config to a temp file with no spotlighting keys
    config_file = tmp_path / "spellbook.json"
    config_file.write_text(json.dumps({"some_other_key": "value"}))

    proxy = bigfoot.mock("spellbook.core.config:get_config_path")
    proxy.returns(config_file).returns(config_file)

    with bigfoot:
        result = config_get("security.spotlighting.enabled")
        assert result is True

        result = config_get("security.spotlighting.tier")
        assert result == "standard"

    proxy.assert_call(args=(), kwargs={})
    proxy.assert_call(args=(), kwargs={})


def test_config_get_user_override_takes_precedence(tmp_path):
    """User-set value should override CONFIG_DEFAULTS."""
    config_file = tmp_path / "spellbook.json"
    config_file.write_text(json.dumps({"security.spotlighting.enabled": False}))

    proxy = bigfoot.mock("spellbook.core.config:get_config_path")
    proxy.returns(config_file)

    with bigfoot:
        result = config_get("security.spotlighting.enabled")
        assert result is False

    proxy.assert_call(args=(), kwargs={})


def test_config_get_no_file_returns_default(tmp_path):
    """When config file doesn't exist, return CONFIG_DEFAULTS."""
    nonexistent = tmp_path / "nonexistent.json"

    proxy = bigfoot.mock("spellbook.core.config:get_config_path")
    proxy.returns(nonexistent)

    with bigfoot:
        result = config_get("security.spotlighting.enabled")
        assert result is True

    proxy.assert_call(args=(), kwargs={})
