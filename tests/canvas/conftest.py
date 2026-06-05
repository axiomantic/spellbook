"""Shared fixtures for canvas tests.

Per design §12 (Test Plan, "Existing fixtures:"), exposes reusable fixtures
consumed by the store tests, MCP tool tests, route tests, and integration
tests. Downstream test modules import these explicitly:

    from tests.canvas.conftest import canvas_tmp_root, mock_ctx, event_subscriber  # noqa: F401

This keeps canvas-specific fixtures owned by the canvas test package and
avoids leaking them into the top-level ``tests/conftest.py``.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def canvas_tmp_root(tmp_path, monkeypatch):
    """Override ``spellbook.canvas.store._resolve_canvas_root`` to return a
    fresh temp directory per test. Yields the directory path as a string.
    """
    root = tmp_path / "canvas"
    root.mkdir()
    monkeypatch.setattr(
        "spellbook.canvas.store._resolve_canvas_root", lambda: str(root)
    )
    yield str(root)


class _MockContext:
    """Minimal stand-in for FastMCP ``Context`` used by canvas MCP tools.

    The canvas tools never call methods on ``ctx`` directly; the parameter
    exists for FastMCP's auto-schema generation.
    """

    def __init__(self) -> None:
        self.session_id = "test-session"


@pytest.fixture
def mock_ctx() -> _MockContext:
    """Return a fake FastMCP ``Context`` for MCP tool tests."""
    return _MockContext()


@pytest.fixture
def mcp_ctx_with_session():
    """Factory: returns a Context-like object whose ``.session_id == sid``.

    ``_get_session_id(ctx)`` (sessions.py:151-158) returns ``sid`` for it. The
    decision tests call ``mcp_ctx_with_session("sess-1")`` to build a context
    bound to a specific session id.
    """

    def _make(sid: str):
        class _Ctx:
            session_id = sid

        return _Ctx()

    return _make


class _NoSessionCtx:
    """Context whose ``.session_id`` access raises ``RuntimeError``, so the
    guarded accessor ``_get_session_id`` (sessions.py:151-158) returns ``None``.
    """

    @property
    def session_id(self):
        raise RuntimeError("no session identity in this context")


@pytest.fixture
def mcp_ctx_no_session() -> _NoSessionCtx:
    """Return a context whose ``.session_id`` raises, mirroring the guard at
    sessions.py:151-158 so ``_get_session_id`` returns ``None``."""
    return _NoSessionCtx()


@pytest.fixture
def event_subscriber(monkeypatch):
    """Capture every event passed to ``event_bus.publish``.

    Replaces the singleton's ``publish`` coroutine with one that appends
    to a list. Test assertions read the list directly. Yields the list.

    Why monkeypatch rather than ``event_bus.subscribe``: pytest-asyncio
    creates a fresh event loop per test, and the singleton's per-subscriber
    asyncio.Queue is bound to whichever loop it was created on. Patching
    the publish method itself avoids loop-affinity races entirely.
    """
    received: list[Any] = []

    from spellbook.admin.events import event_bus

    async def _fake_publish(event):
        received.append(event)

    monkeypatch.setattr(event_bus, "publish", _fake_publish)
    yield received
