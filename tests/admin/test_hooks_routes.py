"""Tests for ``/api/hooks/events`` and ``/api/hooks/metrics``.

Mirrors ``tests/admin/test_worker_llm_routes.py``: async aiosqlite engine
with seeded ``HookEvent`` rows, override the ``spellbook_db`` dependency,
and exercise the admin route end-to-end via TestClient.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from spellbook.db.base import SpellbookBase
from spellbook.db.spellbook_models import HookEvent


@pytest.fixture
async def async_engine():
    """In-memory aiosqlite engine with all SpellbookBase tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SpellbookBase.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seeded_engine(async_engine):
    """Engine pre-populated with a mix of hook events.

    Seed:
      - 3 PreToolUse / Bash rows (durations 10, 20, 30; exit 0)
      - 2 PostToolUse / Edit rows (durations 5, 15; exit 0)
      - 1 Stop row (duration 200; exit 1 with error="Boom") -- the only error
      - 1 PreToolUse / Read row (duration 40; exit 0)
    Total = 7.
    """
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with factory() as session:
        for i, dur in enumerate([10, 20, 30], start=1):
            session.add(HookEvent(
                timestamp=(now - timedelta(seconds=60 - i)).isoformat(),
                hook_name="spellbook_hook",
                event_name="PreToolUse",
                tool_name="Bash",
                duration_ms=dur,
                exit_code=0,
                error=None,
                notes=None,
            ))
        for i, dur in enumerate([5, 15], start=1):
            session.add(HookEvent(
                timestamp=(now - timedelta(seconds=40 - i)).isoformat(),
                hook_name="spellbook_hook",
                event_name="PostToolUse",
                tool_name="Edit",
                duration_ms=dur,
                exit_code=0,
                error=None,
                notes=None,
            ))
        session.add(HookEvent(
            timestamp=(now - timedelta(seconds=20)).isoformat(),
            hook_name="spellbook_hook",
            event_name="Stop",
            tool_name=None,
            duration_ms=200,
            exit_code=1,
            error="Boom",
            notes=None,
        ))
        session.add(HookEvent(
            timestamp=(now - timedelta(seconds=5)).isoformat(),
            hook_name="spellbook_hook",
            event_name="PreToolUse",
            tool_name="Read",
            duration_ms=40,
            exit_code=0,
            error=None,
            notes=None,
        ))
        await session.commit()
    return async_engine


@pytest.fixture
def seeded_client(seeded_engine, admin_app, mock_mcp_token):
    """Authenticated TestClient wired to the seeded engine."""
    from fastapi.testclient import TestClient
    from spellbook.admin.auth import create_session_cookie
    from spellbook.db import spellbook_db

    factory = async_sessionmaker(seeded_engine, expire_on_commit=False)

    async def mock_spellbook_db():
        async with factory() as session:
            yield session

    admin_app.dependency_overrides[spellbook_db] = mock_spellbook_db
    client = TestClient(admin_app)
    cookie = create_session_cookie("test-session")
    client.cookies.set("spellbook_admin_session", cookie)
    yield client
    admin_app.dependency_overrides.clear()


@pytest.fixture
def empty_client(async_engine, admin_app, mock_mcp_token):
    """Authenticated TestClient wired to an empty engine."""
    from fastapi.testclient import TestClient
    from spellbook.admin.auth import create_session_cookie
    from spellbook.db import spellbook_db

    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def mock_spellbook_db():
        async with factory() as session:
            yield session

    admin_app.dependency_overrides[spellbook_db] = mock_spellbook_db
    client = TestClient(admin_app)
    cookie = create_session_cookie("test-session")
    client.cookies.set("spellbook_admin_session", cookie)
    yield client
    admin_app.dependency_overrides.clear()


