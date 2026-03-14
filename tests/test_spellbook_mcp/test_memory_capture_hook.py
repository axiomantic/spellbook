"""Tests for memory-capture behavior via the unified hook (spellbook_hook.py).

PostToolUse handler (_memory_capture):
- Receives JSON on stdin with tool_name, tool_input, tool_use_id, session_id, cwd
- Extracts tool usage data and POSTs to /api/memory/event
- Computes project namespace from cwd (project-encoded: strip leading /, replace / with -)
- Generates summary from tool usage
- FAIL-OPEN: always exits 0, never blocks tool execution
- Skips blacklisted interactive/management tools
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# Project root: tests/test_spellbook_mcp/test_memory_capture_hook.py -> test_spellbook_mcp -> tests -> root
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
UNIFIED_HOOK = os.path.join(PROJECT_ROOT, "hooks", "spellbook_hook.py")

# Port where nothing listens, used for server-unreachable tests
DEAD_PORT = "19999"


def _run_hook(
    stdin_data: dict | str,
    *,
    env_overrides: dict | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Run the unified hook with given stdin data as PostToolUse event."""
    if isinstance(stdin_data, str):
        input_str = stdin_data
    else:
        payload = dict(stdin_data)
        payload["hook_event_name"] = "PostToolUse"
        input_str = json.dumps(payload)

    env = os.environ.copy()
    env["SPELLBOOK_DIR"] = PROJECT_ROOT
    env["PYTHONPATH"] = PROJECT_ROOT
    # Use a dead port by default so we don't accidentally hit a real daemon
    env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
    env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"
    if env_overrides:
        env.update(env_overrides)

    return subprocess.run(
        [sys.executable, UNIFIED_HOOK],
        input=input_str,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


# =============================================================================
# Fail-open behavior
# =============================================================================


class TestFailOpen:
    """Memory capture hook must NEVER block tool execution (always exit 0)."""

    def test_exits_zero_with_valid_input_server_unreachable(self):
        """When MCP server is unreachable, exits 0 without blocking."""
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/Users/alice/project/src/main.py"},
            "tool_use_id": "tu_12345",
            "session_id": "sess-abc",
            "cwd": "/Users/alice/project",
        }
        proc = _run_hook(stdin_data)
        assert proc.returncode == 0

    def test_exits_zero_with_empty_stdin(self):
        """Empty stdin should not crash, exit 0."""
        proc = _run_hook("")
        assert proc.returncode == 0

    def test_exits_zero_with_invalid_json(self):
        """Invalid JSON on stdin should not crash, exit 0."""
        proc = _run_hook("not valid json {{{")
        assert proc.returncode == 0

    def test_exits_zero_with_missing_tool_name(self):
        """JSON without tool_name field should exit 0."""
        stdin_data = {
            "tool_input": {},
            "session_id": "sess-abc",
            "cwd": "/tmp/project",
        }
        proc = _run_hook(stdin_data)
        assert proc.returncode == 0


# =============================================================================
# Blacklist behavior
# =============================================================================


class TestBlacklist:
    """Hook must skip blacklisted interactive/management tools."""

    @pytest.mark.parametrize(
        "tool_name",
        [
            "AskUserQuestion",
            "TodoRead",
            "TodoWrite",
            "TaskCreate",
            "TaskUpdate",
            "TaskGet",
            "TaskList",
        ],
    )
    def test_blacklisted_tool_exits_zero(self, tool_name):
        """Blacklisted tools should exit 0 cleanly."""
        stdin_data = {
            "tool_name": tool_name,
            "tool_input": {},
            "tool_use_id": "tu_skip",
            "session_id": "sess-abc",
            "cwd": "/Users/alice/project",
        }
        proc = _run_hook(stdin_data)
        assert proc.returncode == 0

    def test_non_blacklisted_tool_exits_zero(self):
        """Non-blacklisted tools should also exit 0 (fail-open)."""
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
            "tool_use_id": "tu_123",
            "session_id": "sess-abc",
            "cwd": "/Users/alice/project",
        }
        proc = _run_hook(stdin_data)
        assert proc.returncode == 0
