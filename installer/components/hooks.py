"""
Claude Code hook registration for security hooks.

Manages PreToolUse and PostToolUse hook entries in .claude/settings.local.json
that point to spellbook security scripts.

Tier 1 (PreToolUse):
  - Bash -> bash-gate.sh
  - spawn_claude_session -> spawn-guard.sh

Tier 2 (PreToolUse + PostToolUse):
  - mcp__spellbook__workflow_state_save -> state-sanitize.sh (timeout: 15)
  - Bash|Read|WebFetch|Grep|mcp__.* -> audit-log.sh (async, timeout: 10)
  - Bash|Read|WebFetch|Grep|mcp__.* -> canary-check.sh (timeout: 10)
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Hook definitions grouped by phase. Each phase maps to a list of matcher entries.
# Hooks can be plain strings (simple command path) or dicts with type/command/async/timeout.
# Paths use $SPELLBOOK_DIR which the hooks resolve at runtime.
HOOK_DEFINITIONS: Dict[str, List[Dict]] = {
    "PreToolUse": [
        {
            "matcher": "Bash",
            "hooks": ["$SPELLBOOK_DIR/hooks/bash-gate.sh"],
        },
        {
            "matcher": "spawn_claude_session",
            "hooks": ["$SPELLBOOK_DIR/hooks/spawn-guard.sh"],
        },
        {
            "matcher": "mcp__spellbook__workflow_state_save",
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/state-sanitize.sh",
                    "timeout": 15,
                },
            ],
        },
    ],
    "PostToolUse": [
        {
            "matcher": "Bash|Read|WebFetch|Grep|mcp__.*",
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/audit-log.sh",
                    "async": True,
                    "timeout": 10,
                },
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/canary-check.sh",
                    "timeout": 10,
                },
            ],
        },
    ],
}

# All phases that contain spellbook hooks
_HOOK_PHASES = list(HOOK_DEFINITIONS.keys())

# Prefix used to identify spellbook-managed hook paths
_SPELLBOOK_HOOK_PREFIX = "$SPELLBOOK_DIR/hooks/"


@dataclass
class HookResult:
    """Result of a hook install/uninstall operation."""

    component: str
    success: bool
    action: str
    message: str


def _get_hook_path(hook: Union[str, Dict[str, Any]]) -> str:
    """Extract the command path from a hook entry.

    Handles both plain string hooks and object-format hooks with a 'command' key.
    """
    if isinstance(hook, str):
        return hook
    return hook.get("command", "")


def _is_spellbook_hook(hook: Union[str, Dict[str, Any]]) -> bool:
    """Check if a hook is managed by spellbook.

    Works with both string hooks ("$SPELLBOOK_DIR/hooks/foo.sh") and
    object hooks ({"type": "command", "command": "$SPELLBOOK_DIR/hooks/foo.sh"}).
    """
    return _get_hook_path(hook).startswith(_SPELLBOOK_HOOK_PREFIX)


def _load_settings(settings_path: Path) -> Optional[Dict]:
    """Load and parse settings.local.json, returning None on missing file or empty content."""
    if not settings_path.exists():
        return {}

    content = settings_path.read_text(encoding="utf-8").strip()
    if not content:
        return {}

    return json.loads(content)


def _merge_hooks_for_phase(
    phase_entries: List[Dict],
    hook_defs: List[Dict],
) -> None:
    """Merge spellbook hook definitions into an existing phase array.

    For each hook definition, finds or creates a matcher entry, removes
    any old spellbook hooks, and appends the new ones. User hooks are
    never removed or replaced.
    """
    for hook_def in hook_defs:
        matcher = hook_def["matcher"]
        spellbook_hooks = hook_def["hooks"]

        # Find existing entry with this matcher
        existing_entry = None
        for entry in phase_entries:
            if entry.get("matcher") == matcher:
                existing_entry = entry
                break

        if existing_entry is not None:
            # Remove any old spellbook hooks from this entry
            existing_hooks = existing_entry.get("hooks", [])
            cleaned_hooks = [h for h in existing_hooks if not _is_spellbook_hook(h)]
            # Add the new spellbook hooks
            cleaned_hooks.extend(spellbook_hooks)
            existing_entry["hooks"] = cleaned_hooks
        else:
            # Add a new entry for this matcher
            phase_entries.append({
                "matcher": matcher,
                "hooks": list(spellbook_hooks),
            })


def _clean_hooks_for_phase(phase_entries: List[Dict]) -> List[Dict]:
    """Remove spellbook hooks from a phase array, preserving user hooks.

    Returns a new list with spellbook hooks removed. Matcher entries that
    have no remaining hooks after cleanup are dropped entirely.
    """
    cleaned = []
    for entry in phase_entries:
        hooks_list = entry.get("hooks", [])
        remaining = [h for h in hooks_list if not _is_spellbook_hook(h)]
        if remaining:
            cleaned.append({
                "matcher": entry["matcher"],
                "hooks": remaining,
            })
    return cleaned


def install_hooks(settings_path: Path, dry_run: bool = False) -> HookResult:
    """Install spellbook security hooks into settings.local.json.

    Merges hook entries into PreToolUse and PostToolUse arrays. If a matcher
    already exists (e.g., user has their own Bash hook), the spellbook
    hook is appended to that entry's hooks list. Existing user hooks are
    never removed or replaced.

    Args:
        settings_path: Path to .claude/settings.local.json
        dry_run: If True, do not write any changes

    Returns:
        HookResult indicating success/failure and action taken
    """
    if dry_run:
        return HookResult(
            component="hooks",
            success=True,
            action="installed",
            message="hooks: would be installed (dry run)",
        )

    # Load existing settings
    try:
        settings = _load_settings(settings_path)
    except json.JSONDecodeError as e:
        return HookResult(
            component="hooks",
            success=False,
            action="failed",
            message=f"hooks: failed to parse {settings_path.name} - JSON decode error: {e}",
        )

    if settings is None:
        settings = {}

    # Ensure hooks structure exists
    if "hooks" not in settings:
        settings["hooks"] = {}

    # Merge hooks for each phase
    for phase, hook_defs in HOOK_DEFINITIONS.items():
        if phase not in settings["hooks"]:
            settings["hooks"][phase] = []
        _merge_hooks_for_phase(settings["hooks"][phase], hook_defs)

    # Write back
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings, indent=2) + "\n",
        encoding="utf-8",
    )

    return HookResult(
        component="hooks",
        success=True,
        action="installed",
        message="hooks: security hooks registered in settings.local.json",
    )


def uninstall_hooks(settings_path: Path, dry_run: bool = False) -> HookResult:
    """Remove spellbook security hooks from settings.local.json.

    Removes only spellbook-managed hook paths (those starting with
    $SPELLBOOK_DIR/hooks/) from all phases. User-defined hooks are
    preserved. If removing the spellbook hook leaves a matcher entry
    with no hooks, the entire entry is removed.

    Args:
        settings_path: Path to .claude/settings.local.json
        dry_run: If True, do not write any changes

    Returns:
        HookResult indicating success/failure and action taken
    """
    if not settings_path.exists():
        return HookResult(
            component="hooks",
            success=True,
            action="unchanged",
            message="hooks: settings.local.json not found, nothing to remove",
        )

    if dry_run:
        return HookResult(
            component="hooks",
            success=True,
            action="removed",
            message="hooks: would be removed (dry run)",
        )

    try:
        settings = _load_settings(settings_path)
    except json.JSONDecodeError:
        return HookResult(
            component="hooks",
            success=True,
            action="unchanged",
            message="hooks: settings.local.json has invalid JSON, skipping",
        )

    if settings is None:
        settings = {}

    hooks_section = settings.get("hooks", {})

    # Check if there are any spellbook hooks to remove across all phases
    has_spellbook_hooks = False
    for phase in _HOOK_PHASES:
        phase_entries = hooks_section.get(phase, [])
        for entry in phase_entries:
            for hook in entry.get("hooks", []):
                if _is_spellbook_hook(hook):
                    has_spellbook_hooks = True
                    break
            if has_spellbook_hooks:
                break
        if has_spellbook_hooks:
            break

    if not has_spellbook_hooks:
        return HookResult(
            component="hooks",
            success=True,
            action="unchanged",
            message="hooks: no spellbook hooks found",
        )

    # Clean spellbook hooks from each phase
    for phase in _HOOK_PHASES:
        if phase in hooks_section:
            hooks_section[phase] = _clean_hooks_for_phase(hooks_section[phase])

    settings["hooks"] = hooks_section

    # Write back
    settings_path.write_text(
        json.dumps(settings, indent=2) + "\n",
        encoding="utf-8",
    )

    return HookResult(
        component="hooks",
        success=True,
        action="removed",
        message="hooks: spellbook security hooks removed from settings.local.json",
    )
