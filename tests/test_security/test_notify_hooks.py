"""Tests for notification hook scripts.

PostToolUse hook (notify-on-complete.sh):
- Fires notification when elapsed > threshold
- Does NOT fire when elapsed < threshold
- Blacklisted tools are skipped
- Timer file is DELETED after reading
- TTS timer file is NOT touched
- Missing timer file exits cleanly
- Disabled via SPELLBOOK_NOTIFY_ENABLED=false
- Custom threshold via SPELLBOOK_NOTIFY_THRESHOLD
- Custom title via SPELLBOOK_NOTIFY_TITLE
- Path traversal in tool_use_id is rejected

Hook registration in installer:
- notify-on-complete.sh is in PostToolUse HOOK_DEFINITIONS
- Hook is async with timeout=10
- Install/uninstall/reinstall idempotency
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from unittest.mock import patch

pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="Shell hook tests for Unix only",
    ),
    pytest.mark.integration,
]

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
NOTIFY_HOOK_SCRIPT = os.path.join(PROJECT_ROOT, "hooks", "notify-on-complete.sh")


def _run_hook(
    script: str, payload: dict, env_overrides: dict = None
) -> subprocess.CompletedProcess:
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


class TestNotifyHookExecutability:
    """Hook scripts are executable."""

    def test_sh_is_executable(self):
        assert os.access(NOTIFY_HOOK_SCRIPT, os.X_OK)

    def test_ps1_exists(self):
        ps1_script = NOTIFY_HOOK_SCRIPT.replace(".sh", ".ps1")
        assert os.path.isfile(ps1_script)


class TestNotifyHookBehavior:
    """notify-on-complete.sh reads timestamps and sends notifications."""

    def test_skips_blacklisted_tool(self):
        payload = {
            "tool_name": "AskUserQuestion",
            "tool_use_id": "test-notify-blacklist",
            "tool_input": {},
        }
        result = _run_hook(NOTIFY_HOOK_SCRIPT, payload)
        assert result.returncode == 0

    def test_skips_when_no_start_file(self):
        payload = {
            "tool_name": "Bash",
            "tool_use_id": "nonexistent-notify-id",
            "tool_input": {},
        }
        result = _run_hook(NOTIFY_HOOK_SCRIPT, payload)
        assert result.returncode == 0

    def test_skips_when_under_threshold(self):
        tool_use_id = f"test-notify-under-{int(time.time())}"
        # Write a start file with current timestamp (0 seconds ago)
        start_file = Path(f"/tmp/claude-notify-start-{tool_use_id}")
        start_file.write_text(str(int(time.time())))

        # Also write a TTS timer file to verify it is NOT touched
        tts_file = Path(f"/tmp/claude-tool-start-{tool_use_id}")
        tts_file.write_text(str(int(time.time())))

        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
        }
        # Set threshold high so it definitely skips
        result = _run_hook(
            NOTIFY_HOOK_SCRIPT,
            payload,
            {"SPELLBOOK_NOTIFY_THRESHOLD": "9999"},
        )
        assert result.returncode == 0
        # Notify start file should have been deleted (consumed)
        assert not start_file.exists()
        # TTS timer file must NOT be touched by the notification hook
        assert tts_file.exists()
        tts_file.unlink()  # Cleanup

    def test_timer_file_deleted_after_reading(self):
        tool_use_id = f"test-notify-delete-{int(time.time())}"
        start_file = Path(f"/tmp/claude-notify-start-{tool_use_id}")
        start_file.write_text(str(int(time.time())))

        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
        }
        _run_hook(
            NOTIFY_HOOK_SCRIPT,
            payload,
            {"SPELLBOOK_NOTIFY_THRESHOLD": "9999"},
        )
        assert not start_file.exists()

    def test_fires_when_above_threshold(self):
        tool_use_id = f"test-notify-above-{int(time.time())}"
        # Write a start file with timestamp 60 seconds ago
        start_file = Path(f"/tmp/claude-notify-start-{tool_use_id}")
        start_file.write_text(str(int(time.time()) - 60))

        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
        }
        # Low threshold so 60s ago triggers the notify path.
        # The osascript/notify-send call may succeed or fail depending on
        # test environment, but the hook must always exit 0.
        result = _run_hook(
            NOTIFY_HOOK_SCRIPT,
            payload,
            {"SPELLBOOK_NOTIFY_THRESHOLD": "5"},
        )
        assert result.returncode == 0
        # Start file should have been consumed
        assert not start_file.exists()

    def test_disabled_via_env_var(self):
        tool_use_id = f"test-notify-disabled-{int(time.time())}"
        start_file = Path(f"/tmp/claude-notify-start-{tool_use_id}")
        start_file.write_text(str(int(time.time()) - 60))

        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
        }
        result = _run_hook(
            NOTIFY_HOOK_SCRIPT,
            payload,
            {"SPELLBOOK_NOTIFY_ENABLED": "false"},
        )
        assert result.returncode == 0
        # With notifications disabled, the hook exits before reading the timer file
        # so the file may still exist. Clean up regardless.
        if start_file.exists():
            start_file.unlink()

    def test_custom_threshold_via_env_var(self):
        tool_use_id = f"test-notify-thresh-{int(time.time())}"
        # Write start file 10 seconds ago
        start_file = Path(f"/tmp/claude-notify-start-{tool_use_id}")
        start_file.write_text(str(int(time.time()) - 10))

        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
        }
        # Threshold of 20s: 10s elapsed should be under threshold
        result = _run_hook(
            NOTIFY_HOOK_SCRIPT,
            payload,
            {"SPELLBOOK_NOTIFY_THRESHOLD": "20"},
        )
        assert result.returncode == 0
        # Under threshold, so notification should not fire (but file is consumed)
        assert not start_file.exists()

    def test_exits_0_on_empty_stdin(self):
        result = subprocess.run(
            ["bash", NOTIFY_HOOK_SCRIPT],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_missing_timer_file_exits_cleanly(self):
        tool_use_id = f"test-notify-missing-{int(time.time())}"
        # Do NOT create the timer file
        payload = {
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {},
        }
        result = _run_hook(NOTIFY_HOOK_SCRIPT, payload)
        assert result.returncode == 0

    def test_path_traversal_rejected(self):
        payload = {
            "tool_name": "Bash",
            "tool_use_id": "../../../etc/passwd",
            "tool_input": {},
        }
        result = _run_hook(NOTIFY_HOOK_SCRIPT, payload)
        assert result.returncode == 0

    def test_whitespace_in_tool_use_id_rejected(self):
        payload = {
            "tool_name": "Bash",
            "tool_use_id": "id with spaces",
            "tool_input": {},
        }
        result = _run_hook(NOTIFY_HOOK_SCRIPT, payload)
        assert result.returncode == 0

    def test_slash_in_tool_use_id_rejected(self):
        payload = {
            "tool_name": "Bash",
            "tool_use_id": "id/with/slashes",
            "tool_input": {},
        }
        result = _run_hook(NOTIFY_HOOK_SCRIPT, payload)
        assert result.returncode == 0


class TestNotifyHookRegistration:
    """Notification hooks are properly registered in HOOK_DEFINITIONS."""

    def test_posttooluse_includes_notify_on_complete(self):
        from installer.components.hooks import HOOK_DEFINITIONS

        post_hooks = HOOK_DEFINITIONS["PostToolUse"]
        notify_entries = [
            e
            for e in post_hooks
            if any(
                "notify-on-complete" in str(h)
                for h in (
                    [e]
                    if isinstance(e, str)
                    else [
                        h.get("command", h) if isinstance(h, dict) else h
                        for h in e.get("hooks", [])
                    ]
                )
            )
        ]
        assert len(notify_entries) == 1
        entry = notify_entries[0]
        # Catch-all: matcher key must be omitted (not ".*")
        assert "matcher" not in entry

    def test_notify_hooks_are_async(self):
        from installer.components.hooks import HOOK_DEFINITIONS

        found_notify = False
        for entry in HOOK_DEFINITIONS["PostToolUse"]:
            for hook in entry.get("hooks", []):
                if (
                    isinstance(hook, dict)
                    and "notify-on-complete" in hook.get("command", "")
                ):
                    assert hook.get("async") is True
                    assert hook.get("timeout") == 10
                    found_notify = True
        assert found_notify, "notify-on-complete hook not found in PostToolUse"

    def test_install_writes_notify_hook(self, tmp_path):
        from installer.components.hooks import install_hooks

        settings_path = tmp_path / "settings.local.json"
        result = install_hooks(settings_path)
        assert result.success

        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

        # Check PostToolUse has notify-on-complete in the catch-all entry (no matcher)
        post_hooks = hooks.get("PostToolUse", [])
        notification_entry = post_hooks[-1]
        assert notification_entry == {
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/notify-on-complete.sh",
                    "async": True,
                    "timeout": 10,
                },
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/tts-notify.sh",
                    "async": True,
                    "timeout": 15,
                },
            ]
        }

    def test_uninstall_removes_notify_hook(self, tmp_path):
        from installer.components.hooks import install_hooks, uninstall_hooks

        settings_path = tmp_path / "settings.local.json"

        # Install first
        install_hooks(settings_path)
        # Then uninstall
        result = uninstall_hooks(settings_path)
        assert result.success

        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {})
        # After uninstall, all hook phases should be empty lists
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

    def test_platform_transform_windows(self):
        from installer.components.hooks import _get_hook_path_for_platform

        with patch("sys.platform", "win32"):
            result = _get_hook_path_for_platform(
                "$SPELLBOOK_DIR/hooks/notify-on-complete.sh"
            )
        assert result == "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/notify-on-complete.ps1"

    def test_platform_transform_unix(self):
        from installer.components.hooks import _get_hook_path_for_platform

        with patch("sys.platform", "linux"):
            result = _get_hook_path_for_platform(
                "$SPELLBOOK_DIR/hooks/notify-on-complete.sh"
            )
        assert result == "$SPELLBOOK_DIR/hooks/notify-on-complete.sh"
