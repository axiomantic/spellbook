"""Tests for hook-related REST API routes in spellbook/mcp/routes.py.

Tests /api/hook-log and /api/messaging/poll endpoints by calling the
route handler functions directly with mock Starlette Request objects.
"""

import asyncio
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Mock the entire TTS module tree before importing routes.
# The tts module depends on numpy/sounddevice/wyoming which may not
# be installed in the test environment.
_tts_mock = ModuleType("spellbook.notifications.tts")
for _mod_name in (
    "numpy", "sounddevice", "wyoming", "wyoming.audio",
    "wyoming.tts", "wyoming.event", "wyoming.info",
    "spellbook.notifications.tts",
):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = ModuleType(_mod_name) if _mod_name != "spellbook.notifications.tts" else _tts_mock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(body: dict) -> MagicMock:
    """Create a mock Starlette Request with a JSON body."""
    request = MagicMock()

    async def _json():
        return body

    request.json = _json
    return request


def _make_bad_request() -> MagicMock:
    """Create a mock Starlette Request that raises on .json()."""
    request = MagicMock()

    async def _json():
        raise ValueError("invalid JSON")

    request.json = _json
    return request


# ---------------------------------------------------------------------------
# Tests: /api/hook-log
# ---------------------------------------------------------------------------

class TestApiHookLog:
    @pytest.mark.asyncio
    async def test_accepts_valid_payload(self, tmp_path, monkeypatch):
        """Valid payload writes to log file and returns ok."""
        monkeypatch.setattr(
            "spellbook.mcp.routes.get_spellbook_config_dir",
            lambda: tmp_path,
        )
        from spellbook.mcp.routes import api_hook_log

        request = _make_request({
            "timestamp": "2026-04-08T12:00:00Z",
            "event": "PostToolUse:Bash",
            "traceback": "Traceback...\nValueError: boom",
        })

        resp = await api_hook_log(request)
        body = json.loads(resp.body.decode())
        assert body == {"ok": True}
        assert resp.status_code == 200

        # Verify log file was created
        log_file = tmp_path / "logs" / "hook-errors.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "PostToolUse:Bash" in content
        assert "ValueError: boom" in content

    @pytest.mark.asyncio
    async def test_rejects_invalid_json(self, tmp_path, monkeypatch):
        """Invalid JSON body returns 400."""
        monkeypatch.setattr(
            "spellbook.mcp.routes.get_spellbook_config_dir",
            lambda: tmp_path,
        )
        from spellbook.mcp.routes import api_hook_log

        request = _make_bad_request()
        resp = await api_hook_log(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_missing_event(self, tmp_path, monkeypatch):
        """Missing 'event' field returns 400."""
        monkeypatch.setattr(
            "spellbook.mcp.routes.get_spellbook_config_dir",
            lambda: tmp_path,
        )
        from spellbook.mcp.routes import api_hook_log

        request = _make_request({
            "timestamp": "2026-04-08T12:00:00Z",
            "traceback": "something",
        })
        resp = await api_hook_log(request)
        body = json.loads(resp.body.decode())
        assert resp.status_code == 400
        assert "event" in body.get("error", "")


# ---------------------------------------------------------------------------
# Tests: /api/messaging/poll
# ---------------------------------------------------------------------------

class TestApiMessagingPoll:
    @pytest.mark.asyncio
    async def test_returns_empty_for_no_messages(self, tmp_path, monkeypatch):
        """No messaging directory returns empty list."""
        monkeypatch.setattr(
            "spellbook.mcp.routes.get_spellbook_config_dir",
            lambda: tmp_path,
        )
        from spellbook.mcp.routes import api_messaging_poll

        request = _make_request({"session_id": "test-session"})
        resp = await api_messaging_poll(request)
        body = json.loads(resp.body.decode())
        assert body == {"messages": []}

    @pytest.mark.asyncio
    async def test_returns_and_deletes_messages(self, tmp_path, monkeypatch):
        """Valid messages are returned and inbox files deleted."""
        monkeypatch.setattr(
            "spellbook.mcp.routes.get_spellbook_config_dir",
            lambda: tmp_path,
        )
        from spellbook.mcp.routes import api_messaging_poll

        # Set up inbox
        alias_dir = tmp_path / "messaging" / "worker-1"
        inbox = alias_dir / "inbox"
        inbox.mkdir(parents=True)
        (alias_dir / ".session_id").write_text("test-session")

        msg = {
            "id": "msg-001",
            "sender": "orchestrator",
            "recipient": "worker-1",
            "payload": {"task": "deploy"},
            "message_type": "direct",
            "correlation_id": "corr-123",
        }
        msg_file = inbox / "msg-001.json"
        msg_file.write_text(json.dumps(msg))

        request = _make_request({"session_id": "test-session"})
        resp = await api_messaging_poll(request)
        body = json.loads(resp.body.decode())

        assert len(body["messages"]) == 1
        assert body["messages"][0]["sender"] == "orchestrator"
        assert body["messages"][0]["payload"] == {"task": "deploy"}
        assert body["messages"][0]["correlation_id"] == "corr-123"
        assert body["messages"][0]["message_type"] == "direct"

        # File should be deleted
        assert not msg_file.exists()

    @pytest.mark.asyncio
    async def test_rejects_missing_session_id(self, tmp_path, monkeypatch):
        """Missing session_id returns 400."""
        monkeypatch.setattr(
            "spellbook.mcp.routes.get_spellbook_config_dir",
            lambda: tmp_path,
        )
        from spellbook.mcp.routes import api_messaging_poll

        request = _make_request({})
        resp = await api_messaging_poll(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_filters_by_session_id(self, tmp_path, monkeypatch):
        """Only messages for the requested session_id are returned."""
        monkeypatch.setattr(
            "spellbook.mcp.routes.get_spellbook_config_dir",
            lambda: tmp_path,
        )
        from spellbook.mcp.routes import api_messaging_poll

        # Set up two alias dirs with different session_ids
        for alias, sid in [("mine", "my-session"), ("theirs", "other-session")]:
            alias_dir = tmp_path / "messaging" / alias
            inbox = alias_dir / "inbox"
            inbox.mkdir(parents=True)
            (alias_dir / ".session_id").write_text(sid)
            msg = {"sender": alias, "payload": {}, "message_type": "direct"}
            (inbox / "msg.json").write_text(json.dumps(msg))

        request = _make_request({"session_id": "my-session"})
        resp = await api_messaging_poll(request)
        body = json.loads(resp.body.decode())

        assert len(body["messages"]) == 1
        assert body["messages"][0]["sender"] == "mine"

        # Other session's file should still exist
        assert (tmp_path / "messaging" / "theirs" / "inbox" / "msg.json").exists()

    @pytest.mark.asyncio
    async def test_rejects_invalid_json(self, tmp_path, monkeypatch):
        """Invalid JSON body returns 400."""
        monkeypatch.setattr(
            "spellbook.mcp.routes.get_spellbook_config_dir",
            lambda: tmp_path,
        )
        from spellbook.mcp.routes import api_messaging_poll

        request = _make_bad_request()
        resp = await api_messaging_poll(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_handles_malformed_inbox_files(self, tmp_path, monkeypatch):
        """Malformed JSON in inbox files is deleted and skipped."""
        monkeypatch.setattr(
            "spellbook.mcp.routes.get_spellbook_config_dir",
            lambda: tmp_path,
        )
        from spellbook.mcp.routes import api_messaging_poll

        alias_dir = tmp_path / "messaging" / "worker"
        inbox = alias_dir / "inbox"
        inbox.mkdir(parents=True)
        (alias_dir / ".session_id").write_text("test-session")

        bad_file = inbox / "bad.json"
        bad_file.write_text("not valid json {{{")

        request = _make_request({"session_id": "test-session"})
        resp = await api_messaging_poll(request)
        body = json.loads(resp.body.decode())

        assert body["messages"] == []
        # Bad file should be cleaned up
        assert not bad_file.exists()
