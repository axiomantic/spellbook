"""Ed25519 cryptographic key management and content signing.

Provides key generation, signing, and verification for content
provenance in the injection defense system.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger(__name__)

_PRIVATE_KEY_FILE = "signing.key"
_PUBLIC_KEY_FILE = "signing.pub"


def generate_keypair(keys_dir: str) -> None:
    """Generate an Ed25519 keypair if one does not already exist.

    Creates the keys directory if needed. Private key is stored with
    0600 permissions.

    Args:
        keys_dir: Directory to store the keypair.
    """
    keys_path = Path(keys_dir)
    keys_path.mkdir(parents=True, exist_ok=True)

    priv_path = keys_path / _PRIVATE_KEY_FILE
    pub_path = keys_path / _PUBLIC_KEY_FILE

    if priv_path.exists() and pub_path.exists():
        return  # Keypair already exists

    private_key = Ed25519PrivateKey.generate()

    # Write private key
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    priv_path.write_bytes(priv_bytes)
    os.chmod(str(priv_path), 0o600)

    # Write public key
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_path.write_bytes(pub_bytes)


def load_private_key(keys_dir: str) -> Ed25519PrivateKey | None:
    """Load the Ed25519 private key from disk.

    Args:
        keys_dir: Directory containing the keypair.

    Returns:
        Private key object or None if not found.
    """
    priv_path = Path(keys_dir) / _PRIVATE_KEY_FILE
    if not priv_path.exists():
        return None
    key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
    if isinstance(key, Ed25519PrivateKey):
        return key
    return None


def load_public_key(keys_dir: str) -> Ed25519PublicKey | None:
    """Load the Ed25519 public key from disk.

    Args:
        keys_dir: Directory containing the keypair.

    Returns:
        Public key object or None if not found.
    """
    pub_path = Path(keys_dir) / _PUBLIC_KEY_FILE
    if not pub_path.exists():
        return None
    key = serialization.load_pem_public_key(pub_path.read_bytes())
    if isinstance(key, Ed25519PublicKey):
        return key
    return None


def sign_content(content_hash: str, keys_dir: str) -> str | None:
    """Sign a content hash with the Ed25519 private key.

    Args:
        content_hash: SHA-256 hash string to sign.
        keys_dir: Directory containing the keypair.

    Returns:
        Base64-encoded signature string, or None if key not found.
    """
    private_key = load_private_key(keys_dir)
    if private_key is None:
        return None
    signature = private_key.sign(content_hash.encode())
    return base64.b64encode(signature).decode()


def verify_signature(
    content_hash: str,
    signature_b64: str,
    keys_dir: str,
) -> bool:
    """Verify an Ed25519 signature against a content hash.

    Args:
        content_hash: SHA-256 hash string that was signed.
        signature_b64: Base64-encoded signature to verify.
        keys_dir: Directory containing the keypair.

    Returns:
        True if signature is valid, False otherwise.
    """
    public_key = load_public_key(keys_dir)
    if public_key is None:
        return False
    try:
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, content_hash.encode())
        return True
    except (InvalidSignature, Exception):
        return False


def get_key_fingerprint(keys_dir: str) -> str | None:
    """Get the SHA-256 fingerprint of the public key.

    Args:
        keys_dir: Directory containing the keypair.

    Returns:
        Hex-encoded fingerprint string, or None if key not found.
    """
    pub_path = Path(keys_dir) / _PUBLIC_KEY_FILE
    if not pub_path.exists():
        return None
    pub_bytes = pub_path.read_bytes()
    return hashlib.sha256(pub_bytes).hexdigest()
