"""Tests for session content accumulator."""
import os
import pytest


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    os.environ["SPELLBOOK_DB_PATH"] = path
    from spellbook.core.db import init_db
    init_db(path)
    yield path
    os.environ.pop("SPELLBOOK_DB_PATH", None)


def test_accumulator_write_creates_entry(db_path):
    from spellbook.security.accumulator import do_accumulator_write
    result = do_accumulator_write(
        session_id="sess-1",
        content_hash="abc123",
        source_tool="WebFetch",
        content_summary="test content",
        content_size=100,
        db_path=db_path,
    )
    assert result["success"] is True
    assert result["entries_count"] >= 1


def test_accumulator_status_empty(db_path):
    from spellbook.security.accumulator import do_accumulator_status
    result = do_accumulator_status(session_id="sess-empty", db_path=db_path)
    assert result["entries"] == 0


def test_accumulator_status_after_writes(db_path):
    from spellbook.security.accumulator import do_accumulator_write, do_accumulator_status
    for i in range(3):
        do_accumulator_write(
            session_id="sess-2",
            content_hash=f"hash-{i}",
            source_tool="WebFetch",
            content_summary=f"content {i}",
            content_size=50,
            db_path=db_path,
        )
    result = do_accumulator_status(session_id="sess-2", db_path=db_path)
    assert result["entries"] == 3
    assert "WebFetch" in result["sources"]
    assert result["sources"]["WebFetch"] == 3


def test_accumulator_alerts_on_repeated_source(db_path):
    from spellbook.security.accumulator import do_accumulator_write, do_accumulator_status
    for i in range(4):
        do_accumulator_write(
            session_id="sess-3",
            content_hash=f"hash-{i}",
            source_tool="WebFetch",
            content_summary=f"content {i}",
            content_size=50,
            db_path=db_path,
        )
    result = do_accumulator_status(session_id="sess-3", db_path=db_path)
    alerts = [a for a in result.get("alerts", []) if a["type"] == "repeated_source"]
    assert len(alerts) >= 1
    assert alerts[0]["tool"] == "WebFetch"


def test_accumulator_cleanup_expired(db_path):
    """Expired entries should be cleaned up on write."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    # Insert an already-expired entry
    conn.execute(
        "INSERT INTO session_content_accumulator "
        "(session_id, content_hash, source_tool, content_size, "
        "received_at, expires_at) VALUES (?, ?, ?, ?, datetime('now'), datetime('now', '-1 hour'))",
        ("sess-4", "old-hash", "WebFetch", 10),
    )
    conn.commit()
    conn.close()

    from spellbook.security.accumulator import do_accumulator_write
    do_accumulator_write(
        session_id="sess-4",
        content_hash="new-hash",
        source_tool="WebFetch",
        content_summary="new",
        content_size=20,
        db_path=db_path,
    )

    # Check that expired entry was cleaned
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM session_content_accumulator WHERE session_id='sess-4'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1  # Only the new entry remains
