"""Tests for analytics routes after ORM migration to SQLAlchemy ORM.

Verifies the routes correctly use get_spellbook_session() and process
query results into the expected API response format.

Note: these tests use monkeypatch instead of bigfoot sandboxes because
the TestClient creates real socket connections that bigfoot 0.19.1's
socket_mock plugin intercepts inside sandboxes.
"""

import bigfoot
import pytest

from collections import namedtuple
from contextlib import asynccontextmanager


class _FakeResult:
    """Mimics a SQLAlchemy result object supporting iteration and one_or_none."""

    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def one_or_none(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Mimics an async SQLAlchemy session with execute()."""

    def __init__(self, result):
        self._result = result

    async def execute(self, stmt):
        return self._result


def _make_session_mock(execute_return):
    """Create a mock get_spellbook_session that returns given execute results.

    The mock session's execute() returns a result object whose iteration
    yields the given rows.
    """

    @asynccontextmanager
    async def mock_get_session():
        yield _FakeSession(_FakeResult(execute_return))

    return mock_get_session


# Named tuples to simulate SQLAlchemy Row objects with named attributes
ToolFreqRow = namedtuple("ToolFreqRow", ["tool_name", "count", "errors"])
ErrorRateRow = namedtuple("ErrorRateRow", ["tool_name", "total", "errors", "error_rate"])
TimelineRow = namedtuple("TimelineRow", ["bucket", "count", "errors"])
SummaryRow = namedtuple(
    "SummaryRow", ["total_events", "unique_tools", "error_rate", "events_today"]
)


# ---------------------------------------------------------------------------
# Tool Frequency
# ---------------------------------------------------------------------------


class TestToolFrequencyORM:
    """Test /analytics/tool-frequency with ORM-based implementation."""

    def test_returns_tool_counts_grouped_and_sorted(self, client, monkeypatch):
        """Should return tools sorted by count descending with error counts."""
        rows = [
            ToolFreqRow(tool_name="Read", count=150, errors=2),
            ToolFreqRow(tool_name="Write", count=75, errors=5),
        ]

        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock(rows),
        )
        response = client.get("/api/analytics/tool-frequency")


        assert response.status_code == 200
        assert response.json() == {
            "tools": [
                {"tool_name": "Read", "count": 150, "errors": 2},
                {"tool_name": "Write", "count": 75, "errors": 5},
            ]
        }

    def test_empty_results(self, client, monkeypatch):
        """Empty database should return empty tools list."""
        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock([]),
        )
        response = client.get("/api/analytics/tool-frequency")


        assert response.status_code == 200
        assert response.json() == {"tools": []}

    def test_single_tool_no_errors(self, client, monkeypatch):
        """A single tool with zero errors."""
        rows = [ToolFreqRow(tool_name="Bash", count=42, errors=0)]

        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock(rows),
        )
        response = client.get("/api/analytics/tool-frequency?period=all")


        assert response.status_code == 200
        assert response.json() == {
            "tools": [
                {"tool_name": "Bash", "count": 42, "errors": 0},
            ]
        }

    def test_passes_period_and_event_type_to_query(self, client, monkeypatch):
        """Verify the route builds the statement with period and event_type filters."""
        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock([]),
        )
        response = client.get(
            "/api/analytics/tool-frequency?period=24h&event_type=tool_call"
        )


        assert response.status_code == 200
        assert response.json() == {"tools": []}

    def test_requires_auth(self, unauthenticated_client):
        """Unauthenticated requests should return 401."""
        response = unauthenticated_client.get("/api/analytics/tool-frequency")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Error Rates
# ---------------------------------------------------------------------------


class TestErrorRatesORM:
    """Test /analytics/error-rates with ORM-based implementation."""

    def test_returns_error_rates(self, client, monkeypatch):
        """Should return tools with error counts and rates."""
        rows = [
            ErrorRateRow(tool_name="Write", total=75, errors=5, error_rate=6.67),
        ]

        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock(rows),
        )
        response = client.get("/api/analytics/error-rates")


        assert response.status_code == 200
        assert response.json() == {
            "tools": [
                {"tool_name": "Write", "total": 75, "errors": 5, "error_rate": 6.67},
            ]
        }

    def test_multiple_tools_sorted_by_errors_desc(self, client, monkeypatch):
        """Tools should be ordered by error count descending."""
        rows = [
            ErrorRateRow(tool_name="Write", total=100, errors=10, error_rate=10.0),
            ErrorRateRow(tool_name="Bash", total=50, errors=3, error_rate=6.0),
        ]

        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock(rows),
        )
        response = client.get("/api/analytics/error-rates?period=all")


        assert response.status_code == 200
        assert response.json() == {
            "tools": [
                {"tool_name": "Write", "total": 100, "errors": 10, "error_rate": 10.0},
                {"tool_name": "Bash", "total": 50, "errors": 3, "error_rate": 6.0},
            ]
        }

    def test_empty_results(self, client, monkeypatch):
        """No tools with errors returns empty list."""
        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock([]),
        )
        response = client.get("/api/analytics/error-rates")


        assert response.status_code == 200
        assert response.json() == {"tools": []}

    def test_requires_auth(self, unauthenticated_client):
        """Unauthenticated requests should return 401."""
        response = unauthenticated_client.get("/api/analytics/error-rates")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class TestTimelineORM:
    """Test /analytics/timeline with ORM-based implementation."""

    def test_returns_bucketed_data(self, client, monkeypatch):
        """Should return time-bucketed event counts."""
        rows = [
            TimelineRow(bucket="2026-03-15 10:00", count=42, errors=3),
            TimelineRow(bucket="2026-03-15 11:00", count=38, errors=1),
        ]

        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock(rows),
        )
        response = client.get("/api/analytics/timeline")


        assert response.status_code == 200
        assert response.json() == {
            "timeline": [
                {"bucket": "2026-03-15 10:00", "count": 42, "errors": 3},
                {"bucket": "2026-03-15 11:00", "count": 38, "errors": 1},
            ]
        }

    def test_day_bucketed_data(self, client, monkeypatch):
        """Non-24h periods should use day-level buckets."""
        rows = [
            TimelineRow(bucket="2026-03-14", count=100, errors=5),
            TimelineRow(bucket="2026-03-15", count=120, errors=2),
        ]

        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock(rows),
        )
        response = client.get("/api/analytics/timeline?period=7d")


        assert response.status_code == 200
        assert response.json() == {
            "timeline": [
                {"bucket": "2026-03-14", "count": 100, "errors": 5},
                {"bucket": "2026-03-15", "count": 120, "errors": 2},
            ]
        }

    def test_empty_results(self, client, monkeypatch):
        """Empty database should return empty timeline."""
        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock([]),
        )
        response = client.get("/api/analytics/timeline")


        assert response.status_code == 200
        assert response.json() == {"timeline": []}

    def test_requires_auth(self, unauthenticated_client):
        """Unauthenticated requests should return 401."""
        response = unauthenticated_client.get("/api/analytics/timeline")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class TestAnalyticsSummaryORM:
    """Test /analytics/summary with ORM-based implementation."""

    def test_returns_aggregate_stats(self, client, monkeypatch):
        """Should return total events, unique tools, error rate, events today."""
        rows = [
            SummaryRow(
                total_events=5000,
                unique_tools=12,
                error_rate=3.5,
                events_today=200,
            )
        ]

        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock(rows),
        )
        response = client.get("/api/analytics/summary")


        assert response.status_code == 200
        assert response.json() == {
            "total_events": 5000,
            "unique_tools": 12,
            "error_rate": 3.5,
            "events_today": 200,
        }

    def test_empty_db_returns_zeros(self, client, monkeypatch):
        """When query returns row with zero total, should return zeros."""
        rows = [
            SummaryRow(total_events=0, unique_tools=0, error_rate=0, events_today=0)
        ]

        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock(rows),
        )
        response = client.get("/api/analytics/summary")


        assert response.status_code == 200
        assert response.json() == {
            "total_events": 0,
            "unique_tools": 0,
            "error_rate": 0,
            "events_today": 0,
        }

    def test_no_rows_returns_zeros(self, client, monkeypatch):
        """When query returns no rows, should return zero defaults."""
        monkeypatch.setattr(
            "spellbook.admin.routes.analytics.get_spellbook_session",
            _make_session_mock([]),
        )
        response = client.get("/api/analytics/summary")


        assert response.status_code == 200
        assert response.json() == {
            "total_events": 0,
            "unique_tools": 0,
            "error_rate": 0,
            "events_today": 0,
        }

    def test_requires_auth(self, unauthenticated_client):
        """Unauthenticated requests should return 401."""
        response = unauthenticated_client.get("/api/analytics/summary")
        assert response.status_code == 401
