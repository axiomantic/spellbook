"""Tests for update notifications in session_init()."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


class TestSessionGreetingNotifications:
    """Tests for update notifications in session_init()."""

    def test_notification_after_auto_update(self, tmp_path, monkeypatch):
        """session_init includes notification after recent auto-update."""
        from spellbook_mcp.config_tools import session_init, config_get, config_set, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", lock_path)

        # Set up config with recent auto-update
        from datetime import datetime
        config_set("last_auto_update", {
            "version": "0.9.10",
            "from_version": "0.9.9",
            "applied_at": datetime.now().isoformat(),
        })
        config_set("session_mode", "none")

        # Mock resume context
        with patch("spellbook_mcp.config_tools._get_resume_context", return_value={"resume_available": False}):
            result = session_init()

        assert "update_notification" in result
        assert result["update_notification"]["type"] == "applied"
        assert result["update_notification"]["version"] == "0.9.10"

    def test_notification_major_pending(self, tmp_path, monkeypatch):
        """session_init includes major update notification."""
        from spellbook_mcp.config_tools import session_init, config_set, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", lock_path)

        config_set("pending_major_update", {
            "version": "1.0.0",
            "detected_at": "2026-02-19T10:00:00",
        })
        config_set("session_mode", "none")

        with patch("spellbook_mcp.config_tools._get_resume_context", return_value={"resume_available": False}):
            result = session_init()

        assert "update_notification" in result
        assert result["update_notification"]["type"] == "major_pending"
        assert result["update_notification"]["version"] == "1.0.0"

    def test_notification_cleared_after_showing(self, tmp_path, monkeypatch):
        """last_auto_update is cleared after session_init returns it."""
        from spellbook_mcp.config_tools import session_init, config_get, config_set, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", lock_path)

        from datetime import datetime
        config_set("last_auto_update", {
            "version": "0.9.10",
            "from_version": "0.9.9",
            "applied_at": datetime.now().isoformat(),
        })
        config_set("session_mode", "none")

        with patch("spellbook_mcp.config_tools._get_resume_context", return_value={"resume_available": False}):
            session_init()

        # last_auto_update should be cleared
        assert config_get("last_auto_update") is None

    def test_paused_notification(self, tmp_path, monkeypatch):
        """session_init includes paused notification when auto_update_paused."""
        from spellbook_mcp.config_tools import session_init, config_set, get_config_path

        config_path = tmp_path / "spellbook.json"
        lock_path = tmp_path / "config.lock"
        monkeypatch.setattr("spellbook_mcp.config_tools.get_config_path", lambda: config_path)
        monkeypatch.setattr("spellbook_mcp.config_tools.CONFIG_LOCK_PATH", lock_path)

        config_set("auto_update_paused", True)
        config_set("session_mode", "none")

        with patch("spellbook_mcp.config_tools._get_resume_context", return_value={"resume_available": False}):
            result = session_init()

        assert "update_notification" in result
        assert result["update_notification"].get("paused") is True
