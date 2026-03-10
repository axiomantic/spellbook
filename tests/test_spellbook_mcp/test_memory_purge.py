"""Tests for memory_purge_topic feature: topic-based memory deletion across all layers."""

import json
import os

import pytest
from spellbook_mcp.db import init_db, get_connection, close_all_connections
from spellbook_mcp.memory_store import (
    insert_memory,
    get_memory,
    log_raw_event,
    search_memories_by_topic,
    delete_raw_events_by_topic,
)


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    yield db_path
    close_all_connections()


# ---------------------------------------------------------------------------
# Fixtures for filesystem layers
# ---------------------------------------------------------------------------


@pytest.fixture
def understanding_dir(tmp_path):
    """Temp directory simulating understanding docs for a project."""
    docs_dir = tmp_path / "docs" / "project-ns" / "understanding"
    docs_dir.mkdir(parents=True)
    return docs_dir


@pytest.fixture
def auto_memory_dir(tmp_path):
    """Temp directory simulating auto-memory files for a project."""
    mem_dir = tmp_path / "docs" / "project-ns" / "auto-memory"
    mem_dir.mkdir(parents=True)
    return mem_dir


# ===========================================================================
# DB-level tests: search_memories_by_topic
# ===========================================================================


class TestSearchMemoriesByTopic:
    """Tests for search_memories_by_topic in memory_store.py."""

    def test_finds_matching_memories(self, db):
        """FTS query returns memories whose content matches the topic."""
        mem_id = insert_memory(
            db_path=db,
            content="FastAPI uses dependency injection for request handling",
            memory_type="fact",
            namespace="project-ns",
            tags=["fastapi", "dependency-injection"],
            citations=[],
        )
        results = search_memories_by_topic(db, "FastAPI", namespace="project-ns")
        assert len(results) >= 1
        match = results[0]
        assert match["id"] == mem_id
        assert "content" in match
        assert "created_at" in match

    def test_returns_empty_list_when_no_matches(self, db):
        """Query with no matching memories returns empty list."""
        insert_memory(
            db_path=db,
            content="Django uses ORM for database access",
            memory_type="fact",
            namespace="project-ns",
            tags=["django"],
            citations=[],
        )
        results = search_memories_by_topic(db, "kubernetes", namespace="project-ns")
        assert results == []

    def test_respects_namespace_scoping(self, db):
        """Memories from other namespaces are not returned."""
        insert_memory(
            db_path=db,
            content="FastAPI in project alpha",
            memory_type="fact",
            namespace="project-alpha",
            tags=["fastapi"],
            citations=[],
        )
        insert_memory(
            db_path=db,
            content="FastAPI in project beta",
            memory_type="fact",
            namespace="project-beta",
            tags=["fastapi"],
            citations=[],
        )
        results = search_memories_by_topic(db, "FastAPI", namespace="project-alpha")
        assert len(results) == 1
        assert results[0]["content"] == "FastAPI in project alpha"

    def test_returns_id_content_created_at(self, db):
        """Each result contains id, content (or snippet), and created_at."""
        insert_memory(
            db_path=db,
            content="SQLAlchemy manages database connections via engine pools",
            memory_type="fact",
            namespace="project-ns",
            tags=["sqlalchemy"],
            citations=[],
        )
        results = search_memories_by_topic(db, "SQLAlchemy", namespace="project-ns")
        assert len(results) == 1
        result = results[0]
        assert "id" in result
        assert isinstance(result["id"], str)
        assert len(result["id"]) == 36  # UUID4
        assert "content" in result
        assert "created_at" in result
        assert isinstance(result["created_at"], str)

    def test_finds_multiple_matches(self, db):
        """Multiple memories matching the topic are all returned."""
        insert_memory(
            db_path=db,
            content="Redis is used for caching",
            memory_type="fact",
            namespace="ns",
            tags=["redis"],
            citations=[],
        )
        insert_memory(
            db_path=db,
            content="Redis pub/sub handles real-time notifications",
            memory_type="fact",
            namespace="ns",
            tags=["redis"],
            citations=[],
        )
        results = search_memories_by_topic(db, "Redis", namespace="ns")
        assert len(results) == 2


# ===========================================================================
# DB-level tests: delete_raw_events_by_topic
# ===========================================================================


