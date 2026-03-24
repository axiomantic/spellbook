"""Tests for security.crypto.* configuration defaults (E8)."""
from pathlib import Path


def test_crypto_config_defaults_exist():
    """Crypto config defaults module must exist."""
    from spellbook.security.crypto_config import CRYPTO_CONFIG_DEFAULTS
    assert isinstance(CRYPTO_CONFIG_DEFAULTS, dict)


def test_crypto_enabled_default():
    """security.crypto.enabled must default to False (opt-in after install)."""
    from spellbook.security.crypto_config import CRYPTO_CONFIG_DEFAULTS
    assert CRYPTO_CONFIG_DEFAULTS["security.crypto.enabled"] is False


def test_crypto_keys_dir_default():
    """security.crypto.keys_dir must have a default."""
    from spellbook.security.crypto_config import CRYPTO_CONFIG_DEFAULTS
    keys_dir = CRYPTO_CONFIG_DEFAULTS["security.crypto.keys_dir"]
    assert "keys" in keys_dir


def test_gate_spawn_session_default():
    """security.crypto.gate_spawn_session must default to True."""
    from spellbook.security.crypto_config import CRYPTO_CONFIG_DEFAULTS
    assert CRYPTO_CONFIG_DEFAULTS["security.crypto.gate_spawn_session"] is True


def test_gate_workflow_save_default():
    """security.crypto.gate_workflow_save must default to True."""
    from spellbook.security.crypto_config import CRYPTO_CONFIG_DEFAULTS
    assert CRYPTO_CONFIG_DEFAULTS["security.crypto.gate_workflow_save"] is True


def test_all_defaults_have_crypto_prefix():
    """All config keys must start with security.crypto."""
    from spellbook.security.crypto_config import CRYPTO_CONFIG_DEFAULTS
    for key in CRYPTO_CONFIG_DEFAULTS:
        assert key.startswith("security.crypto."), f"Key {key} does not have crypto prefix"
