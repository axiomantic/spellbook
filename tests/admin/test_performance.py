"""Performance validation tests for admin API endpoints.

These tests verify response time budgets from the design doc:
- Memory FTS search < 200ms
- Dashboard load < 1s
- Fractal cytoscape endpoint < 2s for 500 nodes
- WebSocket event delivery < 500ms

Marked with @pytest.mark.slow so they can be skipped during rapid iteration.
"""

import asyncio
import time
from types import SimpleNamespace

import bigfoot
import pytest

from spellbook.admin.events import Event, EventBus, Subsystem


def _async_return(value):
    """Return an async function that returns value (for mocking async callables)."""
    async def _fn(*args, **kwargs):
        return value
    return _fn


class _ExecuteResult:
    """Stub for SQLAlchemy session.execute() result."""

    def __init__(self, items=None, scalar_one_value=None, mappings_all_value=None):
        self._items = items
        self._scalar_one_value = scalar_one_value
        self._mappings_all_value = mappings_all_value

    def scalar_one(self):
        return self._scalar_one_value

    def scalars(self):
        return _ScalarsResult(self._items)

    def mappings(self):
        return _MappingsResult(self._mappings_all_value)


class _ScalarsResult:
    """Stub for SQLAlchemy result.scalars() chain."""

    def __init__(self, items):
        self._items = items

    def first(self):
        if isinstance(self._items, list):
            return self._items[0] if self._items else None
        return self._items

    def all(self):
        if isinstance(self._items, list):
            return self._items
        return [self._items] if self._items is not None else []


class _MappingsResult:
    """Stub for SQLAlchemy result.mappings() chain."""

    def __init__(self, items):
        self._items = items or []

    def all(self):
        return self._items


class _MockAsyncSession:
    """Stub async session that returns pre-configured results from execute()."""

    def __init__(self, results):
        self._results = list(results)
        self._call_count = 0

    async def execute(self, *args, **kwargs):
        idx = self._call_count
        self._call_count += 1
        if idx < len(self._results):
            return self._results[idx]
        raise IndexError(f"MockAsyncSession: no result for call #{idx}")


@pytest.mark.slow
class TestMemorySearchPerformance:
    def test_memory_fts_response_time(self, client):
        """Memory FTS search should respond within 200ms."""
        mock_rows = [
            {
                "id": f"mem-{i}",
                "content": f"test memory {i}",
                "memory_type": "fact",
                "namespace": "test",
                "branch": "main",
                "importance": 1.0,
                "created_at": "2026-03-14T10:00:00Z",
                "accessed_at": None,
                "status": "active",
                "meta": "{}",
                "deleted_at": None,
                "content_hash": None,
                "citation_count": 0,
            }
            for i in range(50)
        ]
        count_result = _ExecuteResult(scalar_one_value=100)
        data_result = _ExecuteResult(mappings_all_value=mock_rows)
        mock_session = _MockAsyncSession([count_result, data_result])

        from spellbook.db import spellbook_db

        client.app.dependency_overrides[spellbook_db] = lambda: mock_session
        try:
            start = time.monotonic()
            response = client.get("/api/memories?q=test")
            elapsed_ms = (time.monotonic() - start) * 1000

            assert response.status_code == 200
            assert elapsed_ms < 200, f"Memory FTS took {elapsed_ms:.0f}ms, budget is 200ms"
        finally:
            client.app.dependency_overrides.pop(spellbook_db, None)


