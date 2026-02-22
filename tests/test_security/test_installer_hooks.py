"""Tests for Claude Code security hook registration in the installer.

The installer should register PreToolUse and PostToolUse hooks in
~/.claude/settings.local.json that point to spellbook security scripts.

Tier 1 (PreToolUse):
  - Bash -> bash-gate.sh
  - spawn_claude_session -> spawn-guard.sh

Tier 2 (PreToolUse + PostToolUse):
  - mcp__spellbook__workflow_state_save -> state-sanitize.sh (PreToolUse, timeout: 15)
  - Bash|Read|WebFetch|Grep|mcp__.* -> audit-log.sh (PostToolUse, async: true, timeout: 10)
  - Bash|Read|WebFetch|Grep|mcp__.* -> canary-check.sh (PostToolUse, timeout: 10)
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

from installer.components.hooks import (
    HOOK_DEFINITIONS,
    install_hooks,
    uninstall_hooks,
)


def _hook_ext():
    """Return the expected hook file extension for the current platform."""
    return ".py" if sys.platform == "win32" else ".sh"


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
    (hooks_dir / "state-sanitize.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (hooks_dir / "audit-log.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (hooks_dir / "canary-check.sh").write_text("#!/usr/bin/env bash\nexit 0\n")

    return spellbook


def _make_settings_file(path, content):
    """Create a settings.local.json file with given content dict."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")


def _read_settings(path):
    """Read and parse settings.local.json."""
    return json.loads(path.read_text(encoding="utf-8"))


def _get_hook_command(hook_entry):
    """Extract the command path from a hook, handling both string and object formats."""
    if isinstance(hook_entry, str):
        return hook_entry
    return hook_entry.get("command", "")


# --- HOOK_DEFINITIONS tests ---


