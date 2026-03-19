"""Tests for notification MCP tool functions in server.py.

Uses .fn to access the underlying function from the FunctionTool wrapper.
All spellbook.notifications.notify functions are mocked. Tests verify tool behavior,
argument handling, and return contracts.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spellbook import server


class TestNotifySend:
    """notify_send() MCP tool."""

    @pytest.mark.asyncio
    async def test_success_returns_ok_json(self):
        mock_result = {"ok": True}
        with patch(
            "spellbook.notifications.notify.send_notification",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result_str = await server.notify_send.fn(body="hello world")
        result = json.loads(result_str)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_not_available_returns_error_json(self):
        mock_result = {"error": "Notifications not available. Missing tools"}
        with patch(
            "spellbook.notifications.notify.send_notification",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result_str = await server.notify_send.fn(body="hello")
        result = json.loads(result_str)
        assert "error" in result
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_passes_title_and_body(self):
        with patch(
            "spellbook.notifications.notify.send_notification",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = {"ok": True}
            await server.notify_send.fn(body="test body", title="Custom Title")
            mock_send.assert_called_once_with(
                title="Custom Title", body="test body"
            )

    @pytest.mark.asyncio
    async def test_title_defaults_to_none(self):
        with patch(
            "spellbook.notifications.notify.send_notification",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = {"ok": True}
            await server.notify_send.fn(body="just body")
            mock_send.assert_called_once_with(title=None, body="just body")


class TestNotifyStatus:
    """notify_status() MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_status_json(self):
        mock_status = {
            "available": True,
            "enabled": True,
            "platform": "macos",
            "title": "Spellbook",
            "error": None,
        }
        with patch("spellbook.notifications.notify.get_status", return_value=mock_status):
            result_str = await server.notify_status.fn()
        result = json.loads(result_str)
        assert result == mock_status

    @pytest.mark.asyncio
    async def test_returns_unavailable_status_json(self):
        mock_status = {
            "available": False,
            "enabled": True,
            "platform": None,
            "title": "Spellbook",
            "error": "Missing tools",
        }
        with patch("spellbook.notifications.notify.get_status", return_value=mock_status):
            result_str = await server.notify_status.fn()
        result = json.loads(result_str)
        assert result["available"] is False
        assert result["error"] == "Missing tools"


class TestNotifySessionSetTool:
    """notify_session_set() MCP tool."""

    @pytest.mark.asyncio
    async def test_updates_session_state(self):
        from spellbook.core.config import _session_states, _session_activity

        _session_states.clear()
        _session_activity.clear()

        result_str = await server.notify_session_set.fn(
            enabled=False, title="Test App"
        )
        result = json.loads(result_str)

        assert result["status"] == "ok"
        assert result["session_notify"]["enabled"] is False
        assert result["session_notify"]["title"] == "Test App"

        _session_states.clear()
        _session_activity.clear()

    @pytest.mark.asyncio
    async def test_partial_update(self):
        from spellbook.core.config import (
            _session_states,
            _session_activity,
            _get_session_state,
        )

        _session_states.clear()
        _session_activity.clear()

        # Set initial values
        state = _get_session_state()
        state["notify"] = {"enabled": True, "title": "Original"}

        result_str = await server.notify_session_set.fn(title="Changed")
        result = json.loads(result_str)

        assert result["session_notify"]["title"] == "Changed"
        assert result["session_notify"]["enabled"] is True  # Unchanged

        _session_states.clear()
        _session_activity.clear()


class TestNotifyConfigSetTool:
    """notify_config_set() MCP tool."""

    @pytest.mark.asyncio
    async def test_sets_all_config_keys(self, tmp_path):
        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")
        with patch(
            "spellbook.core.config.get_config_path",
            return_value=config_file,
        ):
            with patch(
                "spellbook.core.config.CONFIG_LOCK_PATH",
                tmp_path / "config.lock",
            ):
                result_str = await server.notify_config_set.fn(
                    enabled=True, title="My Project"
                )

        result = json.loads(result_str)
        assert result["status"] == "ok"
        assert result["config"]["notify_enabled"] is True
        assert result["config"]["notify_title"] == "My Project"

    @pytest.mark.asyncio
    async def test_partial_update_only_sets_provided(self, tmp_path):
        config_file = tmp_path / "spellbook.json"
        config_file.write_text('{"notify_enabled": true}')
        with patch(
            "spellbook.core.config.get_config_path",
            return_value=config_file,
        ):
            with patch(
                "spellbook.core.config.CONFIG_LOCK_PATH",
                tmp_path / "config.lock",
            ):
                result_str = await server.notify_config_set.fn(
                    title="New Title"
                )

        result = json.loads(result_str)
        assert result["config"]["notify_title"] == "New Title"
        assert result["config"]["notify_enabled"] is True  # Preserved
