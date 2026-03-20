"""Tests for dashboard ORM migration.

Verifies that get_dashboard_data() uses SQLAlchemy ORM sessions
(get_spellbook_session, get_fractal_session, get_coordination_session)
instead of raw SQL query helpers.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spellbook.db.coordination_models import Swarm
from spellbook.db.fractal_models import FractalGraph
from spellbook.db.spellbook_models import Experiment, Memory, SecurityEvent


@pytest.fixture
def mock_event_bus():
    """Mock the event_bus with subscriber_count and total_dropped_events."""
    bus = MagicMock()
    bus.subscriber_count = 2
    bus.total_dropped_events = 5
    return bus


def _make_async_session_ctx(scalars_results):
    """Build an async context manager that yields a mock session.

    scalars_results is a list of lists: each call to session.execute()
    returns the next entry. For scalar_one() calls (counts), wrap in
    a mock that returns the int. For scalars().all() calls (lists),
    wrap accordingly.
    """
    call_index = [0]

    async def _execute(query):
        idx = call_index[0]
        call_index[0] += 1
        result_mock = MagicMock()
        value = scalars_results[idx]
        if isinstance(value, int):
            # For func.count() -> scalar_one()
            result_mock.scalar_one.return_value = value
        else:
            # For list queries -> scalars().all()
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = value
            result_mock.scalars.return_value = scalars_mock
        return result_mock

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, session


@pytest.mark.asyncio
async def test_dashboard_data_uses_orm_sessions():
    """get_dashboard_data uses ORM sessions, not raw SQL query helpers."""
    # Set up spellbook session: 5 execute calls
    # 1. count active memories -> 200
    # 2. count security events 24h -> 10
    # 3. count running/paused experiments -> 1
    # 4. recent security events (list) -> 1 item
    # 5. recent memories (list) -> 1 item
    sec_event = MagicMock(spec=SecurityEvent)
    sec_event.event_type = "canary_check"
    sec_event.created_at = "2026-03-14T12:00:00Z"
    sec_event.detail = "Canary verified"

    mem = MagicMock(spec=Memory)
    mem.created_at = "2026-03-14T11:00:00Z"
    mem.content = "Stored a new memory about testing patterns and conventions"

    spellbook_ctx, spellbook_session = _make_async_session_ctx([
        200,            # active memories count
        10,             # security events 24h count
        1,              # open experiments count
        [sec_event],    # recent security events
        [mem],          # recent memories
    ])

    # Coordination session: 1 execute call - count running swarms
    coord_ctx, coord_session = _make_async_session_ctx([2])

    # Fractal session: 1 execute call - count graphs
    fractal_ctx, fractal_session = _make_async_session_ctx([4])

    with patch(
        "spellbook.admin.routes.dashboard.get_spellbook_session",
        side_effect=spellbook_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.get_coordination_session",
        side_effect=coord_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.get_fractal_session",
        side_effect=fractal_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.event_bus",
    ) as mock_bus, patch(
        "spellbook.admin.routes.dashboard.pkg_version",
        return_value="0.30.5",
    ), patch(
        "spellbook.admin.routes.dashboard._get_db_size",
        return_value=2048,
    ), patch(
        "spellbook.admin.routes.dashboard._count_session_files",
        return_value=3,
    ):
        mock_bus.subscriber_count = 2
        mock_bus.total_dropped_events = 5

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
            "running_swarms": 2,
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
    assert spellbook_session.execute.call_count == 5
    assert coord_session.execute.call_count == 1
    assert fractal_session.execute.call_count == 1


@pytest.mark.asyncio
async def test_dashboard_data_orm_handles_session_errors():
    """Dashboard returns safe defaults when ORM sessions raise exceptions."""

    @asynccontextmanager
    async def _failing_session():
        raise Exception("DB locked")
        yield  # pragma: no cover

    with patch(
        "spellbook.admin.routes.dashboard.get_spellbook_session",
        side_effect=_failing_session,
    ), patch(
        "spellbook.admin.routes.dashboard.get_coordination_session",
        side_effect=_failing_session,
    ), patch(
        "spellbook.admin.routes.dashboard.get_fractal_session",
        side_effect=_failing_session,
    ), patch(
        "spellbook.admin.routes.dashboard.event_bus",
    ) as mock_bus, patch(
        "spellbook.admin.routes.dashboard.pkg_version",
        return_value="0.30.5",
    ), patch(
        "spellbook.admin.routes.dashboard._get_db_size",
        return_value=0,
    ), patch(
        "spellbook.admin.routes.dashboard._count_session_files",
        side_effect=Exception("Filesystem error"),
    ):
        mock_bus.subscriber_count = 0
        mock_bus.total_dropped_events = 0

        from spellbook.admin.routes.dashboard import get_dashboard_data

        result = await get_dashboard_data()

    # All counts should fall back to 0
    assert result["counts"] == {
        "active_sessions": 0,
        "total_memories": 0,
        "security_events_24h": 0,
        "running_swarms": 0,
        "open_experiments": 0,
        "fractal_graphs": 0,
    }
    assert result["recent_activity"] == []


@pytest.mark.asyncio
async def test_dashboard_data_orm_memory_content_truncated_to_80_chars():
    """Recent memories truncate content to 80 characters in the summary."""
    long_content = "A" * 200

    mem = MagicMock(spec=Memory)
    mem.created_at = "2026-03-14T11:00:00Z"
    mem.content = long_content

    spellbook_ctx, _ = _make_async_session_ctx([
        0,          # active memories count
        0,          # security events 24h count
        0,          # open experiments count
        [],         # recent security events
        [mem],      # recent memories with long content
    ])

    coord_ctx, _ = _make_async_session_ctx([0])
    fractal_ctx, _ = _make_async_session_ctx([0])

    with patch(
        "spellbook.admin.routes.dashboard.get_spellbook_session",
        side_effect=spellbook_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.get_coordination_session",
        side_effect=coord_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.get_fractal_session",
        side_effect=fractal_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.event_bus",
    ) as mock_bus, patch(
        "spellbook.admin.routes.dashboard.pkg_version",
        return_value="0.30.5",
    ), patch(
        "spellbook.admin.routes.dashboard._get_db_size",
        return_value=0,
    ), patch(
        "spellbook.admin.routes.dashboard._count_session_files",
        return_value=0,
    ):
        mock_bus.subscriber_count = 0
        mock_bus.total_dropped_events = 0

        from spellbook.admin.routes.dashboard import get_dashboard_data

        result = await get_dashboard_data()

    assert len(result["recent_activity"]) == 1
    activity = result["recent_activity"][0]
    assert activity == {
        "type": "memory_created",
        "timestamp": "2026-03-14T11:00:00Z",
        "summary": "A" * 80,
    }


@pytest.mark.asyncio
async def test_dashboard_data_orm_security_event_detail_fallback():
    """Security events use detail for summary, falling back to event_type."""
    # Event with detail
    ev_with_detail = MagicMock(spec=SecurityEvent)
    ev_with_detail.event_type = "canary_check"
    ev_with_detail.created_at = "2026-03-14T12:00:00Z"
    ev_with_detail.detail = "Canary verified"

    # Event without detail (None)
    ev_without_detail = MagicMock(spec=SecurityEvent)
    ev_without_detail.event_type = "mode_change"
    ev_without_detail.created_at = "2026-03-14T11:00:00Z"
    ev_without_detail.detail = None

    spellbook_ctx, _ = _make_async_session_ctx([
        0,  # active memories count
        0,  # security events 24h count
        0,  # open experiments count
        [ev_with_detail, ev_without_detail],  # recent security events
        [],  # recent memories
    ])

    coord_ctx, _ = _make_async_session_ctx([0])
    fractal_ctx, _ = _make_async_session_ctx([0])

    with patch(
        "spellbook.admin.routes.dashboard.get_spellbook_session",
        side_effect=spellbook_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.get_coordination_session",
        side_effect=coord_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.get_fractal_session",
        side_effect=fractal_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.event_bus",
    ) as mock_bus, patch(
        "spellbook.admin.routes.dashboard.pkg_version",
        return_value="0.30.5",
    ), patch(
        "spellbook.admin.routes.dashboard._get_db_size",
        return_value=0,
    ), patch(
        "spellbook.admin.routes.dashboard._count_session_files",
        return_value=0,
    ):
        mock_bus.subscriber_count = 0
        mock_bus.total_dropped_events = 0

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


@pytest.mark.asyncio
async def test_dashboard_data_orm_activity_sorted_by_timestamp_desc():
    """Recent activity merges security events and memories, sorted desc."""
    # Older security event
    sec_event = MagicMock(spec=SecurityEvent)
    sec_event.event_type = "login"
    sec_event.created_at = "2026-03-14T10:00:00Z"
    sec_event.detail = "Login event"

    # Newer memory
    mem = MagicMock(spec=Memory)
    mem.created_at = "2026-03-14T12:00:00Z"
    mem.content = "Recent memory"

    spellbook_ctx, _ = _make_async_session_ctx([
        0,            # active memories count
        0,            # security events 24h count
        0,            # open experiments count
        [sec_event],  # recent security events (older)
        [mem],        # recent memories (newer)
    ])

    coord_ctx, _ = _make_async_session_ctx([0])
    fractal_ctx, _ = _make_async_session_ctx([0])

    with patch(
        "spellbook.admin.routes.dashboard.get_spellbook_session",
        side_effect=spellbook_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.get_coordination_session",
        side_effect=coord_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.get_fractal_session",
        side_effect=fractal_ctx,
    ), patch(
        "spellbook.admin.routes.dashboard.event_bus",
    ) as mock_bus, patch(
        "spellbook.admin.routes.dashboard.pkg_version",
        return_value="0.30.5",
    ), patch(
        "spellbook.admin.routes.dashboard._get_db_size",
        return_value=0,
    ), patch(
        "spellbook.admin.routes.dashboard._count_session_files",
        return_value=0,
    ):
        mock_bus.subscriber_count = 0
        mock_bus.total_dropped_events = 0

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
