"""Tests for memory hook registration in installer.

Verifies that the two memory hooks are registered in HOOK_DEFINITIONS
with the correct phase, matcher, and hook attributes:

- memory-capture.sh: PostToolUse catch-all, async, timeout 5
- memory-inject.sh: PostToolUse matcher Read|Edit|Grep|Glob, sync, timeout 5
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


def test_memory_capture_hook_registered_with_correct_config():
    """memory-capture.sh is registered as a PostToolUse catch-all async hook."""
    hook = _find_hook_entry("PostToolUse", "memory-capture.sh")
    assert hook is not None, "memory-capture.sh not found in PostToolUse hooks"
    assert hook == {
        "type": "command",
        "command": "$SPELLBOOK_DIR/hooks/memory-capture.sh",
        "async": True,
        "timeout": 5,
    }


def test_memory_capture_hook_is_catch_all():
    """memory-capture.sh entry must have no matcher key (catch-all)."""
    matcher = _find_matcher_for_hook("PostToolUse", "memory-capture.sh")
    assert matcher == "NO_MATCHER", (
        f"memory-capture.sh should be in a catch-all entry (no matcher key), "
        f"but found matcher={matcher!r}"
    )


def test_memory_inject_hook_registered_with_correct_config():
    """memory-inject.sh is registered as a PostToolUse sync hook."""
    hook = _find_hook_entry("PostToolUse", "memory-inject.sh")
    assert hook is not None, "memory-inject.sh not found in PostToolUse hooks"
    assert hook == {
        "type": "command",
        "command": "$SPELLBOOK_DIR/hooks/memory-inject.sh",
        "timeout": 5,
    }


def test_memory_inject_hook_matcher():
    """memory-inject.sh entry must match Read|Edit|Grep|Glob tools."""
    matcher = _find_matcher_for_hook("PostToolUse", "memory-inject.sh")
    assert matcher == "Read|Edit|Grep|Glob", (
        f"memory-inject.sh should match Read|Edit|Grep|Glob, "
        f"but found matcher={matcher!r}"
    )
