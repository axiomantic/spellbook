"""Tests for auto-signing trusted content during installation."""
import hashlib
from pathlib import Path


def test_sign_trusted_files_exists():
    """Installer keys component must have sign_trusted_files."""
    from installer.components.keys import sign_trusted_files
    assert callable(sign_trusted_files)


def test_sign_trusted_files_signs_file(tmp_path):
    """sign_trusted_files must sign the provided file list."""
    from installer.components.keys import ensure_signing_keys, sign_trusted_files

    keys_dir = str(tmp_path / "keys")
    ensure_signing_keys(keys_dir)

    # Create a test file to sign
    test_file = tmp_path / "CLAUDE.md"
    test_file.write_text("# Test content")

    result = sign_trusted_files(keys_dir, [str(test_file)])
    assert result["signed_count"] == 1
    assert result["failed_count"] == 0


def test_sign_trusted_files_skips_missing(tmp_path):
    """sign_trusted_files must skip non-existent files gracefully."""
    from installer.components.keys import ensure_signing_keys, sign_trusted_files

    keys_dir = str(tmp_path / "keys")
    ensure_signing_keys(keys_dir)

    result = sign_trusted_files(keys_dir, ["/nonexistent/file.md"])
    assert result["signed_count"] == 0
    assert result["skipped_count"] == 1


def test_sign_trusted_files_returns_hashes(tmp_path):
    """sign_trusted_files must return content hashes of signed files."""
    from installer.components.keys import ensure_signing_keys, sign_trusted_files

    keys_dir = str(tmp_path / "keys")
    ensure_signing_keys(keys_dir)

    test_file = tmp_path / "AGENTS.md"
    content = "# Agents"
    test_file.write_text(content)

    result = sign_trusted_files(keys_dir, [str(test_file)])
    assert len(result["signed"]) == 1
    signed_entry = result["signed"][0]
    expected_hash = hashlib.sha256(content.encode()).hexdigest()
    assert signed_entry["content_hash"] == expected_hash
    assert signed_entry["signature"] is not None
