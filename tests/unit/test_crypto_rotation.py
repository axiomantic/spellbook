"""Tests for Ed25519 key rotation support."""
from pathlib import Path


def test_rotate_keys_exists():
    """crypto module must have rotate_keys function."""
    from spellbook.security.crypto import rotate_keys
    assert callable(rotate_keys)


def test_rotate_keys_creates_new_pair(tmp_path):
    """rotate_keys must create a new keypair and archive the old one."""
    from spellbook.security.crypto import generate_keypair, rotate_keys

    keys_dir = str(tmp_path / "keys")
    generate_keypair(keys_dir)
    old_pub = (tmp_path / "keys" / "signing.pub").read_bytes()

    result = rotate_keys(keys_dir)

    new_pub = (tmp_path / "keys" / "signing.pub").read_bytes()
    assert old_pub != new_pub
    assert result["rotated"] is True
    assert result["archive_dir"] is not None


def test_rotate_keys_archives_old_key(tmp_path):
    """Old public key must be archived in keys/archive/."""
    from spellbook.security.crypto import generate_keypair, rotate_keys

    keys_dir = str(tmp_path / "keys")
    generate_keypair(keys_dir)

    result = rotate_keys(keys_dir)

    archive_dir = Path(result["archive_dir"])
    assert archive_dir.exists()
    archived_files = list(archive_dir.glob("signing.pub.*"))
    assert len(archived_files) == 1


def test_rotate_keys_old_signatures_verifiable(tmp_path):
    """Signatures from old key must be verifiable with archived key."""
    from spellbook.security.crypto import (
        generate_keypair,
        rotate_keys,
        sign_content,
        verify_signature_with_key_file,
    )

    keys_dir = str(tmp_path / "keys")
    generate_keypair(keys_dir)

    # Sign with old key
    sig = sign_content("test-hash", keys_dir)
    assert sig is not None

    # Rotate
    result = rotate_keys(keys_dir)

    # Old signature should NOT verify with new key
    from spellbook.security.crypto import verify_signature
    assert verify_signature("test-hash", sig, keys_dir) is False

    # Old signature SHOULD verify with archived key
    archive_dir = result["archive_dir"]
    archived_pubs = list(Path(archive_dir).glob("signing.pub.*"))
    assert len(archived_pubs) == 1
    assert verify_signature_with_key_file("test-hash", sig, str(archived_pubs[0])) is True


def test_rotate_keys_no_existing_key(tmp_path):
    """rotate_keys on empty dir must fail gracefully."""
    from spellbook.security.crypto import rotate_keys

    keys_dir = str(tmp_path / "keys")
    result = rotate_keys(keys_dir)
    assert result["rotated"] is False
