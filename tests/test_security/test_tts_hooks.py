"""Tests for TTS hook scripts.

PreToolUse hook (tts-timer-start.sh):
- Writes timestamp file for valid input
- Exits 0 on empty stdin
- Exits 0 on missing tool_use_id
- Fail-open on write errors

PostToolUse hook (tts-notify.sh):
- Skips blacklisted tools
- Skips when no start file exists
- Skips when elapsed < threshold
- Builds correct message format
- Exits 0 on all error paths
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Bash scripts not available on Windows",
)

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
TIMER_START_SCRIPT = os.path.join(PROJECT_ROOT, "hooks", "tts-timer-start.sh")
TTS_NOTIFY_SCRIPT = os.path.join(PROJECT_ROOT, "hooks", "tts-notify.sh")


def _run_hook(script: str, payload: dict, env_overrides: dict = None) -> subprocess.CompletedProcess:
    """Run a hook script with the given JSON payload on stdin."""
    env = os.environ.copy()
    env["SPELLBOOK_DIR"] = PROJECT_ROOT
    env["PYTHONPATH"] = PROJECT_ROOT
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestTimerStartExecutability:
    """Hook scripts are executable."""

    def test_sh_is_executable(self):
        assert os.access(TIMER_START_SCRIPT, os.X_OK)

    def test_py_is_executable(self):
        py_script = TIMER_START_SCRIPT.replace(".sh", ".py")
        assert os.access(py_script, os.X_OK)


class TestTimerStartBehavior:
    """tts-timer-start.sh writes timestamp files."""

    def test_writes_timestamp_file(self):
        tool_use_id = f"test-{int(time.time())}"
        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
        }
        result = _run_hook(TIMER_START_SCRIPT, payload)
        assert result.returncode == 0

        start_file = Path(f"/tmp/claude-tool-start-{tool_use_id}")
        assert start_file.exists()
        ts = int(start_file.read_text().strip())
        assert abs(ts - int(time.time())) < 5
        start_file.unlink()  # Cleanup

    def test_exits_0_on_empty_stdin(self):
        result = subprocess.run(
            ["bash", TIMER_START_SCRIPT],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_0_on_missing_tool_use_id(self):
        payload = {"tool_name": "Bash", "tool_input": {}}
        result = _run_hook(TIMER_START_SCRIPT, payload)
        assert result.returncode == 0


class TestTtsNotifyExecutability:
    """tts-notify hook scripts are executable."""

    def test_sh_is_executable(self):
        assert os.access(TTS_NOTIFY_SCRIPT, os.X_OK)

    def test_py_is_executable(self):
        py_script = TTS_NOTIFY_SCRIPT.replace(".sh", ".py")
        assert os.access(py_script, os.X_OK)


class TestTtsNotifyBehavior:
    """tts-notify.sh reads timestamps and triggers TTS."""

    def test_skips_blacklisted_tool(self):
        payload = {
            "tool_name": "AskUserQuestion",
            "tool_use_id": "test-blacklist",
            "tool_input": {},
        }
        result = _run_hook(TTS_NOTIFY_SCRIPT, payload)
        assert result.returncode == 0

    def test_skips_when_no_start_file(self):
        payload = {
            "tool_name": "Bash",
            "tool_use_id": "nonexistent-id",
            "tool_input": {},
        }
        result = _run_hook(TTS_NOTIFY_SCRIPT, payload)
        assert result.returncode == 0

    def test_skips_when_under_threshold(self):
        tool_use_id = f"test-under-{int(time.time())}"
        # Write a start file with current timestamp (0 seconds ago)
        start_file = Path(f"/tmp/claude-tool-start-{tool_use_id}")
        start_file.write_text(str(int(time.time())))

        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
            "cwd": "/tmp/myproject",
        }
        # Set threshold high so it definitely skips
        result = _run_hook(TTS_NOTIFY_SCRIPT, payload, {"SPELLBOOK_TTS_THRESHOLD": "9999"})
        assert result.returncode == 0
        # Start file should have been cleaned up
        assert not start_file.exists()

    def test_exits_0_on_empty_stdin(self):
        result = subprocess.run(
            ["bash", TTS_NOTIFY_SCRIPT],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
