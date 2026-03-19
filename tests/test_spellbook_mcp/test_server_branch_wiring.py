"""Tests for branch wiring in server.py REST endpoints and MCP tools."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from spellbook.core.db import init_db


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


class TestApiMemoryEventBranch:
    @pytest.mark.asyncio
    async def test_passes_branch_to_do_log_event(self, db_path):
        """REST /api/memory/event should extract branch from body and pass to do_log_event."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_log_event(**kwargs):
            captured.update(kwargs)
            return {"status": "logged", "event_id": 1}

        request = AsyncMock()
        request.json = AsyncMock(
            return_value={
                "session_id": "sess1",
                "project": "test-project",
                "tool_name": "Read",
                "subject": "/path/to/file.py",
                "summary": "Read file",
                "branch": "feature-x",
            }
        )

        with patch("spellbook.mcp.routes.do_log_event", side_effect=mock_do_log_event), \
             patch("spellbook.mcp.routes.get_db_path", return_value=db_path):
            response = await routes.api_memory_event(request)

        assert captured["branch"] == "feature-x"

    @pytest.mark.asyncio
    async def test_branch_defaults_to_empty_when_absent(self, db_path):
        """REST /api/memory/event should default branch to empty when not in body."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_log_event(**kwargs):
            captured.update(kwargs)
            return {"status": "logged", "event_id": 1}

        request = AsyncMock()
        request.json = AsyncMock(
            return_value={
                "session_id": "sess1",
                "project": "test-project",
                "tool_name": "Read",
                "subject": "/path/to/file.py",
                "summary": "Read file",
            }
        )

        with patch("spellbook.mcp.routes.do_log_event", side_effect=mock_do_log_event), \
             patch("spellbook.mcp.routes.get_db_path", return_value=db_path):
            response = await routes.api_memory_event(request)

        assert captured["branch"] == ""


class TestApiMemoryRecallBranch:
    @pytest.mark.asyncio
    async def test_passes_branch_to_do_memory_recall(self, db_path):
        """REST /api/memory/recall should extract branch from body and pass to do_memory_recall."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_memory_recall(**kwargs):
            captured.update(kwargs)
            return {"memories": [], "count": 0}

        request = AsyncMock()
        request.json = AsyncMock(
            return_value={
                "namespace": "test-project",
                "file_path": "/path/to/file.py",
                "branch": "feature-x",
            }
        )

        with patch("spellbook.mcp.routes.do_memory_recall", side_effect=mock_do_memory_recall), \
             patch("spellbook.mcp.routes.get_db_path", return_value=db_path):
            response = await routes.api_memory_recall(request)

        assert captured["branch"] == "feature-x"

    @pytest.mark.asyncio
    async def test_passes_repo_path_to_do_memory_recall(self, db_path):
        """REST /api/memory/recall should extract repo_path from body and pass to do_memory_recall."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_memory_recall(**kwargs):
            captured.update(kwargs)
            return {"memories": [], "count": 0}

        request = AsyncMock()
        request.json = AsyncMock(
            return_value={
                "namespace": "test-project",
                "query": "test",
                "branch": "main",
                "repo_path": "/Users/test/repo",
            }
        )

        with patch("spellbook.mcp.routes.do_memory_recall", side_effect=mock_do_memory_recall), \
             patch("spellbook.mcp.routes.get_db_path", return_value=db_path):
            response = await routes.api_memory_recall(request)

        assert captured["branch"] == "main"
        assert captured["repo_path"] == "/Users/test/repo"

    @pytest.mark.asyncio
    async def test_branch_defaults_to_empty_when_absent(self, db_path):
        """REST /api/memory/recall should default branch to empty when not in body."""
        from spellbook.mcp import routes

        captured = {}

        def mock_do_memory_recall(**kwargs):
            captured.update(kwargs)
            return {"memories": [], "count": 0}

        request = AsyncMock()
        request.json = AsyncMock(
            return_value={
                "namespace": "test-project",
                "query": "test",
            }
        )

        with patch("spellbook.mcp.routes.do_memory_recall", side_effect=mock_do_memory_recall), \
             patch("spellbook.mcp.routes.get_db_path", return_value=db_path):
            response = await routes.api_memory_recall(request)

        assert captured["branch"] == ""
        assert captured["repo_path"] == ""


class TestMcpMemoryRecallBranch:
    @pytest.mark.asyncio
    async def test_detects_branch_from_context(self, db_path):
        """MCP memory_recall should detect branch from context and pass to do_memory_recall."""
        from spellbook import server

        captured = {}

        def mock_do_memory_recall(**kwargs):
            captured.update(kwargs)
            return {"memories": [], "count": 0, "query": "", "namespace": "test-ns"}

        mock_ctx = MagicMock()
        fake_project_path = "/Users/test/myproject"

        with patch("spellbook.mcp.tools.memory.get_db_path", return_value=db_path), \
             patch(
                 "spellbook.mcp.tools.memory.get_project_path_from_context",
                 new_callable=AsyncMock, return_value=fake_project_path,
             ), \
             patch("spellbook.mcp.tools.memory.do_memory_recall", side_effect=mock_do_memory_recall), \
             patch("spellbook.mcp.tools.memory.get_current_branch", return_value="feature-branch"), \
             patch("spellbook.mcp.tools.memory.resolve_repo_root", return_value="/Users/test/myproject"):
            await server.memory_recall.fn(
                ctx=mock_ctx,
                query="test query",
                namespace="",
                limit=10,
                file_path="",
            )

        assert captured["branch"] == "feature-branch"
        assert captured["repo_path"] == "/Users/test/myproject"


class TestMcpMemoryStoreMemoriesBranch:
    @pytest.mark.asyncio
    async def test_detects_branch_from_context(self, db_path):
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

        mock_ctx = MagicMock()
        fake_project_path = "/Users/test/myproject"

        with patch("spellbook.mcp.tools.memory.get_db_path", return_value=db_path), \
             patch(
                 "spellbook.mcp.tools.memory.get_project_path_from_context",
                 new_callable=AsyncMock, return_value=fake_project_path,
             ), \
             patch("spellbook.mcp.tools.memory.do_store_memories", side_effect=mock_do_store_memories), \
             patch("spellbook.mcp.tools.memory.get_current_branch", return_value="dev-branch"):
            await server.memory_store_memories.fn(
                ctx=mock_ctx,
                memories='{"memories": []}',
                event_ids="",
                namespace="",
            )

        assert captured["branch"] == "dev-branch"
