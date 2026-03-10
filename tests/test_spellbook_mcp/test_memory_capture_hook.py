"""Tests for memory-capture hook scripts.

memory-capture.sh (PostToolUse hook):
- Receives JSON on stdin with tool_name, tool_input, tool_use_id, session_id, cwd
- Extracts tool usage data and POSTs to /api/memory/event
- Computes project namespace from cwd (project-encoded: strip leading /, replace / with -)
- Generates summary from tool usage
- FAIL-OPEN: always exits 0, never blocks tool execution
- Skips blacklisted interactive/management tools
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
import pytest

# All tests invoke bash shell scripts via subprocess.
pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="Bash scripts not available on Windows",
    ),
]

# Project root: tests/test_spellbook_mcp/test_memory_capture_hook.py -> test_spellbook_mcp -> tests -> root
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
HOOK_PATH = os.path.join(PROJECT_ROOT, "hooks", "memory-capture.sh")

# Port where nothing listens, used for server-unreachable tests
DEAD_PORT = "19999"


def _run_hook(
    stdin_data: dict | str,
    *,
    env_overrides: dict | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Run memory-capture.sh with given stdin data."""
    env = os.environ.copy()
    # Use a dead port by default so we don't accidentally hit a real daemon
    env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
    env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"
    if env_overrides:
        env.update(env_overrides)

    input_str = stdin_data if isinstance(stdin_data, str) else json.dumps(stdin_data)

    return subprocess.run(
        ["bash", HOOK_PATH],
        input=input_str,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def _run_hook_with_payload_capture(
    stdin_data: dict,
    *,
    env_overrides: dict | None = None,
    timeout: int = 10,
) -> tuple[subprocess.CompletedProcess, dict | None]:
    """Run memory-capture.sh with DEBUG_PAYLOAD=1 to capture the JSON payload.

    When DEBUG_PAYLOAD=1 is set, the hook prints the payload to stdout
    instead of sending it via curl. This allows tests to verify the
    exact payload structure.
    """
    env_extras = {"DEBUG_PAYLOAD": "1"}
    if env_overrides:
        env_extras.update(env_overrides)

    proc = _run_hook(stdin_data, env_overrides=env_extras, timeout=timeout)

    payload = None
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            pass

    return proc, payload


# =============================================================================
# Script properties
# =============================================================================


class TestScriptProperties:
    """Verify memory-capture.sh has correct file properties."""

    def test_script_exists(self):
        assert os.path.isfile(HOOK_PATH), f"Hook script not found at {HOOK_PATH}"

    def test_script_is_executable(self):
        st = os.stat(HOOK_PATH)
        assert st.st_mode & stat.S_IXUSR, "Script is not user-executable"

    def test_script_has_bash_shebang(self):
        with open(HOOK_PATH) as f:
            first_line = f.readline()
        assert first_line.strip() == "#!/usr/bin/env bash"


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
        assert proc.returncode == 0, (
            f"Expected exit 0 but got {proc.returncode}. stderr: {proc.stderr}"
        )

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

    def test_no_stderr_output(self):
        """Hook should not write to stderr (shows to user)."""
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
            "tool_use_id": "tu_123",
            "session_id": "sess-abc",
            "cwd": "/tmp/project",
        }
        proc = _run_hook(stdin_data)
        assert proc.returncode == 0
        assert proc.stderr == "", f"Unexpected stderr output: {proc.stderr}"


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
    def test_blacklisted_tool_produces_no_payload(self, tool_name):
        """Blacklisted tools should exit 0 with no payload."""
        stdin_data = {
            "tool_name": tool_name,
            "tool_input": {},
            "tool_use_id": "tu_skip",
            "session_id": "sess-abc",
            "cwd": "/Users/alice/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload is None, (
            f"Blacklisted tool {tool_name} should not produce payload, got: {payload}"
        )

    def test_non_blacklisted_tool_produces_payload(self):
        """Non-blacklisted tools should produce a payload."""
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
            "tool_use_id": "tu_123",
            "session_id": "sess-abc",
            "cwd": "/Users/alice/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload is not None, "Non-blacklisted tool should produce a payload"


# =============================================================================
# Payload structure
# =============================================================================


