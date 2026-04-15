"""Tests for branch wiring in memory_tools."""

import subprocess

import pytest

from spellbook.core.db import get_connection, init_db, close_all_connections
from spellbook.memory.tools import (
    do_log_event,
    do_memory_recall,
)
from tests._memory_marker import requires_memory_tools

pytestmark = requires_memory_tools


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
    def test_branch_and_repo_path_forwarded(self, tmp_path, monkeypatch, git_repo):
        """do_memory_recall should forward branch so scoring activates."""
        from spellbook.memory.tools import do_memory_store

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        do_memory_store(
            content="Test recall with branch forwarding for scoring activation test",
            type="project",
            kind="fact",
            tags=["test"],
            scope="project",
            branch="main",
            namespace="test-project",
        )
        result = do_memory_recall(
            query="branch forwarding",
            namespace="test-project",
            branch="main",
        )
        assert result["query"] == "branch forwarding"
        assert result["namespace"] == "test-project"
        assert isinstance(result["memories"], list)
        assert result["count"] >= 1

    def test_branch_defaults_to_empty(self, tmp_path, monkeypatch):
        """do_memory_recall should work without branch param (backward compat)."""
        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )

        result = do_memory_recall(
            query="anything",
            namespace="test-project",
        )
        assert result == {
            "memories": [],
            "count": 0,
            "query": "anything",
            "namespace": "test-project",
        }

