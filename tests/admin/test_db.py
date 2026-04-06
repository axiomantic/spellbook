import pytest
import sqlite3
import bigfoot


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
async def test_query_spellbook_db_returns_list(tmp_path, monkeypatch):
    """Test async DB query wrapper returns list of dicts."""
    from spellbook.admin.db import query_spellbook_db

    mock_conn = _make_test_db(tmp_path)

    monkeypatch.setattr("spellbook.core.db.get_connection", lambda *a, **kw: mock_conn)

    results = await query_spellbook_db("SELECT id, name FROM test ORDER BY id")

    assert len(results) == 2
    assert results[0] == {"id": 1, "name": "hello"}
    assert results[1] == {"id": 2, "name": "world"}


@pytest.mark.asyncio
async def test_query_spellbook_db_with_params(tmp_path, monkeypatch):
    """Test that query parameters are passed correctly."""
    from spellbook.admin.db import query_spellbook_db

    mock_conn = _make_test_db(tmp_path)

    monkeypatch.setattr("spellbook.core.db.get_connection", lambda *a, **kw: mock_conn)

    results = await query_spellbook_db(
        "SELECT id, name FROM test WHERE id = ?", (2,)
    )

    assert len(results) == 1
    assert results[0]["name"] == "world"


@pytest.mark.asyncio
async def test_query_spellbook_db_runs_in_thread(monkeypatch):
    """Verify the query runs via asyncio.to_thread (not blocking)."""
    from spellbook.admin.db import query_spellbook_db
    import threading

    call_thread_ids = []

    class StubCursor:
        def fetchall(self):
            return []

    class StubConn:
        def execute(self, *args, **kwargs):
            return StubCursor()

    def mock_get_connection(*a, **kw):
        call_thread_ids.append(threading.current_thread().ident)
        return StubConn()

    main_thread_id = threading.current_thread().ident

    monkeypatch.setattr("spellbook.core.db.get_connection", mock_get_connection)

    await query_spellbook_db("SELECT 1")

    proxy.assert_call(args=(), kwargs={})
    # The DB work should have run on a different thread
    assert len(call_thread_ids) == 1
    assert call_thread_ids[0] != main_thread_id
