import pytest
import tripwire
from dirty_equals import AnyThing
import sqlite3


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

    get_connection_mock = tripwire.mock("spellbook.core.db:get_connection")
    get_connection_mock.calls(lambda *a, **kw: mock_conn)

    with tripwire:
        results = await query_spellbook_db("SELECT id, name FROM test ORDER BY id")

        assert len(results) == 2
        assert results[0] == {"id": 1, "name": "hello"}
        assert results[1] == {"id": 2, "name": "world"}

    get_connection_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing, raised=AnyThing)


@pytest.mark.asyncio
async def test_query_spellbook_db_with_params(tmp_path):
    """Test that query parameters are passed correctly."""
    from spellbook.admin.db import query_spellbook_db

    mock_conn = _make_test_db(tmp_path)

    get_connection_mock = tripwire.mock("spellbook.core.db:get_connection")
    get_connection_mock.calls(lambda *a, **kw: mock_conn)

    with tripwire:
        results = await query_spellbook_db(
            "SELECT id, name FROM test WHERE id = ?", (2,)
        )

        assert len(results) == 1
        assert results[0]["name"] == "world"

    get_connection_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing, raised=AnyThing)


@pytest.mark.asyncio
async def test_query_spellbook_db_runs_in_thread():
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

    get_connection_mock = tripwire.mock("spellbook.core.db:get_connection")
    get_connection_mock.calls(mock_get_connection)

    with tripwire:
        await query_spellbook_db("SELECT 1")

        # The DB work should have run on a different thread
        assert len(call_thread_ids) == 1
        assert call_thread_ids[0] != main_thread_id

    get_connection_mock.assert_call(args=AnyThing, kwargs=AnyThing, returned=AnyThing, raised=AnyThing)
