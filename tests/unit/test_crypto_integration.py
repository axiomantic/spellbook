"""Integration test for the cryptographic content provenance system (E9).

End-to-end: generate keys, sign content, verify signature,
verify unsigned content fails.
"""
import hashlib

import pytest


@pytest.fixture
def keys_dir(tmp_path):
    """Generate a fresh keypair in a temp directory."""
    from spellbook.security.crypto import generate_keypair
    kd = str(tmp_path / "keys")
    generate_keypair(kd)
    return kd


class TestCryptoIntegration:

    def test_full_sign_verify_roundtrip(self, keys_dir):
        """Generate keys -> sign content -> verify signature."""
        from spellbook.security.crypto import (
            get_key_fingerprint,
            sign_content,
            verify_signature,
        )

        content = "Hello, this is trusted content."
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Sign
        signature = sign_content(content_hash, keys_dir)
        assert signature is not None

        # Verify
        assert verify_signature(content_hash, signature, keys_dir) is True

        # Fingerprint is consistent
        fp = get_key_fingerprint(keys_dir)
        assert fp is not None
        assert len(fp) == 64  # SHA-256 hex

    def test_tampered_content_fails_verification(self, keys_dir):
        """Signature on original content must fail for tampered content."""
        from spellbook.security.crypto import sign_content, verify_signature

        original = hashlib.sha256(b"original").hexdigest()
        tampered = hashlib.sha256(b"tampered").hexdigest()

        signature = sign_content(original, keys_dir)
        assert verify_signature(tampered, signature, keys_dir) is False

    def test_rotation_preserves_old_verification(self, keys_dir):
        """After rotation, old signatures verifiable with archived key."""
        from spellbook.security.crypto import (
            rotate_keys,
            sign_content,
            verify_signature,
            verify_signature_with_key_file,
        )
        from pathlib import Path

        content_hash = hashlib.sha256(b"important data").hexdigest()
        old_sig = sign_content(content_hash, keys_dir)

        result = rotate_keys(keys_dir)
        assert result["rotated"] is True

        # Old sig fails with new key
        assert verify_signature(content_hash, old_sig, keys_dir) is False

        # Old sig works with archived key
        archive_dir = Path(result["archive_dir"])
        archived_pub = list(archive_dir.glob("signing.pub.*"))[0]
        assert verify_signature_with_key_file(
            content_hash, old_sig, str(archived_pub)
        ) is True

        # New sig works with new key
        new_sig = sign_content(content_hash, keys_dir)
        assert verify_signature(content_hash, new_sig, keys_dir) is True

    def test_installer_keys_and_autosign(self, tmp_path):
        """Installer component: generate keys then auto-sign files."""
        from installer.components.keys import ensure_signing_keys, sign_trusted_files
        from spellbook.security.crypto import verify_signature

        keys_dir = str(tmp_path / "keys")
        result = ensure_signing_keys(keys_dir)
        assert result["success"] is True
        assert result["created"] is True

        # Create test files
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# Claude Config")
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Agents Config")

        sign_result = sign_trusted_files(keys_dir, [str(claude_md), str(agents_md)])
        assert sign_result["signed_count"] == 2

        # Verify each signature
        for entry in sign_result["signed"]:
            assert verify_signature(
                entry["content_hash"],
                entry["signature"],
                keys_dir,
            ) is True

    def test_crypto_gate_config_respected(self):
        """Crypto gate config keys must be correctly named."""
        from spellbook.security.crypto_config import CRYPTO_CONFIG_DEFAULTS

        # These are the keys the hook checks
        assert "security.crypto.enabled" in CRYPTO_CONFIG_DEFAULTS
        assert "security.crypto.gate_spawn_session" in CRYPTO_CONFIG_DEFAULTS
        assert "security.crypto.gate_workflow_save" in CRYPTO_CONFIG_DEFAULTS