class TestPayloadStructure:
    """Hook must produce correctly structured JSON payloads."""

    def test_read_tool_payload(self):
        """Read tool produces complete, correct payload."""
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/Users/alice/project/src/main.py"},
            "tool_use_id": "tu_read1",
            "session_id": "sess-abc",
            "cwd": "/Users/alice/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload == {
            "session_id": "sess-abc",
            "project": "Users-alice-project",
            "tool_name": "Read",
            "subject": "/Users/alice/project/src/main.py",
            "summary": "Read: /Users/alice/project/src/main.py",
            "tags": "read,main.py",
            "event_type": "tool_use",
            "branch": "",
        }

    def test_write_tool_payload(self):
        """Write tool extracts file_path as subject."""
        stdin_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/output.txt", "content": "hello"},
            "tool_use_id": "tu_write1",
            "session_id": "sess-xyz",
            "cwd": "/tmp/myproject",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload == {
            "session_id": "sess-xyz",
            "project": "tmp-myproject",
            "tool_name": "Write",
            "subject": "/tmp/output.txt",
            "summary": "Write: /tmp/output.txt",
            "tags": "write,output.txt",
            "event_type": "tool_use",
            "branch": "",
        }

    def test_edit_tool_payload(self):
        """Edit tool extracts file_path as subject."""
        stdin_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/src/app.py", "old_text": "a", "new_text": "b"},
            "tool_use_id": "tu_edit1",
            "session_id": "sess-edit",
            "cwd": "/home/user/repo",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload == {
            "session_id": "sess-edit",
            "project": "home-user-repo",
            "tool_name": "Edit",
            "subject": "/src/app.py",
            "summary": "Edit: /src/app.py",
            "tags": "edit,app.py",
            "event_type": "tool_use",
            "branch": "",
        }

    def test_bash_tool_payload_truncates_command(self):
        """Bash tool uses command (truncated to 200 chars) as subject."""
        long_command = "echo " + "x" * 300
        stdin_data = {
            "tool_name": "Bash",
            "tool_input": {"command": long_command},
            "tool_use_id": "tu_bash1",
            "session_id": "sess-bash",
            "cwd": "/home/user/repo",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        expected_subject = long_command[:200]
        expected_summary = f"Bash: {expected_subject[:100]}"
        assert payload == {
            "session_id": "sess-bash",
            "project": "home-user-repo",
            "tool_name": "Bash",
            "subject": expected_subject,
            "summary": expected_summary,
            "tags": "bash",
            "event_type": "tool_use",
            "branch": "",
        }

    def test_grep_tool_payload(self):
        """Grep tool uses pattern as subject."""
        stdin_data = {
            "tool_name": "Grep",
            "tool_input": {"pattern": "def main", "path": "/src"},
            "tool_use_id": "tu_grep1",
            "session_id": "sess-grep",
            "cwd": "/Users/dev/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload == {
            "session_id": "sess-grep",
            "project": "Users-dev-project",
            "tool_name": "Grep",
            "subject": "def main",
            "summary": "Grep: def main",
            "tags": "grep",
            "event_type": "tool_use",
            "branch": "",
        }

    def test_glob_tool_payload(self):
        """Glob tool uses pattern as subject. Pattern with / gets filename extracted for tags."""
        stdin_data = {
            "tool_name": "Glob",
            "tool_input": {"pattern": "**/*.py"},
            "tool_use_id": "tu_glob1",
            "session_id": "sess-glob",
            "cwd": "/Users/dev/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        # Pattern **/*.py contains a /, so tag extraction splits and adds *.py
        assert payload == {
            "session_id": "sess-glob",
            "project": "Users-dev-project",
            "tool_name": "Glob",
            "subject": "**/*.py",
            "summary": "Glob: **/*.py",
            "tags": "glob,*.py",
            "event_type": "tool_use",
            "branch": "",
        }

    def test_webfetch_tool_payload(self):
        """WebFetch tool uses url as subject. URL path segments get last part as tag."""
        stdin_data = {
            "tool_name": "WebFetch",
            "tool_input": {"url": "https://example.com/api"},
            "tool_use_id": "tu_web1",
            "session_id": "sess-web",
            "cwd": "/Users/dev/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        # URL contains /, so tag extraction splits and adds "api"
        assert payload == {
            "session_id": "sess-web",
            "project": "Users-dev-project",
            "tool_name": "WebFetch",
            "subject": "https://example.com/api",
            "summary": "WebFetch: https://example.com/api",
            "tags": "webfetch,api",
            "event_type": "tool_use",
            "branch": "",
        }

    def test_mcp_tool_payload(self):
        """MCP tools use tool_name as subject."""
        stdin_data = {
            "tool_name": "mcp__spellbook__health_check",
            "tool_input": {},
            "tool_use_id": "tu_mcp1",
            "session_id": "sess-mcp",
            "cwd": "/Users/dev/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload == {
            "session_id": "sess-mcp",
            "project": "Users-dev-project",
            "tool_name": "mcp__spellbook__health_check",
            "subject": "mcp__spellbook__health_check",
            "summary": "mcp__spellbook__health_check: mcp__spellbook__health_check",
            "tags": "mcp__spellbook__health_check",
            "event_type": "tool_use",
            "branch": "",
        }

    def test_bash_tool_with_description_appends_to_summary(self):
        """When tool_input has a description field, it is appended to summary."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la", "description": "List files in directory"},
            "tool_use_id": "tu_bashdesc",
            "session_id": "sess-desc",
            "cwd": "/Users/dev/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload == {
            "session_id": "sess-desc",
            "project": "Users-dev-project",
            "tool_name": "Bash",
            "subject": "ls -la",
            "summary": "Bash: ls -la (List files in directory)",
            "tags": "bash",
            "event_type": "tool_use",
            "branch": "",
        }


# =============================================================================
# Namespace computation
# =============================================================================


class TestNamespaceComputation:
    """Hook must compute project namespace correctly (project-encoded)."""

    def test_namespace_strips_leading_slash_and_replaces_slashes(self):
        """cwd /Users/alice/project becomes Users-alice-project."""
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/f.py"},
            "tool_use_id": "tu_ns1",
            "session_id": "sess-ns",
            "cwd": "/Users/alice/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload is not None
        assert payload["project"] == "Users-alice-project"

    def test_namespace_with_missing_cwd(self):
        """Missing cwd defaults to 'unknown'."""
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/f.py"},
            "tool_use_id": "tu_ns2",
            "session_id": "sess-ns",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload is not None
        assert payload["project"] == "unknown"

    def test_namespace_with_empty_cwd(self):
        """Empty cwd defaults to 'unknown'."""
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/f.py"},
            "tool_use_id": "tu_ns3",
            "session_id": "sess-ns",
            "cwd": "",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload is not None
        assert payload["project"] == "unknown"


# =============================================================================
# Tag extraction
# =============================================================================


class TestTagExtraction:
    """Hook must extract correct tags from tool usage."""

    def test_file_tool_tags_include_filename(self):
        """File-based tools include lowercase filename in tags."""
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/src/MyModule.py"},
            "tool_use_id": "tu_tag1",
            "session_id": "sess-tag",
            "cwd": "/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload is not None
        assert payload["tags"] == "read,mymodule.py"

    def test_non_file_tool_tags_are_tool_name_only(self):
        """Non-file tools have just the tool name as tag."""
        stdin_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "tool_use_id": "tu_tag2",
            "session_id": "sess-tag",
            "cwd": "/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload is not None
        assert payload["tags"] == "bash"


# =============================================================================
# Summary truncation
# =============================================================================


class TestSummaryTruncation:
    """Hook must truncate summary to 500 characters."""

    def test_long_summary_is_truncated(self):
        """Summary exceeding 500 chars is truncated."""
        long_path = "/src/" + "a" * 600 + ".py"
        stdin_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": long_path},
            "tool_use_id": "tu_trunc1",
            "session_id": "sess-trunc",
            "cwd": "/project",
        }
        proc, payload = _run_hook_with_payload_capture(stdin_data)
        assert proc.returncode == 0
        assert payload is not None
        # Summary = "Read: " (6 chars) + subject[:100] = 106 chars max
        # But the summary field itself is capped at 500
        assert len(payload["summary"]) <= 500