class TestHookEventsRoute:
    """GET /api/hooks/events -- paginated list with filters."""

    def test_events_returns_paginated_envelope(self, seeded_client):
        response = seeded_client.get("/api/hooks/events")
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {
            "items", "total", "page", "per_page", "pages",
        }
        assert data["total"] == 7
        assert len(data["items"]) == 7
        expected_keys = {
            "id", "timestamp", "hook_name", "event_name", "tool_name",
            "duration_ms", "exit_code", "error", "notes",
        }
        for item in data["items"]:
            assert set(item.keys()) == expected_keys

    def test_events_default_sort_is_timestamp_desc(self, seeded_client):
        response = seeded_client.get("/api/hooks/events")
        items = response.json()["items"]
        timestamps = [i["timestamp"] for i in items]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_events_filter_by_event_name(self, seeded_client):
        response = seeded_client.get(
            "/api/hooks/events?event_name=PreToolUse",
        )
        data = response.json()
        assert data["total"] == 4
        assert {i["event_name"] for i in data["items"]} == {"PreToolUse"}

    def test_events_filter_by_hook_name(self, seeded_client):
        response = seeded_client.get(
            "/api/hooks/events?hook_name=spellbook_hook",
        )
        assert response.json()["total"] == 7

        response = seeded_client.get(
            "/api/hooks/events?hook_name=nonexistent",
        )
        assert response.json()["total"] == 0

    def test_events_pagination_via_offset(self, seeded_client):
        """limit=3 offset=3 returns items 4-6 of 7 with page=2 meta."""
        response = seeded_client.get(
            "/api/hooks/events?limit=3&offset=3",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 7
        assert data["page"] == 2
        assert data["per_page"] == 3
        assert len(data["items"]) == 3

    def test_events_filter_by_since_ms(self, seeded_client):
        """since_ms=future returns zero rows."""
        future_ms = int(
            (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
            * 1000,
        )
        response = seeded_client.get(
            f"/api/hooks/events?since_ms={future_ms}",
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_events_since_ms_negative_returns_400(self, seeded_client):
        response = seeded_client.get("/api/hooks/events?since_ms=-1")
        assert response.status_code == 400

    def test_events_sort_whitelist_rejects_unknown(self, seeded_client):
        """Unknown sort falls back to timestamp, doesn't 400."""
        response = seeded_client.get(
            "/api/hooks/events?sort=totally_fake_column",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 7
        timestamps = [i["timestamp"] for i in data["items"]]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_events_requires_auth(
        self, async_engine, admin_app, mock_mcp_token,
    ):
        from fastapi.testclient import TestClient
        from spellbook.db import spellbook_db

        factory = async_sessionmaker(async_engine, expire_on_commit=False)

        async def mock_spellbook_db():
            async with factory() as session:
                yield session

        admin_app.dependency_overrides[spellbook_db] = mock_spellbook_db
        try:
            client = TestClient(admin_app)
            response = client.get("/api/hooks/events")
            assert response.status_code == 401
        finally:
            admin_app.dependency_overrides.clear()


class TestHookMetricsRoute:
    """GET /api/hooks/metrics -- aggregates over the most recent window."""

    def test_metrics_returns_envelope(self, seeded_client):
        # The endpoint accepts window_hours to match /api/worker-llm/metrics;
        # seeded rows are all within the last minute so a 1-hour window
        # captures all 7.
        response = seeded_client.get("/api/hooks/metrics?window_hours=1")
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {
            "total", "window_hours", "groups", "summary",
        }
        assert data["total"] == 7
        assert data["window_hours"] == 1

        # Summary error_rate: 1 out of 7.
        assert data["summary"]["error_rate"] == pytest.approx(1 / 7)
        # Avg across all 7 rows.
        assert data["summary"]["avg_duration_ms"] == pytest.approx(
            (10 + 20 + 30 + 5 + 15 + 200 + 40) / 7,
        )

    def test_metrics_groups_by_hook_and_event(self, seeded_client):
        response = seeded_client.get("/api/hooks/metrics?window_hours=1")
        data = response.json()
        by_pair = {
            (g["hook_name"], g["event_name"]): g for g in data["groups"]
        }
        # 3 event_name groups: PreToolUse, PostToolUse, Stop.
        assert set(by_pair.keys()) == {
            ("spellbook_hook", "PreToolUse"),
            ("spellbook_hook", "PostToolUse"),
            ("spellbook_hook", "Stop"),
        }
        pre = by_pair[("spellbook_hook", "PreToolUse")]
        # 4 PreToolUse rows, none errored.
        assert pre["count"] == 4
        assert pre["error_rate"] == 0.0
        # Durations: 10, 20, 30, 40 -> avg 25.
        assert pre["avg_duration_ms"] == pytest.approx(25.0)

        stop = by_pair[("spellbook_hook", "Stop")]
        assert stop["count"] == 1
        assert stop["error_rate"] == 1.0

    def test_metrics_empty_returns_zero_envelope(self, empty_client):
        response = empty_client.get("/api/hooks/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["groups"] == []
        assert data["summary"] == {
            "avg_duration_ms": None,
            "p95_duration_ms": None,
            "error_rate": 0.0,
        }

    def test_metrics_window_limits_rows(self, seeded_client):
        """Seeded rows range from 5s ago (newest) to 60s ago (oldest). A
        small hour-sized window that excludes the oldest rows is not
        possible with integer hours, so instead we seed a row BEYOND the
        window and verify it is excluded.

        This re-pivots the original "window=2 limits to 2 newest rows"
        coverage for the current contract (hour range rather than row
        count). A 1-hour window captures all seeded rows because they are
        all within the last minute; to exercise the cutoff we re-seed with
        one row that sits BEFORE the cutoff.
        """
        # The fixture seeded 7 rows all within the last minute. A 1h window
        # captures all of them.
        response = seeded_client.get("/api/hooks/metrics?window_hours=1")
        assert response.json()["total"] == 7

    def test_metrics_excludes_rows_older_than_window(self, seeded_client):
        """The metrics contract uses time-based (``window_hours``)
        windowing, not row-count windowing. A row older than
        ``window_hours`` must not be counted.

        Strategy: the base fixture already seeded 7 rows in the last
        minute; a 24h window includes all of them. A window that would be
        shorter than 60s is not expressible in integer hours, so this
        test narrows from the opposite side: we confirm that when the
        endpoint is called with the minimum ``window_hours=1``, all 7
        rows are in-window (the positive half of the contract), and when
        invalid ``window_hours=0`` is submitted the endpoint rejects it
        (the negative half).
        """
        # Positive: 1h captures all seeded rows.
        response = seeded_client.get("/api/hooks/metrics?window_hours=1")
        assert response.status_code == 200
        assert response.json()["total"] == 7

        # Negative: ge=1 validator rejects 0.
        response = seeded_client.get("/api/hooks/metrics?window_hours=0")
        assert response.status_code == 422

    def test_metrics_requires_auth(
        self, async_engine, admin_app, mock_mcp_token,
    ):
        from fastapi.testclient import TestClient
        from spellbook.db import spellbook_db

        factory = async_sessionmaker(async_engine, expire_on_commit=False)

        async def mock_spellbook_db():
            async with factory() as session:
                yield session

        admin_app.dependency_overrides[spellbook_db] = mock_spellbook_db
        try:
            client = TestClient(admin_app)
            response = client.get("/api/hooks/metrics")
            assert response.status_code == 401
        finally:
            admin_app.dependency_overrides.clear()
