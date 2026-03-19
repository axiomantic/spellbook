"""Tests for Claude Code hook registration in the installer.

The installer registers a unified hook (spellbook_hook.py) across all four
phases in ~/.claude/settings.json. Each phase has a single catch-all entry
(no matcher) pointing to the same script:

  PreToolUse:  spellbook_hook.py (timeout: 15)
  PostToolUse: spellbook_hook.py (timeout: 15)
  PreCompact:  spellbook_hook.py (timeout: 5)
  SessionStart: spellbook_hook.py (timeout: 10)

The unified hook dispatches internally based on event type and tool name.
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

from installer.components.hooks import (
    HOOK_DEFINITIONS,
    _cleanup_legacy_hooks,
    _expand_spellbook_dir,
    _get_hook_path,
    _get_hook_path_for_platform,
    _is_legacy_hook,
    _is_spellbook_hook,
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


def _expected_command(prefix, script_name):
    """Return the expected hook command string for the current platform.

    On Windows, hooks use PowerShell dispatch with .ps1 extension.
    On Unix, hooks use the .sh path directly.

    Args:
        prefix: The path prefix (e.g. "$SPELLBOOK_DIR" or an expanded path).
        script_name: The script basename without extension (e.g. "bash-gate").
    """
    if sys.platform == "win32":
        return f"powershell -ExecutionPolicy Bypass -File {prefix}/hooks/{script_name}.ps1"
    return f"{prefix}/hooks/{script_name}.sh"


def _expected_ext():
    """Return the expected hook script extension for the current platform."""
    return ".ps1" if sys.platform == "win32" else ".sh"


def _expected_unified_command(prefix):
    """Return the expected unified hook command string for the current platform.

    On Windows, the .py hook uses the .ps1 wrapper.
    On Unix, the .py hook is invoked directly.
    """
    if sys.platform == "win32":
        return f"powershell -ExecutionPolicy Bypass -File {prefix}/hooks/spellbook_hook.ps1"
    return f"{prefix}/hooks/spellbook_hook.py"


# --- HOOK_DEFINITIONS tests ---


class TestHookDefinitions:
    """HOOK_DEFINITIONS should declare unified hook for all phases."""

    def test_has_all_four_phases(self):
        assert set(HOOK_DEFINITIONS.keys()) == {
            "PreToolUse", "PostToolUse", "PreCompact", "SessionStart",
        }

    def test_pre_tool_use_has_unified_hook(self):
        entries = HOOK_DEFINITIONS["PreToolUse"]
        assert len(entries) == 1
        hooks = entries[0]["hooks"]
        assert len(hooks) == 1
        assert hooks[0] == {
            "type": "command",
            "command": "$SPELLBOOK_DIR/hooks/spellbook_hook.py",
            "timeout": 15,
        }

    def test_post_tool_use_has_unified_hook(self):
        entries = HOOK_DEFINITIONS["PostToolUse"]
        assert len(entries) == 1
        hooks = entries[0]["hooks"]
        assert len(hooks) == 1
        assert hooks[0] == {
            "type": "command",
            "command": "$SPELLBOOK_DIR/hooks/spellbook_hook.py",
            "timeout": 15,
        }

    def test_pre_compact_has_unified_hook(self):
        entries = HOOK_DEFINITIONS["PreCompact"]
        assert len(entries) == 1
        hooks = entries[0]["hooks"]
        assert len(hooks) == 1
        assert hooks[0] == {
            "type": "command",
            "command": "$SPELLBOOK_DIR/hooks/spellbook_hook.py",
            "timeout": 5,
        }

    def test_session_start_has_unified_hook(self):
        entries = HOOK_DEFINITIONS["SessionStart"]
        assert len(entries) == 1
        hooks = entries[0]["hooks"]
        assert len(hooks) == 1
        assert hooks[0] == {
            "type": "command",
            "command": "$SPELLBOOK_DIR/hooks/spellbook_hook.py",
            "timeout": 10,
        }

    def test_no_async_on_any_unified_hook(self):
        """The unified hook handles async internally via daemon threads."""
        for phase, entries in HOOK_DEFINITIONS.items():
            for entry in entries:
                for hook in entry["hooks"]:
                    assert hook.get("async") is not True, (
                        f"Unified hook in {phase} must not have async=True"
                    )

    def test_no_matchers_on_unified_hooks(self):
        """Unified hook is catch-all (no matcher), dispatches internally."""
        for phase, entries in HOOK_DEFINITIONS.items():
            for entry in entries:
                assert "matcher" not in entry, (
                    f"Unified hook in {phase} should not have a matcher"
                )


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

    def test_pre_tool_use_has_one_unified_entry(self, tmp_path):
        """PreToolUse should have 1 entry (unified hook, catch-all)."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        assert isinstance(pre_tool_use, list)
        assert len(pre_tool_use) == 1
        assert len(pre_tool_use[0]["hooks"]) == 1
        assert "spellbook_hook" in pre_tool_use[0]["hooks"][0]["command"]

    def test_post_tool_use_has_one_unified_entry(self, tmp_path):
        """PostToolUse should have 1 entry (unified hook, catch-all)."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        assert isinstance(post_tool_use, list)
        assert len(post_tool_use) == 1
        assert len(post_tool_use[0]["hooks"]) == 1
        assert "spellbook_hook" in post_tool_use[0]["hooks"][0]["command"]

    def test_unified_hook_entry_correct_in_pre_tool_use(self, tmp_path):
        """The unified hook entry in PreToolUse should have correct properties."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        assert len(pre_tool_use) == 1
        entry = pre_tool_use[0]
        assert "matcher" not in entry  # catch-all
        assert len(entry["hooks"]) == 1
        hook = entry["hooks"][0]
        assert hook == {
            "type": "command",
            "command": _expected_unified_command("$SPELLBOOK_DIR"),
            "timeout": 15,
        }

    def test_unified_hook_entry_correct_in_post_tool_use(self, tmp_path):
        """The unified hook entry in PostToolUse should have correct properties."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        assert len(post_tool_use) == 1
        entry = post_tool_use[0]
        assert "matcher" not in entry  # catch-all
        assert len(entry["hooks"]) == 1
        hook = entry["hooks"][0]
        assert hook == {
            "type": "command",
            "command": _expected_unified_command("$SPELLBOOK_DIR"),
            "timeout": 15,
        }

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
        write_hooks = [e for e in pre_tool_use if e.get("matcher") == "Write"]
        assert len(write_hooks) == 1
        assert write_hooks[0]["hooks"] == ["/usr/local/bin/my-custom-hook.sh"]
        # Unified spellbook hook should also be present (catch-all, no matcher)
        unified = [
            e for e in pre_tool_use
            if any(
                isinstance(h, dict) and "spellbook_hook" in h.get("command", "")
                for h in e.get("hooks", [])
            )
        ]
        assert len(unified) == 1

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
        write_hooks = [e for e in post_tool_use if e.get("matcher") == "Write"]
        assert len(write_hooks) == 1
        assert write_hooks[0]["hooks"] == ["/usr/local/bin/post-write.sh"]
        # Unified spellbook hook should also be present (catch-all, no matcher)
        unified = [
            e for e in post_tool_use
            if any(
                isinstance(h, dict) and "spellbook_hook" in h.get("command", "")
                for h in e.get("hooks", [])
            )
        ]
        assert len(unified) == 1

    def test_preserves_user_hooks_on_shared_post_matcher(self, tmp_path):
        """If user already has hooks on a PostToolUse matcher, user hooks coexist with unified hook."""
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
        # User's matcher entry should be preserved
        matching = [
            e for e in post_tool_use
            if e.get("matcher") == "Bash|Read|WebFetch|Grep|mcp__.*"
        ]
        assert len(matching) == 1
        assert matching[0]["hooks"] == ["/usr/local/bin/my-post-hook.sh"]
        # Unified hook added as a separate catch-all entry (no matcher)
        catchall = [e for e in post_tool_use if "matcher" not in e]
        assert len(catchall) == 1
        unified_cmds = [
            _get_hook_path(h) for h in catchall[0]["hooks"]
            if isinstance(h, dict) and "command" in h
        ]
        assert len(unified_cmds) == 1
        assert unified_cmds[0].endswith(("spellbook_hook.py", "spellbook_hook.ps1"))

    def test_idempotent_no_duplicates(self, tmp_path):
        """Running install_hooks twice should not create duplicate entries."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)
        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        # Each phase should have exactly 1 entry with 1 hook (unified hook)
        for phase in ("PreToolUse", "PostToolUse", "PreCompact", "SessionStart"):
            entries = settings["hooks"][phase]
            assert len(entries) == 1, f"{phase} should have 1 entry, got {len(entries)}"
            assert len(entries[0]["hooks"]) == 1, (
                f"{phase} should have 1 hook, got {len(entries[0]['hooks'])}"
            )

    def test_updates_existing_spellbook_hook_path(self, tmp_path):
        """Old individual spellbook hooks are replaced by the unified hook on reinstall."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Old spellbook hook with per-tool matcher
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.sh"},
                        ],
                    },
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        # Old "Bash" matcher entry should be cleaned (spellbook hook removed, entry dropped)
        bash_entries = [e for e in pre_tool_use if e.get("matcher") == "Bash"]
        assert len(bash_entries) == 0
        # Unified catch-all entry should exist
        catchall = [e for e in pre_tool_use if "matcher" not in e]
        assert len(catchall) == 1
        assert len(catchall[0]["hooks"]) == 1
        assert _get_hook_path(catchall[0]["hooks"][0]).endswith(("spellbook_hook.py", "spellbook_hook.ps1"))

    def test_merges_hooks_into_existing_matcher(self, tmp_path):
        """If a user has their own Bash hook, the unified hook is added as a separate catch-all entry."""
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
        # User's Bash matcher entry should be preserved
        bash_entries = [e for e in pre_tool_use if e.get("matcher") == "Bash"]
        assert len(bash_entries) == 1
        assert bash_entries[0]["hooks"] == ["/usr/local/bin/my-bash-hook.sh"]
        # Unified hook should be a separate catch-all entry
        catchall = [e for e in pre_tool_use if "matcher" not in e]
        assert len(catchall) == 1
        assert _get_hook_path(catchall[0]["hooks"][0]).endswith(("spellbook_hook.py", "spellbook_hook.ps1"))

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

    def test_total_hook_count_is_four(self, tmp_path):
        """4 hooks total: 1 unified hook per phase (PreToolUse, PostToolUse, PreCompact, SessionStart)."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        # Count individual hook scripts across all phases
        total_hooks = 0
        for phase in ("PreToolUse", "PostToolUse", "PreCompact", "SessionStart"):
            for entry in settings["hooks"].get(phase, []):
                total_hooks += len(entry["hooks"])
        assert total_hooks == 4

    def test_upgrades_old_string_format_spellbook_hooks(self, tmp_path):
        """Old string-format spellbook hooks should be replaced cleanly by unified hook on reinstall."""
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
        # Old per-tool entries should be removed; unified hook replaces them
        pre = settings["hooks"]["PreToolUse"]
        post = settings["hooks"]["PostToolUse"]
        # PreToolUse: old Bash + spawn entries cleaned, 1 catch-all unified entry
        assert len(pre) == 1
        assert "matcher" not in pre[0]
        assert _get_hook_path(pre[0]["hooks"][0]).endswith(("spellbook_hook.py", "spellbook_hook.ps1"))
        # PostToolUse: 1 catch-all unified entry
        assert len(post) == 1
        assert "matcher" not in post[0]
        assert _get_hook_path(post[0]["hooks"][0]).endswith(("spellbook_hook.py", "spellbook_hook.ps1"))


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
        matchers = [e.get("matcher") for e in pre_tool_use]
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
            if e.get("matcher") == "Bash|Read|WebFetch|Grep|mcp__.*"
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
        bash_entries = [e for e in pre_tool_use if e.get("matcher") == "Bash"]
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


