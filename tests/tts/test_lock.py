"""Tests for TTS provisioning lock."""

import os

import pytest

from spellbook.core.paths import get_data_dir
from spellbook.tts.lock import DEFAULT_LOCK_FILE, ProvisioningLocked, provisioning_lock


class TestProvisioningLock:
    def test_acquire_and_release(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with provisioning_lock(lock_file=lock_file):
            assert lock_file.exists()
        # Verify PID was written after release
        assert lock_file.read_text() == str(os.getpid())

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
        assert DEFAULT_LOCK_FILE.name == "tts-provision.lock"
        assert DEFAULT_LOCK_FILE.parent == get_data_dir()

    def test_lock_released_after_exit(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with provisioning_lock(lock_file=lock_file):
            pass
        # Verify PID was written after release
        assert lock_file.read_text() == str(os.getpid())
        # Should be able to re-acquire after release
        with provisioning_lock(lock_file=lock_file):
            pass

    def test_lock_released_on_exception(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with pytest.raises(ValueError, match="deliberate"):
            with provisioning_lock(lock_file=lock_file):
                raise ValueError("deliberate")
        # Verify PID was written after exception
        assert lock_file.read_text() == str(os.getpid())
        # Should be able to re-acquire after exception
        with provisioning_lock(lock_file=lock_file):
            pass
