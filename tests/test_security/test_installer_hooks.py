"""Tests for Claude Code security hook registration in the installer.

The installer should register PreToolUse hooks in ~/.claude/settings.local.json
that point to the security hook scripts (bash-gate.sh and spawn-guard.sh).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from installer.components.hooks import (
    HOOK_DEFINITIONS,
    install_hooks,
    uninstall_hooks,
)


# --- Helpers ---


def _make_spellbook_dir(tmp_path):
    """Create a minimal mock spellbook directory for hook tests."""
    spellbook = tmp_path / "spellbook"
    spellbook.mkdir()

    # Version file
    (spellbook / ".version").write_text("1.0.0")

    # Hooks directory with scripts
    hooks_dir = spellbook / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "bash-gate.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (hooks_dir / "spawn-guard.sh").write_text("#!/usr/bin/env bash\nexit 0\n")

    return spellbook


def _make_settings_file(path, content):
    """Create a settings.local.json file with given content dict."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")


def _read_settings(path):
    """Read and parse settings.local.json."""
    return json.loads(path.read_text(encoding="utf-8"))


# --- HOOK_DEFINITIONS tests ---


class TestHookDefinitions:
    """HOOK_DEFINITIONS should declare the expected hooks."""

    def test_has_bash_hook(self):
        matchers = [h["matcher"] for h in HOOK_DEFINITIONS]
        assert "Bash" in matchers

    def test_has_spawn_hook(self):
        matchers = [h["matcher"] for h in HOOK_DEFINITIONS]
        assert "spawn_claude_session" in matchers

    def test_bash_hook_references_correct_script(self):
        bash_hook = next(h for h in HOOK_DEFINITIONS if h["matcher"] == "Bash")
        assert bash_hook["hooks"] == ["$SPELLBOOK_DIR/hooks/bash-gate.sh"]

    def test_spawn_hook_references_correct_script(self):
        spawn_hook = next(
            h for h in HOOK_DEFINITIONS if h["matcher"] == "spawn_claude_session"
        )
        assert spawn_hook["hooks"] == ["$SPELLBOOK_DIR/hooks/spawn-guard.sh"]


# --- install_hooks() tests ---


