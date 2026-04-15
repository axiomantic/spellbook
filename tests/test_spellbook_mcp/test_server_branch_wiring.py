"""Tests for branch wiring in server.py REST endpoints and MCP tools."""

import json
from types import SimpleNamespace

import pytest

from spellbook.core.db import init_db
from spellbook.core.path_utils import encode_cwd


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _make_request(body: dict):
    """Create a fake Starlette-like request with an async json() method."""

    async def _json():
        return body

    return SimpleNamespace(json=_json)


class TestApiMemoryEventBranch:
    @pytest.mark.asyncio
    async def test_passes_branch_to_do_log_event(self, db_path, monkeypatch):
        """REST /api/memory/event should extract branch from body and pass to do_log_event."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_log_event(**kwargs):
            captured.update(kwargs)
            return {"status": "logged", "event_id": 1}

        monkeypatch.setattr("spellbook.mcp.routes.do_log_event", mock_do_log_event)
        monkeypatch.setattr("spellbook.mcp.routes.get_db_path", lambda: db_path)

        request = _make_request(
            {
                "session_id": "sess1",
                "project": "test-project",
                "tool_name": "Read",
                "subject": "/path/to/file.py",
                "summary": "Read file",
                "branch": "feature-x",
            }
        )

        await routes.api_memory_event(request)

        assert captured["branch"] == "feature-x"
        assert captured["db_path"] == str(db_path)

    @pytest.mark.asyncio
    async def test_branch_defaults_to_empty_when_absent(self, db_path, monkeypatch):
        """REST /api/memory/event should default branch to empty when not in body."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_log_event(**kwargs):
            captured.update(kwargs)
            return {"status": "logged", "event_id": 1}

        monkeypatch.setattr("spellbook.mcp.routes.do_log_event", mock_do_log_event)
        monkeypatch.setattr("spellbook.mcp.routes.get_db_path", lambda: db_path)

        request = _make_request(
            {
                "session_id": "sess1",
                "project": "test-project",
                "tool_name": "Read",
                "subject": "/path/to/file.py",
                "summary": "Read file",
            }
        )

        await routes.api_memory_event(request)

        assert captured["branch"] == ""


class TestApiMemoryRecallBranch:
    @pytest.mark.asyncio
    async def test_passes_branch_to_filestore_recall(self, db_path, monkeypatch):
        """REST /api/memory/recall should extract branch from body and pass to filestore recall."""
        from spellbook.mcp import routes

        captured = {}

        def mock_recall(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr("spellbook.mcp.routes._filestore_recall", mock_recall)

        request = _make_request(
            {
                "namespace": "test-project",
                "file_path": "/path/to/file.py",
                "branch": "feature-x",
            }
        )

        await routes.api_memory_recall(request)

        assert captured["branch"] == "feature-x"

    @pytest.mark.asyncio
    async def test_passes_file_path_to_filestore_recall(self, db_path, monkeypatch):
        """REST /api/memory/recall should forward file_path to filestore recall."""
        from spellbook.mcp import routes

        captured = {}

        def mock_recall(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr("spellbook.mcp.routes._filestore_recall", mock_recall)

        request = _make_request(
            {
                "namespace": "test-project",
                "query": "test",
                "branch": "main",
                "file_path": "/src/module.py",
            }
        )

        await routes.api_memory_recall(request)

        assert captured["branch"] == "main"
        assert captured["file_path"] == "/src/module.py"

    @pytest.mark.asyncio
    async def test_branch_defaults_to_none_when_absent(self, db_path, monkeypatch):
        """REST /api/memory/recall should default branch to None when not in body."""
        from spellbook.mcp import routes

        captured = {}

        def mock_recall(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr("spellbook.mcp.routes._filestore_recall", mock_recall)

        request = _make_request(
            {
                "namespace": "test-project",
                "query": "test",
            }
        )

        await routes.api_memory_recall(request)

        assert captured["branch"] is None


class TestMcpMemoryRecallBranch:
    @pytest.mark.asyncio
    async def test_detects_branch_from_context(self, db_path, monkeypatch):
        """MCP memory_recall should detect branch from context and pass to do_memory_recall."""
        from spellbook import server

        captured = {}

        def mock_do_memory_recall(**kwargs):
            captured.update(kwargs)
            return {"memories": [], "count": 0, "query": "", "namespace": "test-ns"}

        fake_project_path = "/Users/test/myproject"
        expected_namespace = encode_cwd(fake_project_path)
        mock_ctx = SimpleNamespace()

        monkeypatch.setattr("spellbook.mcp.tools.memory.get_db_path", lambda: db_path)

        async def _return_project_path(*args, **kwargs):
            return fake_project_path

        monkeypatch.setattr(
            "spellbook.mcp.tools.memory.get_project_path_from_context",
            _return_project_path,
        )
        monkeypatch.setattr("spellbook.mcp.tools.memory.do_memory_recall", mock_do_memory_recall)
        monkeypatch.setattr(
            "spellbook.mcp.tools.memory.get_current_branch",
            lambda p: "feature-branch",
        )
        monkeypatch.setattr(
            "spellbook.mcp.tools.memory.resolve_repo_root",
            lambda p: "/Users/test/myproject",
        )

        await server.memory_recall.fn(
            ctx=mock_ctx,
            query="test query",
            namespace="",
            limit=10,
            file_path="",
        )

        assert captured["branch"] == "feature-branch"
        assert captured["namespace"] == expected_namespace

