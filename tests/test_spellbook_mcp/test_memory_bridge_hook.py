"""Tests for auto-memory bridge hook path matching and content capture."""

import bigfoot
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

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.__call__.required(False).returns(None)

        with bigfoot:
            _memory_bridge("Read", self._make_data("/some/file.md"))

    def test_ignores_non_memory_path(self):
        from hooks.spellbook_hook import _memory_bridge

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.__call__.required(False).returns(None)

        with bigfoot:
            _memory_bridge("Write", self._make_data("/Users/alice/project/src/main.py"))

    def test_ignores_empty_content(self):
        from hooks.spellbook_hook import _memory_bridge

        data = self._make_data(
            "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md",
            content="",
        )
        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.__call__.required(False).returns(None)

        with bigfoot:
            _memory_bridge("Write", data)

    def test_ignores_spellbook_managed_content(self):
        """Skips re-capturing spellbook-generated MEMORY.md (echo prevention)."""
        from hooks.spellbook_hook import _memory_bridge

        data = self._make_data(
            "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md",
            content="# Spellbook Memory System\n\nThe contents of this file are managed...",
        )
        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.__call__.required(False).returns(None)

        with bigfoot:
            _memory_bridge("Write", data)

    def test_dispatches_audit_and_content(self):
        from hooks.spellbook_hook import _memory_bridge

        file_path = "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md"
        data = self._make_data(file_path, content="# Key facts\n- Python 3.10")

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns(None).returns(None)
        mock_git = bigfoot.mock("hooks.spellbook_hook:_resolve_git_context")
        mock_git.returns(("/Users/alice/project", "main"))

        with bigfoot:
            _memory_bridge("Write", data)

        mock_git.assert_call(args=("/Users/alice/project",), kwargs={})

        # First call: audit trail to /api/memory/event
        mock_post.assert_call(
            args=(
                "/api/memory/event",
                {
                    "session_id": "sess-123",
                    "project": "Users-alice-project",
                    "tool_name": "Write",
                    "subject": file_path,
                    "summary": "auto-memory primary: MEMORY.md",
                    "tags": "auto-memory,bridge,memory",
                    "event_type": "auto_memory_bridge",
                    "branch": "main",
                },
            ),
            kwargs={"timeout": 5},
        )

        # Second call: content to /api/memory/bridge-content
        mock_post.assert_call(
            args=(
                "/api/memory/bridge-content",
                {
                    "session_id": "sess-123",
                    "project": "Users-alice-project",
                    "file_path": file_path,
                    "filename": "MEMORY.md",
                    "content": "# Key facts\n- Python 3.10",
                    "is_primary": True,
                    "branch": "main",
                },
            ),
            kwargs={"timeout": 10},
        )

    def test_detects_topic_file(self):
        from hooks.spellbook_hook import _memory_bridge

        file_path = "/Users/alice/.claude/projects/-Users-alice-project/memory/debugging.md"
        data = self._make_data(file_path, content="# Debug notes")

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns(None).returns(None)
        mock_git = bigfoot.mock("hooks.spellbook_hook:_resolve_git_context")
        mock_git.returns(("/Users/alice/project", "main"))

        with bigfoot:
            _memory_bridge("Write", data)

        mock_git.assert_call(args=("/Users/alice/project",), kwargs={})

        # Audit call should say "topic"
        mock_post.assert_call(
            args=(
                "/api/memory/event",
                {
                    "session_id": "sess-123",
                    "project": "Users-alice-project",
                    "tool_name": "Write",
                    "subject": file_path,
                    "summary": "auto-memory topic: debugging.md",
                    "tags": "auto-memory,bridge,debugging",
                    "event_type": "auto_memory_bridge",
                    "branch": "main",
                },
            ),
            kwargs={"timeout": 5},
        )

        # Content call should have is_primary=False
        mock_post.assert_call(
            args=(
                "/api/memory/bridge-content",
                {
                    "session_id": "sess-123",
                    "project": "Users-alice-project",
                    "file_path": file_path,
                    "filename": "debugging.md",
                    "content": "# Debug notes",
                    "is_primary": False,
                    "branch": "main",
                },
            ),
            kwargs={"timeout": 10},
        )

    def test_caps_content_at_50k(self):
        from hooks.spellbook_hook import _memory_bridge

        file_path = "/Users/alice/.claude/projects/-Users-alice-project/memory/MEMORY.md"
        huge_content = "x" * 60000
        data = self._make_data(file_path, content=huge_content)

        captured_content = {}

        def capture_post(url, payload, **kwargs):
            if "bridge-content" in url:
                captured_content["length"] = len(payload["content"])

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.calls(capture_post).calls(capture_post)
        mock_git = bigfoot.mock("hooks.spellbook_hook:_resolve_git_context")
        mock_git.returns(("/Users/alice/project", "main"))

        with bigfoot:
            _memory_bridge("Write", data)

        mock_git.assert_call(args=("/Users/alice/project",), kwargs={})

        with bigfoot.in_any_order():
            mock_post.assert_call(
                args=(
                    "/api/memory/event",
                    {
                        "session_id": "sess-123",
                        "project": "Users-alice-project",
                        "tool_name": "Write",
                        "subject": file_path,
                        "summary": "auto-memory primary: MEMORY.md",
                        "tags": "auto-memory,bridge,memory",
                        "event_type": "auto_memory_bridge",
                        "branch": "main",
                    },
                ),
                kwargs={"timeout": 5},
            )
            mock_post.assert_call(
                args=(
                    "/api/memory/bridge-content",
                    {
                        "session_id": "sess-123",
                        "project": "Users-alice-project",
                        "file_path": file_path,
                        "filename": "MEMORY.md",
                        "content": "x" * 50000,
                        "is_primary": True,
                        "branch": "main",
                    },
                ),
                kwargs={"timeout": 10},
            )

        assert captured_content["length"] == 50000

    def test_missing_tool_input(self):
        """Handles missing tool_input gracefully (fail-open)."""
        from hooks.spellbook_hook import _memory_bridge

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.__call__.required(False).returns(None)

        with bigfoot:
            _memory_bridge("Write", {"cwd": "/tmp", "session_id": "s"})

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
        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns(None).returns(None)
        mock_git = bigfoot.mock("hooks.spellbook_hook:_resolve_git_context")
        mock_git.returns(("/Users/alice/project", "feature-branch"))

        with bigfoot:
            _memory_bridge("Write", data)

        mock_git.assert_call(
            args=("/Users/alice/project/.worktrees/feature-branch",), kwargs={},
        )

        # Audit call
        mock_post.assert_call(
            args=(
                "/api/memory/event",
                {
                    "session_id": "sess-wt",
                    "project": "Users-alice-project",
                    "tool_name": "Write",
                    "subject": file_path,
                    "summary": "auto-memory primary: MEMORY.md",
                    "tags": "auto-memory,bridge,memory",
                    "event_type": "auto_memory_bridge",
                    "branch": "feature-branch",
                },
            ),
            kwargs={"timeout": 5},
        )

        # Content call: namespace should be based on main repo, not worktree path
        mock_post.assert_call(
            args=(
                "/api/memory/bridge-content",
                {
                    "session_id": "sess-wt",
                    "project": "Users-alice-project",
                    "file_path": file_path,
                    "filename": "MEMORY.md",
                    "content": "# Test",
                    "is_primary": True,
                    "branch": "feature-branch",
                },
            ),
            kwargs={"timeout": 10},
        )
