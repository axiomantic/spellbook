"""Tests for session watcher thread."""

import pytest
import time
import sqlite3
from pathlib import Path
from datetime import datetime


def test_watcher_starts_and_stops(tmp_path):
    """Test watcher thread lifecycle."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path))
    thread = watcher.start()

    assert thread.is_alive()
    assert watcher.is_running()

    watcher.stop()
    thread.join(timeout=2.0)

    assert not thread.is_alive()
    assert not watcher.is_running()


def test_watcher_writes_heartbeat(tmp_path):
    """Test that watcher updates heartbeat periodically."""
    from spellbook_mcp.watcher import SessionWatcher
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    watcher = SessionWatcher(str(db_path), poll_interval=0.5)
    thread = watcher.start()

    # Wait for at least 2 heartbeats
    time.sleep(1.5)

    # Check heartbeat was written
    conn = get_connection(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp FROM heartbeat WHERE id = 1")
    row = cursor.fetchone()

    assert row is not None
    heartbeat = datetime.fromisoformat(row[0])
    age = (datetime.now() - heartbeat).total_seconds()

    assert age < 2.0  # Should be very recent

    watcher.stop()
    thread.join(timeout=2.0)


def test_watcher_heartbeat_freshness_check(tmp_path):
    """Test heartbeat freshness validation."""
    from spellbook_mcp.watcher import is_heartbeat_fresh
    from spellbook_mcp.db import init_db, get_connection

    db_path = tmp_path / "test.db"
    init_db(str(db_path))

    # No heartbeat yet
    assert not is_heartbeat_fresh(str(db_path))

    # Insert fresh heartbeat
    conn = get_connection(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
        (datetime.now().isoformat(),)
    )
    conn.commit()

    assert is_heartbeat_fresh(str(db_path))

    # Insert stale heartbeat (40 seconds ago)
    stale_time = datetime.now().timestamp() - 40
    conn.execute(
        "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
        (datetime.fromtimestamp(stale_time).isoformat(),)
    )
    conn.commit()

    assert not is_heartbeat_fresh(str(db_path))
