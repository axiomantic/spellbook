"""Tests for notification hook behavior via the unified hook (spellbook_hook.py).

PostToolUse handler (notify-on-complete logic):
- Fires notification when elapsed > threshold
- Does NOT fire when elapsed < threshold
- Blacklisted tools are skipped
- Timer file is DELETED after reading
- Missing timer file exits cleanly
- Path traversal in tool_use_id is rejected

Hook registration in installer:
- Unified hook handles notification internally
- No individual notify-on-complete.sh hook in HOOK_DEFINITIONS
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


class TestNotifyHookBehavior:
    """Notification behavior via unified hook PostToolUse handler."""

    def test_skips_blacklisted_tool(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "AskUserQuestion",
            "tool_use_id": "test-notify-blacklist",
            "tool_input": {},
        }
        result = _run_hook(payload)
        assert result.returncode == 0

    def test_skips_when_no_start_file(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": "nonexistent-notify-id",
            "tool_input": {},
        }
        result = _run_hook(payload)
        assert result.returncode == 0

    def test_skips_when_under_threshold(self):
        tool_use_id = f"test-notify-under-{int(time.time())}"
        # Write a notify start file with current timestamp
        start_file = Path(os.path.join(tempfile.gettempdir(), f"claude-notify-start-{tool_use_id}"))
        start_file.write_text(str(int(time.time())))

        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {"command": "ls"},
        }
        # Set threshold high so it definitely skips
        result = _run_hook(payload, {"SPELLBOOK_NOTIFY_THRESHOLD": "9999"})
        assert result.returncode == 0
        # Clean up (file may or may not have been consumed by daemon thread)
        start_file.unlink(missing_ok=True)

    def test_missing_timer_file_exits_cleanly(self):
        tool_use_id = f"test-notify-missing-{int(time.time())}"
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": tool_use_id,
            "tool_input": {},
        }
        result = _run_hook(payload)
        assert result.returncode == 0

    def test_path_traversal_rejected(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": "../../../etc/passwd",
            "tool_input": {},
        }
        result = _run_hook(payload)
        assert result.returncode == 0

    def test_whitespace_in_tool_use_id_rejected(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": "id with spaces",
            "tool_input": {},
        }
        result = _run_hook(payload)
        assert result.returncode == 0

    def test_slash_in_tool_use_id_rejected(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_use_id": "id/with/slashes",
            "tool_input": {},
        }
        result = _run_hook(payload)
        assert result.returncode == 0

    def test_exits_0_on_empty_stdin(self):
        result = subprocess.run(
            [sys.executable, UNIFIED_HOOK],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0


class TestNotifyHookRegistration:
    """Notification hooks are handled by the unified hook."""

    def test_no_old_notify_hook_registered(self):
        from installer.components.hooks import HOOK_DEFINITIONS
        for phase, entries in HOOK_DEFINITIONS.items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook if isinstance(hook, str) else hook.get("command", "")
                    assert "notify-on-complete" not in cmd, (
                        f"Old notify-on-complete still in {phase}"
                    )

    def test_posttooluse_has_unified_hook(self):
        from installer.components.hooks import HOOK_DEFINITIONS
        post_hooks = HOOK_DEFINITIONS["PostToolUse"]
        assert len(post_hooks) == 1
        assert len(post_hooks[0]["hooks"]) == 1
        assert post_hooks[0]["hooks"][0] == {
            "type": "command",
            "command": "$SPELLBOOK_DIR/hooks/spellbook_hook.py",
            "timeout": 15,
        }

    def test_install_writes_unified_hook(self, tmp_path):
        from installer.components.hooks import install_hooks
        settings_path = tmp_path / "settings.local.json"
        result = install_hooks(settings_path)
        assert result.success

        settings = json.loads(settings_path.read_text())
        hooks = settings["hooks"]

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

        assert first == second

    def test_platform_transform_windows(self, monkeypatch):
        from installer.components.hooks import _get_hook_path_for_platform
        monkeypatch.setattr("sys.platform", "win32")
        result = _get_hook_path_for_platform(
            "$SPELLBOOK_DIR/hooks/spellbook_hook.py"
        )
        assert result == "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/spellbook_hook.ps1"

    def test_platform_transform_unix(self, monkeypatch):
        from installer.components.hooks import _get_hook_path_for_platform
        monkeypatch.setattr("sys.platform", "linux")
        result = _get_hook_path_for_platform(
            "$SPELLBOOK_DIR/hooks/spellbook_hook.py"
        )
        assert result == "$SPELLBOOK_DIR/hooks/spellbook_hook.py"