@pytest.mark.timeout(120)
@pytest.mark.integration
class TestClaudeCodeInstallerHookIntegration:
    """ClaudeCodeInstaller.install() should register security hooks."""

    def _make_installer_spellbook_dir(self, tmp_path):
        """Create a mock spellbook dir suitable for the full installer."""
        spellbook = tmp_path / "spellbook"
        spellbook.mkdir()
        (spellbook / ".version").write_text("1.0.0")
        mcp_dir = spellbook / "spellbook"
        mcp_dir.mkdir()
        (mcp_dir / "server.py").write_text("# stub")
        (spellbook / "AGENTS.spellbook.md").write_text("# Spellbook Context\n\nTest content.")
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
        """Full installer should register security hooks in settings.json."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = self._make_installer_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)

        with patch.object(Path, "home", return_value=tmp_path), \
             patch("installer.platforms.claude_code.check_claude_cli_available", return_value=False):
            installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
            results = installer.install()

        # Check that hooks were registered
        settings_path = config_dir / "settings.json"
        assert settings_path.exists(), "settings.json should be created"
        settings = _read_settings(settings_path)
        assert "hooks" in settings
        assert "PreToolUse" in settings["hooks"]
        assert "PostToolUse" in settings["hooks"]

        # Verify hook results
        hook_results = [r for r in results if r.component == "hooks"]
        assert len(hook_results) == 1
        assert hook_results[0].success

    def test_install_registers_unified_hooks(self, tmp_path):
        """Full installer should register unified hooks (1 per phase, 4 total)."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = self._make_installer_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)

        with patch.object(Path, "home", return_value=tmp_path), \
             patch("installer.platforms.claude_code.check_claude_cli_available", return_value=False):
            installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
            results = installer.install()

        settings_path = config_dir / "settings.json"
        settings = _read_settings(settings_path)

        # Count all individual hook scripts across all 4 phases
        total_hooks = 0
        for phase in ("PreToolUse", "PostToolUse", "PreCompact", "SessionStart"):
            for entry in settings["hooks"].get(phase, []):
                total_hooks += len(entry["hooks"])
        assert total_hooks == 4

    def test_uninstall_removes_hooks(self, tmp_path):
        """Full uninstaller should remove security hooks from settings.json."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = self._make_installer_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)

        with patch.object(Path, "home", return_value=tmp_path), \
             patch("installer.platforms.claude_code.uninstall_daemon", return_value=(True, "ok")), \
             patch("installer.platforms.claude_code.check_claude_cli_available", return_value=False):
            installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
            installer.install()
            results = installer.uninstall()

        # Hooks should be removed from both phases
        settings_path = config_dir / "settings.json"
        if settings_path.exists():
            content = settings_path.read_text(encoding="utf-8")
            assert "$SPELLBOOK_DIR" not in content
            # Also verify no expanded spellbook paths remain
            assert str(spellbook_dir) + "/hooks/" not in content

    def test_install_writes_expanded_paths(self, tmp_path):
        """Full installer should write expanded absolute paths, not literal $SPELLBOOK_DIR."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        spellbook_dir = self._make_installer_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)

        with patch.object(Path, "home", return_value=tmp_path), \
             patch("installer.platforms.claude_code.check_claude_cli_available", return_value=False):
            installer = ClaudeCodeInstaller(spellbook_dir, config_dir, "1.0.0", dry_run=False)
            installer.install()

        settings_path = config_dir / "settings.json"
        content = settings_path.read_text(encoding="utf-8")
        # Literal $SPELLBOOK_DIR should NOT appear in the written file
        assert "$SPELLBOOK_DIR" not in content
        # The expanded spellbook_dir path should appear instead
        # Use json.dumps to get the JSON-escaped version (handles Windows backslashes)
        assert json.dumps(str(spellbook_dir))[1:-1] in content

        settings = _read_settings(settings_path)
        # Verify the unified hook path is expanded
        pre_tool_use = settings["hooks"]["PreToolUse"]
        assert len(pre_tool_use) == 1
        catchall_entry = pre_tool_use[0]
        assert "matcher" not in catchall_entry
        assert len(catchall_entry["hooks"]) == 1
        hook = catchall_entry["hooks"][0]
        assert hook["type"] == "command"
        expected_path = _expected_unified_command(str(spellbook_dir))
        assert hook["command"] == expected_path


