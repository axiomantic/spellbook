import pytest
import sqlite3
from unittest.mock import patch, MagicMock


def _make_test_db(tmp_path):
    """Create a test DB and return a cross-thread-safe connection."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'hello')")
    conn.execute("INSERT INTO test VALUES (2, 'world')")
    conn.commit()
    conn.close()

    # check_same_thread=False matches real get_connection() behavior
    mock_conn = sqlite3.connect(db_path, check_same_thread=False)
    mock_conn.row_factory = sqlite3.Row
    return mock_conn


@pytest.mark.asyncio
async def test_query_spellbook_db_returns_list(tmp_path):
    """Test async DB query wrapper returns list of dicts."""
    from spellbook.admin.db import query_spellbook_db

    mock_conn = _make_test_db(tmp_path)

    with patch("spellbook.core.db.get_connection", return_value=mock_conn):
        results = await query_spellbook_db("SELECT id, name FROM test ORDER BY id")
        assert len(results) == 2
        assert results[0] == {"id": 1, "name": "hello"}
        assert results[1] == {"id": 2, "name": "world"}


@pytest.mark.asyncio
async def test_query_spellbook_db_with_params(tmp_path):
    """Test that query parameters are passed correctly."""
    from spellbook.admin.db import query_spellbook_db

    mock_conn = _make_test_db(tmp_path)

    with patch("spellbook.core.db.get_connection", return_value=mock_conn):
        results = await query_spellbook_db(
            "SELECT id, name FROM test WHERE id = ?", (2,)
        )
        assert len(results) == 1
        assert results[0]["name"] == "world"


@pytest.mark.asyncio
async def test_execute_spellbook_db_returns_rowcount(tmp_path):
    """Test write query returns affected row count."""
    from spellbook.admin.db import execute_spellbook_db

    mock_conn = _make_test_db(tmp_path)

    with patch("spellbook.core.db.get_connection", return_value=mock_conn):
        affected = await execute_spellbook_db(
            "UPDATE test SET name = ? WHERE id = ?", ("updated", 1)
        )
        assert affected == 1


@pytest.mark.asyncio
async def test_query_spellbook_db_runs_in_thread():
    """Verify the query runs via asyncio.to_thread (not blocking)."""
    from spellbook.admin.db import query_spellbook_db
    import threading

    call_thread_ids = []

    def mock_get_connection():
        call_thread_ids.append(threading.current_thread().ident)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        return mock_conn

    main_thread_id = threading.current_thread().ident

    with patch("spellbook.core.db.get_connection", side_effect=mock_get_connection):
        await query_spellbook_db("SELECT 1")

    # The DB work should have run on a different thread
    assert len(call_thread_ids) == 1
    assert call_thread_ids[0] != main_thread_id


@pytest.mark.asyncio
async def test_query_coordination_db_returns_empty_for_missing_db(tmp_path):
    """Test coordination DB returns empty list when DB file doesn't exist."""
    from spellbook.admin.db import query_coordination_db

    with patch("spellbook.admin.db.Path.home", return_value=tmp_path):
        results = await query_coordination_db("SELECT 1")
        assert results == []
