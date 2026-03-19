"""Tests for DB file permission hardening and connection health (Findings #9, #10)."""

import os
import sys
import stat
import sqlite3
import time

import pytest
from pathlib import Path
from unittest.mock import patch

from spellbook import db as db_module


@pytest.mark.skipif(sys.platform == "win32", reason="Unix permissions only")
class TestDBFilePermissions:
    """DB files and directories must have restrictive permissions."""

    def test_db_directory_has_0700_permissions(self, tmp_path):
        """DB directory created by get_db_path must be owner-only (0700).

        ESCAPE: test_db_directory_has_0700_permissions
          CLAIM: get_db_path sets directory permissions to 0700
          PATH: get_db_path() -> mkdir -> chmod
          CHECK: Exact octal permission match on directory
          MUTATION: Removing os.chmod(db_dir, 0o700) causes failure
          ESCAPE: If chmod silently fails (returns success but doesn't change perms).
                  Mitigated: we check actual stat, not return value.
          IMPACT: Other users on shared system can read DB containing session state.
        """
        from spellbook.core.db import get_db_path

        with pytest.MonkeyPatch().context() as m:
            m.setattr(Path, "home", lambda: tmp_path)
            db_path = get_db_path()
            db_dir = db_path.parent
            mode = stat.S_IMODE(db_dir.stat().st_mode)
            assert mode == 0o700

    def test_db_file_has_0600_permissions(self, tmp_path):
        """DB file must be owner-only readable/writable (0600) after get_connection.

        ESCAPE: test_db_file_has_0600_permissions
          CLAIM: get_connection sets file permissions to 0600
          PATH: get_connection() -> sqlite3.connect -> os.chmod
          CHECK: Exact octal permission match on file
          MUTATION: Removing os.chmod(db_path, 0o600) causes failure
          ESCAPE: If the file system ignores chmod (e.g. FAT32).
                  Mitigated: test runs on Unix with tmp_path (real FS).
          IMPACT: Other users can read/write the DB, enabling data theft or corruption.
        """
        from spellbook.core.db import get_connection, init_db, _connections, _connections_lock

        db_path = str(tmp_path / "test.db")

        # Clear any cached connections for this path
        with _connections_lock:
            _connections.pop(db_path, None)

        init_db(db_path)
        get_connection(db_path)

        mode = stat.S_IMODE(os.stat(db_path).st_mode)
        assert mode == 0o600


class TestConnectionHealthCheck:
    """Cached connections must be health-checked and TTL-limited (Finding #10)."""

    def setup_method(self):
        """Clear connection cache before each test."""
        with db_module._connections_lock:
            db_module._connections.clear()

    def test_stale_connection_replaced(self, tmp_path):
        """A broken cached connection must be replaced with a new one.

        ESCAPE: test_stale_connection_replaced
          CLAIM: get_connection detects broken connections and creates new ones
          PATH: get_connection() -> SELECT 1 health check fails -> reconnect
          CHECK: New connection works (SELECT 1 succeeds), is different object
          MUTATION: Removing health check (SELECT 1) causes sqlite3.ProgrammingError
          ESCAPE: If close() doesn't actually close (implementation detail of sqlite3).
                  Mitigated: we test the observable behavior (new conn works).
          IMPACT: Cached broken connections cause all DB operations to fail.
        """
        db_path = str(tmp_path / "test.db")
        db_module.init_db(db_path)

        # Get a connection (caches it)
        conn1 = db_module.get_connection(db_path)
        conn1_id = id(conn1)

        # Close the underlying connection to simulate corruption
        conn1.close()

        # Next call should detect the broken connection and create a new one
        conn2 = db_module.get_connection(db_path)
        conn2_id = id(conn2)

        # Must be a different (new) connection object
        assert conn2_id != conn1_id
        # Must be functional
        result = conn2.execute("SELECT 1").fetchone()
        assert result == (1,)

    def test_ttl_expired_connection_replaced(self, tmp_path):
        """A connection past its TTL must be replaced.

        ESCAPE: test_ttl_expired_connection_replaced
          CLAIM: get_connection replaces connections older than TTL
          PATH: get_connection() -> check created_at -> time exceeds TTL -> reconnect
          CHECK: New connection is a different object and is functional
          MUTATION: Removing TTL check means old connections are reused forever
          ESCAPE: If time.time() is mocked incorrectly. Mitigated: we directly
                  manipulate the cache tuple timestamp.
          IMPACT: Connections held open indefinitely accumulate leaked resources.
        """
        db_path = str(tmp_path / "test.db")
        db_module.init_db(db_path)

        conn1 = db_module.get_connection(db_path)
        conn1_id = id(conn1)

        # Simulate TTL expiration by manipulating the stored timestamp
        with db_module._connections_lock:
            if db_path in db_module._connections:
                conn, _ = db_module._connections[db_path]
                # Set created_at to 2 hours ago (well past any reasonable TTL)
                db_module._connections[db_path] = (conn, time.time() - 7200)

        conn2 = db_module.get_connection(db_path)
        conn2_id = id(conn2)

        # Must be a different (new) connection object
        assert conn2_id != conn1_id
        # Must be functional
        result = conn2.execute("SELECT 1").fetchone()
        assert result == (1,)

    def test_healthy_connection_reused(self, tmp_path):
        """A healthy cached connection within TTL must be reused (not recreated).

        ESCAPE: test_healthy_connection_reused
          CLAIM: get_connection returns the same cached connection when healthy
          PATH: get_connection() -> found in cache -> SELECT 1 passes -> return same
          CHECK: Same object identity (is)
          MUTATION: Always creating new connections would fail identity check
          ESCAPE: If caching is broken in a way that returns equal but not identical
                  objects. Mitigated: `is` checks identity, not equality.
          IMPACT: Creating new connections on every call wastes resources and breaks
                  transactions.
        """
        db_path = str(tmp_path / "test.db")
        db_module.init_db(db_path)

        conn1 = db_module.get_connection(db_path)
        conn2 = db_module.get_connection(db_path)
        assert conn1 is conn2

    def test_close_all_connections_works_with_ttl_cache(self, tmp_path):
        """close_all_connections must handle the (conn, timestamp) tuple format.

        ESCAPE: test_close_all_connections_works_with_ttl_cache
          CLAIM: close_all_connections handles new tuple cache format without error
          PATH: close_all_connections() -> iterate (conn, created_at) tuples -> close each
          CHECK: No exception raised, cache is empty after call
          MUTATION: Not unpacking tuple causes TypeError on conn.close()
          ESCAPE: Nothing reasonable; we verify both no-error and empty cache.
          IMPACT: Test cleanup and shutdown would crash, leaking connections.
        """
        db_path = str(tmp_path / "test.db")
        db_module.init_db(db_path)
        db_module.get_connection(db_path)

        # Should not raise
        db_module.close_all_connections()

        # Cache should be empty
        with db_module._connections_lock:
            assert db_module._connections == {}
