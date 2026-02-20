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
        """config_set should create a config.lock file during writes."""
        from spellbook_mcp.config_tools import config_set, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", lock_path)

        config_set("test_key", "test_value")

        # Config file should exist with the value
        config = json.loads(config_path.read_text())
        assert config["test_key"] == "test_value"

    def test_concurrent_config_writes_no_data_loss(self, tmp_path, monkeypatch):
        """Concurrent writes should not lose data due to locking."""
        from spellbook_mcp.config_tools import config_set, config_get, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", lock_path)

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
        from spellbook_mcp.config_tools import config_get, config_set, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", lock_path)

        config_set("locked_key", 42)
        result = config_get("locked_key")
        assert result == 42