class TestInstallHooks:
    """install_hooks() should write correct hook entries to settings.local.json."""

    def test_creates_settings_file_if_missing(self, tmp_path):
        """When settings.local.json does not exist, it should be created."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        result = install_hooks(settings_path, dry_run=False)

        assert result.success
        assert settings_path.exists()

    def test_generates_correct_json_structure(self, tmp_path):
        """The generated JSON should have hooks.PreToolUse array with correct entries."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        assert "hooks" in settings
        assert "PreToolUse" in settings["hooks"]

        pre_tool_use = settings["hooks"]["PreToolUse"]
        assert isinstance(pre_tool_use, list)
        assert len(pre_tool_use) == 2

    def test_bash_hook_entry_correct(self, tmp_path):
        """The Bash hook entry should have correct matcher and hook path."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        bash_entry = next(
            (e for e in pre_tool_use if e["matcher"] == "Bash"), None
        )
        assert bash_entry is not None
        assert bash_entry["hooks"] == ["$SPELLBOOK_DIR/hooks/bash-gate.sh"]

    def test_spawn_hook_entry_correct(self, tmp_path):
        """The spawn_claude_session hook entry should have correct matcher and hook path."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        spawn_entry = next(
            (e for e in pre_tool_use if e["matcher"] == "spawn_claude_session"),
            None,
        )
        assert spawn_entry is not None
        assert spawn_entry["hooks"] == ["$SPELLBOOK_DIR/hooks/spawn-guard.sh"]

    def test_preserves_existing_settings(self, tmp_path):
        """Existing non-hook settings should be preserved."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Pre-existing settings
        _make_settings_file(settings_path, {
            "permissions": {"allow": ["Read", "Write"]},
            "model": "claude-opus-4-6",
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        assert settings["permissions"] == {"allow": ["Read", "Write"]}
        assert settings["model"] == "claude-opus-4-6"
        assert "hooks" in settings

    def test_preserves_existing_non_spellbook_hooks(self, tmp_path):
        """Existing user-defined hooks that are not spellbook hooks should be preserved."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        user_hook = {
            "matcher": "Write",
            "hooks": ["/usr/local/bin/my-custom-hook.sh"],
        }
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [user_hook],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        # User hook should still be present
        write_hooks = [e for e in pre_tool_use if e["matcher"] == "Write"]
        assert len(write_hooks) == 1
        assert write_hooks[0]["hooks"] == ["/usr/local/bin/my-custom-hook.sh"]
        # Spellbook hooks should also be present
        matchers = [e["matcher"] for e in pre_tool_use]
        assert "Bash" in matchers
        assert "spawn_claude_session" in matchers

    def test_preserves_other_hook_types(self, tmp_path):
        """Existing hooks in other phases (e.g., PostToolUse) should be preserved."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        _make_settings_file(settings_path, {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Bash", "hooks": ["/usr/local/bin/post-hook.sh"]},
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        # PostToolUse should be untouched
        assert "PostToolUse" in settings["hooks"]
        assert len(settings["hooks"]["PostToolUse"]) == 1
        # PreToolUse should be added
        assert "PreToolUse" in settings["hooks"]

    def test_idempotent_no_duplicates(self, tmp_path):
        """Running install_hooks twice should not create duplicate entries."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)
        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        bash_entries = [e for e in pre_tool_use if e["matcher"] == "Bash"]
        spawn_entries = [
            e for e in pre_tool_use if e["matcher"] == "spawn_claude_session"
        ]
        assert len(bash_entries) == 1
        assert len(spawn_entries) == 1

    def test_updates_existing_spellbook_hook_path(self, tmp_path):
        """If a spellbook hook entry exists with an old path, it should be updated."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Old spellbook hook with different path
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": ["/old/path/hooks/bash-gate.sh"],
                    },
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        bash_entries = [e for e in pre_tool_use if e["matcher"] == "Bash"]
        assert len(bash_entries) == 1
        # The hook list should contain the spellbook path
        assert "$SPELLBOOK_DIR/hooks/bash-gate.sh" in bash_entries[0]["hooks"]

    def test_merges_hooks_into_existing_matcher(self, tmp_path):
        """If a user has their own Bash hook, spellbook adds its hook to the same entry's hooks list."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # User already has a Bash matcher with their own hook
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": ["/usr/local/bin/my-bash-hook.sh"],
                    },
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        bash_entries = [e for e in pre_tool_use if e["matcher"] == "Bash"]
        assert len(bash_entries) == 1
        # Both hooks should be in the list
        hooks_list = bash_entries[0]["hooks"]
        assert "/usr/local/bin/my-bash-hook.sh" in hooks_list
        assert "$SPELLBOOK_DIR/hooks/bash-gate.sh" in hooks_list

    def test_dry_run_does_not_write(self, tmp_path):
        """In dry_run mode, no file should be created or modified."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        result = install_hooks(settings_path, dry_run=True)

        assert result.success
        assert not settings_path.exists()

    def test_dry_run_existing_file_unchanged(self, tmp_path):
        """In dry_run mode, existing file should not be modified."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        original_content = {"model": "claude-opus-4-6"}
        _make_settings_file(settings_path, original_content)
        original_text = settings_path.read_text(encoding="utf-8")

        install_hooks(settings_path, dry_run=True)

        assert settings_path.read_text(encoding="utf-8") == original_text

    def test_creates_parent_directory(self, tmp_path):
        """If the parent directory (.claude) does not exist, it should be created."""
        config_dir = tmp_path / ".claude"
        settings_path = config_dir / "settings.local.json"
        # Do NOT create config_dir

        result = install_hooks(settings_path, dry_run=False)

        assert result.success
        assert settings_path.exists()

    def test_handles_empty_settings_file(self, tmp_path):
        """If settings.local.json exists but is empty, handle gracefully."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"
        settings_path.write_text("", encoding="utf-8")

        result = install_hooks(settings_path, dry_run=False)

        assert result.success
        settings = _read_settings(settings_path)
        assert "hooks" in settings

    def test_handles_malformed_json(self, tmp_path):
        """If settings.local.json contains invalid JSON, return failure."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"
        settings_path.write_text("{invalid json", encoding="utf-8")

        result = install_hooks(settings_path, dry_run=False)

        assert not result.success
        assert "json" in result.message.lower() or "parse" in result.message.lower()

    def test_result_reports_installed_action(self, tmp_path):
        """The result should report 'installed' action on success."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        result = install_hooks(settings_path, dry_run=False)

        assert result.success
        assert result.action == "installed"
        assert result.component == "hooks"


# --- uninstall_hooks() tests ---


class TestUninstallHooks:
    """uninstall_hooks() should remove spellbook hook entries from settings."""

    def test_removes_spellbook_hooks(self, tmp_path):
        """Spellbook hook entries should be removed on uninstall."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Install first
        install_hooks(settings_path, dry_run=False)
        # Then uninstall
        result = uninstall_hooks(settings_path, dry_run=False)

        assert result.success
        settings = _read_settings(settings_path)
        pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
        matchers = [e["matcher"] for e in pre_tool_use]
        # Spellbook-only matchers should be gone
        assert "spawn_claude_session" not in matchers

    def test_preserves_user_hooks_on_uninstall(self, tmp_path):
        """User-defined hooks should be preserved on uninstall."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Set up user hook + spellbook hooks
        user_hook = {
            "matcher": "Write",
            "hooks": ["/usr/local/bin/my-custom-hook.sh"],
        }
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [user_hook],
            },
        })
        install_hooks(settings_path, dry_run=False)
        # Uninstall
        uninstall_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        assert len(pre_tool_use) == 1
        assert pre_tool_use[0]["matcher"] == "Write"

    def test_removes_spellbook_hook_from_shared_matcher(self, tmp_path):
        """If a matcher has both user and spellbook hooks, only remove the spellbook one."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # User has their own Bash hook
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": ["/usr/local/bin/my-bash-hook.sh"],
                    },
                ],
            },
        })
        install_hooks(settings_path, dry_run=False)
        # Now uninstall
        uninstall_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        bash_entries = [e for e in pre_tool_use if e["matcher"] == "Bash"]
        assert len(bash_entries) == 1
        assert bash_entries[0]["hooks"] == ["/usr/local/bin/my-bash-hook.sh"]

    def test_no_settings_file_is_noop(self, tmp_path):
        """If settings.local.json does not exist, uninstall should be a no-op."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        result = uninstall_hooks(settings_path, dry_run=False)

        assert result.success
        assert result.action in ("unchanged", "skipped")

    def test_dry_run_does_not_modify(self, tmp_path):
        """In dry_run mode, file should not be modified."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)
        original_text = settings_path.read_text(encoding="utf-8")

        uninstall_hooks(settings_path, dry_run=True)

        assert settings_path.read_text(encoding="utf-8") == original_text


