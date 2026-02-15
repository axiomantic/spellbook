"""Tests for auto-elevating security modes with DB persistence and auto-restore.

Validates:
- should_auto_elevate() returns correct mode for various contexts
- do_set_security_mode() persists mode to DB with auto_restore_at
- --get-mode CLI reads from DB and performs lazy restore
- DB unavailable fallback to "standard"
- Mode transitions logged as security events
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_test_db(tmp_path):
    """Create a test DB with schema initialized, return db_path string."""
    from spellbook_mcp.db import close_all_connections, init_db

    close_all_connections()
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


def _get_security_mode_row(db_path):
    """Read the security_mode singleton row."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM security_mode WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else None


def _get_security_events(db_path, event_type=None):
    """Read security events, optionally filtered by type."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if event_type:
        rows = conn.execute(
            "SELECT * FROM security_events WHERE event_type = ?",
            (event_type,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM security_events").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===========================================================================
# should_auto_elevate tests
# ===========================================================================


class TestShouldAutoElevatePrReview:
    """Auto-elevate to paranoid for PR review contexts."""

    def test_pr_review_context_returns_paranoid(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({"pr_review": True})
        assert result == "paranoid"

    def test_pr_review_false_returns_none(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({"pr_review": False})
        assert result is None


class TestShouldAutoElevateWebFetch:
    """Auto-elevate to paranoid when WebFetch tool is invoked."""

    def test_webfetch_tool_returns_paranoid(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({"tool_name": "WebFetch"})
        assert result == "paranoid"

    def test_other_tool_returns_none(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({"tool_name": "Read"})
        assert result is None


class TestShouldAutoElevateUntrustedRepo:
    """Auto-elevate to paranoid for untrusted repositories."""

    def test_untrusted_repo_returns_paranoid(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({"untrusted_repo": True})
        assert result == "paranoid"

    def test_trusted_repo_returns_none(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({"untrusted_repo": False})
        assert result is None


class TestShouldAutoElevateThirdPartySkill:
    """Auto-elevate to paranoid for third-party skills."""

    def test_third_party_skill_returns_paranoid(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({"third_party_skill": True})
        assert result == "paranoid"

    def test_first_party_skill_returns_none(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({"third_party_skill": False})
        assert result is None


class TestShouldAutoElevateNoTrigger:
    """Returns None when no elevation trigger is present."""

    def test_empty_context_returns_none(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({})
        assert result is None

    def test_unrelated_context_returns_none(self):
        from spellbook_mcp.security.check import should_auto_elevate

        result = should_auto_elevate({"user": "alice", "action": "read"})
        assert result is None


# ===========================================================================
# do_set_security_mode tests
# ===========================================================================


class TestDoSetSecurityModeBasic:
    """Basic mode setting and DB persistence."""

    def test_sets_paranoid_mode(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        result = do_set_security_mode("paranoid", db_path=db_path)
        assert result["mode"] == "paranoid"

    def test_sets_permissive_mode(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        result = do_set_security_mode("permissive", db_path=db_path)
        assert result["mode"] == "permissive"

    def test_sets_standard_mode(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("paranoid", db_path=db_path)
        result = do_set_security_mode("standard", db_path=db_path)
        assert result["mode"] == "standard"

    def test_persists_to_db(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("paranoid", db_path=db_path)
        row = _get_security_mode_row(db_path)
        assert row["mode"] == "paranoid"

    def test_returns_auto_restore_at(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        result = do_set_security_mode("paranoid", db_path=db_path)
        assert "auto_restore_at" in result
        assert result["auto_restore_at"] is not None

    def test_auto_restore_at_is_30_minutes_ahead(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        now = datetime.now(timezone.utc)
        result = do_set_security_mode("paranoid", db_path=db_path)

        restore_at = datetime.fromisoformat(result["auto_restore_at"])
        # Allow small delta for test execution time
        expected = now + timedelta(minutes=30)
        delta = abs((restore_at - expected).total_seconds())
        assert delta < 5, f"auto_restore_at off by {delta}s"

    def test_invalid_mode_raises(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        with pytest.raises(ValueError, match="invalid.*mode"):
            do_set_security_mode("lockdown", db_path=db_path)


class TestDoSetSecurityModeReason:
    """Mode setting with optional reason and updated_by."""

    def test_reason_stored_as_updated_by(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode(
            "paranoid", reason="PR review detected", db_path=db_path
        )
        row = _get_security_mode_row(db_path)
        assert row["updated_by"] == "PR review detected"

    def test_no_reason_leaves_updated_by_none(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("paranoid", db_path=db_path)
        row = _get_security_mode_row(db_path)
        # updated_by should be None or the reason; when no reason, None
        assert row["updated_by"] is None


class TestDoSetSecurityModeEventLogging:
    """Mode transitions are logged as security events."""

    def test_logs_security_event(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("paranoid", db_path=db_path)
        events = _get_security_events(db_path, "mode_change")
        assert len(events) == 1

    def test_event_contains_new_mode(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("paranoid", db_path=db_path)
        events = _get_security_events(db_path, "mode_change")
        assert "paranoid" in events[0]["detail"]

    def test_event_severity_is_info(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("paranoid", db_path=db_path)
        events = _get_security_events(db_path, "mode_change")
        assert events[0]["severity"] == "INFO"

    def test_multiple_transitions_log_multiple_events(self, tmp_path):
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("paranoid", db_path=db_path)
        do_set_security_mode("standard", db_path=db_path)
        events = _get_security_events(db_path, "mode_change")
        assert len(events) == 2


# ===========================================================================
# get_current_mode (DB read + lazy restore) tests
# ===========================================================================


class TestGetCurrentModeFromDb:
    """get_current_mode reads from DB."""

    def test_reads_default_standard(self, tmp_path):
        from spellbook_mcp.security.check import get_current_mode

        db_path = _init_test_db(tmp_path)
        mode = get_current_mode(db_path=db_path)
        assert mode == "standard"

    def test_reads_set_mode(self, tmp_path):
        from spellbook_mcp.security.check import get_current_mode
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("paranoid", db_path=db_path)
        mode = get_current_mode(db_path=db_path)
        assert mode == "paranoid"


class TestGetCurrentModeLazyRestore:
    """Lazy restore: expired auto_restore_at resets to standard."""

    def test_expired_mode_restores_to_standard(self, tmp_path):
        from spellbook_mcp.security.check import get_current_mode

        db_path = _init_test_db(tmp_path)
        # Set mode to paranoid with auto_restore_at in the past
        conn = sqlite3.connect(db_path)
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        conn.execute(
            "UPDATE security_mode SET mode = ?, auto_restore_at = ? WHERE id = 1",
            ("paranoid", past),
        )
        conn.commit()
        conn.close()

        mode = get_current_mode(db_path=db_path)
        assert mode == "standard"

    def test_lazy_restore_updates_db(self, tmp_path):
        from spellbook_mcp.security.check import get_current_mode

        db_path = _init_test_db(tmp_path)
        conn = sqlite3.connect(db_path)
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        conn.execute(
            "UPDATE security_mode SET mode = ?, auto_restore_at = ? WHERE id = 1",
            ("paranoid", past),
        )
        conn.commit()
        conn.close()

        get_current_mode(db_path=db_path)
        row = _get_security_mode_row(db_path)
        assert row["mode"] == "standard"

    def test_non_expired_mode_not_restored(self, tmp_path):
        from spellbook_mcp.security.check import get_current_mode

        db_path = _init_test_db(tmp_path)
        conn = sqlite3.connect(db_path)
        future = (datetime.now(timezone.utc) + timedelta(minutes=25)).isoformat()
        conn.execute(
            "UPDATE security_mode SET mode = ?, auto_restore_at = ? WHERE id = 1",
            ("paranoid", future),
        )
        conn.commit()
        conn.close()

        mode = get_current_mode(db_path=db_path)
        assert mode == "paranoid"

    def test_standard_mode_with_expired_restore_stays_standard(self, tmp_path):
        """If mode is already standard and auto_restore_at is expired, no-op."""
        from spellbook_mcp.security.check import get_current_mode

        db_path = _init_test_db(tmp_path)
        conn = sqlite3.connect(db_path)
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        conn.execute(
            "UPDATE security_mode SET mode = ?, auto_restore_at = ? WHERE id = 1",
            ("standard", past),
        )
        conn.commit()
        conn.close()

        mode = get_current_mode(db_path=db_path)
        assert mode == "standard"

    def test_null_auto_restore_at_does_not_trigger_restore(self, tmp_path):
        """Mode with no auto_restore_at should persist indefinitely."""
        from spellbook_mcp.security.check import get_current_mode

        db_path = _init_test_db(tmp_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE security_mode SET mode = ?, auto_restore_at = NULL WHERE id = 1",
            ("paranoid",),
        )
        conn.commit()
        conn.close()

        mode = get_current_mode(db_path=db_path)
        assert mode == "paranoid"


class TestGetCurrentModeDbUnavailable:
    """Falls back to 'standard' when DB is unavailable."""

    def test_nonexistent_db_returns_standard(self, tmp_path):
        from spellbook_mcp.security.check import get_current_mode

        db_path = str(tmp_path / "nonexistent" / "missing.db")
        mode = get_current_mode(db_path=db_path)
        assert mode == "standard"

    def test_corrupted_db_returns_standard(self, tmp_path):
        from spellbook_mcp.security.check import get_current_mode

        db_path = str(tmp_path / "corrupt.db")
        with open(db_path, "w") as f:
            f.write("not a database")
        mode = get_current_mode(db_path=db_path)
        assert mode == "standard"


# ===========================================================================
# CLI --get-mode integration tests
# ===========================================================================


class TestCliGetModeReadsFromDb:
    """CLI --get-mode reads from DB instead of hardcoded 'standard'."""

    def test_get_mode_returns_db_value(self, tmp_path):
        """--get-mode should read from DB when available."""
        from spellbook_mcp.security.check import get_current_mode
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("paranoid", db_path=db_path)
        mode = get_current_mode(db_path=db_path)
        assert mode == "paranoid"

    def test_get_mode_lazy_restores(self, tmp_path):
        """--get-mode should perform lazy restore on expired modes."""
        from spellbook_mcp.security.check import get_current_mode

        db_path = _init_test_db(tmp_path)
        conn = sqlite3.connect(db_path)
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        conn.execute(
            "UPDATE security_mode SET mode = ?, auto_restore_at = ? WHERE id = 1",
            ("permissive", past),
        )
        conn.commit()
        conn.close()

        mode = get_current_mode(db_path=db_path)
        assert mode == "standard"


# ===========================================================================
# do_set_security_mode DB unavailable fallback
# ===========================================================================


class TestDoSetSecurityModeDbUnavailable:
    """do_set_security_mode handles DB errors gracefully."""

    def test_invalid_db_path_raises_or_returns_error(self, tmp_path):
        """When DB path is invalid, raise or return error."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = str(tmp_path / "nonexistent" / "subdir" / "missing.db")
        # Should raise an error since we cannot write to a nonexistent dir
        with pytest.raises(Exception):
            do_set_security_mode("paranoid", db_path=db_path)