@pytest.mark.slow
class TestDashboardPerformance:
    def test_dashboard_load_time(self, client):
        """Dashboard endpoint should respond within 1 second."""
        dashboard_data = {
            "health": {
                "status": "ok",
                "version": "0.30.5",
                "uptime_seconds": 100.0,
                "db_size_bytes": 1024 * 1024,
                "event_bus_subscribers": 0,
                "event_bus_dropped_events": 0,
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
        mock_get = bigfoot.mock(
            "spellbook.admin.routes.dashboard:get_dashboard_data",
        )
        mock_get.calls(_async_return(dashboard_data))

        with bigfoot:
            start = time.monotonic()
            response = client.get("/api/dashboard")
            elapsed_ms = (time.monotonic() - start) * 1000

        mock_get.assert_call()

        assert response.status_code == 200
        assert elapsed_ms < 1000, f"Dashboard took {elapsed_ms:.0f}ms, budget is 1000ms"


@pytest.mark.slow
class TestFractalCytoscapePerformance:
    def test_cytoscape_500_nodes(self, client):
        """Cytoscape endpoint should handle 500 nodes within 2 seconds."""
        statuses = ["open", "claimed", "answered", "synthesized", "saturated"]

        # Build stub node objects
        mock_nodes = []
        for i in range(500):
            node = SimpleNamespace(
                id=f"n-{i}",
                node_type="question" if i % 2 == 0 else "answer",
                text=f"Node text for node {i}",
                depth=i % 5,
                status=statuses[i % 5],
                parent_id=f"n-{i // 2}" if i > 0 else None,
                owner=f"agent-{i % 3}",
                session_id=None,
                claimed_at=None,
                answered_at=None,
                synthesized_at=None,
            )
            mock_nodes.append(node)

        # Build stub edge objects
        mock_edges = []
        for i in range(499):
            edge = SimpleNamespace(
                from_node=f"n-{i}",
                to_node=f"n-{i + 1}",
                edge_type="parent_child",
            )
            mock_edges.append(edge)
        mock_edges.append(SimpleNamespace(
            from_node="n-10",
            to_node="n-20",
            edge_type="convergence",
        ))
        mock_edges.append(SimpleNamespace(
            from_node="n-30",
            to_node="n-40",
            edge_type="contradiction",
        ))

        graph_obj = SimpleNamespace(id="g-1")
        graph_result = _ExecuteResult(items=graph_obj)
        nodes_result = _ExecuteResult(items=mock_nodes)
        edges_result = _ExecuteResult(items=mock_edges)
        mock_session = _MockAsyncSession([graph_result, nodes_result, edges_result])

        from spellbook.db import fractal_db

        client.app.dependency_overrides[fractal_db] = lambda: mock_session
        try:
            start = time.monotonic()
            response = client.get("/api/fractal/graphs/g-1/cytoscape")
            elapsed_ms = (time.monotonic() - start) * 1000

            assert response.status_code == 200
            data = response.json()
            assert data["stats"]["total_nodes"] == 500
            assert elapsed_ms < 2000, f"Cytoscape took {elapsed_ms:.0f}ms, budget is 2000ms"
        finally:
            client.app.dependency_overrides.pop(fractal_db, None)


@pytest.mark.slow
class TestWebSocketEventDelivery:
    @pytest.mark.asyncio
    async def test_event_delivery_latency(self):
        """Event should be delivered to subscriber queue within 500ms."""
        bus = EventBus()
        queue = await bus.subscribe("perf-test")

        event = Event(
            subsystem=Subsystem.MEMORY,
            event_type="created",
            data={"id": "perf-1"},
        )

        start = time.monotonic()
        await bus.publish(event)
        received = queue.get_nowait()
        elapsed_ms = (time.monotonic() - start) * 1000

        assert received.event_type == "created"
        assert elapsed_ms < 500, f"Event delivery took {elapsed_ms:.0f}ms, budget is 500ms"

    @pytest.mark.asyncio
    async def test_event_delivery_with_100_subscribers(self):
        """Event delivery to 100 subscribers should stay under 500ms."""
        bus = EventBus()
        queues = []
        for i in range(100):
            q = await bus.subscribe(f"sub-{i}")
            queues.append(q)

        event = Event(
            subsystem=Subsystem.CONFIG,
            event_type="updated",
            data={"key": "test"},
        )

        start = time.monotonic()
        await bus.publish(event)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Verify all received
        for q in queues:
            assert not q.empty()

        assert elapsed_ms < 500, f"Delivery to 100 subs took {elapsed_ms:.0f}ms, budget is 500ms"
