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


class TestRecallByQueryScope:
    @pytest.fixture(autouse=True)
    def seed_memories(self, db_path):
        """Seed DB with project and global memories for recall tests."""
        insert_memory(
            db_path=db_path,
            content="SQLAlchemy uses session pattern",
            memory_type="fact",
            namespace="proj-a",
            tags=["sqlalchemy", "orm"],
            citations=[],
            scope="project",
        )
        insert_memory(
            db_path=db_path,
            content="SQLite WAL is single-writer",
            memory_type="fact",
            namespace="proj-a",
            tags=["sqlite", "wal"],
            citations=[],
            scope="global",
        )
        insert_memory(
            db_path=db_path,
            content="Redis caching pattern",
            memory_type="fact",
            namespace="proj-b",
            tags=["redis", "cache"],
            citations=[],
            scope="project",
        )

    def test_recall_project_scope_default(self, db_path):
        """scope='project' returns only project-scoped memories in namespace."""
        from spellbook.memory.store import recall_by_query

        results = recall_by_query(
            db_path=db_path,
            query="",
            namespace="proj-a",
            scope="project",
        )
        assert len(results) == 1
        assert results[0]["content"] == "SQLAlchemy uses session pattern"

    def test_recall_global_scope(self, db_path):
        """scope='global' returns only global-scoped memories (any namespace)."""
        from spellbook.memory.store import recall_by_query

        results = recall_by_query(
            db_path=db_path,
            query="",
            namespace="proj-a",
            scope="global",
        )
        assert len(results) == 1
        assert results[0]["content"] == "SQLite WAL is single-writer"

    def test_recall_all_scope(self, db_path):
        """scope='all' returns project memories + global memories."""
        from spellbook.memory.store import recall_by_query

        results = recall_by_query(
            db_path=db_path,
            query="",
            namespace="proj-a",
            scope="all",
        )
        assert len(results) == 2
        contents = {r["content"] for r in results}
        assert contents == {
            "SQLAlchemy uses session pattern",
            "SQLite WAL is single-writer",
        }

    def test_recall_project_excludes_global(self, db_path):
        """scope='project' does not return global memories."""
        from spellbook.memory.store import recall_by_query

        results = recall_by_query(
            db_path=db_path,
            query="",
            namespace="proj-a",
            scope="project",
        )
        contents = {r["content"] for r in results}
        assert "SQLite WAL is single-writer" not in contents

    def test_recall_global_excludes_project(self, db_path):
        """scope='global' does not return project memories."""
        from spellbook.memory.store import recall_by_query

        results = recall_by_query(
            db_path=db_path,
            query="",
            namespace="proj-a",
            scope="global",
        )
        contents = {r["content"] for r in results}
        assert "SQLAlchemy uses session pattern" not in contents

    def test_cross_namespace_global_recall(self, db_path):
        """Global memories are visible from any namespace with scope='all'."""
        from spellbook.memory.store import recall_by_query

        results = recall_by_query(
            db_path=db_path,
            query="",
            namespace="proj-b",
            scope="all",
        )
        contents = {r["content"] for r in results}
        # proj-b project memory + global memory
        assert contents == {
            "Redis caching pattern",
            "SQLite WAL is single-writer",
        }

    def test_fts5_recall_with_scope_all(self, db_path):
        """FTS5 query with scope='all' returns both project and global matches."""
        from spellbook.memory.store import recall_by_query

        results = recall_by_query(
            db_path=db_path,
            query="pattern",
            namespace="proj-a",
            scope="all",
        )
        # "SQLAlchemy uses session pattern" (project) should match
        assert len(results) >= 1

    def test_scope_field_in_results(self, db_path):
        """Returned memory dicts include the scope field."""
        from spellbook.memory.store import recall_by_query

        results = recall_by_query(
            db_path=db_path,
            query="",
            namespace="proj-a",
            scope="all",
        )
        for r in results:
            assert "scope" in r
            assert r["scope"] in ("project", "global")


