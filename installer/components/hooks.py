"""
Claude Code hook registration for security hooks.

Manages PreToolUse hook entries in .claude/settings.local.json that
point to spellbook security scripts (bash-gate.sh, spawn-guard.sh).
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Hook definitions: each entry maps a Claude Code tool matcher to a hook script.
# Paths use $SPELLBOOK_DIR which the hooks resolve at runtime.
HOOK_DEFINITIONS: List[Dict] = [
    {
        "matcher": "Bash",
        "hooks": ["$SPELLBOOK_DIR/hooks/bash-gate.sh"],
    },
    {
        "matcher": "spawn_claude_session",
        "hooks": ["$SPELLBOOK_DIR/hooks/spawn-guard.sh"],
    },
]

# Prefix used to identify spellbook-managed hook paths
_SPELLBOOK_HOOK_PREFIX = "$SPELLBOOK_DIR/hooks/"


@dataclass
class HookResult:
    """Result of a hook install/uninstall operation."""

    component: str
    success: bool
    action: str
    message: str


def _is_spellbook_hook(hook_path: str) -> bool:
    """Check if a hook path is managed by spellbook."""
    return hook_path.startswith(_SPELLBOOK_HOOK_PREFIX)


def _load_settings(settings_path: Path) -> Optional[Dict]:
    """Load and parse settings.local.json, returning None on missing file or empty content."""
    if not settings_path.exists():
        return {}

    content = settings_path.read_text(encoding="utf-8").strip()
    if not content:
        return {}

    return json.loads(content)


def install_hooks(settings_path: Path, dry_run: bool = False) -> HookResult:
    """Install spellbook security hooks into settings.local.json.

    Merges hook entries into the existing PreToolUse array. If a matcher
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

    # Ensure hooks.PreToolUse structure exists
    if "hooks" not in settings:
        settings["hooks"] = {}
    if "PreToolUse" not in settings["hooks"]:
        settings["hooks"]["PreToolUse"] = []

    pre_tool_use: List[Dict] = settings["hooks"]["PreToolUse"]

    # For each hook definition, merge into the PreToolUse array
    for hook_def in HOOK_DEFINITIONS:
        matcher = hook_def["matcher"]
        spellbook_hooks = hook_def["hooks"]

        # Find existing entry with this matcher
        existing_entry = None
        for entry in pre_tool_use:
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
            pre_tool_use.append({
                "matcher": matcher,
                "hooks": list(spellbook_hooks),
            })

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
    $SPELLBOOK_DIR/hooks/). User-defined hooks are preserved. If removing
    the spellbook hook leaves a matcher entry with no hooks, the entire
    entry is removed.

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

    pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
    if not pre_tool_use:
        return HookResult(
            component="hooks",
            success=True,
            action="unchanged",
            message="hooks: no PreToolUse hooks found",
        )

    # Filter out spellbook hooks from each entry
    new_pre_tool_use = []
    for entry in pre_tool_use:
        hooks_list = entry.get("hooks", [])
        cleaned = [h for h in hooks_list if not _is_spellbook_hook(h)]
        if cleaned:
            # Keep entry with remaining user hooks
            new_pre_tool_use.append({
                "matcher": entry["matcher"],
                "hooks": cleaned,
            })
        # If cleaned is empty, drop the entry entirely

    settings["hooks"]["PreToolUse"] = new_pre_tool_use

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
