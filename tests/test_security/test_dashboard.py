"""Tests for security dashboard business logic.

Validates:
- do_dashboard() returns zeroed counts and empty lists on empty DB
- do_dashboard() returns correct counts with populated data
- since_hours filtering restricts events to time window
- top_blocked_rules ordering and limit
- recent_alerts filters to CRITICAL/HIGH only, limit 5
- Graceful degradation when tables are missing
"""

import sqlite3

import pytest

from spellbook_mcp.db import close_all_connections, init_db


@pytest.fixture(autouse=True)
def _clean_connections():
    """Close cached DB connections after each test to avoid cross-contamination."""
    yield
    close_all_connections()


def _setup_db(tmp_path):
    """Initialize a fresh test database and return its path as string."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


# =============================================================================
# TestDashboardEmpty: empty DB returns zeroed counts and empty lists
# =============================================================================


class TestDashboardEmpty:
    """Empty database returns sensible defaults for all dashboard fields."""

    def test_returns_security_mode(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path)
        assert result["security_mode"] == "standard"

    def test_returns_period_hours(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path, since_hours=12)
        assert result["period_hours"] == 12

    def test_returns_zero_total_events(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path)
        assert result["total_events"] == 0

    def test_returns_zero_injections_detected(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path)
        assert result["injections_detected"] == 0

    def test_returns_canary_status_zeroed(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path)
        assert result["canary_status"] == {"total": 0, "triggered": 0}

    def test_returns_empty_trust_distribution(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path)
        assert result["trust_distribution"] == {}

    def test_returns_empty_top_blocked_rules(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path)
        assert result["top_blocked_rules"] == []

    def test_returns_zero_honeypot_triggers(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path)
        assert result["honeypot_triggers"] == 0

    def test_returns_empty_recent_alerts(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path)
        assert result["recent_alerts"] == []

    def test_returns_all_required_keys(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        result = do_dashboard(db_path=db_path)
        expected_keys = {
            "security_mode",
            "period_hours",
            "total_events",
            "injections_detected",
            "canary_status",
            "trust_distribution",
            "top_blocked_rules",
            "honeypot_triggers",
            "recent_alerts",
        }
        assert set(result.keys()) == expected_keys


# =============================================================================
# TestDashboardPopulated: insert events, canaries, trust; verify counts
# =============================================================================


class TestDashboardPopulated:
    """Populated database returns correct counts."""

    def _insert_events(self, db_path, events):
        """Insert events into security_events table.

        Each event is a tuple: (event_type, severity, source, detail, action_taken).
        """
        conn = sqlite3.connect(db_path)
        for ev in events:
            conn.execute(
                "INSERT INTO security_events "
                "(event_type, severity, source, detail, action_taken) "
                "VALUES (?, ?, ?, ?, ?)",
                ev,
            )
        conn.commit()
        conn.close()

    def _insert_canaries(self, db_path, canaries):
        """Insert canary tokens. Each is (token, token_type, context, triggered_at)."""
        conn = sqlite3.connect(db_path)
        for c in canaries:
            conn.execute(
                "INSERT INTO canary_tokens "
                "(token, token_type, context, triggered_at) "
                "VALUES (?, ?, ?, ?)",
                c,
            )
        conn.commit()
        conn.close()

    def _insert_trust(self, db_path, entries):
        """Insert trust registry entries. Each is (content_hash, source, trust_level)."""
        conn = sqlite3.connect(db_path)
        for e in entries:
            conn.execute(
                "INSERT INTO trust_registry "
                "(content_hash, source, trust_level) "
                "VALUES (?, ?, ?)",
                e,
            )
        conn.commit()
        conn.close()

    def test_total_events_counts_all(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        self._insert_events(db_path, [
            ("injection_detected", "HIGH", "test", "detail1", None),
            ("mode_change", "INFO", "test", "detail2", None),
            ("canary_triggered", "CRITICAL", "test", "detail3", None),
        ])
        result = do_dashboard(db_path=db_path, since_hours=24)
        assert result["total_events"] == 3

    def test_injections_detected_counts_injection_events(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        self._insert_events(db_path, [
            ("injection_detected", "HIGH", "test", "detail1", None),
            ("injection_blocked", "CRITICAL", "test", "detail2", None),
            ("blocked_bash_command", "HIGH", "test", "detail3", None),
            ("mode_change", "INFO", "test", "detail4", None),
        ])
        result = do_dashboard(db_path=db_path, since_hours=24)
        assert result["injections_detected"] == 3

    def test_canary_status_counts(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        self._insert_canaries(db_path, [
            ("CANARY-abc123-P", "prompt", "ctx1", None),
            ("CANARY-def456-F", "file", "ctx2", "2025-01-01T00:00:00"),
            ("CANARY-ghi789-C", "config", "ctx3", None),
        ])
        result = do_dashboard(db_path=db_path)
        assert result["canary_status"]["total"] == 3
        assert result["canary_status"]["triggered"] == 1

    def test_trust_distribution(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        self._insert_trust(db_path, [
            ("hash1", "src1", "system"),
            ("hash2", "src2", "user"),
            ("hash3", "src3", "user"),
            ("hash4", "src4", "untrusted"),
        ])
        result = do_dashboard(db_path=db_path)
        assert result["trust_distribution"] == {
            "system": 1,
            "user": 2,
            "untrusted": 1,
        }

    def test_honeypot_triggers_counts_honeypot_events(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        self._insert_events(db_path, [
            ("honeypot_triggered", "HIGH", "test", "detail1", None),
            ("honeypot_triggered", "CRITICAL", "test", "detail2", None),
            ("injection_detected", "HIGH", "test", "detail3", None),
        ])
        result = do_dashboard(db_path=db_path, since_hours=24)
        assert result["honeypot_triggers"] == 2


# =============================================================================
# TestDashboardTimeWindow: since_hours filtering
# =============================================================================


class TestDashboardTimeWindow:
    """Events outside the time window are excluded."""

    def test_excludes_old_events(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        conn = sqlite3.connect(db_path)
        # Insert a recent event (within window)
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            ("injection_detected", "HIGH", "test", "recent", ),
        )
        # Insert an old event (outside 1-hour window)
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now', '-2 hours'))",
            ("injection_detected", "HIGH", "test", "old"),
        )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=1)
        assert result["total_events"] == 1

    def test_includes_events_within_window(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        conn = sqlite3.connect(db_path)
        # Insert 3 recent events
        for i in range(3):
            conn.execute(
                "INSERT INTO security_events "
                "(event_type, severity, source, detail, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                ("injection_detected", "HIGH", "test", f"event{i}"),
            )
        # Insert 2 old events (outside 24-hour window)
        for i in range(2):
            conn.execute(
                "INSERT INTO security_events "
                "(event_type, severity, source, detail, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now', '-48 hours'))",
                ("injection_detected", "HIGH", "test", f"old{i}"),
            )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=24)
        assert result["total_events"] == 3

    def test_time_window_affects_injections_count(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        conn = sqlite3.connect(db_path)
        # Recent injection
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            ("injection_detected", "HIGH", "test", "recent"),
        )
        # Old injection
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now', '-48 hours'))",
            ("injection_blocked", "HIGH", "test", "old"),
        )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=24)
        assert result["injections_detected"] == 1

    def test_time_window_affects_honeypot_count(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        conn = sqlite3.connect(db_path)
        # Recent honeypot
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            ("honeypot_triggered", "HIGH", "test", "recent"),
        )
        # Old honeypot
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now', '-48 hours'))",
            ("honeypot_triggered", "HIGH", "test", "old"),
        )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=24)
        assert result["honeypot_triggers"] == 1


# =============================================================================
# TestDashboardTopBlocked: rule_id ordering and limit
# =============================================================================


class TestDashboardTopBlocked:
    """Top blocked rules returns (rule_id, count) ordered by count descending."""

    def _insert_blocked_events(self, db_path, rule_counts):
        """Insert blocked events with action_taken containing rule_id.

        rule_counts: list of (rule_id, count) tuples.
        """
        conn = sqlite3.connect(db_path)
        for rule_id, count in rule_counts:
            for _ in range(count):
                conn.execute(
                    "INSERT INTO security_events "
                    "(event_type, severity, source, detail, action_taken) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("blocked", "HIGH", "test", f"blocked by {rule_id}", rule_id),
                )
        conn.commit()
        conn.close()

    def test_returns_rules_ordered_by_count_desc(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        self._insert_blocked_events(db_path, [
            ("INJ-001", 5),
            ("INJ-002", 10),
            ("EXFIL-001", 3),
        ])
        result = do_dashboard(db_path=db_path, since_hours=24)
        rules = result["top_blocked_rules"]
        assert len(rules) == 3
        assert rules[0] == ["INJ-002", 10]
        assert rules[1] == ["INJ-001", 5]
        assert rules[2] == ["EXFIL-001", 3]

    def test_limits_to_10_rules(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        # Insert 12 different rules
        rule_counts = [(f"RULE-{i:03d}", 12 - i) for i in range(12)]
        self._insert_blocked_events(db_path, rule_counts)
        result = do_dashboard(db_path=db_path, since_hours=24)
        assert len(result["top_blocked_rules"]) == 10

    def test_empty_when_no_blocked_events(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        # Insert non-blocked events
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail) "
            "VALUES (?, ?, ?, ?)",
            ("mode_change", "INFO", "test", "not blocked"),
        )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=24)
        assert result["top_blocked_rules"] == []


# =============================================================================
# TestDashboardRecentAlerts: severity filtering and limit
# =============================================================================


class TestDashboardRecentAlerts:
    """Recent alerts returns only CRITICAL/HIGH events, limited to 5."""

    def test_returns_only_critical_and_high(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail) "
            "VALUES (?, ?, ?, ?)",
            ("injection_detected", "CRITICAL", "test", "critical event"),
        )
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail) "
            "VALUES (?, ?, ?, ?)",
            ("injection_detected", "HIGH", "test", "high event"),
        )
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail) "
            "VALUES (?, ?, ?, ?)",
            ("mode_change", "INFO", "test", "info event"),
        )
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail) "
            "VALUES (?, ?, ?, ?)",
            ("something", "MEDIUM", "test", "medium event"),
        )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=24)
        alerts = result["recent_alerts"]
        assert len(alerts) == 2
        severities = {a["severity"] for a in alerts}
        assert severities == {"CRITICAL", "HIGH"}

    def test_limits_to_5_alerts(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        conn = sqlite3.connect(db_path)
        for i in range(8):
            conn.execute(
                "INSERT INTO security_events "
                "(event_type, severity, source, detail) "
                "VALUES (?, ?, ?, ?)",
                ("injection_detected", "CRITICAL", "test", f"event {i}"),
            )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=24)
        assert len(result["recent_alerts"]) == 5

    def test_alert_contains_required_fields(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail) "
            "VALUES (?, ?, ?, ?)",
            ("injection_detected", "CRITICAL", "test", "some detail text"),
        )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=24)
        alert = result["recent_alerts"][0]
        assert "event_type" in alert
        assert "severity" in alert
        assert "timestamp" in alert
        assert "detail" in alert

    def test_alert_detail_is_truncated_if_long(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        long_detail = "x" * 500
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail) "
            "VALUES (?, ?, ?, ?)",
            ("injection_detected", "CRITICAL", "test", long_detail),
        )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=24)
        alert = result["recent_alerts"][0]
        assert len(alert["detail"]) <= 200

    def test_alerts_ordered_newest_first(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = _setup_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now', '-1 hour'))",
            ("injection_detected", "HIGH", "test", "older"),
        )
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            ("injection_detected", "CRITICAL", "test", "newer"),
        )
        conn.commit()
        conn.close()

        result = do_dashboard(db_path=db_path, since_hours=24)
        alerts = result["recent_alerts"]
        assert alerts[0]["detail"] == "newer"
        assert alerts[1]["detail"] == "older"


# =============================================================================
# TestDashboardGraceful: missing tables return clean empty response
# =============================================================================


class TestDashboardGraceful:
    """Missing or corrupt database returns clean empty response, never errors."""

    def test_empty_db_no_tables(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        # Create a database WITHOUT running init_db (no tables)
        db_path = str(tmp_path / "empty.db")
        conn = sqlite3.connect(db_path)
        conn.close()

        result = do_dashboard(db_path=db_path)
        assert result["total_events"] == 0
        assert result["injections_detected"] == 0
        assert result["canary_status"] == {"total": 0, "triggered": 0}
        assert result["trust_distribution"] == {}
        assert result["top_blocked_rules"] == []
        assert result["honeypot_triggers"] == 0
        assert result["recent_alerts"] == []

    def test_nonexistent_db_path(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = str(tmp_path / "does_not_exist.db")
        # SQLite will create the file but without tables
        result = do_dashboard(db_path=db_path)
        assert result["total_events"] == 0
        assert result["recent_alerts"] == []

    def test_graceful_returns_security_mode_standard(self, tmp_path):
        from spellbook_mcp.security.tools import do_dashboard

        db_path = str(tmp_path / "empty.db")
        conn = sqlite3.connect(db_path)
        conn.close()

        result = do_dashboard(db_path=db_path)
        assert result["security_mode"] == "standard"
