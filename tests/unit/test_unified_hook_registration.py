"""Test that the installer registers the unified hook."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from installer.components.hooks import HOOK_DEFINITIONS


def _extract_commands_from_phase(phase_name: str) -> list[str]:
    """Extract all command strings from a given phase in HOOK_DEFINITIONS."""
    commands = []
    for entry in HOOK_DEFINITIONS.get(phase_name, []):
        for hook in entry.get("hooks", []):
            if isinstance(hook, dict):
                commands.append(hook.get("command", ""))
            else:
                commands.append(hook)
    return commands


class TestUnifiedHookRegistration:
    """Verify HOOK_DEFINITIONS uses the unified hook."""

    def test_pre_tool_use_has_unified_hook(self):
        commands = _extract_commands_from_phase("PreToolUse")
        unified = [c for c in commands if "spellbook_hook" in c]
        assert len(unified) == 1, f"Expected exactly 1 unified hook in PreToolUse, found: {commands}"

    def test_post_tool_use_has_unified_hook(self):
        commands = _extract_commands_from_phase("PostToolUse")
        unified = [c for c in commands if "spellbook_hook" in c]
        assert len(unified) == 1, f"Expected exactly 1 unified hook in PostToolUse, found: {commands}"

    def test_pre_compact_has_unified_hook(self):
        commands = _extract_commands_from_phase("PreCompact")
        unified = [c for c in commands if "spellbook_hook" in c]
        assert len(unified) == 1, f"Expected exactly 1 unified hook in PreCompact, found: {commands}"

    def test_session_start_has_unified_hook(self):
        commands = _extract_commands_from_phase("SessionStart")
        unified = [c for c in commands if "spellbook_hook" in c]
        assert len(unified) == 1, f"Expected exactly 1 unified hook in SessionStart, found: {commands}"

    def test_no_old_shell_hooks_remain(self):
        """Verify no individual .sh hooks are registered."""
        old_hooks = {
            "bash-gate.sh", "spawn-guard.sh", "state-sanitize.sh",
            "tts-timer-start.sh", "audit-log.sh", "canary-check.sh",
            "memory-inject.sh", "notify-on-complete.sh", "tts-notify.sh",
            "memory-capture.sh", "pre-compact-save.sh", "post-compact-recover.sh",
        }
        for phase, entries in HOOK_DEFINITIONS.items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "") if isinstance(hook, dict) else hook
                    for old in old_hooks:
                        assert old not in cmd, (
                            f"Old hook {old} still registered in {phase}: {cmd}"
                        )

    def test_unified_hook_command_path(self):
        """Verify the exact command path for the unified hook."""
        commands = _extract_commands_from_phase("PreToolUse")
        unified = [c for c in commands if "spellbook_hook" in c]
        assert unified[0] == "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py"

    def test_pre_tool_use_is_synchronous(self):
        """PreToolUse must NOT have async: true (security gates must block)."""
        for entry in HOOK_DEFINITIONS["PreToolUse"]:
            for hook in entry.get("hooks", []):
                if isinstance(hook, dict) and "spellbook_hook" in hook.get("command", ""):
                    assert hook.get("async") is not True, (
                        "PreToolUse unified hook must be synchronous for security gates"
                    )

    def test_post_tool_use_is_synchronous(self):
        """PostToolUse must NOT have async (canary-check and memory-inject need stdout)."""
        for entry in HOOK_DEFINITIONS["PostToolUse"]:
            for hook in entry.get("hooks", []):
                if isinstance(hook, dict) and "spellbook_hook" in hook.get("command", ""):
                    assert hook.get("async") is not True, (
                        "PostToolUse unified hook must be synchronous for context injection"
                    )

    def test_all_phases_present(self):
        """All four hook phases must be defined."""
        expected_phases = {"PreToolUse", "PostToolUse", "PreCompact", "SessionStart"}
        assert set(HOOK_DEFINITIONS.keys()) == expected_phases, (
            f"Expected phases {expected_phases}, got {set(HOOK_DEFINITIONS.keys())}"
        )

    def test_exactly_one_entry_per_phase(self):
        """Each phase should have exactly one entry (unified hook handles all matching)."""
        for phase in ("PreToolUse", "PostToolUse", "PreCompact", "SessionStart"):
            entries = HOOK_DEFINITIONS[phase]
            assert len(entries) == 1, (
                f"Expected 1 entry in {phase}, got {len(entries)}: {entries}"
            )
