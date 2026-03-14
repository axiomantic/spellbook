"""Unit tests for the unified spellbook hook entrypoint."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
HOOK_SCRIPT = os.path.join(PROJECT_ROOT, "hooks", "spellbook_hook.py")


def _run_hook(stdin_data: dict | str, env_overrides: dict | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run the unified hook with given stdin."""
    env = os.environ.copy()
    env["SPELLBOOK_MCP_PORT"] = "19999"  # dead port
    env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"
    if env_overrides:
        env.update(env_overrides)

    input_str = json.dumps(stdin_data) if isinstance(stdin_data, dict) else stdin_data

    return subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=input_str,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


class TestHookScriptProperties:
    """Verify spellbook_hook.py has correct file properties."""

    def test_script_exists(self):
        assert os.path.isfile(HOOK_SCRIPT), f"Script not found at {HOOK_SCRIPT}"

    def test_script_has_python_shebang(self):
        with open(HOOK_SCRIPT) as f:
            first_line = f.readline()
        assert first_line == "#!/usr/bin/env python3\n", f"Expected '#!/usr/bin/env python3\\n', got: {first_line!r}"


class TestEventDetection:
    """Test that the hook correctly identifies event types."""

    def test_pre_tool_use_detected(self):
        """PreToolUse: has tool_name but no tool_result."""
        proc = _run_hook({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert proc.returncode == 0

    def test_post_tool_use_detected(self):
        """PostToolUse: has tool_result."""
        proc = _run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_result": "file1.py\nfile2.py",
        })
        assert proc.returncode == 0

    def test_pre_compact_detected(self):
        """PreCompact: has hook_event_name."""
        proc = _run_hook({
            "hook_event_name": "PreCompact",
            "cwd": "/tmp/test",
            "trigger": "auto",
        })
        assert proc.returncode == 0

    def test_session_start_detected(self):
        """SessionStart: has hook_event_name."""
        proc = _run_hook({
            "hook_event_name": "SessionStart",
            "cwd": "/tmp/test",
            "source": "compact",
            "session_id": "test-123",
        })
        assert proc.returncode == 0

    def test_empty_stdin_exits_zero(self):
        proc = _run_hook("")
        assert proc.returncode == 0

    def test_invalid_json_exits_zero(self):
        proc = _run_hook("not valid json {{{")
        assert proc.returncode == 0

    def test_unknown_event_exits_zero(self):
        proc = _run_hook({"random_field": "value"})
        assert proc.returncode == 0
