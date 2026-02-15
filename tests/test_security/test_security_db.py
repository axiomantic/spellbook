"""Tests for security database schema additions.

Validates that init_db() creates the 4 security tables
(trust_registry, security_events, canary_tokens, security_mode)
with correct columns, indexes, default data, and idempotent behavior.
"""

import sqlite3

import pytest


def _get_table_columns(cursor: sqlite3.Cursor, table: str) -> dict[str, str]:
    """Return {column_name: column_type} for a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1]: row[2] for row in cursor.fetchall()}


def _get_index_names(cursor: sqlite3.Cursor, table: str) -> list[str]:
    """Return list of index names for a table."""
    cursor.execute(f"PRAGMA index_list({table})")
    return [row[1] for row in cursor.fetchall()]


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _index_exists(cursor: sqlite3.Cursor, index_name: str) -> bool:
    """Check if an index exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    )
    return cursor.fetchone() is not None


# ---------------------------------------------------------------------------
# trust_registry
# ---------------------------------------------------------------------------


class TestTrustRegistryTable:
    """Tests for the trust_registry table."""

    def test_table_created(self, tmp_path):
        """trust_registry table exists after init_db()."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        conn = get_connection(db_path)
        assert _table_exists(conn.cursor(), "trust_registry")
        conn.close()

    def test_columns(self, tmp_path):
        """trust_registry has the expected columns."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        cols = _get_table_columns(get_connection(db_path).cursor(), "trust_registry")

        expected = {
            "id",
            "content_hash",
            "source",
            "trust_level",
            "registered_at",
            "expires_at",
            "registered_by",
        }
        assert set(cols.keys()) == expected

    def test_index_on_content_hash(self, tmp_path):
        """idx_trust_content_hash index exists."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        cur = get_connection(db_path).cursor()
        assert _index_exists(cur, "idx_trust_content_hash")


# ---------------------------------------------------------------------------
# security_events
# ---------------------------------------------------------------------------


class TestSecurityEventsTable:
    """Tests for the security_events table."""

    def test_table_created(self, tmp_path):
        """security_events table exists after init_db()."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        assert _table_exists(get_connection(db_path).cursor(), "security_events")

    def test_columns(self, tmp_path):
        """security_events has the expected columns."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        cols = _get_table_columns(
            get_connection(db_path).cursor(), "security_events"
        )

        expected = {
            "id",
            "event_type",
            "severity",
            "source",
            "detail",
            "session_id",
            "tool_name",
            "action_taken",
            "created_at",
        }
        assert set(cols.keys()) == expected

    def test_index_on_event_type(self, tmp_path):
        """idx_security_events_type index exists."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        assert _index_exists(
            get_connection(db_path).cursor(), "idx_security_events_type"
        )

    def test_index_on_severity(self, tmp_path):
        """idx_security_events_severity index exists."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        assert _index_exists(
            get_connection(db_path).cursor(), "idx_security_events_severity"
        )


# ---------------------------------------------------------------------------
# canary_tokens
# ---------------------------------------------------------------------------


class TestCanaryTokensTable:
    """Tests for the canary_tokens table."""

    def test_table_created(self, tmp_path):
        """canary_tokens table exists after init_db()."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        assert _table_exists(get_connection(db_path).cursor(), "canary_tokens")

    def test_columns(self, tmp_path):
        """canary_tokens has the expected columns."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        cols = _get_table_columns(
            get_connection(db_path).cursor(), "canary_tokens"
        )

        expected = {
            "id",
            "token",
            "token_type",
            "context",
            "created_at",
            "triggered_at",
            "triggered_by",
        }
        assert set(cols.keys()) == expected

    def test_index_on_token(self, tmp_path):
        """idx_canary_token index exists."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        assert _index_exists(get_connection(db_path).cursor(), "idx_canary_token")


# ---------------------------------------------------------------------------
# security_mode (singleton)
# ---------------------------------------------------------------------------


class TestSecurityModeTable:
    """Tests for the security_mode singleton table."""

    def test_table_created(self, tmp_path):
        """security_mode table exists after init_db()."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        assert _table_exists(get_connection(db_path).cursor(), "security_mode")

    def test_columns(self, tmp_path):
        """security_mode has the expected columns."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        cols = _get_table_columns(
            get_connection(db_path).cursor(), "security_mode"
        )

        expected = {"id", "mode", "updated_at", "updated_by", "auto_restore_at"}
        assert set(cols.keys()) == expected

    def test_default_row_seeded(self, tmp_path):
        """security_mode is seeded with id=1, mode='standard'."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        cur = get_connection(db_path).cursor()
        cur.execute("SELECT id, mode FROM security_mode")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] == "standard"

    def test_singleton_constraint(self, tmp_path):
        """Cannot insert a second row into security_mode."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        conn = get_connection(db_path)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO security_mode (id, mode) VALUES (2, 'lockdown')"
            )


# ---------------------------------------------------------------------------
# Cross-cutting concerns
# ---------------------------------------------------------------------------


class TestIdempotentCreation:
    """Calling init_db() twice must not raise or lose data."""

    def test_double_init_no_error(self, tmp_path):
        """init_db() is safe to call twice."""
        from spellbook_mcp.db import init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        init_db(db_path)  # Must not raise

    def test_double_init_preserves_security_mode_default(self, tmp_path):
        """Second init_db() does not duplicate or overwrite the default row."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        conn = get_connection(db_path)

        # Update the mode to something else
        conn.execute(
            "UPDATE security_mode SET mode='lockdown' WHERE id=1"
        )
        conn.commit()

        # Re-init
        init_db(db_path)

        cur = conn.cursor()
        cur.execute("SELECT mode FROM security_mode WHERE id=1")
        row = cur.fetchone()
        # INSERT OR IGNORE should not overwrite the existing row
        assert row[0] == "lockdown"

    def test_double_init_preserves_all_tables(self, tmp_path):
        """All 4 security tables still exist after a second init_db()."""
        from spellbook_mcp.db import get_connection, init_db

        db_path = str(tmp_path / "test.db")
        init_db(db_path)
        init_db(db_path)

        cur = get_connection(db_path).cursor()
        for table in (
            "trust_registry",
            "security_events",
            "canary_tokens",
            "security_mode",
        ):
            assert _table_exists(cur, table), f"{table} missing after double init"
