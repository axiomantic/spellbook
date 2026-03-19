"""Tests for branch wiring in memory_tools."""

import json
import subprocess

import pytest

from spellbook.core.db import get_connection, init_db, close_all_connections
from spellbook.memory.tools import (
    do_log_event,
    do_memory_recall,
    do_store_memories,
)


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    yield path
    close_all_connections()


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repo with a main branch."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True,
                    capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo,
                    check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo,
                    check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo,
                    check=True, capture_output=True)
    return str(repo)


class TestDoLogEventBranch:
    def test_branch_passed_to_log_raw_event(self, db_path):
        result = do_log_event(
            db_path=db_path,
            session_id="sess1",
            project="test-project",
            tool_name="Read",
            subject="/path/to/file.py",
            summary="Read file",
            branch="feature-x",
        )
        assert result == {"status": "logged", "event_id": result["event_id"]}
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT branch FROM raw_events WHERE id = ?", (result["event_id"],)
        )
        assert cursor.fetchone()[0] == "feature-x"

    def test_branch_defaults_to_empty(self, db_path):
        result = do_log_event(
            db_path=db_path,
            session_id="sess1",
            project="test-project",
            tool_name="Read",
            subject="/path/to/file.py",
            summary="Read file",
        )
        assert result == {"status": "logged", "event_id": result["event_id"]}
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT branch FROM raw_events WHERE id = ?", (result["event_id"],)
        )
        assert cursor.fetchone()[0] == ""


class TestDoMemoryRecallBranch:
    def test_branch_and_repo_path_forwarded(self, db_path, git_repo):
        """do_memory_recall should forward branch/repo_path so scoring activates."""
        from spellbook.core.branch_ancestry import clear_ancestry_cache
        from spellbook.memory.store import insert_memory

        clear_ancestry_cache()
        insert_memory(
            db_path=db_path,
            content="Test recall with branch forwarding",
            memory_type="fact",
            namespace="test-project",
            tags=["test"],
            citations=[],
            branch="main",
        )
        result = do_memory_recall(
            db_path=db_path,
            query="branch forwarding",
            namespace="test-project",
            branch="main",
            repo_path=git_repo,
        )
        assert result["query"] == "branch forwarding"
        assert result["namespace"] == "test-project"
        assert isinstance(result["memories"], list)
        assert result["count"] >= 1
        # Verify branch scoring actually ran by checking branch_relationship field
        for mem in result["memories"]:
            assert "branch_relationship" in mem, (
                "branch_relationship missing - scoring did not activate"
            )

    def test_branch_defaults_to_empty(self, db_path):
        """do_memory_recall should work without branch param (backward compat)."""
        result = do_memory_recall(
            db_path=db_path,
            query="anything",
            namespace="test-project",
        )
        assert result == {
            "memories": [],
            "count": 0,
            "query": "anything",
            "namespace": "test-project",
        }


class TestDoStoreMemoriesBranch:
    def test_branch_passed_to_insert(self, db_path):
        """do_store_memories should pass branch to insert_memory."""
        memories = json.dumps(
            {
                "memories": [
                    {
                        "content": "Test store with branch",
                        "memory_type": "fact",
                        "tags": ["test"],
                        "citations": [],
                    }
                ]
            }
        )
        result = do_store_memories(
            db_path=db_path,
            memories_json=memories,
            namespace="test-project",
            branch="feature-x",
        )
        assert result["status"] == "success"
        assert result["memories_created"] == 1
        # Verify branch was stored in memories table
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT branch FROM memories WHERE id = ?",
            (result["memory_ids"][0],),
        )
        assert cursor.fetchone()[0] == "feature-x"
        # Verify junction table entry
        cursor = conn.execute(
            "SELECT branch_name, association_type FROM memory_branches WHERE memory_id = ?",
            (result["memory_ids"][0],),
        )
        row = cursor.fetchone()
        assert row[0] == "feature-x"
        assert row[1] == "origin"

    def test_branch_defaults_to_empty(self, db_path):
        """do_store_memories should work without branch param (backward compat)."""
        memories = json.dumps(
            {
                "memories": [
                    {
                        "content": "Test store without branch",
                        "memory_type": "fact",
                        "tags": ["test"],
                        "citations": [],
                    }
                ]
            }
        )
        result = do_store_memories(
            db_path=db_path,
            memories_json=memories,
            namespace="test-project",
        )
        assert result["status"] == "success"
        assert result["memories_created"] == 1
        # Branch should be empty string
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT branch FROM memories WHERE id = ?",
            (result["memory_ids"][0],),
        )
        assert cursor.fetchone()[0] == ""
