"""Tests for tool call analytics API routes."""

from unittest.mock import AsyncMock, patch

import pytest


class TestToolFrequency:
    def test_returns_tool_counts(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {"tool_name": "Read", "count": 150, "errors": 2},
                {"tool_name": "Write", "count": 75, "errors": 5},
            ]
            response = client.get("/api/analytics/tool-frequency")
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "tools": [
                    {"tool_name": "Read", "count": 150, "errors": 2},
                    {"tool_name": "Write", "count": 75, "errors": 5},
                ]
            }

    def test_filters_by_period_24h(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/analytics/tool-frequency?period=24h")
            assert response.status_code == 200
            sql = mock.call_args[0][0]
            assert "datetime('now', ?)" in sql
            params = mock.call_args[0][1]
            assert params == ("-24 hours",)

    def test_filters_by_period_7d(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/analytics/tool-frequency?period=7d")
            assert response.status_code == 200
            params = mock.call_args[0][1]
            assert params == ("-7 days",)

    def test_filters_by_period_30d(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/analytics/tool-frequency?period=30d")
            assert response.status_code == 200
            params = mock.call_args[0][1]
            assert params == ("-30 days",)

    def test_period_all_no_date_filter(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/analytics/tool-frequency?period=all")
            assert response.status_code == 200
            sql = mock.call_args[0][0]
            assert "datetime('now', ?)" not in sql
            # No period params should be passed
            params = mock.call_args[0][1]
            assert params == ()

    def test_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/analytics/tool-frequency")
        assert response.status_code == 401

    def test_empty_results(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/analytics/tool-frequency")
            assert response.status_code == 200
            assert response.json() == {"tools": []}


class TestErrorRates:
    def test_returns_error_rates(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {"tool_name": "Write", "total": 75, "errors": 5, "error_rate": 6.67},
            ]
            response = client.get("/api/analytics/error-rates")
            assert response.status_code == 200
            assert response.json() == {
                "tools": [
                    {"tool_name": "Write", "total": 75, "errors": 5, "error_rate": 6.67},
                ]
            }

    def test_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/analytics/error-rates")
        assert response.status_code == 401

    def test_empty_results(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/analytics/error-rates")
            assert response.status_code == 200
            assert response.json() == {"tools": []}


class TestTimeline:
    def test_returns_bucketed_data(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {"bucket": "2026-03-15 10:00", "count": 42, "errors": 3},
                {"bucket": "2026-03-15 11:00", "count": 38, "errors": 1},
            ]
            response = client.get("/api/analytics/timeline")
            assert response.status_code == 200
            assert response.json() == {
                "timeline": [
                    {"bucket": "2026-03-15 10:00", "count": 42, "errors": 3},
                    {"bucket": "2026-03-15 11:00", "count": 38, "errors": 1},
                ]
            }

    def test_24h_uses_hour_buckets(self, client):
        """24h period should use hour-level bucketing in the SQL."""
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/analytics/timeline?period=24h")
            assert response.status_code == 200
            sql = mock.call_args[0][0]
            assert "%H:00" in sql or "%H:" in sql

    def test_7d_uses_day_buckets(self, client):
        """Non-24h periods should use day-level bucketing."""
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/analytics/timeline?period=7d")
            assert response.status_code == 200
            sql = mock.call_args[0][0]
            # Day buckets: %Y-%m-%d without hour component
            assert "%Y-%m-%d" in sql
            assert "%H:00" not in sql

    def test_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/analytics/timeline")
        assert response.status_code == 401


class TestAnalyticsSummary:
    def test_returns_aggregate_stats(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {
                    "total_events": 5000,
                    "unique_tools": 12,
                    "error_rate": 3.5,
                    "events_today": 200,
                }
            ]
            response = client.get("/api/analytics/summary")
            assert response.status_code == 200
            assert response.json() == {
                "total_events": 5000,
                "unique_tools": 12,
                "error_rate": 3.5,
                "events_today": 200,
            }

    def test_empty_db_returns_zeros(self, client):
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = [
                {
                    "total_events": 0,
                    "unique_tools": 0,
                    "error_rate": 0,
                    "events_today": 0,
                }
            ]
            response = client.get("/api/analytics/summary")
            assert response.status_code == 200
            assert response.json() == {
                "total_events": 0,
                "unique_tools": 0,
                "error_rate": 0,
                "events_today": 0,
            }

    def test_no_rows_returns_zeros(self, client):
        """When query returns empty list, should return zero defaults."""
        with patch(
            "spellbook.admin.routes.analytics.query_spellbook_db",
            new_callable=AsyncMock,
        ) as mock:
            mock.return_value = []
            response = client.get("/api/analytics/summary")
            assert response.status_code == 200
            assert response.json() == {
                "total_events": 0,
                "unique_tools": 0,
                "error_rate": 0,
                "events_today": 0,
            }

    def test_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/analytics/summary")
        assert response.status_code == 401
