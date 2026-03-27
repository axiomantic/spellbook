"""Tests for notification MCP tool functions in server.py.

Uses .fn to access the underlying function from the FunctionTool wrapper.
All spellbook.notifications.notify functions are mocked. Tests verify tool behavior,
argument handling, and return contracts.
"""

import json

import bigfoot
import pytest

from spellbook import server


def _async_return(value):
    """Create an async function that returns ``value``, suitable for bigfoot .calls()."""
    async def _fn(*args, **kwargs):
        return value
    return _fn


class TestNotifySend:
    """notify_send() MCP tool."""

    @pytest.mark.asyncio
    async def test_success_returns_ok_json(self):
        mock_send = bigfoot.mock(
            "spellbook.notifications.notify:send_notification"
        )
        mock_send.calls(_async_return({"ok": True}))

        async with bigfoot:
            result_str = await server.notify_send.fn(body="hello world")

        mock_send.assert_call(args=(), kwargs={"title": None, "body": "hello world"})
        result = json.loads(result_str)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_not_available_returns_error_json(self):
        mock_send = bigfoot.mock(
            "spellbook.notifications.notify:send_notification"
        )
        mock_send.calls(
            _async_return({"error": "Notifications not available. Missing tools"})
        )

        async with bigfoot:
            result_str = await server.notify_send.fn(body="hello")

        mock_send.assert_call(args=(), kwargs={"title": None, "body": "hello"})
        result = json.loads(result_str)
        assert "error" in result
        assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_passes_title_and_body(self):
        mock_send = bigfoot.mock(
            "spellbook.notifications.notify:send_notification"
        )
        mock_send.calls(_async_return({"ok": True}))

        async with bigfoot:
            await server.notify_send.fn(body="test body", title="Custom Title")

        mock_send.assert_call(
            args=(), kwargs={"title": "Custom Title", "body": "test body"}
        )

    @pytest.mark.asyncio
    async def test_title_defaults_to_none(self):
        mock_send = bigfoot.mock(
            "spellbook.notifications.notify:send_notification"
        )
        mock_send.calls(_async_return({"ok": True}))

        async with bigfoot:
            await server.notify_send.fn(body="just body")

        mock_send.assert_call(
            args=(), kwargs={"title": None, "body": "just body"}
        )


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
        mock_get = bigfoot.mock("spellbook.notifications.notify:get_status")
        mock_get.returns(mock_status)

        async with bigfoot:
            result_str = await server.notify_status.fn()

        mock_get.assert_call()
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
        mock_get = bigfoot.mock("spellbook.notifications.notify:get_status")
        mock_get.returns(mock_status)

        async with bigfoot:
            result_str = await server.notify_status.fn()

        mock_get.assert_call()
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
    async def test_sets_all_config_keys(self, tmp_path, monkeypatch):
        import spellbook.core.config as config_mod

        config_file = tmp_path / "spellbook.json"
        config_file.write_text("{}")

        monkeypatch.setattr(config_mod, "CONFIG_LOCK_PATH", tmp_path / "config.lock")

        mock_config_path = bigfoot.mock("spellbook.core.config:get_config_path")
        # config_set_many calls get_config_path once, then config_get calls it twice
        mock_config_path.returns(config_file).returns(config_file).returns(config_file)

        async with bigfoot:
            result_str = await server.notify_config_set.fn(
                enabled=True, title="My Project"
            )

        with bigfoot.in_any_order():
            mock_config_path.assert_call()
            mock_config_path.assert_call()
            mock_config_path.assert_call()
        result = json.loads(result_str)
        assert result["status"] == "ok"
        assert result["config"]["notify_enabled"] is True
        assert result["config"]["notify_title"] == "My Project"

    @pytest.mark.asyncio
    async def test_partial_update_only_sets_provided(self, tmp_path, monkeypatch):
        import spellbook.core.config as config_mod

        config_file = tmp_path / "spellbook.json"
        config_file.write_text('{"notify_enabled": true}')

        monkeypatch.setattr(config_mod, "CONFIG_LOCK_PATH", tmp_path / "config.lock")

        mock_config_path = bigfoot.mock("spellbook.core.config:get_config_path")
        # config_set_many calls get_config_path once, then config_get calls it twice
        mock_config_path.returns(config_file).returns(config_file).returns(config_file)

        async with bigfoot:
            result_str = await server.notify_config_set.fn(
                title="New Title"
            )

        with bigfoot.in_any_order():
            mock_config_path.assert_call()
            mock_config_path.assert_call()
            mock_config_path.assert_call()
        result = json.loads(result_str)
        assert result["config"]["notify_title"] == "New Title"
        assert result["config"]["notify_enabled"] is True  # Preserved
