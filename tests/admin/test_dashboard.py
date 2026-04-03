"""Tests for the dashboard API endpoint."""

from contextlib import asynccontextmanager
from dataclasses import dataclass



def _async_return(value):
    """Return an async function that returns value (for mocking async callables)."""
    async def _fn(*args, **kwargs):
        return value
    return _fn


def test_dashboard_returns_200(client, monkeypatch):
    """Dashboard endpoint returns health, counts, and activity."""
    dashboard_data = {
        "health": {
            "status": "ok",
            "version": "0.30.5",
            "uptime_seconds": 100.0,
            "db_size_bytes": 1024,
            "event_bus_subscribers": 0,
            "event_bus_dropped_events": 0,
        },
        "counts": {
            "active_sessions": 1,
            "total_memories": 100,
            "security_events_24h": 5,
            "running_swarms": 0,
            "open_experiments": 1,
            "fractal_graphs": 2,
        },
        "recent_activity": [
            {
                "type": "security_event",
                "timestamp": "2026-03-14T10:00:00Z",
                "summary": "Login from new IP",
            },
        ],
    }
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.get_dashboard_data",
        _async_return(dashboard_data),
    )

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert "health" in data
    assert "counts" in data
    assert "recent_activity" in data
    assert data["health"]["status"] == "ok"
    assert data["health"]["version"] == "0.30.5"
    assert data["health"]["uptime_seconds"] == 100.0
    assert data["health"]["db_size_bytes"] == 1024
    assert data["health"]["event_bus_subscribers"] == 0
    assert data["health"]["event_bus_dropped_events"] == 0
    assert data["counts"]["active_sessions"] == 1
    assert data["counts"]["total_memories"] == 100
    assert data["counts"]["security_events_24h"] == 5
    assert data["counts"]["running_swarms"] == 0
    assert data["counts"]["open_experiments"] == 1
    assert data["counts"]["fractal_graphs"] == 2
    assert len(data["recent_activity"]) == 1
    assert data["recent_activity"][0]["type"] == "security_event"
    assert data["recent_activity"][0]["summary"] == "Login from new IP"


def test_dashboard_requires_auth(unauthenticated_client):
    """Dashboard endpoint returns 401 without authentication."""
    response = unauthenticated_client.get("/api/dashboard")
    assert response.status_code == 401


def test_dashboard_response_schema(client, monkeypatch):
    """DashboardResponse schema validates all required fields and types."""
    dashboard_data = {
        "health": {
            "status": "degraded",
            "version": "0.30.5",
            "uptime_seconds": 0.0,
            "db_size_bytes": 0,
            "event_bus_subscribers": 3,
            "event_bus_dropped_events": 12,
        },
        "counts": {
            "active_sessions": 0,
            "total_memories": 0,
            "security_events_24h": 0,
            "running_swarms": 0,
            "open_experiments": 0,
            "fractal_graphs": 0,
        },
        "recent_activity": [],
    }
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.get_dashboard_data",
        _async_return(dashboard_data),
    )

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    data = response.json()

    # Verify health fields and types
    health = data["health"]
    assert isinstance(health["status"], str)
    assert isinstance(health["version"], str)
    assert isinstance(health["uptime_seconds"], (int, float))
    assert isinstance(health["db_size_bytes"], int)
    assert isinstance(health["event_bus_subscribers"], int)
    assert isinstance(health["event_bus_dropped_events"], int)

    # Verify counts fields and types
    counts = data["counts"]
    assert isinstance(counts["active_sessions"], int)
    assert isinstance(counts["total_memories"], int)
    assert isinstance(counts["security_events_24h"], int)
    assert isinstance(counts["running_swarms"], int)
    assert isinstance(counts["open_experiments"], int)
    assert isinstance(counts["fractal_graphs"], int)

    # Verify activity is a list
    assert isinstance(data["recent_activity"], list)


@dataclass
class _FakeEventBus:
    """Lightweight stand-in for event_bus with the attributes the dashboard reads."""
    subscriber_count: int = 0
    total_dropped_events: int = 0


class _FakeResult:
    """Minimal stand-in for an ORM execute() result."""

    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