class TestHookDefinitions:
    """HOOK_DEFINITIONS should declare hooks grouped by phase."""

    def test_has_pre_tool_use_phase(self):
        assert "PreToolUse" in HOOK_DEFINITIONS

    def test_has_post_tool_use_phase(self):
        assert "PostToolUse" in HOOK_DEFINITIONS

    def test_pre_tool_use_has_bash_hook(self):
        matchers = [h["matcher"] for h in HOOK_DEFINITIONS["PreToolUse"]]
        assert "Bash" in matchers

    def test_pre_tool_use_has_spawn_hook(self):
        matchers = [h["matcher"] for h in HOOK_DEFINITIONS["PreToolUse"]]
        assert "spawn_claude_session" in matchers

    def test_pre_tool_use_has_state_sanitize_hook(self):
        matchers = [h["matcher"] for h in HOOK_DEFINITIONS["PreToolUse"]]
        assert "mcp__spellbook__workflow_state_save" in matchers

    def test_bash_hook_references_correct_script(self):
        bash_hook = next(
            h for h in HOOK_DEFINITIONS["PreToolUse"] if h["matcher"] == "Bash"
        )
        assert bash_hook["hooks"] == ["$SPELLBOOK_DIR/hooks/bash-gate.sh"]

    def test_spawn_hook_references_correct_script(self):
        spawn_hook = next(
            h for h in HOOK_DEFINITIONS["PreToolUse"]
            if h["matcher"] == "spawn_claude_session"
        )
        assert spawn_hook["hooks"] == ["$SPELLBOOK_DIR/hooks/spawn-guard.sh"]

    def test_state_sanitize_hook_references_correct_script(self):
        hook = next(
            h for h in HOOK_DEFINITIONS["PreToolUse"]
            if h["matcher"] == "mcp__spellbook__workflow_state_save"
        )
        assert len(hook["hooks"]) == 1
        entry = hook["hooks"][0]
        assert entry["type"] == "command"
        assert entry["command"] == "$SPELLBOOK_DIR/hooks/state-sanitize.sh"
        assert entry["timeout"] == 15

    def test_post_tool_use_has_audit_and_canary_hooks(self):
        post_hooks = HOOK_DEFINITIONS["PostToolUse"]
        assert len(post_hooks) == 1  # single matcher entry
        entry = post_hooks[0]
        assert entry["matcher"] == "Bash|Read|WebFetch|Grep|mcp__.*"
        assert len(entry["hooks"]) == 2

    def test_audit_log_hook_properties(self):
        post_entry = HOOK_DEFINITIONS["PostToolUse"][0]
        audit_hook = next(
            h for h in post_entry["hooks"]
            if h["command"].endswith("audit-log.sh")
        )
        assert audit_hook["type"] == "command"
        assert audit_hook["command"] == "$SPELLBOOK_DIR/hooks/audit-log.sh"
        assert audit_hook["async"] is True
        assert audit_hook["timeout"] == 10

    def test_canary_check_hook_properties(self):
        post_entry = HOOK_DEFINITIONS["PostToolUse"][0]
        canary_hook = next(
            h for h in post_entry["hooks"]
            if h["command"].endswith("canary-check.sh")
        )
        assert canary_hook["type"] == "command"
        assert canary_hook["command"] == "$SPELLBOOK_DIR/hooks/canary-check.sh"
        assert canary_hook["timeout"] == 10
        # canary-check is NOT async (synchronous by default)
        assert "async" not in canary_hook or canary_hook.get("async") is not True


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

    def test_generates_both_hook_phases(self, tmp_path):
        """The generated JSON should have both PreToolUse and PostToolUse arrays."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        assert "hooks" in settings
        assert "PreToolUse" in settings["hooks"]
        assert "PostToolUse" in settings["hooks"]

    def test_pre_tool_use_has_three_entries(self, tmp_path):
        """PreToolUse should have 3 matcher entries (Bash, spawn, state-sanitize)."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        assert isinstance(pre_tool_use, list)
        assert len(pre_tool_use) == 3

    def test_post_tool_use_has_one_entry_with_two_hooks(self, tmp_path):
        """PostToolUse should have 1 matcher entry with 2 hooks (audit-log, canary-check)."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        assert isinstance(post_tool_use, list)
        assert len(post_tool_use) == 1
        assert post_tool_use[0]["matcher"] == "Bash|Read|WebFetch|Grep|mcp__.*"
        assert len(post_tool_use[0]["hooks"]) == 2

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
        assert bash_entry["hooks"] == [f"$SPELLBOOK_DIR/hooks/bash-gate{_hook_ext()}"]

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
        assert spawn_entry["hooks"] == [f"$SPELLBOOK_DIR/hooks/spawn-guard{_hook_ext()}"]

    def test_state_sanitize_hook_entry_correct(self, tmp_path):
        """The state-sanitize hook should be in PreToolUse with timeout."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        state_entry = next(
            (e for e in pre_tool_use
             if e["matcher"] == "mcp__spellbook__workflow_state_save"),
            None,
        )
        assert state_entry is not None
        assert len(state_entry["hooks"]) == 1
        hook = state_entry["hooks"][0]
        assert hook["type"] == "command"
        assert hook["command"] == f"$SPELLBOOK_DIR/hooks/state-sanitize{_hook_ext()}"
        assert hook["timeout"] == 15

    def test_audit_log_hook_entry_correct(self, tmp_path):
        """The audit-log PostToolUse hook should have async and timeout."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        post_entry = post_tool_use[0]
        ext = _hook_ext()
        audit_hook = next(
            (h for h in post_entry["hooks"]
             if isinstance(h, dict) and h.get("command", "").endswith(f"audit-log{ext}")),
            None,
        )
        assert audit_hook is not None
        assert audit_hook["type"] == "command"
        assert audit_hook["async"] is True
        assert audit_hook["timeout"] == 10

    def test_canary_check_hook_entry_correct(self, tmp_path):
        """The canary-check PostToolUse hook should have timeout but not async."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        post_entry = post_tool_use[0]
        ext = _hook_ext()
        canary_hook = next(
            (h for h in post_entry["hooks"]
             if isinstance(h, dict) and h.get("command", "").endswith(f"canary-check{ext}")),
            None,
        )
        assert canary_hook is not None
        assert canary_hook["type"] == "command"
        assert canary_hook["timeout"] == 10

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

    def test_preserves_user_post_tool_use_hooks(self, tmp_path):
        """Existing user PostToolUse hooks should be preserved alongside spellbook hooks."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        _make_settings_file(settings_path, {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Write", "hooks": ["/usr/local/bin/post-write.sh"]},
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        # User hook should still be present
        write_hooks = [e for e in post_tool_use if e["matcher"] == "Write"]
        assert len(write_hooks) == 1
        assert write_hooks[0]["hooks"] == ["/usr/local/bin/post-write.sh"]
        # Spellbook PostToolUse hooks should also be present
        spellbook_matchers = [
            e["matcher"] for e in post_tool_use
            if e["matcher"] == "Bash|Read|WebFetch|Grep|mcp__.*"
        ]
        assert len(spellbook_matchers) == 1

    def test_preserves_user_hooks_on_shared_post_matcher(self, tmp_path):
        """If user already has hooks on the same PostToolUse matcher, both coexist."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        _make_settings_file(settings_path, {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Bash|Read|WebFetch|Grep|mcp__.*",
                        "hooks": ["/usr/local/bin/my-post-hook.sh"],
                    },
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        matching = [
            e for e in post_tool_use
            if e["matcher"] == "Bash|Read|WebFetch|Grep|mcp__.*"
        ]
        assert len(matching) == 1
        hooks_list = matching[0]["hooks"]
        # User hook preserved
        assert "/usr/local/bin/my-post-hook.sh" in hooks_list
        # Spellbook hooks added
        commands = [
            h["command"] for h in hooks_list if isinstance(h, dict) and "command" in h
        ]
        ext = _hook_ext()
        assert f"$SPELLBOOK_DIR/hooks/audit-log{ext}" in commands
        assert f"$SPELLBOOK_DIR/hooks/canary-check{ext}" in commands

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
        state_entries = [
            e for e in pre_tool_use
            if e["matcher"] == "mcp__spellbook__workflow_state_save"
        ]
        assert len(bash_entries) == 1
        assert len(spawn_entries) == 1
        assert len(state_entries) == 1

        # PostToolUse idempotency
        post_tool_use = settings["hooks"]["PostToolUse"]
        post_entries = [
            e for e in post_tool_use
            if e["matcher"] == "Bash|Read|WebFetch|Grep|mcp__.*"
        ]
        assert len(post_entries) == 1
        # Should have exactly 2 hooks, not 4
        assert len(post_entries[0]["hooks"]) == 2

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
        # The hook list should contain the spellbook path (platform-appropriate extension)
        assert f"$SPELLBOOK_DIR/hooks/bash-gate{_hook_ext()}" in bash_entries[0]["hooks"]

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
        assert f"$SPELLBOOK_DIR/hooks/bash-gate{_hook_ext()}" in hooks_list

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

    def test_total_hook_count_is_five(self, tmp_path):
        """All 5 hooks should be installed: 3 PreToolUse + 2 PostToolUse."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        # Count individual hook scripts across all phases
        total_hooks = 0
        for phase in ["PreToolUse", "PostToolUse"]:
            for entry in settings["hooks"].get(phase, []):
                total_hooks += len(entry["hooks"])
        assert total_hooks == 5

    def test_upgrades_old_string_format_spellbook_hooks(self, tmp_path):
        """Old string-format spellbook hooks should be replaced cleanly on reinstall."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Simulate old Tier 1-only installation (string format, PreToolUse only)
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": ["$SPELLBOOK_DIR/hooks/bash-gate.sh"]},
                    {"matcher": "spawn_claude_session", "hooks": ["$SPELLBOOK_DIR/hooks/spawn-guard.sh"]},
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        # Should now have all 5 hooks across both phases
        pre = settings["hooks"]["PreToolUse"]
        post = settings["hooks"]["PostToolUse"]
        assert len(pre) == 3  # Bash, spawn, state-sanitize
        assert len(post) == 1  # single matcher with 2 hooks
        assert len(post[0]["hooks"]) == 2


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
        assert "mcp__spellbook__workflow_state_save" not in matchers

    def test_removes_post_tool_use_hooks(self, tmp_path):
        """Spellbook PostToolUse hooks should be removed on uninstall."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)
        uninstall_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings.get("hooks", {}).get("PostToolUse", [])
        # PostToolUse matcher entry should be gone (no user hooks to preserve)
        assert len(post_tool_use) == 0

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

    def test_preserves_user_post_tool_use_hooks_on_uninstall(self, tmp_path):
        """User PostToolUse hooks should be preserved when spellbook hooks are removed."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # User has their own PostToolUse hook on the same matcher
        _make_settings_file(settings_path, {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Bash|Read|WebFetch|Grep|mcp__.*",
                        "hooks": ["/usr/local/bin/my-post-hook.sh"],
                    },
                ],
            },
        })
        install_hooks(settings_path, dry_run=False)
        uninstall_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        matching = [
            e for e in post_tool_use
            if e["matcher"] == "Bash|Read|WebFetch|Grep|mcp__.*"
        ]
        assert len(matching) == 1
        assert matching[0]["hooks"] == ["/usr/local/bin/my-post-hook.sh"]

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

    def test_uninstall_leaves_no_spellbook_traces(self, tmp_path):
        """After uninstall, no $SPELLBOOK_DIR paths should remain in any phase."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)
        uninstall_hooks(settings_path, dry_run=False)

        content = settings_path.read_text(encoding="utf-8")
        assert "$SPELLBOOK_DIR" not in content


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
        (hooks_dir / "state-sanitize.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        (hooks_dir / "audit-log.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        (hooks_dir / "canary-check.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
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
        assert "PostToolUse" in settings["hooks"]

        # Verify hook results
        hook_results = [r for r in results if r.component == "hooks"]
        assert len(hook_results) == 1
        assert hook_results[0].success

    def test_install_registers_all_five_hooks(self, tmp_path):
        """Full installer should register all 5 hooks (3 PreToolUse + 2 PostToolUse)."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = self._make_installer_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)

        with patch.object(Path, "home", return_value=tmp_path), \
             patch("installer.platforms.claude_code.install_daemon", return_value=(True, "ok")), \
             patch("installer.platforms.claude_code.check_claude_cli_available", return_value=False):
            installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
            results = installer.install()

        settings_path = config_dir / "settings.local.json"
        settings = _read_settings(settings_path)

        # Count all individual hook scripts
        total_hooks = 0
        for phase in ["PreToolUse", "PostToolUse"]:
            for entry in settings["hooks"].get(phase, []):
                total_hooks += len(entry["hooks"])
        assert total_hooks == 5

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

        # Hooks should be removed from both phases
        settings_path = config_dir / "settings.local.json"
        if settings_path.exists():
            content = settings_path.read_text(encoding="utf-8")
            assert "$SPELLBOOK_DIR" not in content
