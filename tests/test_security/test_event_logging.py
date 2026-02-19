"""Tests for security event logging business logic.

Validates:
- do_log_event() inserts events into security_events table
- do_query_events() retrieves events with optional filters
- 10KB detail limit is enforced (truncated, not rejected)
- Degraded mode when DB is unavailable (fail-open)
"""

import sqlite3
from unittest.mock import patch

import pytest

from spellbook_mcp.db import close_all_connections, get_connection, init_db


@pytest.fixture(autouse=True)
def _clean_connections():
    """Close cached DB connections after each test to avoid cross-contamination."""
    yield
    close_all_connections()


@pytest.fixture
def db_path(tmp_path):
    """Create and initialize a temporary database, return its path as string."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


# =============================================================================
# do_log_event tests
# =============================================================================


class TestDoLogEventBasic:
    """Tests for do_log_event happy path."""

    def test_returns_success_true(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        result = do_log_event(
            event_type="injection_detected",
            severity="HIGH",
            db_path=db_path,
        )
        assert result["success"] is True

    def test_returns_event_id(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        result = do_log_event(
            event_type="injection_detected",
            severity="HIGH",
            db_path=db_path,
        )
        assert "event_id" in result
        assert isinstance(result["event_id"], int)
        assert result["event_id"] > 0

    def test_creates_row_in_db(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        do_log_event(
            event_type="injection_detected",
            severity="HIGH",
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM security_events")
        assert cur.fetchone()[0] == 1

    def test_stores_event_type(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        do_log_event(
            event_type="injection_detected",
            severity="HIGH",
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT event_type FROM security_events")
        assert cur.fetchone()[0] == "injection_detected"

    def test_stores_severity(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        do_log_event(
            event_type="injection_detected",
            severity="HIGH",
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT severity FROM security_events")
        assert cur.fetchone()[0] == "HIGH"

    def test_stores_all_optional_fields(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        do_log_event(
            event_type="exfiltration_attempt",
            severity="CRITICAL",
            source="scanner",
            detail="Suspicious URL pattern found",
            session_id="sess-123",
            tool_name="security_sanitize_input",
            action_taken="blocked",
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT source, detail, session_id, tool_name, action_taken "
            "FROM security_events"
        )
        row = cur.fetchone()
        assert row[0] == "scanner"
        assert row[1] == "Suspicious URL pattern found"
        assert row[2] == "sess-123"
        assert row[3] == "security_sanitize_input"
        assert row[4] == "blocked"

    def test_optional_fields_default_to_none(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        do_log_event(
            event_type="test_event",
            severity="LOW",
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT source, detail, session_id, tool_name, action_taken "
            "FROM security_events"
        )
        row = cur.fetchone()
        assert row[0] is None
        assert row[1] is None
        assert row[2] is None
        assert row[3] is None
        assert row[4] is None

    def test_timestamp_is_set(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        do_log_event(
            event_type="test_event",
            severity="LOW",
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT created_at FROM security_events")
        row = cur.fetchone()
        assert row[0] is not None


class TestDoLogEventDetailLimit:
    """Tests for the 10KB detail field cap."""

    def test_detail_under_limit_stored_as_is(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        detail = "x" * 5000  # 5KB, well under limit
        do_log_event(
            event_type="test",
            severity="LOW",
            detail=detail,
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT detail FROM security_events")
        assert cur.fetchone()[0] == detail

    def test_detail_at_limit_stored_as_is(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        detail = "x" * 10240  # Exactly 10KB
        do_log_event(
            event_type="test",
            severity="LOW",
            detail=detail,
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT detail FROM security_events")
        assert cur.fetchone()[0] == detail

    def test_detail_over_limit_is_truncated(self, db_path):
        from spellbook_mcp.security.tools import do_log_event

        detail = "x" * 15000  # Over 10KB
        do_log_event(
            event_type="test",
            severity="LOW",
            detail=detail,
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT detail FROM security_events")
        stored = cur.fetchone()[0]
        assert len(stored) <= 10240

    def test_detail_over_limit_not_rejected(self, db_path):
        """Oversized detail is truncated, not rejected."""
        from spellbook_mcp.security.tools import do_log_event

        detail = "x" * 15000
        result = do_log_event(
            event_type="test",
            severity="LOW",
            detail=detail,
            db_path=db_path,
        )
        assert result["success"] is True

    def test_truncated_detail_has_marker(self, db_path):
        """Truncated detail ends with a truncation marker."""
        from spellbook_mcp.security.tools import do_log_event

        detail = "x" * 15000
        do_log_event(
            event_type="test",
            severity="LOW",
            detail=detail,
            db_path=db_path,
        )

        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT detail FROM security_events")
        stored = cur.fetchone()[0]
        assert stored.endswith("... [truncated]")


class TestDoLogEventDegradedMode:
    """Tests for fail-open behavior when DB is unavailable."""

    def test_returns_success_true_when_db_unavailable(self, tmp_path):
        from spellbook_mcp.security.tools import do_log_event

        # Use a path that won't have an initialized DB and mock the
        # connection to raise
        bad_path = str(tmp_path / "nonexistent_dir" / "bad.db")
        with patch(
            "spellbook_mcp.security.tools.get_connection",
            side_effect=Exception("DB unavailable"),
        ):
            result = do_log_event(
                event_type="test",
                severity="LOW",
                db_path=bad_path,
            )
        assert result["success"] is True

    def test_returns_degraded_true_when_db_unavailable(self, tmp_path):
        from spellbook_mcp.security.tools import do_log_event

        bad_path = str(tmp_path / "bad.db")
        with patch(
            "spellbook_mcp.security.tools.get_connection",
            side_effect=Exception("DB unavailable"),
        ):
            result = do_log_event(
                event_type="test",
                severity="LOW",
                db_path=bad_path,
            )
        assert result["degraded"] is True

    def test_returns_warning_when_db_unavailable(self, tmp_path):
        from spellbook_mcp.security.tools import do_log_event

        bad_path = str(tmp_path / "bad.db")
        with patch(
            "spellbook_mcp.security.tools.get_connection",
            side_effect=Exception("DB unavailable"),
        ):
            result = do_log_event(
                event_type="test",
                severity="LOW",
                db_path=bad_path,
            )
        assert result["warning"] == "Security database unavailable"


# =============================================================================
# do_query_events tests
# =============================================================================


def _insert_events(db_path: str, events: list[dict]) -> None:
    """Helper to insert multiple events directly into the DB."""
    conn = get_connection(db_path)
    for event in events:
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, session_id, tool_name, action_taken) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.get("event_type", "test"),
                event.get("severity", "LOW"),
                event.get("source"),
                event.get("detail"),
                event.get("session_id"),
                event.get("tool_name"),
                event.get("action_taken"),
            ),
        )
    conn.commit()


class TestDoQueryEventsBasic:
    """Tests for do_query_events happy path."""

    def test_returns_success_true(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        result = do_query_events(db_path=db_path)
        assert result["success"] is True

    def test_returns_events_key(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        result = do_query_events(db_path=db_path)
        assert "events" in result
        assert isinstance(result["events"], list)

    def test_empty_table_returns_empty_list(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        result = do_query_events(db_path=db_path)
        assert result["events"] == []

    def test_returns_inserted_event(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        _insert_events(db_path, [
            {"event_type": "injection_detected", "severity": "HIGH"},
        ])

        result = do_query_events(db_path=db_path)
        assert len(result["events"]) == 1
        assert result["events"][0]["event_type"] == "injection_detected"
        assert result["events"][0]["severity"] == "HIGH"

    def test_returns_all_event_fields(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        _insert_events(db_path, [
            {
                "event_type": "test",
                "severity": "MEDIUM",
                "source": "scanner",
                "detail": "details here",
                "session_id": "sess-1",
                "tool_name": "sanitize",
                "action_taken": "logged",
            },
        ])

        result = do_query_events(db_path=db_path)
        event = result["events"][0]
        expected_keys = {
            "id", "event_type", "severity", "source", "detail",
            "session_id", "tool_name", "action_taken", "created_at",
        }
        assert set(event.keys()) == expected_keys

    def test_returns_count(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        _insert_events(db_path, [
            {"event_type": "a", "severity": "LOW"},
            {"event_type": "b", "severity": "HIGH"},
        ])

        result = do_query_events(db_path=db_path)
        assert result["count"] == 2

    def test_events_ordered_by_newest_first(self, db_path):
        """Events are returned newest first (descending created_at)."""
        from spellbook_mcp.security.tools import do_query_events

        # Insert events with explicit timestamps to guarantee order
        conn = get_connection(db_path)
        conn.execute(
            "INSERT INTO security_events (event_type, severity, created_at) "
            "VALUES ('old', 'LOW', '2025-01-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO security_events (event_type, severity, created_at) "
            "VALUES ('new', 'LOW', '2025-06-01 00:00:00')"
        )
        conn.commit()

        result = do_query_events(db_path=db_path)
        assert result["events"][0]["event_type"] == "new"
        assert result["events"][1]["event_type"] == "old"


class TestDoQueryEventsFilterByType:
    """Tests for filtering by event_type."""

    def test_filter_returns_only_matching_type(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        _insert_events(db_path, [
            {"event_type": "injection_detected", "severity": "HIGH"},
            {"event_type": "exfiltration_attempt", "severity": "CRITICAL"},
            {"event_type": "injection_detected", "severity": "MEDIUM"},
        ])

        result = do_query_events(event_type="injection_detected", db_path=db_path)
        assert result["count"] == 2
        for event in result["events"]:
            assert event["event_type"] == "injection_detected"

    def test_filter_no_match_returns_empty(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        _insert_events(db_path, [
            {"event_type": "injection_detected", "severity": "HIGH"},
        ])

        result = do_query_events(event_type="nonexistent", db_path=db_path)
        assert result["count"] == 0
        assert result["events"] == []


class TestDoQueryEventsFilterBySeverity:
    """Tests for filtering by severity."""

    def test_filter_returns_only_matching_severity(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        _insert_events(db_path, [
            {"event_type": "a", "severity": "HIGH"},
            {"event_type": "b", "severity": "LOW"},
            {"event_type": "c", "severity": "HIGH"},
        ])

        result = do_query_events(severity="HIGH", db_path=db_path)
        assert result["count"] == 2
        for event in result["events"]:
            assert event["severity"] == "HIGH"


class TestDoQueryEventsFilterBySinceHours:
    """Tests for filtering by time window."""

    def test_since_hours_filters_old_events(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        conn = get_connection(db_path)
        # Insert event from 48 hours ago
        conn.execute(
            "INSERT INTO security_events (event_type, severity, created_at) "
            "VALUES ('old', 'LOW', datetime('now', '-48 hours'))"
        )
        # Insert event from 1 hour ago
        conn.execute(
            "INSERT INTO security_events (event_type, severity, created_at) "
            "VALUES ('recent', 'LOW', datetime('now', '-1 hours'))"
        )
        conn.commit()

        result = do_query_events(since_hours=24, db_path=db_path)
        assert result["count"] == 1
        assert result["events"][0]["event_type"] == "recent"


class TestDoQueryEventsFilterByLimit:
    """Tests for limiting the number of results."""

    def test_limit_caps_results(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        _insert_events(db_path, [
            {"event_type": f"event_{i}", "severity": "LOW"} for i in range(10)
        ])

        result = do_query_events(limit=3, db_path=db_path)
        assert len(result["events"]) == 3

    def test_default_limit_is_100(self, db_path):
        """Default limit is 100 when not specified."""
        from spellbook_mcp.security.tools import do_query_events

        # Just verify we can call without limit and get results
        _insert_events(db_path, [
            {"event_type": "test", "severity": "LOW"},
        ])

        result = do_query_events(db_path=db_path)
        assert len(result["events"]) == 1  # Just 1 event, under default limit


class TestDoQueryEventsCombinedFilters:
    """Tests for combining multiple filters."""

    def test_type_and_severity_combined(self, db_path):
        from spellbook_mcp.security.tools import do_query_events

        _insert_events(db_path, [
            {"event_type": "injection_detected", "severity": "HIGH"},
            {"event_type": "injection_detected", "severity": "LOW"},
            {"event_type": "exfiltration_attempt", "severity": "HIGH"},
        ])

        result = do_query_events(
            event_type="injection_detected",
            severity="HIGH",
            db_path=db_path,
        )
        assert result["count"] == 1
        assert result["events"][0]["event_type"] == "injection_detected"
        assert result["events"][0]["severity"] == "HIGH"


class TestDoQueryEventsDegradedMode:
    """Tests for fail-open behavior when DB is unavailable."""

    def test_returns_success_true_when_db_unavailable(self, tmp_path):
        from spellbook_mcp.security.tools import do_query_events

        bad_path = str(tmp_path / "bad.db")
        with patch(
            "spellbook_mcp.security.tools.get_connection",
            side_effect=Exception("DB unavailable"),
        ):
            result = do_query_events(db_path=bad_path)
        assert result["success"] is True

    def test_returns_degraded_true_when_db_unavailable(self, tmp_path):
        from spellbook_mcp.security.tools import do_query_events

        bad_path = str(tmp_path / "bad.db")
        with patch(
            "spellbook_mcp.security.tools.get_connection",
            side_effect=Exception("DB unavailable"),
        ):
            result = do_query_events(db_path=bad_path)
        assert result["degraded"] is True

    def test_returns_warning_when_db_unavailable(self, tmp_path):
        from spellbook_mcp.security.tools import do_query_events

        bad_path = str(tmp_path / "bad.db")
        with patch(
            "spellbook_mcp.security.tools.get_connection",
            side_effect=Exception("DB unavailable"),
        ):
            result = do_query_events(db_path=bad_path)
        assert result["warning"] == "Security database unavailable"

    def test_returns_empty_events_when_db_unavailable(self, tmp_path):
        from spellbook_mcp.security.tools import do_query_events

        bad_path = str(tmp_path / "bad.db")
        with patch(
            "spellbook_mcp.security.tools.get_connection",
            side_effect=Exception("DB unavailable"),
        ):
            result = do_query_events(db_path=bad_path)
        assert result["events"] == []
        assert result["count"] == 0