class TestDeleteRawEventsByTopic:
    """Tests for delete_raw_events_by_topic in memory_store.py."""

    def test_finds_raw_events_by_summary(self, db):
        """Finds raw events whose summary matches the LIKE query."""
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-ns",
            event_type="tool_use",
            tool_name="Read",
            subject="src/auth.py",
            summary="Read authentication module src/auth.py",
            tags="auth,python",
        )
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-ns",
            event_type="tool_use",
            tool_name="Read",
            subject="src/db.py",
            summary="Read database module src/db.py",
            tags="database,python",
        )
        result = delete_raw_events_by_topic(
            db, "authentication", namespace="project-ns", dry_run=True,
        )
        assert result["matched"] >= 1

    def test_finds_raw_events_by_tags(self, db):
        """Finds raw events whose tags match the LIKE query."""
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-ns",
            event_type="tool_use",
            tool_name="Edit",
            subject="src/cache.py",
            summary="Edited cache layer",
            tags="redis,caching,performance",
        )
        result = delete_raw_events_by_topic(
            db, "redis", namespace="project-ns", dry_run=True,
        )
        assert result["matched"] >= 1

    def test_dry_run_does_not_delete(self, db):
        """dry_run=True returns matches without actually deleting."""
        eid = log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-ns",
            event_type="tool_use",
            tool_name="Read",
            subject="src/auth.py",
            summary="Read auth module",
            tags="auth",
        )
        result = delete_raw_events_by_topic(
            db, "auth", namespace="project-ns", dry_run=True,
        )
        assert result["matched"] >= 1
        assert result.get("deleted", 0) == 0

        # Verify event still exists
        conn = get_connection(db)
        cursor = conn.execute("SELECT COUNT(*) FROM raw_events WHERE id = ?", (eid,))
        assert cursor.fetchone()[0] == 1

    def test_execute_deletes_matching_events(self, db):
        """dry_run=False actually deletes matching raw events."""
        eid = log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-ns",
            event_type="tool_use",
            tool_name="Read",
            subject="src/auth.py",
            summary="Read auth module",
            tags="auth",
        )
        result = delete_raw_events_by_topic(
            db, "auth", namespace="project-ns", dry_run=False,
        )
        assert result["deleted"] >= 1

        # Verify event was actually removed
        conn = get_connection(db)
        cursor = conn.execute("SELECT COUNT(*) FROM raw_events WHERE id = ?", (eid,))
        assert cursor.fetchone()[0] == 0

    def test_respects_namespace_scoping(self, db):
        """Only deletes events from the specified namespace/project."""
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-alpha",
            event_type="tool_use",
            tool_name="Read",
            subject="src/auth.py",
            summary="Read auth module",
            tags="auth",
        )
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-beta",
            event_type="tool_use",
            tool_name="Read",
            subject="src/auth.py",
            summary="Read auth module",
            tags="auth",
        )
        result = delete_raw_events_by_topic(
            db, "auth", namespace="project-alpha", dry_run=False,
        )
        assert result["deleted"] == 1

        # Verify project-beta event is untouched
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM raw_events WHERE project = 'project-beta'"
        )
        assert cursor.fetchone()[0] == 1

    def test_returns_accurate_counts(self, db):
        """Returned counts match actual number of matching/deleted events."""
        for i in range(3):
            log_raw_event(
                db_path=db,
                session_id="sess-1",
                project="ns",
                event_type="tool_use",
                tool_name="Read",
                subject=f"src/auth_{i}.py",
                summary=f"Read auth module {i}",
                tags="auth",
            )
        # One non-matching event
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="ns",
            event_type="tool_use",
            tool_name="Read",
            subject="src/db.py",
            summary="Read database module",
            tags="database",
        )
        dry_result = delete_raw_events_by_topic(
            db, "auth", namespace="ns", dry_run=True,
        )
        assert dry_result["matched"] == 3

        exec_result = delete_raw_events_by_topic(
            db, "auth", namespace="ns", dry_run=False,
        )
        assert exec_result["deleted"] == 3

        # Non-matching event remains
        conn = get_connection(db)
        cursor = conn.execute("SELECT COUNT(*) FROM raw_events WHERE project = 'ns'")
        assert cursor.fetchone()[0] == 1


# ===========================================================================
# Tool-level tests: do_memory_purge_topic
# ===========================================================================