# --- Integration with ClaudeCodeInstaller ---


class TestClaudeCodeInstallerHookIntegration:
    """ClaudeCodeInstaller.install() should register security hooks."""

    def _make_installer_spellbook_dir(self, tmp_path):
        """Create a mock spellbook dir suitable for the full installer."""
        spellbook = tmp_path / "spellbook"
        spellbook.mkdir()
        (spellbook / ".version").write_text("1.0.0")
        mcp_dir = spellbook / "spellbook_mcp"
        mcp_dir.mkdir()
        (mcp_dir / "server.py").write_text("# stub")
        (spellbook / "CLAUDE.spellbook.md").write_text("# Spellbook Context\n\nTest content.")
        (spellbook / "skills").mkdir()
        (spellbook / "commands").mkdir()
        hooks_dir = spellbook / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "bash-gate.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        (hooks_dir / "spawn-guard.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        return spellbook

    def test_install_registers_hooks(self, tmp_path):
        """Full installer should register security hooks in settings.local.json."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = self._make_installer_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)

        with patch.object(Path, "home", return_value=tmp_path), \
             patch("installer.platforms.claude_code.install_daemon", return_value=(True, "ok")), \
             patch("installer.platforms.claude_code.check_claude_cli_available", return_value=False):
            installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
            results = installer.install()

        # Check that hooks were registered
        settings_path = config_dir / "settings.local.json"
        assert settings_path.exists(), "settings.local.json should be created"
        settings = _read_settings(settings_path)
        assert "hooks" in settings
        assert "PreToolUse" in settings["hooks"]

        # Verify hook results
        hook_results = [r for r in results if r.component == "hooks"]
        assert len(hook_results) == 1
        assert hook_results[0].success

    def test_uninstall_removes_hooks(self, tmp_path):
        """Full uninstaller should remove security hooks from settings.local.json."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = self._make_installer_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)

        with patch.object(Path, "home", return_value=tmp_path), \
             patch("installer.platforms.claude_code.install_daemon", return_value=(True, "ok")), \
             patch("installer.platforms.claude_code.uninstall_daemon", return_value=(True, "ok")), \
             patch("installer.platforms.claude_code.check_claude_cli_available", return_value=False):
            installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
            installer.install()
            results = installer.uninstall()

        # Hooks should be removed
        settings_path = config_dir / "settings.local.json"
        if settings_path.exists():
            settings = _read_settings(settings_path)
            pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
            spellbook_hooks = [
                e for e in pre_tool_use
                if any("$SPELLBOOK_DIR" in h for h in e.get("hooks", []))
            ]
            assert len(spellbook_hooks) == 0
