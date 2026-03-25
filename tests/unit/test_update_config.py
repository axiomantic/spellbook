"""Tests for thread-safe config access and update notification integration."""

import json
import os
import threading
import pytest
from pathlib import Path
from unittest.mock import patch

try:
    import fcntl
except ImportError:
    fcntl = None  # Windows


class TestConfigFileLocking:
    """Tests for file-level locking in config_get/config_set."""

    def test_config_set_creates_lock_file(self, tmp_path, monkeypatch):
        """config_set should use CrossPlatformLock during writes."""
        from spellbook.core.config import config_set, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook.core.config.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook.core.config.CONFIG_LOCK_PATH", lock_path)

        # Patch CrossPlatformLock to verify it's used as a context manager
        from spellbook.core.compat import CrossPlatformLock

        original_enter = CrossPlatformLock.__enter__
        lock_entered = {"value": False}

        def tracking_enter(self):
            lock_entered["value"] = True
            return original_enter(self)

        with patch.object(CrossPlatformLock, "__enter__", tracking_enter):
            config_set("test_key", "test_value")

        # Verify lock was actually entered as a context manager
        assert lock_entered["value"], "CrossPlatformLock was not used as context manager"

        # Config file should exist with the value
        config = json.loads(config_path.read_text())
        assert config["test_key"] == "test_value"

    def test_concurrent_config_writes_no_data_loss(self, tmp_path, monkeypatch):
        """Concurrent writes should not lose data due to locking."""
        from spellbook.core.config import config_set, config_get, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook.core.config.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook.core.config.CONFIG_LOCK_PATH", lock_path)

        # Write initial config
        config_path.write_text(json.dumps({"initial": True}) + "\n")

        errors = []

        def write_key(key, value):
            try:
                config_set(key, value)
            except Exception as e:
                errors.append(e)

        # Concurrent writes
        threads = []
        for i in range(10):
            t = threading.Thread(target=write_key, args=(f"key_{i}", f"value_{i}"))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # All keys should be present (no lost updates)
        final_config = json.loads(config_path.read_text())
        assert final_config["initial"] is True
        for i in range(10):
            assert final_config[f"key_{i}"] == f"value_{i}"

    def test_config_get_reads_with_shared_lock(self, tmp_path, monkeypatch):
        """config_get should work correctly with locking."""
        from spellbook.core.config import config_get, config_set, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook.core.config.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook.core.config.CONFIG_LOCK_PATH", lock_path)

        config_set("locked_key", 42)
        result = config_get("locked_key")
        assert result == 42

    def test_config_write_is_atomic(self, tmp_path, monkeypatch):
        """Config write uses atomic replace pattern.

        Verifies that config_set writes to a temp file then replaces,
        so a Ctrl+C mid-write cannot corrupt the original config file.
        """
        from spellbook.core.config import config_set

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook.core.config.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook.core.config.CONFIG_LOCK_PATH", lock_path)

        # Write initial valid config
        config_path.write_text(json.dumps({"existing": "data"}) + "\n")

        # Track os.replace calls to verify atomic pattern
        replace_calls = []
        original_replace = os.replace

        def tracking_replace(src, dst):
            replace_calls.append((src, dst))
            return original_replace(src, dst)

        monkeypatch.setattr("os.replace", tracking_replace)

        config_set("new_key", "new_value")

        # Verify os.replace was called (atomic rename)
        assert len(replace_calls) == 1, "os.replace should be called exactly once"
        src, dst = replace_calls[0]
        assert dst == str(config_path), "os.replace target should be the config path"
        assert src.endswith(".tmp"), "os.replace source should be a .tmp file"

        # Verify final config is valid and contains both keys
        config = json.loads(config_path.read_text())
        assert config["existing"] == "data"
        assert config["new_key"] == "new_value"

    def test_config_write_atomic_cleanup_on_failure(self, tmp_path, monkeypatch):
        """If write fails before os.replace, original config is untouched."""
        from spellbook.core.config import config_set

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook.core.config.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook.core.config.CONFIG_LOCK_PATH", lock_path)

        # Write initial valid config
        original_content = json.dumps({"precious": "data"}) + "\n"
        config_path.write_text(original_content)

        # Make os.write fail to simulate interrupted write
        original_write = os.write

        def failing_write(fd, data):
            os.close(fd)  # Close fd so cleanup doesn't double-close
            raise OSError("simulated write failure")

        monkeypatch.setattr("os.write", failing_write)

        with pytest.raises(OSError, match="simulated write failure"):
            config_set("bad_key", "bad_value")

        # Original config must be untouched
        assert config_path.read_text() == original_content

        # No leftover temp files
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Temp files should be cleaned up: {tmp_files}"
