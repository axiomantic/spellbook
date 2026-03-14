"""Tests for security event log API routes."""

from unittest.mock import patch, AsyncMock

import pytest


class TestSecurityEvents:
    def test_list_events_returns_paginated(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                [{"cnt": 1}],  # count query
                [
                    {
                        "id": 1,
                        "event_type": "tool_blocked",
                        "severity": "warning",
                        "source": "test",
                        "detail": "blocked tool",
                        "session_id": None,
                        "tool_name": "rm",
                        "action_taken": "blocked",
                        "created_at": "2026-03-14T10:00:00Z",
                    }
                ],
            ]
            response = client.get("/api/security/events")
            assert response.status_code == 200
            data = response.json()
            assert "events" in data
            assert "total" in data
            assert data["total"] == 1
            assert data["page"] == 1
            assert data["pages"] == 1
            assert len(data["events"]) == 1
            assert data["events"][0]["severity"] == "warning"
            assert data["events"][0]["event_type"] == "tool_blocked"
            assert data["events"][0]["id"] == 1

    def test_list_events_filters_by_severity(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [[{"cnt": 0}], []]
            response = client.get("/api/security/events?severity=critical")
            assert response.status_code == 200
            # Verify the count query included severity filter
            count_sql = mock.call_args_list[0][0][0]
            count_params = mock.call_args_list[0][0][1]
            assert "severity = ?" in count_sql
            assert "critical" in count_params

    def test_list_events_filters_by_event_type(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [[{"cnt": 0}], []]
            response = client.get("/api/security/events?event_type=tool_blocked")
            assert response.status_code == 200
            count_sql = mock.call_args_list[0][0][0]
            count_params = mock.call_args_list[0][0][1]
            assert "event_type = ?" in count_sql
            assert "tool_blocked" in count_params

    def test_list_events_filters_by_date_range(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [[{"cnt": 0}], []]
            response = client.get(
                "/api/security/events?since=2026-03-01&until=2026-03-14"
            )
            assert response.status_code == 200
            count_sql = mock.call_args_list[0][0][0]
            count_params = mock.call_args_list[0][0][1]
            assert "created_at >= ?" in count_sql
            assert "created_at <= ?" in count_sql
            assert "2026-03-01" in count_params
            assert "2026-03-14" in count_params

    def test_list_events_pagination(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [[{"cnt": 75}], []]
            response = client.get("/api/security/events?page=2&per_page=25")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 75
            assert data["page"] == 2
            assert data["per_page"] == 25
            assert data["pages"] == 3
            # Verify offset in data query
            data_sql = mock.call_args_list[1][0][0]
            data_params = mock.call_args_list[1][0][1]
            assert "LIMIT ?" in data_sql
            assert "OFFSET ?" in data_sql
            # per_page=25, offset=(2-1)*25=25
            assert 25 in data_params  # limit
            assert 25 in data_params  # offset

    def test_list_events_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/events")
        assert response.status_code == 401

    def test_list_events_empty(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [[{"cnt": 0}], []]
            response = client.get("/api/security/events")
            assert response.status_code == 200
            data = response.json()
            assert data["events"] == []
            assert data["total"] == 0
            assert data["pages"] == 1


class TestSecurityEventDetail:
    def test_event_detail_returns_event(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {
                    "id": 42,
                    "event_type": "tool_blocked",
                    "severity": "warning",
                    "source": "test-agent",
                    "detail": "Blocked rm -rf /",
                    "session_id": "sess-123",
                    "tool_name": "rm",
                    "action_taken": "blocked",
                    "created_at": "2026-03-14T10:00:00Z",
                }
            ]
            response = client.get("/api/security/events/42")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 42
            assert data["event_type"] == "tool_blocked"
            assert data["detail"] == "Blocked rm -rf /"

    def test_event_detail_404_not_found(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/security/events/999")
            assert response.status_code == 404
            data = response.json()
            assert data["error"]["code"] == "EVENT_NOT_FOUND"

    def test_event_detail_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/events/1")
        assert response.status_code == 401


class TestSecuritySummary:
    def test_summary_returns_counts(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {"severity": "warning", "cnt": 3},
                {"severity": "info", "cnt": 10},
                {"severity": "critical", "cnt": 1},
            ]
            response = client.get("/api/security/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["by_severity"]["warning"] == 3
            assert data["by_severity"]["info"] == 10
            assert data["by_severity"]["critical"] == 1

    def test_summary_empty_db(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/security/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["by_severity"] == {}

    def test_summary_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/summary")
        assert response.status_code == 401


class TestSecurityDashboard:
    def test_dashboard_returns_full_aggregation(self, client):
        with patch(
            "spellbook_mcp.admin.routes.security.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.side_effect = [
                # events by severity (24h)
                [
                    {"severity": "warning", "cnt": 3},
                    {"severity": "info", "cnt": 10},
                ],
                # top event types
                [{"event_type": "tool_blocked", "cnt": 5}],
                # active canaries
                [{"cnt": 2}],
                # trust registry size
                [{"cnt": 15}],
                # security mode
                [{"mode": "standard"}],
            ]
            response = client.get("/api/security/dashboard")
            assert response.status_code == 200
            data = response.json()
            assert data["events_24h"]["warning"] == 3
            assert data["events_24h"]["info"] == 10
            assert data["top_event_types"] == [
                {"event_type": "tool_blocked", "cnt": 5}
            ]
            assert data["active_canaries"] == 2
            assert data["trust_registry_size"] == 15
            assert data["mode"] == "standard"

    def test_dashboard_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/security/dashboard")
        assert response.status_code == 401