class TestDoMemoryPurgeTopicDryRun:
    """Test do_memory_purge_topic in preview/dry-run mode."""

    def test_dry_run_searches_all_layers(self, db, understanding_dir, auto_memory_dir):
        """Dry run searches memories, raw events, understanding docs, and auto-memory."""
        # Layer 1: memories
        insert_memory(
            db_path=db,
            content="Authentication uses JWT tokens",
            memory_type="fact",
            namespace="project-ns",
            tags=["auth", "jwt"],
            citations=[],
        )
        # Layer 2: raw events
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-ns",
            event_type="tool_use",
            tool_name="Read",
            subject="src/auth.py",
            summary="Read authentication module",
            tags="auth",
        )
        # Layer 3: understanding doc
        doc = understanding_dir / "authentication-patterns.md"
        doc.write_text("# Authentication Patterns\nJWT-based auth flow...\n")
        # Layer 4: auto-memory file
        mem_file = auto_memory_dir / "auth-memories.md"
        mem_file.write_text(
            "## Auth memories\n- JWT tokens expire after 1h\n- Refresh tokens stored in DB\n"
        )

        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="authentication",
            namespace="project-ns",
            dry_run=True,
            understanding_dir=str(understanding_dir),
            auto_memory_dir=str(auto_memory_dir),
        )
        assert result["dry_run"] is True
        assert result["total_found"] > 0
        # Should have findings from at least memories and raw_events layers
        assert "memories" in result
        assert "raw_events" in result

    def test_dry_run_does_not_delete_anything(self, db, understanding_dir, auto_memory_dir):
        """Dry run does NOT modify any data."""
        mem_id = insert_memory(
            db_path=db,
            content="Auth uses JWT tokens",
            memory_type="fact",
            namespace="project-ns",
            tags=["auth", "jwt"],
            citations=[],
        )
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-ns",
            event_type="tool_use",
            tool_name="Read",
            subject="src/auth.py",
            summary="Read auth module",
            tags="auth",
        )
        doc = understanding_dir / "auth-patterns.md"
        doc.write_text("# Auth Patterns\nContent about authentication.\n")

        from spellbook_mcp.memory_tools import do_memory_purge_topic

        do_memory_purge_topic(
            db_path=db,
            topic="auth",
            namespace="project-ns",
            dry_run=True,
            understanding_dir=str(understanding_dir),
            auto_memory_dir=str(auto_memory_dir),
        )

        # Memory still active
        mem = get_memory(db, mem_id)
        assert mem["status"] == "active"

        # Raw event still exists
        conn = get_connection(db)
        cursor = conn.execute("SELECT COUNT(*) FROM raw_events")
        assert cursor.fetchone()[0] == 1

        # Understanding doc still exists
        assert doc.exists()

    def test_dry_run_returns_total_found(self, db):
        """Dry run response includes total_found count."""
        insert_memory(
            db_path=db,
            content="Redis caching layer implementation",
            memory_type="fact",
            namespace="ns",
            tags=["redis"],
            citations=[],
        )
        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="Redis",
            namespace="ns",
            dry_run=True,
        )
        assert "total_found" in result
        assert result["total_found"] >= 1
        assert result["dry_run"] is True