class TestRecallByFilePathScope:
    @pytest.fixture(autouse=True)
    def seed_memories(self, db_path):
        """Seed DB with cited memories in different scopes."""
        insert_memory(
            db_path=db_path,
            content="Config patterns for auth module",
            memory_type="fact",
            namespace="proj-a",
            tags=["config"],
            citations=[{"file_path": "/src/auth.py"}],
            scope="project",
        )
        insert_memory(
            db_path=db_path,
            content="Global auth best practices",
            memory_type="rule",
            namespace="proj-a",
            tags=["auth"],
            citations=[{"file_path": "/src/auth.py"}],
            scope="global",
        )

    def test_file_path_recall_project_scope(self, db_path):
        """scope='project' only returns project-scoped file citations."""
        from spellbook.memory.store import recall_by_file_path

        results = recall_by_file_path(
            db_path=db_path,
            file_path="/src/auth.py",
            namespace="proj-a",
            scope="project",
        )
        assert len(results) == 1
        assert results[0]["content"] == "Config patterns for auth module"

    def test_file_path_recall_all_scope(self, db_path):
        """scope='all' returns both project and global citations."""
        from spellbook.memory.store import recall_by_file_path

        results = recall_by_file_path(
            db_path=db_path,
            file_path="/src/auth.py",
            namespace="proj-a",
            scope="all",
        )
        assert len(results) == 2
        contents = {r["content"] for r in results}
        assert contents == {
            "Config patterns for auth module",
            "Global auth best practices",
        }

    def test_file_path_recall_scope_in_results(self, db_path):
        """File path recall results include scope field."""
        from spellbook.memory.store import recall_by_file_path

        results = recall_by_file_path(
            db_path=db_path,
            file_path="/src/auth.py",
            namespace="proj-a",
            scope="all",
        )
        for r in results:
            assert "scope" in r
            assert r["scope"] in ("project", "global")


class TestDoMemoryRecallScope:
    def test_do_recall_passes_scope(self, db_path):
        """do_memory_recall passes scope to recall_by_query."""
        from spellbook.memory.tools import do_memory_recall

        insert_memory(
            db_path=db_path,
            content="Global fact about testing",
            memory_type="fact",
            namespace="proj-a",
            tags=["testing"],
            citations=[],
            scope="global",
        )
        result = do_memory_recall(
            db_path=db_path,
            query="",
            namespace="proj-a",
            scope="global",
        )
        assert result["count"] == 1
        assert result["memories"][0]["scope"] == "global"

    def test_do_recall_default_scope_is_project(self, db_path):
        """do_memory_recall defaults to scope='project'."""
        from spellbook.memory.tools import do_memory_recall

        insert_memory(
            db_path=db_path,
            content="Project fact",
            memory_type="fact",
            namespace="proj-a",
            tags=["test"],
            citations=[],
            scope="project",
        )
        insert_memory(
            db_path=db_path,
            content="Global fact",
            memory_type="fact",
            namespace="proj-a",
            tags=["test"],
            citations=[],
            scope="global",
        )
        result = do_memory_recall(
            db_path=db_path,
            query="",
            namespace="proj-a",
        )
        # Default scope=project should exclude global
        assert result["count"] == 1
        assert result["memories"][0]["content"] == "Project fact"


class TestDoStoreMemoriesScope:
    def test_store_with_global_scope(self, db_path):
        """do_store_memories passes scope through to insert_memory."""
        import json

        from spellbook.memory.tools import do_memory_recall, do_store_memories

        memories = json.dumps({
            "memories": [{"content": "Global convention", "memory_type": "rule"}]
        })
        result = do_store_memories(
            db_path=db_path,
            memories_json=memories,
            namespace="proj-a",
            scope="global",
        )
        assert result["status"] == "success"
        assert result["memories_created"] == 1

        # Verify it was stored with global scope
        recall = do_memory_recall(
            db_path=db_path,
            query="",
            namespace="proj-a",
            scope="global",
        )
        assert recall["count"] == 1
        assert recall["memories"][0]["scope"] == "global"
