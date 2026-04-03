"""Tests for unified hook registration in installer.

Verifies that the unified hook (spellbook_hook.py) is registered in
HOOK_DEFINITIONS for all four phases, replacing the old per-hook entries:

- PreToolUse: spellbook_hook.py (timeout 15, catch-all, no async)
- PostToolUse: spellbook_hook.py (timeout 15, catch-all, no async)
- PreCompact: spellbook_hook.py (timeout 5, catch-all, no async)
- SessionStart: spellbook_hook.py (timeout 10, catch-all, no async)

Memory hooks (memory-capture, memory-inject) are now handled internally
by the unified hook's PostToolUse dispatcher.
"""

from installer.components.hooks import HOOK_DEFINITIONS


def _find_hook_entry(phase: str, command_suffix: str) -> dict | None:
    """Find a hook dict in HOOK_DEFINITIONS by phase and command suffix."""
    for entry in HOOK_DEFINITIONS.get(phase, []):
        for hook in entry.get("hooks", []):
            cmd = hook if isinstance(hook, str) else hook.get("command", "")
            if cmd.endswith(command_suffix):
                return hook
    return None


def _find_matcher_for_hook(phase: str, command_suffix: str) -> str | None:
    """Find the matcher value for the entry containing a given hook.

    Returns the matcher string, or the sentinel "NO_MATCHER" if the entry
    has no matcher key (catch-all), or None if the hook is not found at all.
    """
    for entry in HOOK_DEFINITIONS.get(phase, []):
        for hook in entry.get("hooks", []):
            cmd = hook if isinstance(hook, str) else hook.get("command", "")
            if cmd.endswith(command_suffix):
                return entry.get("matcher", "NO_MATCHER")
    return None


def test_unified_hook_registered_in_post_tool_use():
    """spellbook_hook.py is registered as a PostToolUse catch-all hook (no async)."""
    hook = _find_hook_entry("PostToolUse", "spellbook_hook.py")
    assert hook is not None, "spellbook_hook.py not found in PostToolUse hooks"
    assert hook == {
        "type": "command",
        "command": "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py",
        "timeout": 15,
    }


def test_unified_hook_is_catch_all_in_post_tool_use():
    """spellbook_hook.py entry in PostToolUse must have no matcher key (catch-all)."""
    matcher = _find_matcher_for_hook("PostToolUse", "spellbook_hook.py")
    assert matcher == "NO_MATCHER", (
        f"spellbook_hook.py should be in a catch-all entry (no matcher key), "
        f"but found matcher={matcher!r}"
    )


def test_unified_hook_registered_in_pre_tool_use():
    """spellbook_hook.py is registered as a PreToolUse catch-all hook (no async)."""
    hook = _find_hook_entry("PreToolUse", "spellbook_hook.py")
    assert hook is not None, "spellbook_hook.py not found in PreToolUse hooks"
    assert hook == {
        "type": "command",
        "command": "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py",
        "timeout": 15,
    }


def test_unified_hook_is_catch_all_in_pre_tool_use():
    """spellbook_hook.py entry in PreToolUse must have no matcher key (catch-all)."""
    matcher = _find_matcher_for_hook("PreToolUse", "spellbook_hook.py")
    assert matcher == "NO_MATCHER", (
        f"spellbook_hook.py should be in a catch-all entry (no matcher key), "
        f"but found matcher={matcher!r}"
    )


def test_old_memory_hooks_not_registered():
    """Old individual memory hooks should not be in HOOK_DEFINITIONS."""
    for phase in HOOK_DEFINITIONS:
        for entry in HOOK_DEFINITIONS[phase]:
            for hook in entry.get("hooks", []):
                cmd = hook if isinstance(hook, str) else hook.get("command", "")
                assert "memory-capture.sh" not in cmd, (
                    f"Old memory-capture.sh still registered in {phase}"
                )
                assert "memory-inject.sh" not in cmd, (
                    f"Old memory-inject.sh still registered in {phase}"
                )
