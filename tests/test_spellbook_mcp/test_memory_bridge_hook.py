"""Tests for auto-memory bridge hook path matching and content capture."""

from unittest.mock import patch, call

import pytest


class TestIsAutoMemoryPath:
    """_is_auto_memory_path detects writes to Claude Code's auto-memory directory."""

    def test_primary_memory_md(self):
        from hooks.spellbook_hook import _is_auto_memory_path

        path = "/Users/alice/.claude/projects/-Users-alice-myproject/memory/MEMORY.md"
        assert _is_auto_memory_path(path) is True

    def test_topic_file(self):
        from hooks.spellbook_hook import _is_auto_memory_path

        path = "/Users/alice/.claude/projects/-Users-alice-myproject/memory/debugging.md"
        assert _is_auto_memory_path(path) is True

    def test_non_memory_file(self):
        from hooks.spellbook_hook import _is_auto_memory_path

        path = "/Users/alice/project/src/main.py"
        assert _is_auto_memory_path(path) is False

    def test_memory_in_wrong_directory(self):
        """Path containing 'memory' but not in .claude/projects/ returns False."""
        from hooks.spellbook_hook import _is_auto_memory_path

        path = "/Users/alice/memory/notes.md"
        assert _is_auto_memory_path(path) is False

    def test_non_md_file_in_memory_dir(self):
        from hooks.spellbook_hook import _is_auto_memory_path

        path = "/Users/alice/.claude/projects/-Users-alice-myproject/memory/notes.txt"
        assert _is_auto_memory_path(path) is False

    def test_windows_path(self):
        from hooks.spellbook_hook import _is_auto_memory_path

        path = "C:\\Users\\alice\\.claude\\projects\\-Users-alice-myproject\\memory\\MEMORY.md"
        assert _is_auto_memory_path(path) is True

    def test_empty_path(self):
        from hooks.spellbook_hook import _is_auto_memory_path

        assert _is_auto_memory_path("") is False

    def test_claude_projects_without_memory_subdir(self):
        from hooks.spellbook_hook import _is_auto_memory_path

        path = "/Users/alice/.claude/projects/-Users-alice-myproject/MEMORY.md"
        assert _is_auto_memory_path(path) is False


