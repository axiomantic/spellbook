"""Tests for crypto key generation during installation."""
from pathlib import Path


def test_keys_component_exists():
    """Installer keys component module must exist."""
    from installer.components import keys
    assert hasattr(keys, "ensure_signing_keys")


def test_ensure_signing_keys_creates_keypair(tmp_path):
    """ensure_signing_keys must create key files."""
    from installer.components.keys import ensure_signing_keys
    keys_dir = tmp_path / "keys"
    result = ensure_signing_keys(str(keys_dir))
    assert result["success"] is True
    assert (keys_dir / "signing.key").exists()
    assert (keys_dir / "signing.pub").exists()


def test_ensure_signing_keys_idempotent(tmp_path):
    """Calling ensure_signing_keys twice must not regenerate keys."""
    from installer.components.keys import ensure_signing_keys
    keys_dir = tmp_path / "keys"
    result1 = ensure_signing_keys(str(keys_dir))
    pub1 = (keys_dir / "signing.pub").read_bytes()
    result2 = ensure_signing_keys(str(keys_dir))
    pub2 = (keys_dir / "signing.pub").read_bytes()
    assert pub1 == pub2
    assert result1["created"] is True
    assert result2["created"] is False


def test_ensure_signing_keys_returns_fingerprint(tmp_path):
    """Result must include the key fingerprint."""
    from installer.components.keys import ensure_signing_keys
    keys_dir = tmp_path / "keys"
    result = ensure_signing_keys(str(keys_dir))
    assert "fingerprint" in result
    assert len(result["fingerprint"]) > 10
