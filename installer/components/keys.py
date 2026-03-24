"""Signing key generation component for the spellbook installer.

Generates Ed25519 signing keypairs on first install. Keys are used
for cryptographic content provenance in the injection defense system.
"""

from __future__ import annotations

from pathlib import Path


def ensure_signing_keys(keys_dir: str | None = None) -> dict:
    """Generate Ed25519 signing keys if they do not exist.

    Args:
        keys_dir: Directory for key storage. Defaults to
            ~/.local/spellbook/keys/

    Returns:
        Dict with success, created (bool), fingerprint, and keys_dir.
    """
    from spellbook.security.crypto import generate_keypair, get_key_fingerprint

    if keys_dir is None:
        keys_dir = str(Path.home() / ".local" / "spellbook" / "keys")

    keys_path = Path(keys_dir)
    already_exists = (keys_path / "signing.key").exists() and (
        keys_path / "signing.pub"
    ).exists()

    generate_keypair(keys_dir)

    fingerprint = get_key_fingerprint(keys_dir)

    return {
        "success": True,
        "created": not already_exists,
        "fingerprint": fingerprint,
        "keys_dir": keys_dir,
    }
