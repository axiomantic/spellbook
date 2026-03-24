"""Tests for memory scope (global/project) support."""

import pytest

from spellbook.core.db import close_all_connections, get_connection, init_db
from spellbook.memory.store import insert_memory


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database with schema initialized."""
    path = str(tmp_path / "test.db")
    init_db(path)
    yield path
    close_all_connections()


class TestSchemaMigration:
    def test_scope_column_exists_on_fresh_db(self, db_path):
        """Fresh init_db creates memories table with scope column."""
        conn = get_connection(db_path)
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()
        }
        assert "scope" in cols

    def test_scope_column_default_is_project(self, db_path):
        """Default value for scope column is 'project'."""
        mem_id = insert_memory(
            db_path=db_path,
            content="Test memory",
            memory_type="fact",
            namespace="test-ns",
            tags=["test"],
            citations=[],
        )
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT scope FROM memories WHERE id = ?", (mem_id,)
        ).fetchone()
        assert row[0] == "project"

    def test_scope_index_exists(self, db_path):
        """Index on scope column is created."""
        conn = get_connection(db_path)
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='memories'"
        ).fetchall()
        index_names = {row[0] for row in indexes}
        assert "idx_memories_scope" in index_names

    def test_migration_adds_scope_to_existing_db(self, tmp_path):
        """Upgrading an existing DB without scope column adds it."""
        import sqlite3

        path = str(tmp_path / "legacy.db")
        # Create a minimal legacy DB without scope column
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE memories ("
            "id TEXT PRIMARY KEY, content TEXT NOT NULL, memory_type TEXT, "
            "namespace TEXT NOT NULL, branch TEXT DEFAULT '', "
            "importance REAL DEFAULT 1.0, created_at TEXT NOT NULL, "
            "accessed_at TEXT, status TEXT DEFAULT 'active', "
            "deleted_at TEXT, content_hash TEXT NOT NULL, meta TEXT DEFAULT '{}')"
        )
        conn.execute(
            "INSERT INTO memories (id, content, namespace, created_at, content_hash) "
            "VALUES ('old1', 'legacy', 'ns', '2026-01-01', 'abc123')"
        )
        conn.commit()
        conn.close()

        # Now init_db should migrate
        init_db(path)
        conn = get_connection(path)
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()
        }
        assert "scope" in cols

        # Existing row should have default 'project'
        row = conn.execute("SELECT scope FROM memories WHERE id = 'old1'").fetchone()
        assert row[0] == "project"
        close_all_connections()


class TestInsertMemoryScope:
    def test_store_project_scope_default(self, db_path):
        """Store without scope kwarg defaults to scope='project'."""
        mem_id = insert_memory(
            db_path=db_path,
            content="Project-scoped memory",
            memory_type="fact",
            namespace="proj-a",
            tags=["test"],
            citations=[],
        )
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT scope FROM memories WHERE id = ?", (mem_id,)
        ).fetchone()
        assert row[0] == "project"

    def test_store_global_scope(self, db_path):
        """Store with scope='global' sets scope column to 'global'."""
        mem_id = insert_memory(
            db_path=db_path,
            content="Global memory",
            memory_type="fact",
            namespace="proj-a",
            tags=["test"],
            citations=[],
            scope="global",
        )
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT scope FROM memories WHERE id = ?", (mem_id,)
        ).fetchone()
        assert row[0] == "global"

    def test_dedup_within_scope(self, db_path):
        """Same content + namespace + scope deduplicates (returns existing ID)."""
        id1 = insert_memory(
            db_path=db_path,
            content="Duplicate content",
            memory_type="fact",
            namespace="proj-a",
            tags=["test"],
            citations=[],
            scope="global",
        )
        id2 = insert_memory(
            db_path=db_path,
            content="Duplicate content",
            memory_type="fact",
            namespace="proj-a",
            tags=["test"],
            citations=[],
            scope="global",
        )
        assert id1 == id2

    def test_dedup_across_scopes_allows_duplicates(self, db_path):
        """Same content in different scopes creates separate memories."""
        id1 = insert_memory(
            db_path=db_path,
            content="Cross-scope content",
            memory_type="fact",
            namespace="proj-a",
            tags=["test"],
            citations=[],
            scope="project",
        )
        id2 = insert_memory(
            db_path=db_path,
            content="Cross-scope content",
            memory_type="fact",
            namespace="proj-a",
            tags=["test"],
            citations=[],
            scope="global",
        )
        assert id1 != id2
