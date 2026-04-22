"""Tests for hook-related REST API routes in spellbook/mcp/routes.py.

Tests /api/hook-log endpoint by calling the route handler function
directly with stub Starlette Request objects.
"""

import asyncio
import json

import pytest


async def _await_len(collection, expected: int, timeout: float = 2.0) -> None:
    """Poll ``collection`` until it reaches ``expected`` length or ``timeout``.

    ``record_hook_event`` is offloaded to ``loop.run_in_executor`` via
    ``_spawn_background``, so the handler returns before the spy is
    populated. Tests poll here instead of asserting synchronously. The
    2-second ceiling is generous relative to a typical thread-pool hop
    (<1ms) but keeps CI hangs observable.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while len(collection) < expected:
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(
                f"collection did not reach {expected} entries within "
                f"{timeout}s; current len={len(collection)}"
            )
        await asyncio.sleep(0.01)


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


# ---------------------------------------------------------------------------
# Tests: /api/hooks/record
# ---------------------------------------------------------------------------


class TestApiHooksRecord:
    @pytest.mark.asyncio
    async def test_accepts_valid_payload(self, monkeypatch):
        """Valid payload invokes record_hook_event with the right args."""
        calls: list[dict] = []

        def _fake_record(**kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(
            "spellbook.hooks.observability.record_hook_event",
            _fake_record,
        )
        from spellbook.mcp.routes import api_hooks_record

        request = _make_request({
            "hook_name": "spellbook_hook",
            "event_name": "PreToolUse",
            "duration_ms": 42,
            "exit_code": 0,
            "tool_name": "Bash",
            "error": None,
            "notes": None,
        })

        resp = await api_hooks_record(request)
        assert resp.status_code == 202
        body = json.loads(resp.body.decode())
        assert body == {"ok": True}

        await _await_len(calls, 1)
        c = calls[0]
        assert c["hook_name"] == "spellbook_hook"
        assert c["event_name"] == "PreToolUse"
        assert c["duration_ms"] == 42
        assert c["exit_code"] == 0
        assert c["tool_name"] == "Bash"

    @pytest.mark.asyncio
    async def test_rejects_missing_hook_name(self):
        from spellbook.mcp.routes import api_hooks_record

        request = _make_request({
            "event_name": "Stop",
            "duration_ms": 10,
            "exit_code": 0,
        })
        resp = await api_hooks_record(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_negative_duration(self):
        from spellbook.mcp.routes import api_hooks_record

        request = _make_request({
            "hook_name": "h",
            "event_name": "e",
            "duration_ms": -1,
            "exit_code": 0,
        })
        resp = await api_hooks_record(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_oversized_notes(self):
        from spellbook.mcp.routes import api_hooks_record

        request = _make_request({
            "hook_name": "h",
            "event_name": "e",
            "duration_ms": 0,
            "exit_code": 0,
            "notes": "x" * 4001,
        })
        resp = await api_hooks_record(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_invalid_json(self):
        from spellbook.mcp.routes import api_hooks_record

        request = _make_bad_request()
        resp = await api_hooks_record(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_record_failure_still_returns_202(self, monkeypatch):
        """record_hook_event is best-effort; route still returns 202."""
        def _boom(**kwargs):
            raise RuntimeError("DB down")

        monkeypatch.setattr(
            "spellbook.hooks.observability.record_hook_event",
            _boom,
        )
        from spellbook.mcp.routes import api_hooks_record

        request = _make_request({
            "hook_name": "h",
            "event_name": "e",
            "duration_ms": 0,
            "exit_code": 0,
        })
        resp = await api_hooks_record(request)
        assert resp.status_code == 202


