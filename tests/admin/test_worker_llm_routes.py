"""Tests for ``/api/worker-llm/calls`` and ``/api/worker-llm/metrics``.

Strategy
--------
Per the impl plan (Step 12), these tests use the existing async-SQLite engine
override pattern (see ``tests/admin/test_focus_routes.py``): create an
in-memory aiosqlite engine with ``StintStack`` + ``WorkerLLMCall`` tables,
seed rows via a sessionmaker, then override the ``spellbook_db`` FastAPI
dependency so the route queries hit the seeded engine instead of the real
``~/.local/spellbook/spellbook.db``.

This is the established DB-route test idiom in this repo (not
``bigfoot.db_mock``). The plan explicitly permits it: "For DB tests, use the
existing pattern (tmp-file SQLite fixture + override
``get_spellbook_sync_session``). Look at ``tests/test_worker_llm/
test_observability.py`` fresh_db fixture for precedent." — the routes here
are async and use the ASYNC ``spellbook_db`` dependency, so the async-engine
analog of that fixture is what we seed.

Auth: the ``client`` fixture from ``tests/admin/conftest.py`` already sets a
signed session cookie; the ``unauthenticated_client`` fixture doesn't.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from spellbook.db.base import SpellbookBase
from spellbook.db.spellbook_models import WorkerLLMCall


def _ts(offset_seconds: int = 0) -> str:
    """ISO-8601 UTC timestamp offset from now (seconds)."""
    return (
        datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    ).isoformat()


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
    """Engine pre-populated with a mix of call outcomes for metrics tests.

    Rows: 5 success (latencies 10, 20, 30, 40, 50), 2 error (rate_limit,
    rate_limit), 1 timeout, 1 fail_open — 9 total, all timestamped "now"
    so they fall inside the default 24h window.
    """
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with factory() as session:
        # 5 successes with varied latencies
        for i, lat in enumerate([10, 20, 30, 40, 50], start=1):
            session.add(WorkerLLMCall(
                timestamp=(now - timedelta(seconds=60 - i)).isoformat(),
                task="tool_safety",
                model="gpt-test",
                status="success",
                latency_ms=lat,
                prompt_len=100,
                response_len=200,
                error=None,
                override_loaded=0,
            ))
        # 2 errors with same error string -> Counter groups them
        for i in range(2):
            session.add(WorkerLLMCall(
                timestamp=(now - timedelta(seconds=30 - i)).isoformat(),
                task="safety",
                model="gpt-test",
                status="error",
                latency_ms=0,
                prompt_len=50,
                response_len=0,
                error="rate_limit",
                override_loaded=0,
            ))
        # 1 timeout
        session.add(WorkerLLMCall(
            timestamp=(now - timedelta(seconds=20)).isoformat(),
            task="tool_safety",
            model="gpt-test",
            status="timeout",
            latency_ms=5000,
            prompt_len=50,
            response_len=0,
            error="deadline_exceeded",
            override_loaded=0,
        ))
        # 1 fail_open
        session.add(WorkerLLMCall(
            timestamp=(now - timedelta(seconds=10)).isoformat(),
            task="tool_safety",
            model="",
            status="fail_open",
            latency_ms=0,
            prompt_len=0,
            response_len=0,
            error="prompt_load_error: missing.md",
            override_loaded=0,
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


class TestWorkerLLMCallsRoute:
    """GET /api/worker-llm/calls -- paginated list with filters."""

    def test_calls_returns_paginated_envelope(self, seeded_client):
        """T13: response matches build_list_response envelope; rows present.

        ESCAPE: test_calls_returns_paginated_envelope
          CLAIM:    /calls returns {items, total, page, per_page, pages}
                    with 9 seeded rows.
          PATH:     route -> select(WorkerLLMCall) -> count -> paginate ->
                    build_list_response.
          CHECK:    Exact envelope keys + counts; each item is a full to_dict().
          MUTATION: If the route returned rows but omitted `total`, the
                    ``total == 9`` check fails. If it hard-coded a wrapper
                    key (e.g. `"calls"`), the items key check fails.
                    If to_dict dropped a column, the row-shape assertion
                    on the first item's keys fails.
          ESCAPE:   A route that forgot the envelope entirely (e.g. returned
                    a bare list) would fail the dict-shape check.
          IMPACT:   Frontend tables would mis-render or break entirely.
        """
        response = seeded_client.get("/api/worker-llm/calls")
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {"items", "total", "page", "per_page", "pages"}
        assert data["total"] == 9
        assert data["page"] == 1
        assert data["per_page"] == 50
        assert data["pages"] == 1
        assert len(data["items"]) == 9
        # Every returned row exposes the full to_dict shape.
        expected_keys = {
            "id", "timestamp", "task", "model", "status", "latency_ms",
            "prompt_len", "response_len", "error", "override_loaded",
        }
        for item in data["items"]:
            assert set(item.keys()) == expected_keys

    def test_calls_default_sort_is_timestamp_desc(self, seeded_client):
        """Default sort is timestamp DESC (most recent first)."""
        response = seeded_client.get("/api/worker-llm/calls")
        assert response.status_code == 200
        items = response.json()["items"]
        timestamps = [i["timestamp"] for i in items]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_calls_filter_by_task(self, seeded_client):
        """T14 (task filter): only rows with task='safety' (2 errors)."""
        response = seeded_client.get("/api/worker-llm/calls?task=safety")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert {item["task"] for item in data["items"]} == {"safety"}

    def test_calls_filter_by_status(self, seeded_client):
        """T14 (status filter): only rows with status='error' (2 rows)."""
        response = seeded_client.get("/api/worker-llm/calls?status=error")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert {item["status"] for item in data["items"]} == {"error"}

    def test_calls_filter_by_task_and_status(self, seeded_client):
        """Combined filter: task=tool_safety AND status=timeout (1 row)."""
        response = seeded_client.get(
            "/api/worker-llm/calls?task=tool_safety&status=timeout"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["task"] == "tool_safety"
        assert data["items"][0]["status"] == "timeout"

    def test_calls_filter_by_since(self, seeded_client):
        """since=future-timestamp returns zero rows.

        Uses httpx ``params`` (not an f-string) so the ``+`` in the
        ``+00:00`` TZ offset gets URL-encoded to ``%2B``; inlining the
        ISO string via an f-string would let the ``+`` be interpreted as
        a space on the server and crash ``datetime.fromisoformat``.
        """
        future = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat()
        response = seeded_client.get(
            "/api/worker-llm/calls", params={"since": future},
        )
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "items": [],
            "total": 0,
            "page": 1,
            "per_page": 50,
            "pages": 1,
        }

    def test_calls_since_invalid_returns_400(self, seeded_client):
        """T16b: non-ISO `since` -> 400 with 'invalid `since`' message."""
        response = seeded_client.get(
            "/api/worker-llm/calls?since=not-an-iso-date"
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "invalid `since`" in detail
        assert "not-an-iso-date" in detail

    def test_calls_pagination(self, seeded_client):
        """per_page=3, page=2 returns items 4-6 of 9 with correct meta."""
        response = seeded_client.get(
            "/api/worker-llm/calls?per_page=3&page=2"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 9
        assert data["page"] == 2
        assert data["per_page"] == 3
        assert data["pages"] == 3
        assert len(data["items"]) == 3

    def test_calls_per_page_cap_enforced(self, seeded_client):
        """per_page=10000 -> 422 (FastAPI validator caps at 200)."""
        response = seeded_client.get(
            "/api/worker-llm/calls?per_page=10000"
        )
        assert response.status_code == 422

    def test_calls_sort_by_latency_asc(self, seeded_client):
        """Sort by latency_ms ascending orders rows by latency low->high."""
        response = seeded_client.get(
            "/api/worker-llm/calls?sort=latency_ms&order=asc"
        )
        assert response.status_code == 200
        latencies = [i["latency_ms"] for i in response.json()["items"]]
        assert latencies == sorted(latencies)

    def test_calls_sort_whitelist_rejects_unknown_column(self, seeded_client):
        """Unknown sort column silently falls back to default 'timestamp'.

        Plan §5: whitelist against the 10 WorkerLLMCall columns; default
        'timestamp'. The route does NOT 400 on unknown sort — it falls back.
        """
        response = seeded_client.get(
            "/api/worker-llm/calls?sort=totally_fake_column"
        )
        assert response.status_code == 200
        # Falls back to timestamp DESC, so the response is well-formed.
        data = response.json()
        assert data["total"] == 9
        timestamps = [i["timestamp"] for i in data["items"]]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_calls_requires_auth(self, async_engine, admin_app, mock_mcp_token):
        """Unauthenticated request returns 401."""
        from fastapi.testclient import TestClient
        from spellbook.db import spellbook_db

        factory = async_sessionmaker(async_engine, expire_on_commit=False)

        async def mock_spellbook_db():
            async with factory() as session:
                yield session

        admin_app.dependency_overrides[spellbook_db] = mock_spellbook_db
        try:
            client = TestClient(admin_app)
            # No session cookie set.
            response = client.get("/api/worker-llm/calls")
            assert response.status_code == 401
        finally:
            admin_app.dependency_overrides.clear()


class TestWorkerLLMMetricsRoute:
    """GET /api/worker-llm/metrics -- aggregate metrics over a window."""

    def test_metrics_returns_six_key_shape(self, seeded_client):
        """T15: 6-key response shape with expected values from seed mix.

        Seed mix within the 24h window:
          - 5 successes (latencies 10, 20, 30, 40, 50)
          - 2 errors (error='rate_limit')
          - 1 timeout (error='deadline_exceeded')
          - 1 fail_open (error='prompt_load_error: missing.md')
        Total = 9; successes = 5; success_rate = 5/9.

        ESCAPE: test_metrics_returns_six_key_shape
          CLAIM:    /metrics returns the documented 6-key shape with
                    correctly computed success_rate, percentiles, and a
                    Counter-based error_breakdown.
          PATH:     route -> SELECT rows in window -> count successes ->
                    sort success latencies -> statistics.quantiles ->
                    Counter(errors).most_common(10).
          CHECK:    Exact key set; total_calls == 9; success_rate == 5/9;
                    p95/p99 non-null ints; error_breakdown has the 3
                    expected buckets with the right counts.
          MUTATION: If the route counted 'timeout' as a success, success_rate
                    would jump above 5/9 — caught. If it swapped p95 and p99
                    by index, we can't catch with 5 samples — but we DO catch
                    both being null (would happen if the percentile helper
                    short-circuited on small samples). If error_breakdown
                    included 'success' keys (i.e., grouped ALL rows, not
                    just non-success), the rate_limit count would be 2 and
                    additional 'None' entries would appear — caught by
                    exact-dict assertion on error_breakdown.
          ESCAPE:   An implementation that reported success_rate on a count
                    of ALL rows (including failures) would still produce
                    5/9 — same expected value. That shared value is a known
                    weak spot; the per-status breakdown assertion is what
                    differentiates the two implementations.
          IMPACT:   Operator dashboard would silently mis-report health.
        """
        response = seeded_client.get("/api/worker-llm/metrics?window_hours=24")
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) == {
            "success_rate", "p95_latency_ms", "p99_latency_ms",
            "error_breakdown", "total_calls", "window_hours",
        }
        assert data["total_calls"] == 9
        assert data["window_hours"] == 24
        assert data["success_rate"] == pytest.approx(5 / 9)
        # With 5 latencies {10,20,30,40,50}, statistics.quantiles(n=100,
        # method='inclusive') interpolates. Both p95 and p99 land near the
        # top of the distribution; assert they are integers inside the
        # observed range.
        assert isinstance(data["p95_latency_ms"], int)
        assert isinstance(data["p99_latency_ms"], int)
        assert 40 <= data["p95_latency_ms"] <= 50
        assert 40 <= data["p99_latency_ms"] <= 50
        assert data["p99_latency_ms"] >= data["p95_latency_ms"]
        # 4 non-success rows total: 2x rate_limit, 1x deadline_exceeded,
        # 1x prompt_load_error. dict preserves Counter.most_common order.
        assert data["error_breakdown"] == {
            "rate_limit": 2,
            "deadline_exceeded": 1,
            "prompt_load_error: missing.md": 1,
        }

    def test_metrics_empty_window_returns_nulls(self, empty_client):
        """T16: zero rows -> success_rate/p95/p99 null, empty breakdown.

        ESCAPE: test_metrics_empty_window_returns_nulls
          CLAIM:    Empty window returns the documented null-shape envelope.
          PATH:     route -> SELECT returns 0 rows -> early return branch.
          CHECK:    Full-dict equality.
          MUTATION: If the empty branch returned success_rate=0.0 (not None),
                    the equality check fails. If it raised ZeroDivisionError
                    (no early return), status would be 500.
          ESCAPE:   An impl that returned success_rate=None but computed
                    percentiles on an empty list would crash — caught.
          IMPACT:   Frontend needs null to render "—" vs "0%".
        """
        response = empty_client.get("/api/worker-llm/metrics?window_hours=24")
        assert response.status_code == 200
        assert response.json() == {
            "success_rate": None,
            "p95_latency_ms": None,
            "p99_latency_ms": None,
            "error_breakdown": {},
            "total_calls": 0,
            "window_hours": 24,
        }

    def test_metrics_excludes_rows_outside_window(
        self, async_engine, admin_app, mock_mcp_token,
    ):
        """window_hours=1 excludes rows timestamped 25h ago.

        ESCAPE: test_metrics_excludes_rows_outside_window
          CLAIM:    Rows older than `window_hours` are excluded from metrics.
          PATH:     route -> cutoff = now - window -> WHERE timestamp >= cutoff.
          CHECK:    Seed 1 row at now-25h, 0 rows in last hour -> total=0.
          MUTATION: If the route ignored the cutoff, total would be 1 —
                    caught. If the cutoff comparator were inverted (<= now -
                    window), total could be 1 — caught.
          ESCAPE:   An impl that compared cutoff against a stale cached "now"
                    would still pass if the test runs fast enough; the 25h
                    offset is large enough to make that cache irrelevant.
          IMPACT:   Operator would see stale values from outside the window.
        """
        from fastapi.testclient import TestClient
        from spellbook.admin.auth import create_session_cookie
        from spellbook.db import spellbook_db

        factory = async_sessionmaker(async_engine, expire_on_commit=False)
        old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()

        async def seed_and_override():
            async with factory() as session:
                session.add(WorkerLLMCall(
                    timestamp=old,
                    task="t",
                    model="m",
                    status="success",
                    latency_ms=10,
                    prompt_len=0,
                    response_len=0,
                    error=None,
                    override_loaded=0,
                ))
                await session.commit()

        import asyncio
        asyncio.get_event_loop().run_until_complete(seed_and_override())

        async def mock_spellbook_db():
            async with factory() as session:
                yield session

        admin_app.dependency_overrides[spellbook_db] = mock_spellbook_db
        try:
            client = TestClient(admin_app)
            cookie = create_session_cookie("test-session")
            client.cookies.set("spellbook_admin_session", cookie)
            response = client.get("/api/worker-llm/metrics?window_hours=1")
            assert response.status_code == 200
            assert response.json() == {
                "success_rate": None,
                "p95_latency_ms": None,
                "p99_latency_ms": None,
                "error_breakdown": {},
                "total_calls": 0,
                "window_hours": 1,
            }
        finally:
            admin_app.dependency_overrides.clear()

    def test_metrics_requires_auth(
        self, async_engine, admin_app, mock_mcp_token,
    ):
        """Unauthenticated request returns 401."""
        from fastapi.testclient import TestClient
        from spellbook.db import spellbook_db

        factory = async_sessionmaker(async_engine, expire_on_commit=False)

        async def mock_spellbook_db():
            async with factory() as session:
                yield session

        admin_app.dependency_overrides[spellbook_db] = mock_spellbook_db
        try:
            client = TestClient(admin_app)
            response = client.get("/api/worker-llm/metrics")
            assert response.status_code == 401
        finally:
            admin_app.dependency_overrides.clear()
