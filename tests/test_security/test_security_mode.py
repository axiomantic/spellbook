"""Tests for permissive mode removal from security_set_mode (Finding #9).

Validates:
- "permissive" mode is rejected with a descriptive error dict
- "standard" and "paranoid" remain valid
- Permissive mode attempts are logged as security events
- Invalid modes still raise ValueError
"""

import sqlite3

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


def _get_security_mode_row(db_path):
    """Read the security_mode singleton row."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM security_mode WHERE id = 1").fetchone()
    conn.close()
    return dict(row) if row else None


# ===========================================================================
# Permissive mode rejection
# ===========================================================================


class TestPermissiveModeRejected:
    """Permissive mode must be rejected with an error dict."""

    def test_permissive_returns_error_dict(self, tmp_path):
        """Requesting permissive mode returns error dict instead of raising."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        result = do_set_security_mode("permissive", db_path=db_path)

        # ESCAPE: test_permissive_returns_error_dict
        #   CLAIM: Requesting "permissive" returns a specific error dict
        #   PATH: do_set_security_mode("permissive", ...) executes the mode validation
        #   CHECK: Exact dict equality on returned error
        #   MUTATION: Returning {} or {"mode": "permissive"} would fail
        #   ESCAPE: Nothing reasonable -- exact dict equality catches any content change
        #   IMPACT: Permissive mode silently accepted, weakening security posture
        assert result == {
            "error": "Permissive mode has been removed for security. Only 'standard' and 'paranoid' are available."
        }

    def test_permissive_does_not_change_db_mode(self, tmp_path):
        """Requesting permissive must not alter the stored security mode."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        # Set to paranoid first
        do_set_security_mode("paranoid", db_path=db_path)
        # Attempt permissive
        do_set_security_mode("permissive", db_path=db_path)

        row = _get_security_mode_row(db_path)

        # ESCAPE: test_permissive_does_not_change_db_mode
        #   CLAIM: DB mode remains "paranoid" after permissive attempt
        #   PATH: do_set_security_mode("permissive") should not UPDATE security_mode
        #   CHECK: Exact equality on mode field
        #   MUTATION: If permissive writes to DB, mode would be "permissive" not "paranoid"
        #   ESCAPE: Nothing reasonable -- direct DB read verifies no mutation
        #   IMPACT: Security mode silently downgraded in DB
        assert row["mode"] == "paranoid"

    def test_permissive_does_not_raise(self, tmp_path):
        """Permissive mode should return error dict, not raise ValueError."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)

        # ESCAPE: test_permissive_does_not_raise
        #   CLAIM: No exception is raised for permissive mode
        #   PATH: do_set_security_mode("permissive") catches permissive before ValueError
        #   CHECK: No exception raised (implicit -- test would fail on exception)
        #   MUTATION: If permissive falls through to ValueError branch, this test fails
        #   ESCAPE: Nothing reasonable -- any exception propagation fails the test
        #   IMPACT: Callers crash instead of receiving actionable error dict
        result = do_set_security_mode("permissive", db_path=db_path)
        assert result == {
            "error": "Permissive mode has been removed for security. Only 'standard' and 'paranoid' are available."
        }


# ===========================================================================
# Permissive attempt logged as security event
# ===========================================================================


class TestPermissiveAttemptLogged:
    """Attempting permissive mode must log a security event."""

    def test_logs_permissive_attempt_event(self, tmp_path):
        """A security event is logged when permissive mode is requested."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("permissive", db_path=db_path)

        events = _get_security_events(db_path, "permissive_mode_blocked")
        assert len(events) == 1

        event = events[0]

        # ESCAPE: test_logs_permissive_attempt_event
        #   CLAIM: A security event with correct fields is logged
        #   PATH: do_set_security_mode logs event before returning error
        #   CHECK: All event fields verified with exact values
        #   MUTATION: Wrong event_type -> len(events)==0; wrong severity -> field mismatch
        #   ESCAPE: Nothing reasonable -- all semantic fields verified exactly
        #   IMPACT: Security audit trail missing blocked permissive attempts
        assert event["event_type"] == "permissive_mode_blocked"
        assert event["severity"] == "WARNING"
        assert event["source"] == "security_set_mode"
        assert event["detail"] == "Blocked attempt to set permissive security mode"
        assert event["action_taken"] == "rejected"

    def test_multiple_attempts_log_multiple_events(self, tmp_path):
        """Each permissive attempt logs its own event."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        do_set_security_mode("permissive", db_path=db_path)
        do_set_security_mode("permissive", db_path=db_path)

        events = _get_security_events(db_path, "permissive_mode_blocked")

        # ESCAPE: test_multiple_attempts_log_multiple_events
        #   CLAIM: Two attempts produce two events
        #   PATH: Each call to do_set_security_mode("permissive") inserts an event
        #   CHECK: Exact count of events
        #   MUTATION: If events are deduplicated or skipped, count != 2
        #   ESCAPE: Nothing reasonable -- count is exact
        #   IMPACT: Repeated attack attempts not visible in audit log
        assert len(events) == 2