class TestMemoryBridge:
    """_memory_bridge captures auto-memory writes and dispatches to endpoints."""

    def _make_data(self, file_path, content="# Test content", cwd="/Users/alice/project"):
        return {
            "tool_input": {"file_path": file_path, "content": content},
            "cwd": cwd,
            "session_id": "sess-123",
        }

    def test_ignores_non_write_tool(self):
        from hooks.spellbook_hook import _memory_bridge

        with patch("hooks.spellbook_hook._http_post") as mock_post:
            _memory_bridge("Read", self._make_data("/some/file.md"))
            assert mock_post.call_count == 0

    def test_ignores_non_memory_path(self):
        from hooks.spellbook_hook import _memory_bridge

        with patch("hooks.spellbook_hook._http_post") as mock_post:
            _memory_bridge("Write", self._make_data("/Users/alice/project/src/main.py"))
            assert mock_post.call_count == 0

    def test_ignores_empty_content(self):
        from hooks.spellbook_hook import _memory_bridge

        data = self._make_data(
            "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md",
            content="",
        )
        with patch("hooks.spellbook_hook._http_post") as mock_post:
            _memory_bridge("Write", data)
            assert mock_post.call_count == 0

    def test_ignores_spellbook_managed_content(self):
        """Skips re-capturing spellbook-generated MEMORY.md (echo prevention)."""
        from hooks.spellbook_hook import _memory_bridge

        data = self._make_data(
            "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md",
            content="# Spellbook Memory System\n\nThe contents of this file are managed...",
        )
        with patch("hooks.spellbook_hook._http_post") as mock_post:
            _memory_bridge("Write", data)
            assert mock_post.call_count == 0

    def test_dispatches_audit_and_content(self):
        from hooks.spellbook_hook import _memory_bridge

        file_path = "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md"
        data = self._make_data(file_path, content="# Key facts\n- Python 3.10")

        with patch("hooks.spellbook_hook._http_post") as mock_post, \
             patch("hooks.spellbook_hook._resolve_git_context", return_value=("/Users/alice/project", "main")):
            _memory_bridge("Write", data)

            assert mock_post.call_count == 2

            # First call: audit trail to /api/memory/event
            audit_url = mock_post.call_args_list[0][0][0]
            audit_payload = mock_post.call_args_list[0][0][1]
            assert audit_url == "http://127.0.0.1:8765/api/memory/event"
            assert audit_payload == {
                "session_id": "sess-123",
                "project": "Users-alice-project",
                "tool_name": "Write",
                "subject": file_path,
                "summary": "auto-memory primary: MEMORY.md",
                "tags": "auto-memory,bridge,memory",
                "event_type": "auto_memory_bridge",
                "branch": "main",
            }

            # Second call: content to /api/memory/bridge-content
            content_url = mock_post.call_args_list[1][0][0]
            content_payload = mock_post.call_args_list[1][0][1]
            assert content_url == "http://127.0.0.1:8765/api/memory/bridge-content"
            assert content_payload == {
                "session_id": "sess-123",
                "project": "Users-alice-project",
                "file_path": file_path,
                "filename": "MEMORY.md",
                "content": "# Key facts\n- Python 3.10",
                "is_primary": True,
                "branch": "main",
            }

    def test_detects_topic_file(self):
        from hooks.spellbook_hook import _memory_bridge

        file_path = "/Users/alice/.claude/projects/-Users-alice-project/memory/debugging.md"
        data = self._make_data(file_path, content="# Debug notes")

        with patch("hooks.spellbook_hook._http_post") as mock_post, \
             patch("hooks.spellbook_hook._resolve_git_context", return_value=("/Users/alice/project", "main")):
            _memory_bridge("Write", data)

            assert mock_post.call_count == 2

            # Audit call should say "topic"
            audit_payload = mock_post.call_args_list[0][0][1]
            assert audit_payload["summary"] == "auto-memory topic: debugging.md"
            assert audit_payload["tags"] == "auto-memory,bridge,debugging"

            # Content call should have is_primary=False
            content_payload = mock_post.call_args_list[1][0][1]
            assert content_payload["is_primary"] is False
            assert content_payload["filename"] == "debugging.md"

    def test_caps_content_at_50k(self):
        from hooks.spellbook_hook import _memory_bridge

        file_path = "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md"
        huge_content = "x" * 60000
        data = self._make_data(file_path, content=huge_content)

        with patch("hooks.spellbook_hook._http_post") as mock_post, \
             patch("hooks.spellbook_hook._resolve_git_context", return_value=("/Users/alice/project", "main")):
            _memory_bridge("Write", data)

            content_payload = mock_post.call_args_list[1][0][1]
            assert len(content_payload["content"]) == 50000

    def test_missing_tool_input(self):
        """Handles missing tool_input gracefully (fail-open)."""
        from hooks.spellbook_hook import _memory_bridge

        with patch("hooks.spellbook_hook._http_post") as mock_post:
            _memory_bridge("Write", {"cwd": "/tmp", "session_id": "s"})
            assert mock_post.call_count == 0

    def test_namespace_consistency_with_worktree(self):
        """Namespace from _resolve_git_context resolves worktree to main repo root.

        IMPORTANT: _memory_bridge uses _resolve_git_context for namespace encoding,
        while regenerate_memory_md_for_project uses encode_cwd. Both must resolve
        worktree paths to the main repo root to produce matching namespaces.
        If these diverge, bridge-captured events will land in a different namespace
        than what session_init queries, causing memories to appear lost.
        """
        from hooks.spellbook_hook import _memory_bridge

        file_path = "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md"
        data = {
            "tool_input": {"file_path": file_path, "content": "# Test"},
            "cwd": "/Users/alice/project/.worktrees/feature-branch",
            "session_id": "sess-wt",
        }

        # Simulate _resolve_git_context resolving worktree to main repo
        with patch("hooks.spellbook_hook._http_post") as mock_post, \
             patch("hooks.spellbook_hook._resolve_git_context",
                   return_value=("/Users/alice/project", "feature-branch")):
            _memory_bridge("Write", data)

            content_payload = mock_post.call_args_list[1][0][1]
            # Namespace should be based on main repo, not worktree path
            assert "worktrees" not in content_payload["project"]
            assert content_payload["project"] == "Users-alice-project"
