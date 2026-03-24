"""Tests for Ed25519 key management and signing."""
import base64

import pytest
from pathlib import Path


@pytest.fixture
def keys_dir(tmp_path):
    return tmp_path / "keys"


class TestKeyGeneration:

    def test_generate_keypair_creates_files(self, keys_dir):
        from spellbook.security.crypto import generate_keypair
        generate_keypair(str(keys_dir))
        assert (keys_dir / "signing.key").exists()
        assert (keys_dir / "signing.pub").exists()

    def test_private_key_permissions(self, keys_dir):
        from spellbook.security.crypto import generate_keypair
        generate_keypair(str(keys_dir))
        import os
        mode = os.stat(keys_dir / "signing.key").st_mode & 0o777
        assert mode == 0o600, f"Private key has mode {oct(mode)}, expected 0o600"

    def test_generate_keypair_idempotent(self, keys_dir):
        from spellbook.security.crypto import generate_keypair
        generate_keypair(str(keys_dir))
        pub1 = (keys_dir / "signing.pub").read_bytes()
        # Second call should not overwrite
        generate_keypair(str(keys_dir))
        pub2 = (keys_dir / "signing.pub").read_bytes()
        assert pub1 == pub2

    def test_load_keys(self, keys_dir):
        from spellbook.security.crypto import generate_keypair, load_private_key, load_public_key
        generate_keypair(str(keys_dir))
        priv = load_private_key(str(keys_dir))
        pub = load_public_key(str(keys_dir))
        assert priv is not None
        assert pub is not None


class TestSigning:

    def test_sign_and_verify_roundtrip(self, keys_dir):
        from spellbook.security.crypto import generate_keypair, sign_content, verify_signature
        generate_keypair(str(keys_dir))
        content_hash = "abc123def456"
        signature = sign_content(content_hash, str(keys_dir))
        assert signature is not None
        assert verify_signature(content_hash, signature, str(keys_dir)) is True

    def test_verify_fails_with_wrong_hash(self, keys_dir):
        from spellbook.security.crypto import generate_keypair, sign_content, verify_signature
        generate_keypair(str(keys_dir))
        signature = sign_content("correct-hash", str(keys_dir))
        assert verify_signature("wrong-hash", signature, str(keys_dir)) is False

    def test_verify_fails_with_wrong_signature(self, keys_dir):
        from spellbook.security.crypto import generate_keypair, verify_signature
        generate_keypair(str(keys_dir))
        fake_sig = base64.b64encode(b"x" * 64).decode()
        assert verify_signature("any-hash", fake_sig, str(keys_dir)) is False

    def test_key_fingerprint(self, keys_dir):
        from spellbook.security.crypto import generate_keypair, get_key_fingerprint
        generate_keypair(str(keys_dir))
        fp = get_key_fingerprint(str(keys_dir))
        assert isinstance(fp, str)
        assert len(fp) > 10

    def test_sign_without_key_returns_none(self, keys_dir):
        from spellbook.security.crypto import sign_content
        result = sign_content("some-hash", str(keys_dir))
        assert result is None

    def test_verify_without_key_returns_false(self, keys_dir):
        from spellbook.security.crypto import verify_signature
        result = verify_signature("hash", "sig", str(keys_dir))
        assert result is False

    def test_load_private_key_missing_returns_none(self, keys_dir):
        from spellbook.security.crypto import load_private_key
        assert load_private_key(str(keys_dir)) is None

    def test_load_public_key_missing_returns_none(self, keys_dir):
        from spellbook.security.crypto import load_public_key
        assert load_public_key(str(keys_dir)) is None

    def test_fingerprint_without_key_returns_none(self, keys_dir):
        from spellbook.security.crypto import get_key_fingerprint
        assert get_key_fingerprint(str(keys_dir)) is None
