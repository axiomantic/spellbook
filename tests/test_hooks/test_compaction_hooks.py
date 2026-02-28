"""Tests for compaction recovery hook scripts.

pre-compact-save.sh (PreCompact hook):
- Reads stdin JSON and extracts cwd as project path
- Contacts MCP daemon to check/save workflow state
- FAIL-OPEN: always exits 0, never blocks compaction
- Handles daemon-unreachable gracefully

post-compact-recover.sh (SessionStart hook):
- Reads stdin JSON and extracts cwd and source
- Only activates when source == "compact"
- Contacts MCP daemon to load workflow state and skill constraints
- Outputs hookSpecificOutput JSON with recovery directive
- FAIL-OPEN: outputs fallback directive on any error
- Handles daemon-unreachable with minimal fallback
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

# Project root: tests/test_hooks/test_compaction_hooks.py -> tests/test_hooks -> tests -> root
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
PRE_COMPACT_SCRIPT = os.path.join(PROJECT_ROOT, "hooks", "pre-compact-save.sh")
POST_COMPACT_SCRIPT = os.path.join(PROJECT_ROOT, "hooks", "post-compact-recover.sh")

# Port where nothing listens, used for daemon-unreachable tests
DEAD_PORT = "19999"


def _run_pre_compact(
    stdin_data: dict,
    *,
    env_overrides: dict | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Run pre-compact-save.sh with given stdin JSON."""
    env = os.environ.copy()
    # Use a dead port by default so we don't accidentally hit a real daemon
    env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
    env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"
    if env_overrides:
        env.update(env_overrides)

    return subprocess.run(
        ["bash", PRE_COMPACT_SCRIPT],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def _run_post_compact(
    stdin_data: dict,
    *,
    env_overrides: dict | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Run post-compact-recover.sh with given stdin JSON."""
    env = os.environ.copy()
    # Use a dead port by default so we don't accidentally hit a real daemon
    env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
    env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"
    if env_overrides:
        env.update(env_overrides)

    return subprocess.run(
        ["bash", POST_COMPACT_SCRIPT],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


# =============================================================================
# Script executability and structure
# =============================================================================


class TestPreCompactScriptProperties:
    """Verify pre-compact-save.sh has correct file properties."""

    def test_script_exists(self):
        assert os.path.isfile(PRE_COMPACT_SCRIPT), (
            f"Script not found at {PRE_COMPACT_SCRIPT}"
        )

    def test_script_is_executable(self):
        st = os.stat(PRE_COMPACT_SCRIPT)
        assert st.st_mode & stat.S_IXUSR, "Script is not user-executable"

    def test_script_has_bash_shebang(self):
        with open(PRE_COMPACT_SCRIPT) as f:
            first_line = f.readline()
        assert first_line.strip() == "#!/usr/bin/env bash"


class TestPostCompactScriptProperties:
    """Verify post-compact-recover.sh has correct file properties."""

    def test_script_exists(self):
        assert os.path.isfile(POST_COMPACT_SCRIPT), (
            f"Script not found at {POST_COMPACT_SCRIPT}"
        )

    def test_script_is_executable(self):
        st = os.stat(POST_COMPACT_SCRIPT)
        assert st.st_mode & stat.S_IXUSR, "Script is not user-executable"

    def test_script_has_bash_shebang(self):
        with open(POST_COMPACT_SCRIPT) as f:
            first_line = f.readline()
        assert first_line.strip() == "#!/usr/bin/env bash"


# =============================================================================
# pre-compact-save.sh tests
# =============================================================================


class TestPreCompactFailOpen:
    """Pre-compact hook must NEVER block compaction (always exit 0)."""

    def test_exits_zero_with_valid_input_daemon_unreachable(self):
        """When daemon is unreachable, exits 0 without blocking."""
        stdin_data = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/test-session.jsonl",
            "cwd": "/tmp/test-project",
            "permission_mode": "default",
            "hook_event_name": "PreCompact",
            "trigger": "auto",
            "custom_instructions": "",
        }
        proc = _run_pre_compact(stdin_data)
        assert proc.returncode == 0, (
            f"Expected exit 0 but got {proc.returncode}. "
            f"stderr: {proc.stderr}"
        )

    def test_exits_zero_with_empty_stdin(self):
        """Empty stdin should not crash, exit 0."""
        env = os.environ.copy()
        env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
        env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"

        proc = subprocess.run(
            ["bash", PRE_COMPACT_SCRIPT],
            input="",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert proc.returncode == 0

    def test_exits_zero_with_invalid_json(self):
        """Invalid JSON on stdin should not crash, exit 0."""
        env = os.environ.copy()
        env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
        env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"

        proc = subprocess.run(
            ["bash", PRE_COMPACT_SCRIPT],
            input="not valid json {{{",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert proc.returncode == 0

    def test_exits_zero_with_missing_cwd(self):
        """JSON without cwd field should exit 0."""
        stdin_data = {
            "session_id": "test-session",
            "hook_event_name": "PreCompact",
        }
        proc = _run_pre_compact(stdin_data)
        assert proc.returncode == 0

    def test_no_stderr_output(self):
        """Pre-compact hook should not write to stderr (shows to user)."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
            "hook_event_name": "PreCompact",
        }
        proc = _run_pre_compact(stdin_data)
        assert proc.returncode == 0
        # stderr should be empty (all logging goes to file)
        assert proc.stderr == "", (
            f"Unexpected stderr output: {proc.stderr}"
        )


class TestPreCompactNoSourceField:
    """PreCompact hook does not have a source field - should still work."""

    def test_works_without_source_field(self):
        """PreCompact stdin has no source field, unlike SessionStart."""
        stdin_data = {
            "session_id": "abc",
            "transcript_path": "/path/to/session.jsonl",
            "cwd": "/tmp/test-project",
            "permission_mode": "default",
            "hook_event_name": "PreCompact",
            "trigger": "auto",
            "custom_instructions": "",
        }
        proc = _run_pre_compact(stdin_data)
        assert proc.returncode == 0


# =============================================================================
# post-compact-recover.sh tests
# =============================================================================


class TestPostCompactFailOpen:
    """Post-compact hook must NEVER prevent session start (always exit 0)."""

    def test_exits_zero_daemon_unreachable(self):
        """When daemon is unreachable, exits 0 with fallback directive."""
        stdin_data = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/test-session.jsonl",
            "cwd": "/tmp/test-project",
            "permission_mode": "default",
            "hook_event_name": "SessionStart",
            "source": "compact",
            "model": "claude-sonnet-4-6",
        }
        proc = _run_post_compact(stdin_data)
        assert proc.returncode == 0, (
            f"Expected exit 0 but got {proc.returncode}. "
            f"stderr: {proc.stderr}"
        )

    def test_exits_zero_with_empty_stdin(self):
        """Empty stdin should not crash, exit 0."""
        env = os.environ.copy()
        env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
        env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"

        proc = subprocess.run(
            ["bash", POST_COMPACT_SCRIPT],
            input="",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert proc.returncode == 0

    def test_exits_zero_with_invalid_json(self):
        """Invalid JSON on stdin should not crash, exit 0."""
        env = os.environ.copy()
        env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
        env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"

        proc = subprocess.run(
            ["bash", POST_COMPACT_SCRIPT],
            input="totally broken json!!!",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert proc.returncode == 0


class TestPostCompactOutputFormat:
    """Post-compact hook must produce valid hookSpecificOutput JSON."""

    def test_produces_valid_json_on_daemon_unreachable(self):
        """When daemon is unreachable, outputs valid hookSpecificOutput JSON."""
        stdin_data = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/test-session.jsonl",
            "cwd": "/tmp/test-project",
            "permission_mode": "default",
            "hook_event_name": "SessionStart",
            "source": "compact",
            "model": "claude-sonnet-4-6",
        }
        proc = _run_post_compact(stdin_data)
        assert proc.returncode == 0

        # stdout should be valid JSON
        stdout = proc.stdout.strip()
        assert stdout, "Expected JSON output on stdout"

        output = json.loads(stdout)
        assert "hookSpecificOutput" in output, (
            f"Missing hookSpecificOutput key. Got: {output}"
        )

        hook_output = output["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "SessionStart"
        assert "additionalContext" in hook_output
        assert len(hook_output["additionalContext"]) > 0

    def test_fallback_directive_mentions_spellbook_session_init(self):
        """Fallback directive must tell Claude to call spellbook_session_init."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
            "hook_event_name": "SessionStart",
            "source": "compact",
        }
        proc = _run_post_compact(stdin_data)
        assert proc.returncode == 0

        stdout = proc.stdout.strip()
        output = json.loads(stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert "spellbook_session_init" in context, (
            f"Fallback directive must mention spellbook_session_init. "
            f"Got: {context}"
        )

    def test_no_stderr_output(self):
        """Post-compact hook should not write to stderr (shows to user)."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
            "hook_event_name": "SessionStart",
            "source": "compact",
        }
        proc = _run_post_compact(stdin_data)
        assert proc.returncode == 0
        assert proc.stderr == "", (
            f"Unexpected stderr output: {proc.stderr}"
        )


class TestPostCompactSourceFilter:
    """Post-compact hook should only activate for source=compact."""

    def test_non_compact_source_produces_no_output(self):
        """When source is not 'compact', should exit 0 with no output."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
            "hook_event_name": "SessionStart",
            "source": "user",
            "model": "claude-sonnet-4-6",
        }
        proc = _run_post_compact(stdin_data)
        assert proc.returncode == 0
        # When source != compact, script exits early with no stdout
        assert proc.stdout.strip() == "", (
            f"Expected no output for non-compact source, got: {proc.stdout}"
        )

    def test_missing_source_produces_no_output(self):
        """When source field is missing, should exit 0 with no output."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
            "hook_event_name": "SessionStart",
        }
        proc = _run_post_compact(stdin_data)
        assert proc.returncode == 0
        # Missing source is treated as non-compact
        assert proc.stdout.strip() == "", (
            f"Expected no output for missing source, got: {proc.stdout}"
        )

    def test_empty_source_produces_no_output(self):
        """When source is empty string, should exit 0 with no output."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
            "hook_event_name": "SessionStart",
            "source": "",
        }
        proc = _run_post_compact(stdin_data)
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""
