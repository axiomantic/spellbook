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
from unittest.mock import patch

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
        # Verify the hook did NOT attempt to reach /api/speak
        combined = result.stdout + result.stderr
        assert "/api/speak" not in combined
        assert "curl" not in combined

    def test_skips_when_no_start_file(self):
        payload = {
            "tool_name": "Bash",
            "tool_use_id": "nonexistent-id",
            "tool_input": {},
        }
        result = _run_hook(TTS_NOTIFY_SCRIPT, payload)
        assert result.returncode == 0
        # Verify the hook did NOT attempt to reach /api/speak
        combined = result.stdout + result.stderr
        assert "/api/speak" not in combined
        assert "curl" not in combined

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
        # Verify the hook did NOT attempt to reach /api/speak
        combined = result.stdout + result.stderr
        assert "/api/speak" not in combined
        assert "curl" not in combined

    def test_attempts_speak_when_above_threshold(self):
        tool_use_id = f"test-above-{int(time.time())}"
        # Write a start file with timestamp 60 seconds ago
        start_file = Path(f"/tmp/claude-tool-start-{tool_use_id}")
        start_file.write_text(str(int(time.time()) - 60))

        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
            "cwd": "/tmp/myproject",
        }
        # Use a low threshold (5s) so 60s ago triggers the notify path.
        # Point to a port that nothing is listening on so curl fails silently.
        result = _run_hook(TTS_NOTIFY_SCRIPT, payload, {
            "SPELLBOOK_TTS_THRESHOLD": "5",
            "SPELLBOOK_MCP_PORT": "19999",
        })
        assert result.returncode == 0
        # Start file should have been consumed (deleted by the hook)
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


class TestHookRegistration:
    """TTS hooks are properly registered in HOOK_DEFINITIONS."""

    def test_pretooluse_includes_tts_timer_start(self):
        from installer.components.hooks import HOOK_DEFINITIONS
        pre_hooks = HOOK_DEFINITIONS["PreToolUse"]
        tts_entries = [
            e for e in pre_hooks
            if any("tts-timer-start" in str(h) for h in (
                [e] if isinstance(e, str) else
                [h.get("command", h) if isinstance(h, dict) else h for h in e.get("hooks", [])]
            ))
        ]
        assert len(tts_entries) == 1
        entry = tts_entries[0]
        assert entry["matcher"] == ".*"

    def test_posttooluse_includes_tts_notify(self):
        from installer.components.hooks import HOOK_DEFINITIONS
        post_hooks = HOOK_DEFINITIONS["PostToolUse"]
        tts_entries = [
            e for e in post_hooks
            if any("tts-notify" in str(h) for h in (
                [e] if isinstance(e, str) else
                [h.get("command", h) if isinstance(h, dict) else h for h in e.get("hooks", [])]
            ))
        ]
        assert len(tts_entries) == 1
        entry = tts_entries[0]
        assert entry["matcher"] == ".*"

    def test_tts_hooks_are_async(self):
        from installer.components.hooks import HOOK_DEFINITIONS
        # PreToolUse tts hook
        found_timer = False
        for entry in HOOK_DEFINITIONS["PreToolUse"]:
            for hook in entry.get("hooks", []):
                if isinstance(hook, dict) and "tts-timer-start" in hook.get("command", ""):
                    assert hook.get("async") is True
                    assert hook.get("timeout") == 5
                    found_timer = True
        assert found_timer, "tts-timer-start hook not found in PreToolUse"
        # PostToolUse tts hook
        found_notify = False
        for entry in HOOK_DEFINITIONS["PostToolUse"]:
            for hook in entry.get("hooks", []):
                if isinstance(hook, dict) and "tts-notify" in hook.get("command", ""):
                    assert hook.get("async") is True
                    assert hook.get("timeout") == 15
                    found_notify = True
        assert found_notify, "tts-notify hook not found in PostToolUse"

    def test_install_writes_both_tts_hooks(self, tmp_path):
        from installer.components.hooks import install_hooks
        settings_path = tmp_path / "settings.local.json"
        result = install_hooks(settings_path)
        assert result.success

        import json
        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

        # Check PreToolUse has tts-timer-start
        pre_hooks_flat = json.dumps(hooks.get("PreToolUse", []))
        assert "tts-timer-start" in pre_hooks_flat

        # Check PostToolUse has tts-notify
        post_hooks_flat = json.dumps(hooks.get("PostToolUse", []))
        assert "tts-notify" in post_hooks_flat

    def test_uninstall_removes_tts_hooks(self, tmp_path):
        from installer.components.hooks import install_hooks, uninstall_hooks
        import json
        settings_path = tmp_path / "settings.local.json"

        # Install first
        install_hooks(settings_path)
        # Then uninstall
        result = uninstall_hooks(settings_path)
        assert result.success

        settings = json.loads(settings_path.read_text())
        hooks_flat = json.dumps(settings.get("hooks", {}))
        assert "tts-timer-start" not in hooks_flat
        assert "tts-notify" not in hooks_flat

    def test_reinstall_idempotent(self, tmp_path):
        from installer.components.hooks import install_hooks
        import json
        settings_path = tmp_path / "settings.local.json"

        install_hooks(settings_path)
        first = json.loads(settings_path.read_text())
        install_hooks(settings_path)
        second = json.loads(settings_path.read_text())

        assert first == second  # No duplication

    def test_platform_transform_windows(self):
        from installer.components.hooks import _get_hook_path_for_platform
        with patch("sys.platform", "win32"):
            result = _get_hook_path_for_platform("$SPELLBOOK_DIR/hooks/tts-timer-start.sh")
        assert result == "$SPELLBOOK_DIR/hooks/tts-timer-start.py"

    def test_platform_transform_unix(self):
        from installer.components.hooks import _get_hook_path_for_platform
        with patch("sys.platform", "linux"):
            result = _get_hook_path_for_platform("$SPELLBOOK_DIR/hooks/tts-timer-start.sh")
        assert result == "$SPELLBOOK_DIR/hooks/tts-timer-start.sh"
