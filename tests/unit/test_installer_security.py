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
    import bigfoot
    from installer.components.security import (
        apply_security_config,
        get_default_security_config,
    )

    selections = {"spotlighting": True, "crypto": False, "sleuth": False}

    # Build the expected (key, value) pairs the function should write
    defaults = get_default_security_config()
    prefixes = {
        "spotlighting": "security.spotlighting.",
        "crypto": "security.crypto.",
        "sleuth": "security.sleuth.",
    }
    expected_calls = []
    for feature_id, enabled in selections.items():
        pfx = prefixes[feature_id]
        for key, default_value in defaults.items():
            if not key.startswith(pfx):
                continue
            value = enabled if key.endswith(".enabled") else default_value
            expected_calls.append((key, value))

    proxy = bigfoot.mock("installer.components.security:_config_set")
    method = proxy.__call__
    for _ in expected_calls:
        method = method.returns(None)

    with bigfoot:
        apply_security_config(selections, dry_run=False)

    # Assert every interaction in order
    call_proxy = proxy.__call__
    for key, value in expected_calls:
        call_proxy.assert_call(args=(key, value))

    # Extra semantic checks from the original test
    written_keys = {k for k, _ in expected_calls}
    assert "security.spotlighting.enabled" in written_keys
    assert "security.crypto.enabled" in written_keys
    spot_val = next(v for k, v in expected_calls if k == "security.spotlighting.enabled")
    crypto_val = next(v for k, v in expected_calls if k == "security.crypto.enabled")
    assert spot_val is True
    assert crypto_val is False


def test_apply_security_config_dry_run_writes_nothing():
    """Dry run must not write any config values."""
    import bigfoot
    from installer.components.security import apply_security_config

    selections = {"spotlighting": True, "crypto": True, "sleuth": True}

    proxy = bigfoot.mock("installer.components.security:_config_set")
    proxy.__call__.required(False).returns(None)

    with bigfoot:
        result = apply_security_config(selections, dry_run=True)

    # dry_run returns keys that *would* be written, but _config_set is never called
    assert len(result) > 0  # keys are planned
    # No assert_call needed -- the mock was never invoked (required=False)


def test_get_security_summary():
    """get_security_summary must return human-readable summary."""
    from installer.components.security import get_security_summary
    selections = {"spotlighting": True, "crypto": True, "sleuth": False, "lodo": True}
    summary = get_security_summary(selections)
    assert "Spotlighting" in summary
    assert "Cryptographic" in summary or "Crypto" in summary
    assert isinstance(summary, str)
