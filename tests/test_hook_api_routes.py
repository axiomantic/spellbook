"""Tests for hook-related REST API routes in spellbook/mcp/routes.py.

Tests /api/hook-log endpoint by calling the route handler function
directly with stub Starlette Request objects.
"""

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _StubRequest:
    """Minimal Starlette Request stub with a JSON body."""

    def __init__(self, body: dict | None = None, *, raise_on_json: bool = False):
        self._body = body
        self._raise_on_json = raise_on_json

    async def json(self):
        if self._raise_on_json:
            raise ValueError("invalid JSON")
        return self._body


def _make_request(body: dict) -> _StubRequest:
    """Create a stub Starlette Request with a JSON body."""
    return _StubRequest(body)


def _make_bad_request() -> _StubRequest:
    """Create a stub Starlette Request that raises on .json()."""
    return _StubRequest(raise_on_json=True)


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


