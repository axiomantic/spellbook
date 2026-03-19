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

import pytest
from unittest.mock import AsyncMock, patch

from spellbook.admin.events import Event, EventBus, Subsystem


@pytest.mark.slow
class TestMemorySearchPerformance:
    def test_memory_fts_response_time(self, client):
        """Memory FTS search should respond within 200ms."""
        with patch(
            "spellbook.admin.routes.memory.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"cnt": 100}],  # count query
                [
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
                        "citation_count": 0,
                    }
                    for i in range(50)
                ],
            ]

            start = time.monotonic()
            response = client.get("/api/memories?q=test")
            elapsed_ms = (time.monotonic() - start) * 1000

            assert response.status_code == 200
            assert elapsed_ms < 200, f"Memory FTS took {elapsed_ms:.0f}ms, budget is 200ms"


@pytest.mark.slow
class TestDashboardPerformance:
    def test_dashboard_load_time(self, client):
        """Dashboard endpoint should respond within 1 second."""
        with patch(
            "spellbook.admin.routes.dashboard.get_dashboard_data",
            new_callable=AsyncMock,
        ) as mock_data:
            mock_data.return_value = {
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

            start = time.monotonic()
            response = client.get("/api/dashboard")
            elapsed_ms = (time.monotonic() - start) * 1000

            assert response.status_code == 200
            assert elapsed_ms < 1000, f"Dashboard took {elapsed_ms:.0f}ms, budget is 1000ms"


@pytest.mark.slow
class TestFractalCytoscapePerformance:
    def test_cytoscape_500_nodes(self, client):
        """Cytoscape endpoint should handle 500 nodes within 2 seconds."""
        nodes = [
            {
                "id": f"n-{i}",
                "node_type": "question" if i % 2 == 0 else "answer",
                "text": f"Node text for node {i}",
                "depth": i % 5,
                "status": ["open", "claimed", "answered", "synthesized", "saturated"][i % 5],
                "parent_id": f"n-{i // 2}" if i > 0 else None,
                "owner": f"agent-{i % 3}",
                "session_id": None,
                "claimed_at": None,
                "answered_at": None,
                "synthesized_at": None,
            }
            for i in range(500)
        ]

        edges = [
            {
                "source": f"n-{i}",
                "target": f"n-{i + 1}",
                "edge_type": "parent_child",
            }
            for i in range(499)
        ] + [
            {"source": "n-10", "target": "n-20", "edge_type": "convergence"},
            {"source": "n-30", "target": "n-40", "edge_type": "contradiction"},
        ]

        with patch(
            "spellbook.admin.routes.fractal.query_fractal_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"id": "g-1"}],  # graph exists
                nodes,
                edges,
            ]

            start = time.monotonic()
            response = client.get("/api/fractal/graphs/g-1/cytoscape")
            elapsed_ms = (time.monotonic() - start) * 1000

            assert response.status_code == 200
            data = response.json()
            assert data["stats"]["total_nodes"] == 500
            assert elapsed_ms < 2000, f"Cytoscape took {elapsed_ms:.0f}ms, budget is 2000ms"


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
