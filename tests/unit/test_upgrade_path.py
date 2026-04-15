"""Test that upgrading from shell hooks to unified hook produces clean settings."""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from installer.components.hooks import install_hooks, _get_hook_path


def _expected_unified_command(prefix="$SPELLBOOK_DIR", config_prefix="$SPELLBOOK_CONFIG_DIR"):
    """Return the expected unified hook command for the current platform."""
    if sys.platform == "win32":
        return f"powershell -ExecutionPolicy Bypass -File {prefix}/hooks/spellbook_hook.ps1"
    return f"{config_prefix}/daemon-venv/bin/python {prefix}/hooks/spellbook_hook.py"


class TestUpgradeFromShellHooks:
    """Verify install_hooks replaces old shell hooks with unified hook."""

    def test_upgrade_removes_all_old_shell_hooks(self, tmp_path):
        """Settings with old shell hooks should have only unified hook after install."""
        settings_path = tmp_path / "settings.json"
        # Simulate pre-upgrade settings with all 12 old shell hooks
        old_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.sh"},
                        ],
                    },
                    {
                        "matcher": "spawn_claude_session",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/spawn-guard.sh"},
                        ],
                    },
                    {
                        "matcher": "mcp__spellbook__workflow_state_save",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/state-sanitize.sh", "timeout": 15},
                        ],
                    },
                    {
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/tts-timer-start.sh", "async": True, "timeout": 5},
                        ],
                    },
                ],
                "PostToolUse": [
                    {
                        "matcher": "Bash|Read|WebFetch|Grep|mcp__.*",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/audit-log.sh", "async": True, "timeout": 10},
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/canary-check.sh", "timeout": 10},
                        ],
                    },
                    {
                        "matcher": "Read|Edit|Grep|Glob",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/memory-inject.sh", "timeout": 5},
                        ],
                    },
                    {
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/notify-on-complete.sh", "async": True, "timeout": 10},
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/tts-notify.sh", "async": True, "timeout": 15},
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/memory-capture.sh", "async": True, "timeout": 5},
                        ],
                    },
                ],
                "PreCompact": [
                    {
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/pre-compact-save.sh", "timeout": 5},
                        ],
                    },
                ],
                "SessionStart": [
                    {
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/post-compact-recover.sh", "timeout": 10},
                        ],
                    },
                ],
            }
        }
        settings_path.write_text(json.dumps(old_settings))

        result = install_hooks(settings_path)
        assert result.success is True
        assert result.action == "installed"

        updated = json.loads(settings_path.read_text())

        # Collect all commands across all phases
        all_commands = []
        for phase in ("PreToolUse", "PostToolUse", "PreCompact", "SessionStart"):
            for entry in updated.get("hooks", {}).get(phase, []):
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "") if isinstance(hook, dict) else hook
                    all_commands.append(cmd)

        # No old shell hooks should remain
        old_hooks = {
            "bash-gate.sh", "spawn-guard.sh", "state-sanitize.sh",
            "tts-timer-start.sh", "audit-log.sh", "canary-check.sh",
            "memory-inject.sh", "notify-on-complete.sh", "tts-notify.sh",
            "memory-capture.sh", "pre-compact-save.sh", "post-compact-recover.sh",
        }
        for cmd in all_commands:
            for old in old_hooks:
                assert old not in cmd, f"Old hook {old} still present after upgrade: {cmd}"

        # Exactly 4 commands total (one per phase), all unified
        expected_cmd = _expected_unified_command()
        assert all_commands == [expected_cmd, expected_cmd, expected_cmd, expected_cmd]

        # Each phase should have exactly 1 entry with 1 hook, no matcher
        for phase in ("PreToolUse", "PostToolUse", "PreCompact", "SessionStart"):
            entries = updated["hooks"][phase]
            assert len(entries) == 1, f"{phase} should have 1 entry, got {len(entries)}"
            assert "matcher" not in entries[0], f"{phase} should have no matcher"
            assert len(entries[0]["hooks"]) == 1, f"{phase} should have 1 hook"

    def test_upgrade_preserves_user_hooks(self, tmp_path):
        """User-defined hooks must survive the upgrade."""
        settings_path = tmp_path / "settings.json"
        old_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.sh"},
                            {"type": "command", "command": "/usr/local/bin/my-custom-bash-hook.sh"},
                        ],
                    },
                ],
                "PostToolUse": [
                    {
                        "matcher": "Bash|Read|WebFetch|Grep|mcp__.*",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/audit-log.sh", "async": True},
                            "/usr/local/bin/my-post-hook.sh",
                        ],
                    },
                ],
            }
        }
        settings_path.write_text(json.dumps(old_settings))

        result = install_hooks(settings_path)
        assert result.success is True

        updated = json.loads(settings_path.read_text())

        # PreToolUse: user's Bash hook preserved in its own entry, unified hook in catch-all
        pre_tool_use = updated["hooks"]["PreToolUse"]
        bash_entries = [e for e in pre_tool_use if e.get("matcher") == "Bash"]
        assert len(bash_entries) == 1
        assert bash_entries[0]["hooks"] == [
            {"type": "command", "command": "/usr/local/bin/my-custom-bash-hook.sh"},
        ]
        catchall = [e for e in pre_tool_use if "matcher" not in e]
        assert len(catchall) == 1
        assert _get_hook_path(catchall[0]["hooks"][0]).endswith(("spellbook_hook.py", "spellbook_hook.ps1"))

        # PostToolUse: user's hook preserved, unified hook in catch-all
        post_tool_use = updated["hooks"]["PostToolUse"]
        user_entries = [e for e in post_tool_use if e.get("matcher") == "Bash|Read|WebFetch|Grep|mcp__.*"]
        assert len(user_entries) == 1
        assert user_entries[0]["hooks"] == ["/usr/local/bin/my-post-hook.sh"]
        post_catchall = [e for e in post_tool_use if "matcher" not in e]
        assert len(post_catchall) == 1
        assert _get_hook_path(post_catchall[0]["hooks"][0]).endswith(("spellbook_hook.py", "spellbook_hook.ps1"))

    def test_idempotent_install(self, tmp_path):
        """Running install twice should not duplicate hooks."""
        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{}")

        install_hooks(settings_path)
        install_hooks(settings_path)

        updated = json.loads(settings_path.read_text())
        expected_cmd = _expected_unified_command()
        for phase in ("PreToolUse", "PostToolUse", "PreCompact", "SessionStart"):
            entries = updated["hooks"][phase]
            assert len(entries) == 1, (
                f"{phase} should have 1 entry after double install, got {len(entries)}"
            )
            assert len(entries[0]["hooks"]) == 1, (
                f"{phase} should have 1 hook after double install, got {len(entries[0]['hooks'])}"
            )
            assert entries[0]["hooks"][0]["command"] == expected_cmd

    def test_upgrade_with_expanded_paths(self, tmp_path, monkeypatch):
        """Upgrade with spellbook_dir should clean old hooks and use expanded paths."""
        settings_path = tmp_path / "settings.json"
        spellbook_dir = tmp_path / "spellbook"
        spellbook_dir.mkdir()
        (spellbook_dir / ".version").write_text("1.0.0")
        hooks_dir = spellbook_dir / "hooks"
        hooks_dir.mkdir()

        config_dir = tmp_path / ".local" / "spellbook"
        monkeypatch.setattr("installer.config.get_spellbook_config_dir", lambda: config_dir)
        monkeypatch.setattr(
            "installer.config.get_spellbook_config_dir",
            lambda: config_dir,
        )

        old_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": f"{spellbook_dir}/hooks/bash-gate.sh"},
                        ],
                    },
                ],
            }
        }
        settings_path.write_text(json.dumps(old_settings))

        result = install_hooks(settings_path, spellbook_dir=spellbook_dir)
        assert result.success is True

        updated = json.loads(settings_path.read_text())
        content = settings_path.read_text()

        # No $SPELLBOOK_DIR literal paths
        assert "$SPELLBOOK_DIR" not in content
        # No $SPELLBOOK_CONFIG_DIR literal paths
        assert "$SPELLBOOK_CONFIG_DIR" not in content
        # No old hook references
        assert "bash-gate" not in content

        # Unified hook with expanded path
        pre_tool_use = updated["hooks"]["PreToolUse"]
        assert len(pre_tool_use) == 1
        assert "matcher" not in pre_tool_use[0]
        expected_symlink = config_dir / "source"
        expected = _expected_unified_command(str(expected_symlink), str(config_dir))
        assert pre_tool_use[0]["hooks"][0]["command"] == expected
