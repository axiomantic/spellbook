"""Tests for the dashboard API endpoint."""

from unittest.mock import patch, AsyncMock
import pytest


def test_dashboard_returns_200(client):
    """Dashboard endpoint returns health, counts, and activity."""
    with patch(
        "spellbook.admin.routes.dashboard.get_dashboard_data",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = {
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


def test_dashboard_response_schema(client):
    """DashboardResponse schema validates all required fields and types."""
    with patch(
        "spellbook.admin.routes.dashboard.get_dashboard_data",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = {
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


def test_dashboard_cross_db_aggregation(client):
    """get_dashboard_data queries all databases in parallel via asyncio.gather."""
    with patch(
        "spellbook.admin.routes.dashboard.query_spellbook_db",
        new_callable=AsyncMock,
    ) as mock_spellbook, patch(
        "spellbook.admin.routes.dashboard.query_fractal_db",
        new_callable=AsyncMock,
    ) as mock_fractal, patch(
        "spellbook.admin.routes.dashboard.query_coordination_db",
        new_callable=AsyncMock,
    ) as mock_coordination, patch(
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

        # Spellbook DB returns: memories, security count, experiments,
        # recent security events, recent memories
        mock_spellbook.side_effect = [
            [{"cnt": 200}],     # total memories
            [{"cnt": 10}],      # security events 24h
            [{"cnt": 1}],       # open experiments
            [                   # recent security events
                {
                    "type": "canary_check",
                    "timestamp": "2026-03-14T12:00:00Z",
                    "summary": "Canary verified",
                },
            ],
            [                   # recent memories
                {
                    "type": "memory_created",
                    "timestamp": "2026-03-14T11:00:00Z",
                    "summary": "Stored a new memory about testing",
                },
            ],
        ]

        # Coordination DB: swarms
        mock_coordination.return_value = [{"cnt": 2}]

        # Fractal DB: graphs
        mock_fractal.return_value = [{"cnt": 4}]

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

        # Verify DB query functions were called (sessions now come from filesystem)
        assert mock_spellbook.call_count == 5
        assert mock_coordination.call_count == 1
        assert mock_fractal.call_count == 1


def test_dashboard_handles_db_errors_gracefully(client):
    """Dashboard returns safe defaults when database queries fail."""
    with patch(
        "spellbook.admin.routes.dashboard.query_spellbook_db",
        new_callable=AsyncMock,
    ) as mock_spellbook, patch(
        "spellbook.admin.routes.dashboard.query_fractal_db",
        new_callable=AsyncMock,
    ) as mock_fractal, patch(
        "spellbook.admin.routes.dashboard.query_coordination_db",
        new_callable=AsyncMock,
    ) as mock_coordination, patch(
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

        # All queries raise exceptions
        mock_spellbook.side_effect = Exception("DB locked")
        mock_fractal.side_effect = Exception("DB not found")
        mock_coordination.side_effect = Exception("Connection refused")

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
