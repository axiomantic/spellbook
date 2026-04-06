"""Tests for TTS hook behavior via the unified hook (spellbook_hook.py).

PreToolUse handler (timer recording):
- Writes timestamp file for valid input
- Exits 0 on empty stdin
- Exits 0 on missing tool_use_id

PostToolUse handler (TTS notification):
- Skips blacklisted tools
- Skips when no start file exists
- Skips when elapsed < threshold
- Exits 0 on all paths

Hook registration:
- Unified hook is registered in HOOK_DEFINITIONS for PreToolUse and PostToolUse
- No individual tts-timer-start or tts-notify hooks
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
UNIFIED_HOOK = os.path.join(PROJECT_ROOT, "hooks", "spellbook_hook.py")


def _run_hook(
    payload: dict,
    env_overrides: dict | None = None,
) -> subprocess.CompletedProcess:
    """Run the unified hook with the given JSON payload on stdin."""
    env = os.environ.copy()
    env["SPELLBOOK_DIR"] = PROJECT_ROOT
    env["PYTHONPATH"] = PROJECT_ROOT
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, UNIFIED_HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestUnifiedHookExists:
    """Unified hook script exists."""

    def test_hook_exists(self):
        assert os.path.isfile(UNIFIED_HOOK)


class TestTimerStartBehavior:
    """Timer recording via unified hook PreToolUse handler."""

    def test_writes_timestamp_file(self):
        tool_use_id = f"test-{int(time.time())}"
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
        }
        result = _run_hook(payload)
        assert result.returncode == 0

        start_file = Path(os.path.join(tempfile.gettempdir(), f"claude-tool-start-{tool_use_id}"))
        assert start_file.exists()
        ts = int(start_file.read_text().strip())
        assert abs(ts - int(time.time())) < 5
        start_file.unlink()  # Cleanup
        # Also clean up the notify timer file
        notify_file = Path(os.path.join(tempfile.gettempdir(), f"claude-notify-start-{tool_use_id}"))
        if notify_file.exists():
            notify_file.unlink()

    def test_exits_0_on_empty_stdin(self):
        result = subprocess.run(
            [sys.executable, UNIFIED_HOOK],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_0_on_missing_tool_use_id(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.py"},
        }
        result = _run_hook(payload)
        assert result.returncode == 0


class TestTtsNotifyBehavior:
    """TTS notification via unified hook PostToolUse handler."""

    def test_skips_blacklisted_tool(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "AskUserQuestion",
            "tool_use_id": "test-blacklist",
            "tool_input": {},
        }
        result = _run_hook(payload)
        assert result.returncode == 0

    def test_skips_when_no_start_file(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": "nonexistent-id",
            "tool_input": {},
        }
        result = _run_hook(payload)
        assert result.returncode == 0

    def test_skips_when_under_threshold(self):
        tool_use_id = f"test-under-{int(time.time())}"
        # Write a start file with current timestamp (0 seconds ago)
        start_file = Path(os.path.join(tempfile.gettempdir(), f"claude-tool-start-{tool_use_id}"))
        start_file.write_text(str(int(time.time())))

        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
            "cwd": "/tmp/myproject",
        }
        # Set threshold high so it definitely skips
        result = _run_hook(payload, {"SPELLBOOK_TTS_THRESHOLD": "9999"})
        assert result.returncode == 0
        # Clean up (file may or may not have been consumed by daemon thread)
        start_file.unlink(missing_ok=True)

    def test_exits_0_on_empty_stdin(self):
        result = subprocess.run(
            [sys.executable, UNIFIED_HOOK],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0


class TestHookRegistration:
    """Unified hook is properly registered in HOOK_DEFINITIONS."""

    def test_pretooluse_has_unified_hook(self):
        from installer.components.hooks import HOOK_DEFINITIONS
        pre_hooks = HOOK_DEFINITIONS["PreToolUse"]
        assert len(pre_hooks) == 1
        assert len(pre_hooks[0]["hooks"]) == 1
        assert pre_hooks[0]["hooks"][0] == {
            "type": "command",
            "command": "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py",
            "timeout": 15,
        }

    def test_posttooluse_has_unified_hook(self):
        from installer.components.hooks import HOOK_DEFINITIONS
        post_hooks = HOOK_DEFINITIONS["PostToolUse"]
        assert len(post_hooks) == 1
        assert len(post_hooks[0]["hooks"]) == 1
        assert post_hooks[0]["hooks"][0] == {
            "type": "command",
            "command": "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py",
            "timeout": 15,
        }

    def test_no_old_tts_hooks_registered(self):
        from installer.components.hooks import HOOK_DEFINITIONS
        for phase, entries in HOOK_DEFINITIONS.items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook if isinstance(hook, str) else hook.get("command", "")
                    assert "tts-timer-start" not in cmd, (
                        f"Old tts-timer-start still in {phase}"
                    )
                    assert "tts-notify" not in cmd, (
                        f"Old tts-notify still in {phase}"
                    )

    def test_unified_hooks_not_async(self):
        from installer.components.hooks import HOOK_DEFINITIONS
        for phase, entries in HOOK_DEFINITIONS.items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    if isinstance(hook, dict) and "spellbook_hook" in hook.get("command", ""):
                        assert hook.get("async") is not True, (
                            f"Unified hook in {phase} must not have async=True"
                        )

    def test_install_writes_unified_hook(self, tmp_path):
        from installer.components.hooks import install_hooks
        settings_path = tmp_path / "settings.local.json"
        result = install_hooks(settings_path)
        assert result.success

        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

        # PreToolUse: 1 entry with 1 unified hook
        pre_hooks = hooks.get("PreToolUse", [])
        assert len(pre_hooks) == 1
        assert len(pre_hooks[0]["hooks"]) == 1
        assert "spellbook_hook" in pre_hooks[0]["hooks"][0]["command"]

        # PostToolUse: 1 entry with 1 unified hook
        post_hooks = hooks.get("PostToolUse", [])
        assert len(post_hooks) == 1
        assert len(post_hooks[0]["hooks"]) == 1
        assert "spellbook_hook" in post_hooks[0]["hooks"][0]["command"]

    def test_uninstall_removes_hooks(self, tmp_path):
        from installer.components.hooks import install_hooks, uninstall_hooks
        settings_path = tmp_path / "settings.local.json"

        install_hooks(settings_path)
        result = uninstall_hooks(settings_path)
        assert result.success

        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {})
        for phase_name, entries in hooks.items():
            assert entries == [], (
                f"Hook phase {phase_name} still has entries after uninstall: {entries}"
            )

    def test_reinstall_idempotent(self, tmp_path):
        from installer.components.hooks import install_hooks
        settings_path = tmp_path / "settings.local.json"

        install_hooks(settings_path)
        first = json.loads(settings_path.read_text())
        install_hooks(settings_path)
        second = json.loads(settings_path.read_text())

        assert first == second  # No duplication

    def test_platform_transform_windows(self, monkeypatch):
        from installer.components.hooks import _get_hook_path_for_platform
        monkeypatch.setattr("sys.platform", "win32")
        result = _get_hook_path_for_platform("$SPELLBOOK_DIR/hooks/spellbook_hook.py")
        assert result == "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/spellbook_hook.ps1"

    def test_platform_transform_unix(self, monkeypatch):
        from installer.components.hooks import _get_hook_path_for_platform
        monkeypatch.setattr("sys.platform", "linux")
        result = _get_hook_path_for_platform("$SPELLBOOK_DIR/hooks/spellbook_hook.py")
        assert result == "$SPELLBOOK_DIR/hooks/spellbook_hook.py"
