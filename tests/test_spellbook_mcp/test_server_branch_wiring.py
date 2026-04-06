"""Tests for branch wiring in server.py REST endpoints and MCP tools."""

import json
from types import SimpleNamespace

import bigfoot
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

        with bigfoot.in_any_order():
            db_mock.assert_call(args=(), kwargs={})
            log_event_mock.assert_call(
                args=(),
                kwargs={
                    "db_path": str(db_path),
                    "session_id": "sess1",
                    "project": "test-project",
                    "tool_name": "Read",
                    "subject": "/path/to/file.py",
                    "summary": "Read file",
                    "tags": "",
                    "event_type": "tool_use",
                    "branch": "feature-x",
                },
            )
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

        with bigfoot.in_any_order():
            db_mock.assert_call(args=(), kwargs={})
            log_event_mock.assert_call(
                args=(),
                kwargs={
                    "db_path": str(db_path),
                    "session_id": "sess1",
                    "project": "test-project",
                    "tool_name": "Read",
                    "subject": "/path/to/file.py",
                    "summary": "Read file",
                    "tags": "",
                    "event_type": "tool_use",
                    "branch": "",
                },
            )
        assert captured["branch"] == ""


class TestApiMemoryRecallBranch:
    @pytest.mark.asyncio
    async def test_passes_branch_to_do_memory_recall(self, db_path, monkeypatch):
        """REST /api/memory/recall should extract branch from body and pass to do_memory_recall."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_memory_recall(**kwargs):
            captured.update(kwargs)
            return {"memories": [], "count": 0}

        monkeypatch.setattr("spellbook.mcp.routes.do_memory_recall", mock_do_memory_recall)
        monkeypatch.setattr("spellbook.mcp.routes.get_db_path", lambda: db_path)

        request = _make_request(
            {
                "namespace": "test-project",
                "file_path": "/path/to/file.py",
                "branch": "feature-x",
            }
        )

        await routes.api_memory_recall(request)

        with bigfoot.in_any_order():
            db_mock.assert_call(args=(), kwargs={})
            recall_mock.assert_call(
                args=(),
                kwargs={
                    "db_path": str(db_path),
                    "query": "",
                    "namespace": "test-project",
                    "limit": 5,
                    "file_path": "/path/to/file.py",
                    "branch": "feature-x",
                    "repo_path": "",
                },
            )
        assert captured["branch"] == "feature-x"

    @pytest.mark.asyncio
    async def test_passes_repo_path_to_do_memory_recall(self, db_path, monkeypatch):
        """REST /api/memory/recall should extract repo_path from body and pass to do_memory_recall."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_memory_recall(**kwargs):
            captured.update(kwargs)
            return {"memories": [], "count": 0}

        monkeypatch.setattr("spellbook.mcp.routes.do_memory_recall", mock_do_memory_recall)
        monkeypatch.setattr("spellbook.mcp.routes.get_db_path", lambda: db_path)

        request = _make_request(
            {
                "namespace": "test-project",
                "query": "test",
                "branch": "main",
                "repo_path": "/Users/test/repo",
            }
        )

        await routes.api_memory_recall(request)

        with bigfoot.in_any_order():
            db_mock.assert_call(args=(), kwargs={})
            recall_mock.assert_call(
                args=(),
                kwargs={
                    "db_path": str(db_path),
                    "query": "test",
                    "namespace": "test-project",
                    "limit": 5,
                    "file_path": None,
                    "branch": "main",
                    "repo_path": "/Users/test/repo",
                },
            )
        assert captured["branch"] == "main"
        assert captured["repo_path"] == "/Users/test/repo"

    @pytest.mark.asyncio
    async def test_branch_defaults_to_empty_when_absent(self, db_path, monkeypatch):
        """REST /api/memory/recall should default branch to empty when not in body."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_memory_recall(**kwargs):
            captured.update(kwargs)
            return {"memories": [], "count": 0}

        monkeypatch.setattr("spellbook.mcp.routes.do_memory_recall", mock_do_memory_recall)
        monkeypatch.setattr("spellbook.mcp.routes.get_db_path", lambda: db_path)

        request = _make_request(
            {
                "namespace": "test-project",
                "query": "test",
            }
        )

        await routes.api_memory_recall(request)

        with bigfoot.in_any_order():
            db_mock.assert_call(args=(), kwargs={})
            recall_mock.assert_call(
                args=(),
                kwargs={
                    "db_path": str(db_path),
                    "query": "test",
                    "namespace": "test-project",
                    "limit": 5,
                    "file_path": None,
                    "branch": "",
                    "repo_path": "",
                },
            )
        assert captured["branch"] == ""
        assert captured["repo_path"] == ""


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

        with bigfoot.in_any_order():
            db_mock.assert_call(args=(), kwargs={})
            project_mock.assert_call(args=(mock_ctx,), kwargs={})
            repo_mock.assert_call(args=(fake_project_path,), kwargs={})
            branch_mock.assert_call(args=("/Users/test/myproject",), kwargs={})
            recall_mock.assert_call(
                args=(),
                kwargs={
                    "db_path": str(db_path),
                    "query": "test query",
                    "namespace": expected_namespace,
                    "limit": 10,
                    "file_path": None,
                    "branch": "feature-branch",
                    "repo_path": "/Users/test/myproject",
                    "scope": "project",
                },
            )
        assert captured["branch"] == "feature-branch"
        assert captured["repo_path"] == "/Users/test/myproject"
        assert captured["namespace"] == expected_namespace


class TestMcpMemoryStoreMemoriesBranch:
    @pytest.mark.asyncio
    async def test_detects_branch_from_context(self, db_path, monkeypatch):
        """MCP memory_store_memories should detect branch from context and pass to do_store_memories."""
        from spellbook import server

        captured = {}

        def mock_do_store_memories(**kwargs):
            captured.update(kwargs)
            return {
                "status": "success",
                "memories_created": 0,
                "events_consolidated": 0,
                "memory_ids": [],
            }

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
        monkeypatch.setattr("spellbook.mcp.tools.memory.do_store_memories", mock_do_store_memories)
        monkeypatch.setattr(
            "spellbook.mcp.tools.memory.get_current_branch",
            lambda p: "dev-branch",
        )

        await server.memory_store_memories.fn(
            ctx=mock_ctx,
            memories='{"memories": []}',
            event_ids="",
            namespace="",
        )

        with bigfoot.in_any_order():
            db_mock.assert_call(args=(), kwargs={})
            project_mock.assert_call(args=(mock_ctx,), kwargs={})
            branch_mock.assert_call(args=(fake_project_path,), kwargs={})
            store_mock.assert_call(
                args=(),
                kwargs={
                    "db_path": str(db_path),
                    "memories_json": '{"memories": []}',
                    "event_ids_str": "",
                    "namespace": expected_namespace,
                    "branch": "dev-branch",
                    "scope": "project",
                },
            )
        assert captured["branch"] == "dev-branch"
        assert captured["namespace"] == expected_namespace