class TestDoMemoryPurgeTopicExecute:
    """Test do_memory_purge_topic in execute mode (dry_run=False)."""

    def test_soft_deletes_matching_memories(self, db):
        """Execute mode soft-deletes matching memories (status='deleted')."""
        mem_id = insert_memory(
            db_path=db,
            content="Authentication uses JWT tokens for session management",
            memory_type="fact",
            namespace="project-ns",
            tags=["auth", "jwt"],
            citations=[],
        )
        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="authentication",
            namespace="project-ns",
            dry_run=False,
        )
        assert result["dry_run"] is False

        # Verify soft-delete
        mem = get_memory(db, mem_id)
        assert mem["status"] == "deleted"
        assert mem["deleted_at"] is not None

    def test_deletes_matching_raw_events(self, db):
        """Execute mode deletes matching raw events."""
        eid = log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-ns",
            event_type="tool_use",
            tool_name="Read",
            subject="src/auth.py",
            summary="Read authentication module",
            tags="auth",
        )
        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="auth",
            namespace="project-ns",
            dry_run=False,
        )
        # Verify deletion
        conn = get_connection(db)
        cursor = conn.execute("SELECT COUNT(*) FROM raw_events WHERE id = ?", (eid,))
        assert cursor.fetchone()[0] == 0

    def test_deletes_matching_understanding_docs(self, db, understanding_dir):
        """Execute mode deletes understanding docs matching the topic."""
        doc = understanding_dir / "authentication-flow.md"
        doc.write_text("# Authentication Flow\nJWT-based auth...\n")
        other_doc = understanding_dir / "database-schema.md"
        other_doc.write_text("# Database Schema\nPostgres tables...\n")

        from spellbook_mcp.memory_tools import do_memory_purge_topic

        do_memory_purge_topic(
            db_path=db,
            topic="authentication",
            namespace="project-ns",
            dry_run=False,
            understanding_dir=str(understanding_dir),
        )
        # Matching doc deleted
        assert not doc.exists()
        # Non-matching doc preserved
        assert other_doc.exists()

    def test_auto_memory_full_delete_when_majority_match(self, db, auto_memory_dir):
        """Auto-memory file with >50% matching lines is fully deleted."""
        mem_file = auto_memory_dir / "auth-notes.md"
        # All lines about auth (>50% match)
        mem_file.write_text(
            "- JWT tokens expire after 1 hour\n"
            "- Authentication middleware validates tokens\n"
            "- Auth errors return 401 status\n"
            "- Token refresh endpoint at /api/auth/refresh\n"
        )

        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="auth",
            namespace="project-ns",
            dry_run=False,
            auto_memory_dir=str(auto_memory_dir),
        )
        # File should be deleted since >50% of lines match
        assert not mem_file.exists()

    def test_auto_memory_flagged_when_minority_match(self, db, auto_memory_dir):
        """Auto-memory file with <=50% matching lines is flagged for manual edit."""
        mem_file = auto_memory_dir / "mixed-notes.md"
        mem_file.write_text(
            "- Database uses PostgreSQL 15\n"
            "- Redis caching with 5min TTL\n"
            "- Authentication uses JWT\n"
            "- Deployment via Docker Compose\n"
            "- CI/CD pipeline runs on GitHub Actions\n"
            "- Monitoring with Prometheus\n"
        )

        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="auth",
            namespace="project-ns",
            dry_run=False,
            auto_memory_dir=str(auto_memory_dir),
        )
        # File should still exist (not auto-deleted)
        assert mem_file.exists()
        # Result should indicate manual review is needed
        assert "auto_memory" in result
        auto_mem_result = result["auto_memory"]
        # Should flag files needing manual edit
        flagged = auto_mem_result.get("flagged_for_review", [])
        assert len(flagged) >= 1

    def test_returns_deletion_counts_per_layer(self, db, understanding_dir, auto_memory_dir):
        """Execute mode returns deletion counts broken down by layer."""
        # Layer 1: memories
        insert_memory(
            db_path=db,
            content="Auth uses JWT",
            memory_type="fact",
            namespace="ns",
            tags=["auth"],
            citations=[],
        )
        # Layer 2: raw events
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="ns",
            event_type="tool_use",
            tool_name="Read",
            subject="auth.py",
            summary="Read auth module",
            tags="auth",
        )
        # Layer 3: understanding doc
        doc = understanding_dir / "auth.md"
        doc.write_text("# Auth\nJWT auth flow.\n")
        # Layer 4: auto-memory (>50% match, will be deleted)
        mem_file = auto_memory_dir / "auth.md"
        mem_file.write_text("- Auth uses JWT\n- Auth middleware\n")

        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="auth",
            namespace="ns",
            dry_run=False,
            understanding_dir=str(understanding_dir),
            auto_memory_dir=str(auto_memory_dir),
        )
        assert result["dry_run"] is False
        assert "memories" in result
        assert "raw_events" in result
        assert "understanding_docs" in result
        assert "auto_memory" in result


# ===========================================================================
# Edge case tests
# ===========================================================================