def _make_orm_session_ctx(scalars_results):
    """Build an async context manager that yields a fake ORM session.

    scalars_results: list where each entry is either an int (for scalar_one)
    or a list (for scalars().all()). Each session.execute() call consumes
    the next entry.
    """
    call_index = [0]
    execute_count = [0]

    async def _execute(query):
        idx = call_index[0]
        call_index[0] += 1
        execute_count[0] += 1
        return _FakeResult(scalars_results[idx])

    class _FakeSession:
        async def execute(self, query):
            return await _execute(query)

        async def commit(self):
            pass

        async def rollback(self):
            pass

        async def close(self):
            pass

    session = _FakeSession()

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, execute_count


def test_dashboard_cross_db_aggregation(client, monkeypatch):
    """get_dashboard_data queries all databases in parallel via ORM sessions."""

    @dataclass
    class _FakeSecurityEvent:
        event_type: str = "canary_check"
        created_at: str = "2026-03-14T12:00:00Z"
        detail: str = "Canary verified"

    @dataclass
    class _FakeMemory:
        created_at: str = "2026-03-14T11:00:00Z"
        content: str = "Stored a new memory about testing"

    spellbook_ctx, spellbook_exec_count = _make_orm_session_ctx([
        200,                       # active memories count
        10,                        # security events 24h count
        1,                         # open experiments count
        [_FakeSecurityEvent()],    # recent security events
        [_FakeMemory()],           # recent memories
    ])
    coord_ctx, coord_exec_count = _make_orm_session_ctx([2])
    fractal_ctx, fractal_exec_count = _make_orm_session_ctx([4])

    fake_bus = _FakeEventBus(subscriber_count=2, total_dropped_events=5)
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.event_bus", fake_bus,
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.get_spellbook_session", spellbook_ctx,
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.get_coordination_session", coord_ctx,
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.get_fractal_session", fractal_ctx,
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.pkg_version", lambda *a, **kw: "0.30.5",
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard._get_db_size", lambda *a, **kw: 2048,
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard._count_session_files", lambda *a, **kw: 3,
    )

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    data = response.json()

    assert data["health"]["version"] == "0.30.5"
    assert data["health"]["db_size_bytes"] == 2048
    assert data["health"]["event_bus_subscribers"] == 2
    assert data["health"]["event_bus_dropped_events"] == 5
    assert data["counts"]["active_sessions"] == 3
    assert data["counts"]["total_memories"] == 200
    assert data["counts"]["security_events_24h"] == 10
    assert data["counts"]["running_swarms"] == 2
    assert data["counts"]["open_experiments"] == 1
    assert data["counts"]["fractal_graphs"] == 4
    assert len(data["recent_activity"]) == 2

    # Verify ORM sessions were used
    assert spellbook_exec_count[0] == 5
    assert coord_exec_count[0] == 1
    assert fractal_exec_count[0] == 1


def test_dashboard_handles_db_errors_gracefully(client, monkeypatch):
    """Dashboard returns safe defaults when ORM sessions raise exceptions."""

    @asynccontextmanager
    async def _failing_session():
        raise Exception("DB locked")
        yield  # pragma: no cover

    fake_bus = _FakeEventBus(subscriber_count=0, total_dropped_events=0)
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.event_bus", fake_bus,
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.get_spellbook_session", _failing_session,
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.get_fractal_session", _failing_session,
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.get_coordination_session", _failing_session,
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard.pkg_version", lambda *a, **kw: "0.30.5",
    )
    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard._get_db_size", lambda *a, **kw: 0,
    )

    def _raise_fs_error(*a, **kw):
        raise Exception("Filesystem error")

    monkeypatch.setattr(
        "spellbook.admin.routes.dashboard._count_session_files", _raise_fs_error,
    )

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    data = response.json()

    # All counts should fall back to 0
    assert data["counts"]["active_sessions"] == 0
    assert data["counts"]["total_memories"] == 0
    assert data["counts"]["security_events_24h"] == 0
    assert data["counts"]["running_swarms"] == 0
    assert data["counts"]["open_experiments"] == 0
    assert data["counts"]["fractal_graphs"] == 0
    assert data["recent_activity"] == []
