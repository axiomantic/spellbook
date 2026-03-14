"""Tests for compaction recovery via the unified hook (spellbook_hook.py).

PreCompact handler:
- Reads stdin JSON and extracts cwd as project path
- Contacts MCP daemon to check/save workflow state
- FAIL-OPEN: always exits 0, never blocks compaction
- Handles daemon-unreachable gracefully

SessionStart handler (post-compact recovery):
- Reads stdin JSON and extracts cwd and source
- Only activates when source == "compact"
- Contacts MCP daemon to load workflow state and skill constraints
- Outputs hookSpecificOutput JSON with recovery directive
- FAIL-OPEN: outputs fallback directive on any error
- Handles daemon-unreachable with minimal fallback
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# Project root: tests/test_hooks/test_compaction_hooks.py -> test_hooks -> tests -> root
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
UNIFIED_HOOK = os.path.join(PROJECT_ROOT, "hooks", "spellbook_hook.py")

# Port where nothing listens, used for daemon-unreachable tests
DEAD_PORT = "19999"


def _run_hook(
    stdin_data: dict,
    *,
    hook_event_name: str = "PreCompact",
    env_overrides: dict | None = None,
    timeout: int = 10,
) -> subprocess.CompletedProcess:
    """Run the unified hook with given stdin JSON."""
    payload = dict(stdin_data)
    payload["hook_event_name"] = hook_event_name

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
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


# =============================================================================
# pre-compact tests via unified hook
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
            "trigger": "auto",
            "custom_instructions": "",
        }
        proc = _run_hook(stdin_data, hook_event_name="PreCompact")
        assert proc.returncode == 0

    def test_exits_zero_with_empty_stdin(self):
        """Empty stdin should not crash, exit 0."""
        env = os.environ.copy()
        env["SPELLBOOK_DIR"] = PROJECT_ROOT
        env["PYTHONPATH"] = PROJECT_ROOT
        env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
        env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"

        proc = subprocess.run(
            [sys.executable, UNIFIED_HOOK],
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
        env["SPELLBOOK_DIR"] = PROJECT_ROOT
        env["PYTHONPATH"] = PROJECT_ROOT
        env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
        env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"

        proc = subprocess.run(
            [sys.executable, UNIFIED_HOOK],
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
        }
        proc = _run_hook(stdin_data, hook_event_name="PreCompact")
        assert proc.returncode == 0


class TestPreCompactNoSourceField:
    """PreCompact hook does not have a source field - should still work."""

    def test_works_without_source_field(self):
        """PreCompact stdin has no source field, unlike SessionStart."""
        stdin_data = {
            "session_id": "abc",
            "transcript_path": "/path/to/session.jsonl",
            "cwd": "/tmp/test-project",
            "permission_mode": "default",
            "trigger": "auto",
            "custom_instructions": "",
        }
        proc = _run_hook(stdin_data, hook_event_name="PreCompact")
        assert proc.returncode == 0


# =============================================================================
# post-compact-recover (SessionStart) tests via unified hook
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
            "source": "compact",
            "model": "claude-sonnet-4-6",
        }
        proc = _run_hook(stdin_data, hook_event_name="SessionStart")
        assert proc.returncode == 0

    def test_exits_zero_with_empty_stdin(self):
        """Empty stdin should not crash, exit 0."""
        env = os.environ.copy()
        env["SPELLBOOK_DIR"] = PROJECT_ROOT
        env["PYTHONPATH"] = PROJECT_ROOT
        env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
        env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"

        proc = subprocess.run(
            [sys.executable, UNIFIED_HOOK],
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
        env["SPELLBOOK_DIR"] = PROJECT_ROOT
        env["PYTHONPATH"] = PROJECT_ROOT
        env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
        env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"

        proc = subprocess.run(
            [sys.executable, UNIFIED_HOOK],
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
            "source": "compact",
            "model": "claude-sonnet-4-6",
        }
        proc = _run_hook(stdin_data, hook_event_name="SessionStart")
        assert proc.returncode == 0

        # stdout should be valid JSON
        stdout = proc.stdout.strip()
        assert stdout, "Expected JSON output on stdout"

        output = json.loads(stdout)
        assert "hookSpecificOutput" in output

        hook_output = output["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "SessionStart"
        assert "additionalContext" in hook_output
        assert len(hook_output["additionalContext"]) > 0

    def test_fallback_directive_content(self):
        """Fallback directive must provide recovery guidance."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
            "source": "compact",
        }
        proc = _run_hook(stdin_data, hook_event_name="SessionStart")
        assert proc.returncode == 0

        stdout = proc.stdout.strip()
        output = json.loads(stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert context == (
            "Session resumed after compaction. Workflow state could not "
            "be loaded. Re-read any planning documents, check your todo "
            "list, and verify your current working context."
        )


class TestPostCompactSourceFilter:
    """Post-compact hook should only activate for source=compact."""

    def test_non_compact_source_produces_no_output(self):
        """When source is not 'compact', should exit 0 with no output."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
            "source": "user",
            "model": "claude-sonnet-4-6",
        }
        proc = _run_hook(stdin_data, hook_event_name="SessionStart")
        assert proc.returncode == 0
        # When source != compact, handler returns None, no stdout
        assert proc.stdout.strip() == ""

    def test_missing_source_produces_no_output(self):
        """When source field is missing, should exit 0 with no output."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
        }
        proc = _run_hook(stdin_data, hook_event_name="SessionStart")
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""

    def test_empty_source_produces_no_output(self):
        """When source is empty string, should exit 0 with no output."""
        stdin_data = {
            "session_id": "test-session",
            "cwd": "/tmp/test-project",
            "source": "",
        }
        proc = _run_hook(stdin_data, hook_event_name="SessionStart")
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""