class TestDoMemoryPurgeTopicEdgeCases:
    """Edge cases and error handling for do_memory_purge_topic."""

    def test_empty_query_returns_error(self, db):
        """Empty or whitespace-only topic returns an error."""
        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="",
            namespace="ns",
            dry_run=True,
        )
        assert result.get("status") == "error"

        result_whitespace = do_memory_purge_topic(
            db_path=db,
            topic="   ",
            namespace="ns",
            dry_run=True,
        )
        assert result_whitespace.get("status") == "error"

    def test_no_matches_returns_zero_counts(self, db):
        """When no data matches the topic, all counts are zero."""
        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="nonexistent-topic-xyz",
            namespace="ns",
            dry_run=True,
        )
        assert result["total_found"] == 0

    def test_no_matches_execute_returns_zero_counts(self, db):
        """Execute mode with no matches completes gracefully with zero counts."""
        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="nonexistent-topic-xyz",
            namespace="ns",
            dry_run=False,
        )
        assert result["total_found"] == 0
        assert result["dry_run"] is False

    def test_filesystem_error_on_delete_handled_gracefully(self, db, tmp_path):
        """Filesystem errors during file deletion are handled gracefully."""
        # Create a read-only directory to simulate permission error
        readonly_dir = tmp_path / "readonly-docs"
        readonly_dir.mkdir()
        doc = readonly_dir / "auth-doc.md"
        doc.write_text("# Auth doc\nAuthentication patterns.\n")
        # Make directory read-only (prevents file deletion on most systems)
        os.chmod(str(readonly_dir), 0o555)

        from spellbook_mcp.memory_tools import do_memory_purge_topic

        try:
            result = do_memory_purge_topic(
                db_path=db,
                topic="auth",
                namespace="ns",
                dry_run=False,
                understanding_dir=str(readonly_dir),
            )
            # Should not raise; should report the error gracefully
            assert result is not None
        finally:
            # Restore permissions for cleanup
            os.chmod(str(readonly_dir), 0o755)

    def test_cross_namespace_isolation(self, db):
        """Purge in one namespace does not affect another namespace's data."""
        # Insert memories in two namespaces
        mem_alpha = insert_memory(
            db_path=db,
            content="Authentication uses JWT in alpha",
            memory_type="fact",
            namespace="project-alpha",
            tags=["auth", "jwt"],
            citations=[],
        )
        mem_beta = insert_memory(
            db_path=db,
            content="Authentication uses JWT in beta",
            memory_type="fact",
            namespace="project-beta",
            tags=["auth", "jwt"],
            citations=[],
        )
        # Insert raw events in two namespaces
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-alpha",
            event_type="tool_use",
            tool_name="Read",
            subject="auth.py",
            summary="Read auth module",
            tags="auth",
        )
        log_raw_event(
            db_path=db,
            session_id="sess-1",
            project="project-beta",
            event_type="tool_use",
            tool_name="Read",
            subject="auth.py",
            summary="Read auth module",
            tags="auth",
        )

        from spellbook_mcp.memory_tools import do_memory_purge_topic

        # Purge only in project-alpha
        do_memory_purge_topic(
            db_path=db,
            topic="auth",
            namespace="project-alpha",
            dry_run=False,
        )

        # Alpha memory should be soft-deleted
        mem_a = get_memory(db, mem_alpha)
        assert mem_a["status"] == "deleted"

        # Beta memory should be untouched
        mem_b = get_memory(db, mem_beta)
        assert mem_b["status"] == "active"

        # Beta raw events should be untouched
        conn = get_connection(db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM raw_events WHERE project = 'project-beta'"
        )
        assert cursor.fetchone()[0] == 1

    def test_nonexistent_dirs_handled_gracefully(self, db):
        """Passing nonexistent understanding/auto-memory dirs does not crash."""
        from spellbook_mcp.memory_tools import do_memory_purge_topic

        result = do_memory_purge_topic(
            db_path=db,
            topic="auth",
            namespace="ns",
            dry_run=False,
            understanding_dir="/tmp/nonexistent-dir-abc123",
            auto_memory_dir="/tmp/nonexistent-dir-def456",
        )
        # Should complete without error
        assert result is not None
        assert result.get("status") != "error"

    def test_preserves_unrelated_memories(self, db):
        """Memories not matching the topic are left untouched."""
        auth_mem = insert_memory(
            db_path=db,
            content="Authentication uses JWT tokens",
            memory_type="fact",
            namespace="ns",
            tags=["auth"],
            citations=[],
        )
        db_mem = insert_memory(
            db_path=db,
            content="PostgreSQL database uses connection pooling",
            memory_type="fact",
            namespace="ns",
            tags=["database", "postgres"],
            citations=[],
        )
        from spellbook_mcp.memory_tools import do_memory_purge_topic

        do_memory_purge_topic(
            db_path=db,
            topic="authentication",
            namespace="ns",
            dry_run=False,
        )

        # Auth memory deleted
        mem_a = get_memory(db, auth_mem)
        assert mem_a["status"] == "deleted"

        # DB memory untouched
        mem_d = get_memory(db, db_mem)
        assert mem_d["status"] == "active"