# --- _expand_spellbook_dir() tests ---


class TestExpandSpellbookDir:
    """_expand_spellbook_dir() should replace $SPELLBOOK_DIR with actual path."""

    def test_expands_string_hook(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        result = _expand_spellbook_dir("$SPELLBOOK_DIR/hooks/bash-gate.sh", spellbook_dir)
        assert result == f"{spellbook_dir}/hooks/bash-gate.sh"

    def test_expands_dict_hook_command(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        hook = {
            "type": "command",
            "command": "$SPELLBOOK_DIR/hooks/audit-log.sh",
            "async": True,
            "timeout": 10,
        }
        result = _expand_spellbook_dir(hook, spellbook_dir)
        assert result["command"] == f"{spellbook_dir}/hooks/audit-log.sh"
        assert result["async"] is True
        assert result["timeout"] == 10

    def test_preserves_dict_without_command(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        hook = {"type": "custom", "timeout": 5}
        result = _expand_spellbook_dir(hook, spellbook_dir)
        assert result == hook

    def test_does_not_mutate_original_dict(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/foo.sh"}
        result = _expand_spellbook_dir(hook, spellbook_dir)
        assert result is not hook
        assert hook["command"] == "$SPELLBOOK_DIR/hooks/foo.sh"

    def test_no_expansion_without_variable(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        result = _expand_spellbook_dir("/usr/local/bin/my-hook.sh", spellbook_dir)
        assert result == "/usr/local/bin/my-hook.sh"


# --- _is_spellbook_hook() with spellbook_dir tests ---


class TestIsSpellbookHookWithSpellbookDir:
    """_is_spellbook_hook() should recognize both literal and expanded paths."""

    def test_recognizes_literal_prefix(self):
        assert _is_spellbook_hook("$SPELLBOOK_DIR/hooks/bash-gate.sh") is True

    def test_recognizes_literal_dict_hook(self):
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/audit-log.sh"}
        assert _is_spellbook_hook(hook) is True

    def test_rejects_non_spellbook_path(self):
        assert _is_spellbook_hook("/usr/local/bin/my-hook.sh") is False

    def test_recognizes_expanded_path_with_spellbook_dir(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        path = f"{spellbook_dir}/hooks/bash-gate.sh"
        assert _is_spellbook_hook(path, spellbook_dir) is True

    def test_recognizes_expanded_dict_hook_with_spellbook_dir(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        hook = {"type": "command", "command": f"{spellbook_dir}/hooks/audit-log.sh"}
        assert _is_spellbook_hook(hook, spellbook_dir) is True

    def test_rejects_non_spellbook_path_with_spellbook_dir(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        assert _is_spellbook_hook("/usr/local/bin/my-hook.sh", spellbook_dir) is False

    def test_expanded_path_not_recognized_without_spellbook_dir(self, tmp_path):
        """Without spellbook_dir, expanded absolute paths are NOT recognized."""
        spellbook_dir = tmp_path / "spellbook"
        path = f"{spellbook_dir}/hooks/bash-gate.sh"
        assert _is_spellbook_hook(path) is False


# --- install_hooks() with spellbook_dir tests ---


class TestInstallHooksWithSpellbookDir:
    """install_hooks() with spellbook_dir should write expanded paths."""

    def test_writes_expanded_paths(self, tmp_path):
        """Hook paths should use absolute paths, not $SPELLBOOK_DIR."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        content = settings_path.read_text(encoding="utf-8")
        assert "$SPELLBOOK_DIR" not in content
        # Use json.dumps to get the JSON-escaped version (handles Windows backslashes)
        assert json.dumps(str(spellbook_dir))[1:-1] in content

    def test_expanded_unified_hook_correct(self, tmp_path):
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        assert len(pre_tool_use) == 1
        catchall_entry = pre_tool_use[0]
        assert "matcher" not in catchall_entry
        assert len(catchall_entry["hooks"]) == 1
        assert catchall_entry["hooks"][0]["type"] == "command"
        assert catchall_entry["hooks"][0]["command"] == _expected_unified_command(str(spellbook_dir))

    def test_expanded_post_tool_use_hook_correct(self, tmp_path):
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        assert len(post_tool_use) == 1
        post_entry = post_tool_use[0]
        assert "matcher" not in post_entry
        assert len(post_entry["hooks"]) == 1
        hook = post_entry["hooks"][0]
        assert hook["command"] == _expected_unified_command(str(spellbook_dir))
        assert hook["timeout"] == 15

    def test_idempotent_with_expanded_paths(self, tmp_path):
        """Running install_hooks with spellbook_dir twice should not create duplicates."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)
        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        settings = _read_settings(settings_path)
        # Each phase should have exactly 1 entry with 1 hook
        for phase in ("PreToolUse", "PostToolUse", "PreCompact", "SessionStart"):
            entries = settings["hooks"][phase]
            assert len(entries) == 1, f"{phase} should have 1 entry, got {len(entries)}"
            assert len(entries[0]["hooks"]) == 1, (
                f"{phase} should have 1 hook, got {len(entries[0]['hooks'])}"
            )

    def test_replaces_old_literal_paths_with_expanded(self, tmp_path):
        """If settings has old literal $SPELLBOOK_DIR paths, they should be replaced."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Simulate old installation with literal paths
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": ["$SPELLBOOK_DIR/hooks/bash-gate.sh"]},
                    {"matcher": "spawn_claude_session", "hooks": ["$SPELLBOOK_DIR/hooks/spawn-guard.sh"]},
                ],
            },
        })

        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        content = settings_path.read_text(encoding="utf-8")
        assert "$SPELLBOOK_DIR" not in content

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        # Old per-tool entries should be cleaned, only unified catch-all remains
        assert len(pre_tool_use) == 1
        assert "matcher" not in pre_tool_use[0]
        assert len(pre_tool_use[0]["hooks"]) == 1
        assert pre_tool_use[0]["hooks"][0]["command"] == _expected_unified_command(str(spellbook_dir))

    def test_preserves_user_hooks_with_expanded_paths(self, tmp_path):
        """User hooks should be preserved when installing with expanded paths."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)

        settings_path = config_dir / "settings.local.json"

        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": ["/usr/local/bin/my-bash-hook.sh"]},
                ],
            },
        })

        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        # User's Bash matcher entry preserved
        bash_entries = [e for e in pre_tool_use if e.get("matcher") == "Bash"]
        assert len(bash_entries) == 1
        assert bash_entries[0]["hooks"] == ["/usr/local/bin/my-bash-hook.sh"]
        # Unified hook added as catch-all entry
        catchall = [e for e in pre_tool_use if "matcher" not in e]
        assert len(catchall) == 1
        assert catchall[0]["hooks"][0]["command"] == _expected_unified_command(str(spellbook_dir))


# --- uninstall_hooks() with spellbook_dir tests ---


class TestUninstallHooksWithSpellbookDir:
    """uninstall_hooks() with spellbook_dir should remove both literal and expanded paths."""

    def test_removes_expanded_paths(self, tmp_path):
        """Expanded paths installed with spellbook_dir should be removed."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)
        result = uninstall_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        assert result.success
        assert result.action == "removed"
        settings = _read_settings(settings_path)
        post_tool_use = settings.get("hooks", {}).get("PostToolUse", [])
        assert len(post_tool_use) == 0

    def test_removes_legacy_literal_paths(self, tmp_path):
        """Old literal $SPELLBOOK_DIR paths should be cleaned up by uninstall with spellbook_dir."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Simulate old installation with literal paths
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": ["$SPELLBOOK_DIR/hooks/bash-gate.sh"]},
                ],
            },
        })

        result = uninstall_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        assert result.success
        assert result.action == "removed"
        settings = _read_settings(settings_path)
        pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
        assert len(pre_tool_use) == 0

    def test_removes_mixed_literal_and_expanded(self, tmp_path):
        """Settings with both literal and expanded paths should be fully cleaned."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Mix of old literal and new expanded paths
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [
                        "$SPELLBOOK_DIR/hooks/bash-gate.sh",
                        f"{spellbook_dir}/hooks/bash-gate.sh",
                    ]},
                ],
            },
        })

        result = uninstall_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        assert result.success
        settings = _read_settings(settings_path)
        pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
        # Both paths should be removed, leaving no entries
        assert len(pre_tool_use) == 0

    def test_preserves_user_hooks_when_removing_expanded(self, tmp_path):
        """User hooks should be preserved when removing expanded spellbook hooks."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": ["/usr/local/bin/my-hook.sh"]},
                ],
            },
        })
        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)
        uninstall_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        bash_entries = [e for e in pre_tool_use if e.get("matcher") == "Bash"]
        assert len(bash_entries) == 1
        assert bash_entries[0]["hooks"] == ["/usr/local/bin/my-hook.sh"]

    def test_uninstall_leaves_no_traces(self, tmp_path):
        """After uninstall with spellbook_dir, no spellbook paths should remain."""
        spellbook_dir = _make_spellbook_dir(tmp_path)
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        install_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)
        uninstall_hooks(settings_path, spellbook_dir=spellbook_dir, dry_run=False)

        content = settings_path.read_text(encoding="utf-8")
        assert "$SPELLBOOK_DIR" not in content
        assert str(spellbook_dir) + "/hooks/" not in content


