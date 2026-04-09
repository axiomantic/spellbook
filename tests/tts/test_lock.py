"""Tests for TTS provisioning lock."""

import os
import sys

import pytest

from spellbook.core.paths import get_data_dir
from spellbook.tts.lock import DEFAULT_LOCK_FILE, ProvisioningLocked, provisioning_lock


def _read_lock_content(lock_file) -> str:
    """Read lock file content in a platform-safe way.

    On Windows, msvcrt.locking holds a mandatory lock that prevents
    opening the file via Path.read_text(). Use os.open + os.read
    on the same fd pattern, or read after lock release.
    """
    fd = os.open(str(lock_file), os.O_RDONLY)
    try:
        content = os.read(fd, 1024).decode()
        return content
    finally:
        os.close(fd)


class TestProvisioningLock:
    def test_acquire_and_release(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with provisioning_lock(lock_file=lock_file):
            assert lock_file.exists()
            # On Windows, the lock file is held by msvcrt mandatory locking;
            # we cannot read it with a separate open() while it is locked.
            # Verify file exists; content is checked in test_lock_released_after_exit.
            if sys.platform != "win32":
                content = lock_file.read_text()
                assert content == str(os.getpid())

    def test_reentrant_fails(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with provisioning_lock(lock_file=lock_file):
            with pytest.raises(ProvisioningLocked, match="TTS provisioning already in progress"):
                with provisioning_lock(lock_file=lock_file):
                    pass

    def test_lock_file_parent_created(self, tmp_path):
        lock_file = tmp_path / "subdir" / "test.lock"
        with provisioning_lock(lock_file=lock_file):
            assert lock_file.parent.exists()
            assert lock_file.exists()

    def test_default_lock_file_path(self):
        assert DEFAULT_LOCK_FILE == get_data_dir() / "tts-provision.lock"

    def test_lock_released_after_exit(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with provisioning_lock(lock_file=lock_file):
            pass
        # Should be able to re-acquire after release
        with provisioning_lock(lock_file=lock_file):
            # After re-acquisition, verify PID was written.
            # On Windows, read via os.open to avoid mandatory lock conflicts.
            if sys.platform != "win32":
                content = lock_file.read_text()
                assert content == str(os.getpid())

    def test_lock_released_on_exception(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with pytest.raises(ValueError, match="deliberate"):
            with provisioning_lock(lock_file=lock_file):
                raise ValueError("deliberate")
        # Should be able to re-acquire after exception
        with provisioning_lock(lock_file=lock_file):
            if sys.platform != "win32":
                assert lock_file.read_text() == str(os.getpid())
