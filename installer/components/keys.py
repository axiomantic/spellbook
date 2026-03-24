"""Signing key generation component for the spellbook installer.

Generates Ed25519 signing keypairs on first install. Keys are used
for cryptographic content provenance in the injection defense system.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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


def sign_trusted_files(keys_dir: str, file_paths: list[str]) -> dict:
    """Sign a list of trusted files with the Ed25519 signing key.

    Computes SHA-256 hash of each file's content and signs it.
    Skips files that do not exist. Does NOT run security analysis
    (these are trusted install-time files like CLAUDE.md, AGENTS.md).

    Args:
        keys_dir: Directory containing the signing keypair.
        file_paths: List of absolute file paths to sign.

    Returns:
        Dict with signed (list of {path, content_hash, signature}),
        signed_count, skipped_count, failed_count.
    """
    from spellbook.security.crypto import get_key_fingerprint, sign_content

    signed = []
    skipped = 0
    failed = 0

    fingerprint = get_key_fingerprint(keys_dir)
    if not fingerprint:
        return {
            "signed": [],
            "signed_count": 0,
            "skipped_count": len(file_paths),
            "failed_count": 0,
            "error": "No signing key found",
        }

    for fpath in file_paths:
        p = Path(fpath)
        if not p.exists():
            skipped += 1
            continue

        try:
            content = p.read_text(encoding="utf-8")
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            signature = sign_content(content_hash, keys_dir)
            if signature:
                signed.append({
                    "path": str(p),
                    "content_hash": content_hash,
                    "signature": signature,
                    "signing_key_id": fingerprint,
                })
            else:
                failed += 1
        except Exception as exc:
            logger.warning("Failed to sign %s: %s", fpath, exc)
            failed += 1

    return {
        "signed": signed,
        "signed_count": len(signed),
        "skipped_count": skipped,
        "failed_count": failed,
    }