class TestLegacyCatchallMigration:
    """Verify that legacy catch-all matchers (".*", "*", "") are migrated
    to the omitted-matcher form on reinstall."""

    def test_migrates_dotstar_matcher(self, tmp_path):
        """Re-installing should convert '.*' catch-all to omitted matcher with unified hook."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        # Simulate old installation with ".*" matcher (legacy format)
        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": ["$SPELLBOOK_DIR/hooks/bash-gate.sh"]},
                    {
                        "matcher": ".*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "$SPELLBOOK_DIR/hooks/tts-timer-start.sh",
                                "async": True,
                                "timeout": 5,
                            }
                        ],
                    },
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        # Old Bash entry cleaned (spellbook hook removed), ".*" entry migrated
        # to omitted-matcher and replaced with unified hook
        catchall_entries = [e for e in pre_tool_use if "matcher" not in e]
        assert len(catchall_entries) == 1
        # The unified hook should be present (tts-timer-start replaced by spellbook_hook.py)
        assert _get_hook_path(catchall_entries[0]["hooks"][0]).endswith(("spellbook_hook.py", "spellbook_hook.ps1"))

    def test_migrates_star_matcher(self, tmp_path):
        """Re-installing should convert '*' catch-all to omitted matcher with unified hook."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        _make_settings_file(settings_path, {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "$SPELLBOOK_DIR/hooks/tts-notify.sh",
                                "async": True,
                                "timeout": 15,
                            }
                        ],
                    },
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        post_tool_use = settings["hooks"]["PostToolUse"]
        # "*" matcher migrated to omitted-key form, old hook replaced by unified
        catchall_entries = [e for e in post_tool_use if "matcher" not in e]
        assert len(catchall_entries) == 1
        assert _get_hook_path(catchall_entries[0]["hooks"][0]).endswith(("spellbook_hook.py", "spellbook_hook.ps1"))

    def test_migrates_empty_string_matcher(self, tmp_path):
        """Re-installing should convert '' catch-all to omitted matcher with unified hook."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "$SPELLBOOK_DIR/hooks/tts-timer-start.sh",
                                "async": True,
                                "timeout": 5,
                            }
                        ],
                    },
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        # "" matcher migrated to omitted-key form, old hook replaced by unified
        catchall_entries = [e for e in pre_tool_use if "matcher" not in e]
        assert len(catchall_entries) == 1
        assert _get_hook_path(catchall_entries[0]["hooks"][0]).endswith(("spellbook_hook.py", "spellbook_hook.ps1"))

    def test_preserves_user_hooks_in_legacy_catchall(self, tmp_path):
        """User hooks in a legacy '.*' entry should be preserved during migration."""
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        settings_path = config_dir / "settings.local.json"

        _make_settings_file(settings_path, {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            "/usr/local/bin/my-catchall-hook.sh",
                            "$SPELLBOOK_DIR/hooks/tts-timer-start.sh",
                        ],
                    },
                ],
            },
        })

        install_hooks(settings_path, dry_run=False)

        settings = _read_settings(settings_path)
        pre_tool_use = settings["hooks"]["PreToolUse"]
        catchall_entries = [e for e in pre_tool_use if "matcher" not in e]
        assert len(catchall_entries) == 1
        hooks = catchall_entries[0]["hooks"]
        hook_strs = [str(h) for h in hooks]
        # User hook should be preserved
        assert any("/usr/local/bin/my-catchall-hook.sh" in s for s in hook_strs)
        # Unified hook should replace the old tts-timer-start
        assert any("spellbook_hook" in s for s in hook_strs)


# --- PowerShell command format path extraction tests ---


class TestGetHookPathPowerShellExtraction:
    """_get_hook_path() must extract the file path from PowerShell invocation wrappers."""

    def test_extracts_path_from_powershell_string_hook(self):
        """Plain string hook with PS prefix should return just the .ps1 path."""
        hook = "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/bash-gate.ps1"
        result = _get_hook_path(hook)
        assert result == "$SPELLBOOK_DIR/hooks/bash-gate.ps1"

    def test_extracts_path_from_powershell_dict_hook(self):
        """Dict hook with PS command should return just the .ps1 path."""
        hook = {
            "type": "command",
            "command": "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/bash-gate.ps1",
        }
        result = _get_hook_path(hook)
        assert result == "$SPELLBOOK_DIR/hooks/bash-gate.ps1"

    def test_sh_path_unchanged(self):
        """Non-PowerShell .sh path should pass through unchanged."""
        hook = "$SPELLBOOK_DIR/hooks/bash-gate.sh"
        result = _get_hook_path(hook)
        assert result == "$SPELLBOOK_DIR/hooks/bash-gate.sh"

    def test_dict_sh_path_unchanged(self):
        """Dict hook with .sh command should pass through unchanged."""
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.sh"}
        result = _get_hook_path(hook)
        assert result == "$SPELLBOOK_DIR/hooks/bash-gate.sh"

    def test_empty_command_returns_empty(self):
        """Dict hook without command key should return empty string."""
        hook = {"type": "command"}
        result = _get_hook_path(hook)
        assert result == ""

    def test_nim_binary_path_unchanged(self):
        """Legacy Nim binary path should pass through (no PS prefix)."""
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/nim/bin/bash_gate"}
        result = _get_hook_path(hook)
        assert result == "$SPELLBOOK_DIR/hooks/nim/bin/bash_gate"

    def test_expanded_powershell_path(self):
        """Expanded absolute path in PS wrapper should be extracted."""
        hook = {
            "type": "command",
            "command": "powershell -ExecutionPolicy Bypass -File /home/user/spellbook/hooks/bash-gate.ps1",
        }
        result = _get_hook_path(hook)
        assert result == "/home/user/spellbook/hooks/bash-gate.ps1"


class TestIsSpellbookHookWithPowerShell:
    """_is_spellbook_hook() must recognize PowerShell-wrapped spellbook hooks."""

    def test_recognizes_ps_wrapped_dollar_prefix(self):
        """PS-wrapped hook with $SPELLBOOK_DIR should be recognized."""
        hook = {
            "type": "command",
            "command": "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/bash-gate.ps1",
        }
        assert _is_spellbook_hook(hook) is True

    def test_recognizes_ps_wrapped_expanded_path(self, tmp_path):
        """PS-wrapped hook with expanded path should be recognized when spellbook_dir given."""
        spellbook_dir = tmp_path / "spellbook"
        hook = {
            "type": "command",
            "command": f"powershell -ExecutionPolicy Bypass -File {spellbook_dir}/hooks/bash-gate.ps1",
        }
        assert _is_spellbook_hook(hook, spellbook_dir=spellbook_dir) is True

    def test_sh_hook_still_recognized(self):
        """Plain .sh hook should still be recognized (unchanged behavior)."""
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.sh"}
        assert _is_spellbook_hook(hook) is True

    def test_nim_binary_still_recognized(self):
        """Legacy Nim binary path should still be recognized."""
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/nim/bin/bash_gate"}
        assert _is_spellbook_hook(hook) is True

    def test_user_hook_not_recognized(self):
        """Non-spellbook hook should not be recognized."""
        hook = {"type": "command", "command": "/usr/local/bin/my-hook.sh"}
        assert _is_spellbook_hook(hook) is False

    def test_ps_wrapped_non_spellbook_not_recognized(self):
        """PS-wrapped non-spellbook hook should not be recognized."""
        hook = {
            "type": "command",
            "command": "powershell -ExecutionPolicy Bypass -File /usr/local/bin/my-hook.ps1",
        }
        assert _is_spellbook_hook(hook) is False


# --- Two-tier hook path resolution tests ---


class TestTwoTierPathResolution:
    """Tests for 2-tier hook path resolution (Unix: .sh, Windows: .ps1 via PowerShell)."""

    def test_unix_returns_sh_path_unchanged(self):
        """On Unix, _get_hook_path_for_platform returns .sh path as-is."""
        with patch("sys.platform", "linux"):
            hook_path = "$SPELLBOOK_DIR/hooks/bash-gate.sh"
            result = _get_hook_path_for_platform(hook_path)
            assert result == "$SPELLBOOK_DIR/hooks/bash-gate.sh"

    def test_unix_no_nim_available_parameter(self):
        """_get_hook_path_for_platform no longer accepts nim_available."""
        import inspect
        sig = inspect.signature(_get_hook_path_for_platform)
        assert "nim_available" not in sig.parameters

    def test_windows_returns_powershell_command_wrapper(self):
        """On Windows, _get_hook_path_for_platform wraps .ps1 path in PowerShell invocation."""
        with patch("sys.platform", "win32"):
            hook_path = "$SPELLBOOK_DIR/hooks/bash-gate.sh"
            result = _get_hook_path_for_platform(hook_path)
            assert result == "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/bash-gate.ps1"

    def test_install_hooks_no_nim_available_parameter(self):
        """install_hooks no longer accepts nim_available."""
        import inspect
        sig = inspect.signature(install_hooks)
        assert "nim_available" not in sig.parameters

    def test_shell_to_nim_binary_removed(self):
        """_SHELL_TO_NIM_BINARY dict should no longer exist in the module."""
        import installer.components.hooks as hooks_mod
        assert not hasattr(hooks_mod, "_SHELL_TO_NIM_BINARY")

    def test_install_hooks_produces_platform_appropriate_paths(self, tmp_path):
        """install_hooks should produce platform-appropriate hook paths (no nim/bin/)."""
        settings_path = tmp_path / "settings.json"
        spellbook_dir = _make_spellbook_dir(tmp_path)

        result = install_hooks(settings_path, spellbook_dir=spellbook_dir)
        assert result.success is True
        assert result.action == "installed"

        settings = _read_settings(settings_path)
        all_commands = []
        for phase_entries in settings["hooks"].values():
            for entry in phase_entries:
                for hook in entry.get("hooks", []):
                    cmd = _get_hook_command(hook)
                    all_commands.append(cmd)

        # All hook paths should be the unified hook (no nim/bin/, no old .sh scripts)
        for cmd in all_commands:
            path = _get_hook_path(cmd)
            normalized = path.replace("\\", "/")
            assert "/nim/bin/" not in normalized, f"Nim path found: {cmd}"
            # On Unix: spellbook_hook.py, on Windows: spellbook_hook.ps1 via PS wrapper
            if sys.platform == "win32":
                assert normalized.endswith("spellbook_hook.ps1"), f"Expected .ps1 path, found: {cmd}"
            else:
                assert normalized.endswith(("spellbook_hook.py", "spellbook_hook.ps1")), f"Expected spellbook_hook path, found: {cmd}"


# --- Legacy hook detection and cleanup tests ---


class TestIsLegacyHook:
    """_is_legacy_hook() detects Nim binary and .py hook paths for cleanup."""

    def test_nim_binary_with_dollar_prefix_is_legacy(self):
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/nim/bin/bash_gate"}
        assert _is_legacy_hook(hook) is True

    def test_nim_binary_with_exe_is_legacy(self):
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/nim/bin/bash_gate.exe"}
        assert _is_legacy_hook(hook) is True

    def test_py_hook_with_dollar_prefix_is_legacy(self):
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.py"}
        assert _is_legacy_hook(hook) is True

    def test_nim_binary_expanded_path_is_legacy(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        hook = {
            "type": "command",
            "command": f"{spellbook_dir}/hooks/nim/bin/bash_gate",
        }
        assert _is_legacy_hook(hook, spellbook_dir=spellbook_dir) is True

    def test_py_hook_expanded_path_is_legacy(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        hook = {
            "type": "command",
            "command": f"{spellbook_dir}/hooks/bash-gate.py",
        }
        assert _is_legacy_hook(hook, spellbook_dir=spellbook_dir) is True

    def test_sh_hook_is_not_legacy(self):
        hook = {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.sh"}
        assert _is_legacy_hook(hook) is False

    def test_ps1_hook_is_not_legacy(self):
        hook = {
            "type": "command",
            "command": "powershell -ExecutionPolicy Bypass -File $SPELLBOOK_DIR/hooks/bash-gate.ps1",
        }
        assert _is_legacy_hook(hook) is False

    def test_user_py_hook_outside_spellbook_is_not_legacy(self):
        """A .py hook NOT in the spellbook hooks directory is not legacy."""
        hook = {"type": "command", "command": "/usr/local/bin/my-hook.py"}
        assert _is_legacy_hook(hook) is False

    def test_user_hook_is_not_legacy(self):
        hook = {"type": "command", "command": "/usr/local/bin/my-hook.sh"}
        assert _is_legacy_hook(hook) is False

    def test_string_nim_hook_is_legacy(self):
        """Plain string hook with Nim path should also be detected."""
        hook = "$SPELLBOOK_DIR/hooks/nim/bin/tts_timer_start"
        assert _is_legacy_hook(hook) is True

    def test_string_py_hook_is_legacy(self):
        hook = "$SPELLBOOK_DIR/hooks/tts-timer-start.py"
        assert _is_legacy_hook(hook) is True


class TestCleanupLegacyHooks:
    """_cleanup_legacy_hooks() removes Nim and .py entries from settings."""

    def test_removes_nim_binary_entries(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/nim/bin/bash_gate"},
                        ],
                    },
                ],
            },
        }
        _cleanup_legacy_hooks(settings)
        # Matcher group should be removed entirely since no hooks remain
        assert settings == {"hooks": {"PreToolUse": []}}

    def test_removes_py_wrapper_entries(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.py"},
                        ],
                    },
                ],
            },
        }
        _cleanup_legacy_hooks(settings)
        assert settings == {"hooks": {"PreToolUse": []}}

    def test_preserves_user_hooks_removes_legacy(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/nim/bin/bash_gate"},
                            {"type": "command", "command": "/usr/local/bin/user-hook.sh"},
                        ],
                    },
                ],
            },
        }
        _cleanup_legacy_hooks(settings)
        assert settings == {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "/usr/local/bin/user-hook.sh"},
                        ],
                    },
                ],
            },
        }

    def test_preserves_sh_hooks(self):
        """Current .sh hooks should NOT be removed by legacy cleanup."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.sh"},
                        ],
                    },
                ],
            },
        }
        _cleanup_legacy_hooks(settings)
        assert settings == {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/bash-gate.sh"},
                        ],
                    },
                ],
            },
        }

    def test_cleans_multiple_phases(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/nim/bin/bash_gate"},
                        ],
                    },
                ],
                "PostToolUse": [
                    {
                        "matcher": "Bash|Read|WebFetch|Grep|mcp__.*",
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/audit-log.py"},
                        ],
                    },
                ],
            },
        }
        _cleanup_legacy_hooks(settings)
        assert settings == {"hooks": {"PreToolUse": [], "PostToolUse": []}}

    def test_handles_empty_hooks_section(self):
        settings = {"hooks": {}}
        _cleanup_legacy_hooks(settings)
        assert settings == {"hooks": {}}

    def test_handles_no_hooks_key(self):
        settings = {}
        _cleanup_legacy_hooks(settings)
        assert settings == {}

    def test_cleanup_with_expanded_spellbook_dir(self, tmp_path):
        spellbook_dir = tmp_path / "spellbook"
        expanded_nim = f"{spellbook_dir}/hooks/nim/bin/bash_gate"
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": expanded_nim},
                        ],
                    },
                ],
            },
        }
        _cleanup_legacy_hooks(settings, spellbook_dir=spellbook_dir)
        assert settings == {"hooks": {"PreToolUse": []}}

    def test_catchall_entry_preserved_when_non_legacy_hooks_remain(self):
        """Catch-all entries (no matcher key) should be preserved if they have non-legacy hooks."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"type": "command", "command": "$SPELLBOOK_DIR/hooks/nim/bin/tts_timer_start"},
                            {"type": "command", "command": "/usr/local/bin/user-timer.sh"},
                        ],
                    },
                ],
            },
        }
        _cleanup_legacy_hooks(settings)
        assert settings == {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"type": "command", "command": "/usr/local/bin/user-timer.sh"},
                        ],
                    },
                ],
            },
        }


class TestInstallHooksLegacyCleanup:
    """install_hooks() should clean up legacy entries before registering new hooks."""

    def test_legacy_nim_hooks_cleaned_before_registration(self, tmp_path):
        """Pre-existing Nim binary hooks should be removed during install."""
        settings_path = tmp_path / "settings.json"
        spellbook_dir = _make_spellbook_dir(tmp_path)

        # Pre-populate with Nim binary hooks
        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"{spellbook_dir}/hooks/nim/bin/bash_gate",
                            },
                        ],
                    },
                ],
            },
        }
        _make_settings_file(settings_path, legacy_settings)

        result = install_hooks(settings_path, spellbook_dir=spellbook_dir)
        assert result.success is True
        assert result.action == "installed"

        settings = _read_settings(settings_path)
        # All hooks should be current .sh paths (no nim/bin/)
        all_commands = []
        for phase_entries in settings["hooks"].values():
            for entry in phase_entries:
                for hook in entry.get("hooks", []):
                    cmd = _get_hook_command(hook)
                    all_commands.append(cmd)
        nim_commands = [c for c in all_commands if "/nim/bin/" in c.replace("\\", "/")]
        assert nim_commands == [], f"Nim paths still present: {nim_commands}"

    def test_legacy_py_hooks_cleaned_before_registration(self, tmp_path):
        """Pre-existing .py wrapper hooks should be removed during install (except spellbook_hook.py)."""
        settings_path = tmp_path / "settings.json"
        spellbook_dir = _make_spellbook_dir(tmp_path)

        legacy_settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"{spellbook_dir}/hooks/bash-gate.py",
                            },
                        ],
                    },
                ],
            },
        }
        _make_settings_file(settings_path, legacy_settings)

        result = install_hooks(settings_path, spellbook_dir=spellbook_dir)
        assert result.success is True

        settings = _read_settings(settings_path)
        all_commands = []
        for phase_entries in settings["hooks"].values():
            for entry in phase_entries:
                for hook in entry.get("hooks", []):
                    cmd = _get_hook_command(hook)
                    all_commands.append(cmd)
        # Old .py hooks should be gone, but spellbook_hook.py is the new unified hook
        legacy_py = [c for c in all_commands if c.endswith(".py") and "spellbook_hook.py" not in c]
        assert legacy_py == [], f"Legacy .py paths still present: {legacy_py}"
        # spellbook_hook.py should be present (on Unix)
        if sys.platform != "win32":
            unified_py = [c for c in all_commands if "spellbook_hook.py" in c]
            assert len(unified_py) == 4, f"Expected 4 unified hooks, found {len(unified_py)}"


class TestInstallHooksPowerShellCheck:
    """install_hooks() should check PowerShell availability on Windows."""

    def test_windows_without_powershell_returns_skipped(self, tmp_path):
        """On Windows without powershell on PATH, install_hooks should skip."""
        settings_path = tmp_path / "settings.json"
        with patch("sys.platform", "win32"), \
             patch("shutil.which", return_value=None):
            result = install_hooks(settings_path)
        assert result.success is True
        assert result.action == "skipped"
        assert result.message == "PowerShell not found on PATH; hook registration skipped"
        # Settings file should NOT have been created
        assert not settings_path.exists()

    def test_unix_skips_powershell_check(self, tmp_path):
        """On Unix, install_hooks should not check for PowerShell."""
        settings_path = tmp_path / "settings.json"
        # Should succeed even though powershell may not exist
        result = install_hooks(settings_path)
        assert result.success is True
        assert result.action == "installed"
