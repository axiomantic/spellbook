"""Tests for dashboard ORM migration.

Verifies that get_dashboard_data() uses SQLAlchemy ORM sessions
(get_spellbook_session, get_fractal_session)
instead of raw SQL query helpers.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import bigfoot
from dirty_equals import IsInstance
import pytest


def _make_result_mock(value):
    """Build a SimpleNamespace mimicking a SQLAlchemy result.

    For int values: result.scalar_one() returns the int.
    For list values: result.scalars().all() returns the list.
    """
    if isinstance(value, int):
        return SimpleNamespace(scalar_one=lambda: value)
    else:
        scalars_ns = SimpleNamespace(all=lambda: value)
        return SimpleNamespace(scalars=lambda: scalars_ns)


def _make_async_session_ctx(scalars_results):
    """Build an async context manager that yields a fake session.

    scalars_results is a list: each call to session.execute()
    returns the next entry, converted to a result namespace.
    """
    call_index = [0]
    execute_count = [0]

    async def _execute(query):
        idx = call_index[0]
        call_index[0] += 1
        execute_count[0] += 1
        return _make_result_mock(scalars_results[idx])

    session = SimpleNamespace(execute=_execute)

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, execute_count


def _setup_common_mocks(monkeypatch, spellbook_ctx, fractal_ctx,
                         subscriber_count=0, total_dropped_events=0,
                         version="0.30.5", db_size=0, session_files=0,
                         session_files_raises=None):
    """Set up monkeypatch mocks for common dashboard test pattern."""
    import spellbook.admin.routes.dashboard as dashboard_mod

    monkeypatch.setattr(dashboard_mod, "get_spellbook_session", spellbook_ctx)
    monkeypatch.setattr(dashboard_mod, "get_fractal_session", fractal_ctx)

    fake_bus = SimpleNamespace(
        subscriber_count=subscriber_count,
        total_dropped_events=total_dropped_events,
    )
    monkeypatch.setattr(dashboard_mod, "event_bus", fake_bus)

    monkeypatch.setattr(dashboard_mod, "pkg_version", lambda *a, **kw: version)
    monkeypatch.setattr(dashboard_mod, "_get_db_size", lambda *a, **kw: db_size)

    if session_files_raises is not None:
        def _raise_session_files(*a, **kw):
            raise session_files_raises
        monkeypatch.setattr(dashboard_mod, "_count_session_files", _raise_session_files)
    else:
        monkeypatch.setattr(dashboard_mod, "_count_session_files", lambda *a, **kw: session_files)



@pytest.mark.asyncio
async def test_dashboard_data_uses_orm_sessions(monkeypatch):
    """get_dashboard_data uses ORM sessions, not raw SQL query helpers."""
    spellbook_ctx, spellbook_exec_count = _make_async_session_ctx([
        200,            # active memories count
        10,             # security events 24h count
        1,              # open experiments count
        [SimpleNamespace(event_type="canary_check", created_at="2026-03-14T12:00:00Z", detail="Canary verified")],
        [SimpleNamespace(created_at="2026-03-14T11:00:00Z", content="Stored a new memory about testing patterns and conventions")],
    ])

    fractal_ctx, fractal_exec_count = _make_async_session_ctx([4])

    _setup_common_mocks(
        monkeypatch, spellbook_ctx, fractal_ctx,
        subscriber_count=2, total_dropped_events=5,
        db_size=2048, session_files=3,
    )

    from spellbook.admin.routes.dashboard import get_dashboard_data

    result = await get_dashboard_data()

    assert result == {
        "health": {
            "status": "ok",
            "version": "0.30.5",
            "uptime_seconds": result["health"]["uptime_seconds"],  # dynamic
            "db_size_bytes": 2048,
            "event_bus_subscribers": 2,
            "event_bus_dropped_events": 5,
        },
        "counts": {
            "active_sessions": 3,
            "total_memories": 200,
            "security_events_24h": 10,
            "open_experiments": 1,
            "fractal_graphs": 4,
        },
        "recent_activity": [
            {
                "type": "canary_check",
                "timestamp": "2026-03-14T12:00:00Z",
                "summary": "Canary verified",
            },
            {
                "type": "memory_created",
                "timestamp": "2026-03-14T11:00:00Z",
                "summary": "Stored a new memory about testing patterns and conventions",
            },
        ],
    }

    # Verify ORM sessions were actually used (execute was called)
    assert spellbook_exec_count[0] == 5
    assert fractal_exec_count[0] == 1


@pytest.mark.asyncio
async def test_dashboard_data_orm_handles_session_errors(monkeypatch):
    """Dashboard returns safe defaults when ORM sessions raise exceptions."""

    @asynccontextmanager
    async def _failing_session():
        raise Exception("DB locked")
        yield  # pragma: no cover

    _setup_common_mocks(
        monkeypatch, _failing_session, _failing_session,
        session_files_raises=Exception("Filesystem error"),
    )

    from spellbook.admin.routes.dashboard import get_dashboard_data

    result = await get_dashboard_data()

    # All counts should fall back to 0
    assert result["counts"] == {
        "active_sessions": 0,
        "total_memories": 0,
        "security_events_24h": 0,
        "open_experiments": 0,
        "fractal_graphs": 0,
    }
    assert result["recent_activity"] == []

    _assert_common_calls(mocks, session_files_raised=IsInstance(Exception))


@pytest.mark.asyncio
async def test_dashboard_data_orm_memory_content_truncated_to_80_chars(monkeypatch):
    """Recent memories truncate content to 80 characters in the summary."""
    long_content = "A" * 200

    spellbook_ctx, _ = _make_async_session_ctx([
        0, 0, 0,
        [],
        [SimpleNamespace(created_at="2026-03-14T11:00:00Z", content=long_content)],
    ])
    fractal_ctx, _ = _make_async_session_ctx([0])

    _setup_common_mocks(
        monkeypatch, spellbook_ctx, fractal_ctx,
    )

    from spellbook.admin.routes.dashboard import get_dashboard_data

    result = await get_dashboard_data()

    assert len(result["recent_activity"]) == 1
    activity = result["recent_activity"][0]
    assert activity == {
        "type": "memory_created",
        "timestamp": "2026-03-14T11:00:00Z",
        "summary": "A" * 80,
    }

    _assert_common_calls(mocks)


@pytest.mark.asyncio
async def test_dashboard_data_orm_security_event_detail_fallback(monkeypatch):
    """Security events use detail for summary, falling back to event_type."""
    spellbook_ctx, _ = _make_async_session_ctx([
        0, 0, 0,
        [
            SimpleNamespace(event_type="canary_check", created_at="2026-03-14T12:00:00Z", detail="Canary verified"),
            SimpleNamespace(event_type="mode_change", created_at="2026-03-14T11:00:00Z", detail=None),
        ],
        [],
    ])
    fractal_ctx, _ = _make_async_session_ctx([0])

    _setup_common_mocks(
        monkeypatch, spellbook_ctx, fractal_ctx,
    )

    from spellbook.admin.routes.dashboard import get_dashboard_data

    result = await get_dashboard_data()

    assert result["recent_activity"] == [
        {
            "type": "canary_check",
            "timestamp": "2026-03-14T12:00:00Z",
            "summary": "Canary verified",
        },
        {
            "type": "mode_change",
            "timestamp": "2026-03-14T11:00:00Z",
            "summary": "mode_change",
        },
    ]

    _assert_common_calls(mocks)


@pytest.mark.asyncio
async def test_dashboard_data_orm_activity_sorted_by_timestamp_desc(monkeypatch):
    """Recent activity merges security events and memories, sorted desc."""
    spellbook_ctx, _ = _make_async_session_ctx([
        0, 0, 0,
        [SimpleNamespace(event_type="login", created_at="2026-03-14T10:00:00Z", detail="Login event")],
        [SimpleNamespace(created_at="2026-03-14T12:00:00Z", content="Recent memory")],
    ])
    fractal_ctx, _ = _make_async_session_ctx([0])

    _setup_common_mocks(
        monkeypatch, spellbook_ctx, fractal_ctx,
    )

    from spellbook.admin.routes.dashboard import get_dashboard_data

    result = await get_dashboard_data()

    # Memory (newer) should come first
    assert result["recent_activity"] == [
        {
            "type": "memory_created",
            "timestamp": "2026-03-14T12:00:00Z",
            "summary": "Recent memory",
        },
        {
            "type": "login",
            "timestamp": "2026-03-14T10:00:00Z",
            "summary": "Login event",
        },
    ]

    _assert_common_calls(mocks)
