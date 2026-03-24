"""Tests for security feature installation component."""


def test_install_security_features_sets_config():
    """Installing security features must set config keys."""
    from installer.components.security import get_security_config_keys
    keys = get_security_config_keys()
    assert "security.spotlighting.enabled" in keys
    assert "security.crypto.enabled" in keys
    assert "security.sleuth.enabled" in keys


def test_default_security_config():
    from installer.components.security import get_default_security_config
    config = get_default_security_config()
    assert config["security.spotlighting.enabled"] is True
    assert config["security.crypto.enabled"] is True
    assert config["security.sleuth.enabled"] is False  # Requires API key


def test_lodo_config_keys_present():
    """LODO evaluation config keys must be included."""
    from installer.components.security import get_security_config_keys
    keys = get_security_config_keys()
    lodo_keys = [k for k in keys if k.startswith("security.lodo.")]
    assert len(lodo_keys) >= 2
    assert "security.lodo.datasets_dir" in keys
    assert "security.lodo.min_detection_rate" in keys


def test_default_config_covers_all_keys():
    """Every key from get_security_config_keys must have a default."""
    from installer.components.security import (
        get_default_security_config,
        get_security_config_keys,
    )
    keys = get_security_config_keys()
    defaults = get_default_security_config()
    for key in keys:
        assert key in defaults, f"Key {key} has no default value"


def test_apply_security_config_writes_to_store(tmp_path):
    """apply_security_config must write config values."""
    from unittest.mock import patch, call
    from installer.components.security import apply_security_config

    selections = {"spotlighting": True, "crypto": False, "sleuth": False}
    calls_made = []

    def mock_config_set(key, value):
        calls_made.append((key, value))

    with patch("installer.components.security._config_set", mock_config_set):
        apply_security_config(selections, dry_run=False)

    written_keys = {k for k, v in calls_made}
    assert "security.spotlighting.enabled" in written_keys
    assert "security.crypto.enabled" in written_keys

    # Verify spotlighting is enabled and crypto is disabled
    spot_val = next(v for k, v in calls_made if k == "security.spotlighting.enabled")
    crypto_val = next(v for k, v in calls_made if k == "security.crypto.enabled")
    assert spot_val is True
    assert crypto_val is False


def test_apply_security_config_dry_run_writes_nothing():
    """Dry run must not write any config values."""
    from unittest.mock import patch
    from installer.components.security import apply_security_config

    selections = {"spotlighting": True, "crypto": True, "sleuth": True}
    calls_made = []

    def mock_config_set(key, value):
        calls_made.append((key, value))

    with patch("installer.components.security._config_set", mock_config_set):
        apply_security_config(selections, dry_run=True)

    assert len(calls_made) == 0


def test_get_security_summary():
    """get_security_summary must return human-readable summary."""
    from installer.components.security import get_security_summary
    selections = {"spotlighting": True, "crypto": True, "sleuth": False, "lodo": True}
    summary = get_security_summary(selections)
    assert "Spotlighting" in summary
    assert "Cryptographic" in summary or "Crypto" in summary
    assert isinstance(summary, str)