# ===========================================================================
# Valid modes still work
# ===========================================================================


class TestValidModesUnchanged:
    """Standard and paranoid modes must still work correctly."""

    def test_standard_mode_still_valid(self, tmp_path):
        """Standard mode accepted and persisted."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        result = do_set_security_mode("standard", db_path=db_path)

        # ESCAPE: test_standard_mode_still_valid
        #   CLAIM: Standard mode is accepted and returns correct result
        #   PATH: do_set_security_mode("standard") goes through normal flow
        #   CHECK: mode field exact match, auto_restore_at present
        #   MUTATION: If standard removed from valid set -> error or raise
        #   ESCAPE: Nothing reasonable -- mode field verified exactly
        #   IMPACT: Standard mode broken, users cannot set default security
        assert set(result.keys()) == {"mode", "auto_restore_at"}
        assert result["mode"] == "standard"
        # auto_restore_at is a dynamic ISO timestamp
        from datetime import datetime
        datetime.fromisoformat(result["auto_restore_at"])  # validates format
        row = _get_security_mode_row(db_path)
        assert row["mode"] == "standard"

    def test_paranoid_mode_still_valid(self, tmp_path):
        """Paranoid mode accepted and persisted."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)
        result = do_set_security_mode("paranoid", db_path=db_path)

        # ESCAPE: test_paranoid_mode_still_valid
        #   CLAIM: Paranoid mode is accepted and returns correct result
        #   PATH: do_set_security_mode("paranoid") goes through normal flow
        #   CHECK: mode field exact match, auto_restore_at present, DB persisted
        #   MUTATION: If paranoid removed from valid set -> error or raise
        #   ESCAPE: Nothing reasonable -- mode field and DB both verified
        #   IMPACT: Paranoid mode broken, security elevation impossible
        assert set(result.keys()) == {"mode", "auto_restore_at"}
        assert result["mode"] == "paranoid"
        # auto_restore_at is a dynamic ISO timestamp
        from datetime import datetime
        datetime.fromisoformat(result["auto_restore_at"])  # validates format
        row = _get_security_mode_row(db_path)
        assert row["mode"] == "paranoid"


# ===========================================================================
# Invalid modes still raise ValueError
# ===========================================================================


class TestInvalidModesStillRaise:
    """Truly invalid modes (not permissive) still raise ValueError."""

    def test_lockdown_raises_valueerror(self, tmp_path):
        """Unknown mode 'lockdown' raises ValueError."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)

        # ESCAPE: test_lockdown_raises_valueerror
        #   CLAIM: Unknown modes still raise ValueError
        #   PATH: "lockdown" not in valid modes and not "permissive" -> ValueError
        #   CHECK: ValueError raised with descriptive message
        #   MUTATION: If all modes accepted -> no raise
        #   ESCAPE: Nothing reasonable -- pytest.raises catches missing exception
        #   IMPACT: Arbitrary mode strings accepted, bypassing security controls
        with pytest.raises(ValueError, match="invalid.*mode"):
            do_set_security_mode("lockdown", db_path=db_path)

    def test_empty_string_raises_valueerror(self, tmp_path):
        """Empty string mode raises ValueError."""
        from spellbook_mcp.security.tools import do_set_security_mode

        db_path = _init_test_db(tmp_path)

        # ESCAPE: test_empty_string_raises_valueerror
        #   CLAIM: Empty string is not a valid mode
        #   PATH: "" not in valid modes and not "permissive" -> ValueError
        #   CHECK: ValueError raised
        #   MUTATION: If empty string accepted -> no raise
        #   ESCAPE: Nothing reasonable
        #   IMPACT: Empty mode string silently accepted
        with pytest.raises(ValueError, match="invalid.*mode"):
            do_set_security_mode("", db_path=db_path)


# ===========================================================================
# _VALID_MODES constant
# ===========================================================================


class TestValidModesConstant:
    """The _VALID_MODES constant must not include permissive."""

    def test_valid_modes_excludes_permissive(self):
        """_VALID_MODES must contain only standard and paranoid."""
        from spellbook_mcp.security.tools import _VALID_MODES

        # ESCAPE: test_valid_modes_excludes_permissive
        #   CLAIM: _VALID_MODES is exactly {"standard", "paranoid"}
        #   PATH: Direct import of module constant
        #   CHECK: Exact set equality
        #   MUTATION: Adding "permissive" back -> set != {"standard", "paranoid"}
        #   ESCAPE: Nothing reasonable -- exact set equality
        #   IMPACT: Permissive mode bypasses the explicit check
        assert _VALID_MODES == {"standard", "paranoid"}
