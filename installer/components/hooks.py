"""
Claude Code hook registration for security, TTS, and compaction hooks.

Manages hook entries in Claude Code settings files that point to
spellbook security scripts, TTS notification hooks, and compaction
recovery hooks.

PreToolUse hooks:
  - Bash -> bash-gate.sh
  - spawn_claude_session -> spawn-guard.sh
  - mcp__spellbook__workflow_state_save -> state-sanitize.sh (timeout: 15)
  - (catch-all, no matcher) -> tts-timer-start.sh (async, timeout: 5)

PostToolUse hooks:
  - Bash|Read|WebFetch|Grep|mcp__.* -> audit-log.sh (async, timeout: 10)
  - Bash|Read|WebFetch|Grep|mcp__.* -> canary-check.sh (timeout: 10)
  - (catch-all, no matcher) -> tts-notify.sh (async, timeout: 15)

PreCompact hooks:
  - (catch-all, no matcher) -> pre-compact-save.sh (timeout: 5)

SessionStart hooks:
  - (catch-all, no matcher) -> post-compact-recover.sh (timeout: 10)

Note: Catch-all hooks omit the ``matcher`` field entirely rather than
using ``".*"`` or ``"*"``.  Claude Code documentation states: "Use ``*``,
``""``, or omit ``matcher`` entirely to match all occurrences."  In
practice, omitting the field is the most reliable approach.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Hook definitions grouped by phase. Each phase maps to a list of matcher entries.
# All hooks MUST use the object format {type, command, ...}. Plain string hooks
# are no longer accepted by Claude Code (as of ~v2.1).
# Paths use $SPELLBOOK_DIR which the hooks resolve at runtime.
#
# Entries WITHOUT a "matcher" key are catch-all hooks that fire on every tool
# invocation.  Claude Code docs: "omit matcher entirely to match all occurrences."
# Using ".*" does NOT reliably match; omitting the key is the correct approach.
#
# Claude Code deduplicates hooks by command string across all matching groups,
# so a hook appearing in both a specific matcher and the catch-all runs only once.
HOOK_DEFINITIONS: Dict[str, List[Dict]] = {
    "PreToolUse": [
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/bash-gate.sh",
                },
            ],
        },
        {
            "matcher": "spawn_claude_session",
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/spawn-guard.sh",
                },
            ],
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
        {
            # Catch-all: no "matcher" key means fire on every tool invocation
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/tts-timer-start.sh",
                    "async": True,
                    "timeout": 5,
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
        {
            # Catch-all: no "matcher" key means fire on every tool invocation
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/tts-notify.sh",
                    "async": True,
                    "timeout": 15,
                },
            ],
        },
    ],
    "PreCompact": [
        {
            # Catch-all: saves workflow state before compaction.
            # Fail-open (exit 0 always) - must never block compaction.
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/pre-compact-save.sh",
                    "timeout": 5,
                },
            ],
        },
    ],
    "SessionStart": [
        {
            # Catch-all: injects recovery context after compaction.
            # Fail-open (exit 0 always) - must never prevent session start.
            # The script itself filters on source=="compact" internally.
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_DIR/hooks/post-compact-recover.sh",
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

# Name mapping: shell script name -> Nim binary name
_SHELL_TO_NIM_BINARY = {
    "tts-timer-start.sh": "tts_timer_start",
    "bash-gate.sh": "bash_gate",
    "spawn-guard.sh": "spawn_guard",
    "state-sanitize.sh": "state_sanitize",
    "audit-log.sh": "audit_log",
    "canary-check.sh": "canary_check",
    "tts-notify.sh": "tts_notify",
    "pre-compact-save.sh": "pre_compact_save",
    "post-compact-recover.sh": "post_compact_recover",
}


def _get_hook_path_for_platform(hook_path: str, nim_available: bool = False) -> str:
    """Resolve hook path based on platform and Nim availability.

    Priority: Nim binary > shell script > Python wrapper (Windows)

    On Windows with nim_available=True, returns Nim binary path with .exe extension.
    On Windows with nim_available=False, returns .py wrapper path.
    On Unix with nim_available=True, returns Nim binary path.
    On Unix with nim_available=False, returns original .sh path.
    """
    import sys

    is_windows = sys.platform == "win32"

    if nim_available:
        # Extract shell script name using PurePosixPath since template paths
        # always use forward slashes ($SPELLBOOK_DIR/hooks/foo.sh)
        from pathlib import PurePosixPath

        shell_name = PurePosixPath(hook_path).name  # e.g., "bash-gate.sh"
        nim_name = _SHELL_TO_NIM_BINARY.get(shell_name)
        if nim_name:
            # Split on /hooks/ to get the prefix before the hooks directory.
            # Template paths always use forward slashes.
            parts = hook_path.rsplit("/hooks/", 1)
            if len(parts) == 2:
                if is_windows:
                    nim_path = parts[0] + f"/hooks/nim/bin/{nim_name}.exe"
                else:
                    nim_path = parts[0] + f"/hooks/nim/bin/{nim_name}"
                return nim_path

    if is_windows:
        return hook_path.replace(".sh", ".py")

    return hook_path


def _transform_hook_for_platform(
    hook: Union[str, Dict[str, Any]], nim_available: bool = False
) -> Union[str, Dict[str, Any]]:
    """Transform a hook entry's path for the current platform.

    Handles both plain string hooks and object-format hooks.
    """
    if isinstance(hook, str):
        return _get_hook_path_for_platform(hook, nim_available=nim_available)
    # Dict-format hook: transform the 'command' key
    transformed = dict(hook)
    if "command" in transformed:
        transformed["command"] = _get_hook_path_for_platform(
            transformed["command"], nim_available=nim_available
        )
    return transformed


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


def _is_spellbook_hook(hook: Union[str, Dict[str, Any]], spellbook_dir: Optional[Path] = None) -> bool:
    """Check if a hook is managed by spellbook.

    Works with both string hooks ("$SPELLBOOK_DIR/hooks/foo.sh") and
    object hooks ({"type": "command", "command": "$SPELLBOOK_DIR/hooks/foo.sh"}).
    Also detects .py wrapper hooks on Windows and Nim binary paths.

    Recognizes both legacy literal $SPELLBOOK_DIR paths and expanded absolute
    paths when spellbook_dir is provided. On Windows, path separators are
    normalized before comparison so both forward and back slashes match.
    """
    path = _get_hook_path(hook)
    # Normalize to forward slashes for consistent comparison across platforms
    normalized_path = path.replace("\\", "/")
    if normalized_path.startswith(_SPELLBOOK_HOOK_PREFIX):
        return True
    if spellbook_dir is not None:
        # Normalize spellbook_dir to forward slashes as well
        expanded_prefix = str(spellbook_dir).replace("\\", "/") + "/hooks/"
        if normalized_path.startswith(expanded_prefix):
            return True
    return False


def _expand_spellbook_dir(hook: Union[str, Dict[str, Any]], spellbook_dir: Path) -> Union[str, Dict[str, Any]]:
    """Replace $SPELLBOOK_DIR with the actual spellbook directory path."""
    spellbook_str = str(spellbook_dir)
    if isinstance(hook, str):
        return hook.replace("$SPELLBOOK_DIR", spellbook_str)
    expanded = dict(hook)
    if "command" in expanded:
        expanded["command"] = expanded["command"].replace("$SPELLBOOK_DIR", spellbook_str)
    return expanded


def _load_settings(settings_path: Path) -> Optional[Dict]:
    """Load and parse a settings JSON file, returning None on missing file or empty content."""
    if not settings_path.exists():
        return {}

    content = settings_path.read_text(encoding="utf-8").strip()
    if not content:
        return {}

    return json.loads(content)


def _matcher_key(entry: Dict) -> Optional[str]:
    """Return the matcher value from a hook entry, or None if omitted.

    This distinguishes between three cases:
      - "matcher" key absent  -> None (catch-all, fires on every tool)
      - "matcher": ".*"       -> ".*" (legacy catch-all, treated as regex)
      - "matcher": "Bash"     -> "Bash"
    """
    return entry.get("matcher")


# Legacy catch-all matcher values that should be treated as equivalent
# to omitting the matcher key entirely.  When we encounter these in
# existing settings we migrate them to the omitted-key form.
_LEGACY_CATCHALL_MATCHERS = {".*", "*", ""}


def _merge_hooks_for_phase(
    phase_entries: List[Dict],
    hook_defs: List[Dict],
    spellbook_dir: Optional[Path] = None,
    nim_available: bool = False,
) -> None:
    """Merge spellbook hook definitions into an existing phase array.

    For each hook definition, finds or creates a matcher entry, removes
    any old spellbook hooks, and appends the new ones. User hooks are
    never removed or replaced.

    Catch-all entries (no ``matcher`` key) are matched against existing
    entries that also have no matcher, or that use legacy catch-all
    values (``".*"``, ``"*"``, ``""``).  Legacy entries are migrated to
    the omitted-key form.

    If spellbook_dir is provided, $SPELLBOOK_DIR in hook paths is expanded
    to the actual absolute path, and both literal and expanded paths are
    recognized for cleanup of old hooks.
    """
    for hook_def in hook_defs:
        matcher = _matcher_key(hook_def)
        is_catchall = matcher is None

        # Transform hook paths for the current platform (.sh -> .py on Windows, or Nim binary)
        spellbook_hooks = [
            _transform_hook_for_platform(h, nim_available=nim_available) for h in hook_def["hooks"]
        ]
        # Expand $SPELLBOOK_DIR to actual path if provided
        if spellbook_dir is not None:
            spellbook_hooks = [_expand_spellbook_dir(h, spellbook_dir) for h in spellbook_hooks]

        # Find existing entry with this matcher
        existing_entry = None
        for entry in phase_entries:
            entry_matcher = _matcher_key(entry)
            if is_catchall:
                # Match entries with no matcher OR legacy catch-all values
                if entry_matcher is None or entry_matcher in _LEGACY_CATCHALL_MATCHERS:
                    existing_entry = entry
                    break
            else:
                if entry_matcher == matcher:
                    existing_entry = entry
                    break

        if existing_entry is not None:
            # Remove any old spellbook hooks from this entry (both literal and expanded)
            existing_hooks = existing_entry.get("hooks", [])
            cleaned_hooks = [h for h in existing_hooks if not _is_spellbook_hook(h, spellbook_dir)]
            # Add the new spellbook hooks
            cleaned_hooks.extend(spellbook_hooks)
            existing_entry["hooks"] = cleaned_hooks
            # Migrate legacy catch-all matchers to omitted-key form
            if is_catchall and "matcher" in existing_entry:
                del existing_entry["matcher"]
        else:
            # Add a new entry for this matcher
            new_entry: Dict[str, Any] = {"hooks": list(spellbook_hooks)}
            if matcher is not None:
                new_entry["matcher"] = matcher
            phase_entries.append(new_entry)


def _clean_hooks_for_phase(phase_entries: List[Dict], spellbook_dir: Optional[Path] = None) -> List[Dict]:
    """Remove spellbook hooks from a phase array, preserving user hooks.

    Returns a new list with spellbook hooks removed. Matcher entries that
    have no remaining hooks after cleanup are dropped entirely.

    If spellbook_dir is provided, both literal $SPELLBOOK_DIR paths and
    expanded absolute paths are recognized for removal.
    """
    cleaned = []
    for entry in phase_entries:
        hooks_list = entry.get("hooks", [])
        remaining = [h for h in hooks_list if not _is_spellbook_hook(h, spellbook_dir)]
        if remaining:
            new_entry: Dict[str, Any] = {"hooks": remaining}
            if "matcher" in entry:
                new_entry["matcher"] = entry["matcher"]
            cleaned.append(new_entry)
    return cleaned


def install_hooks(
    settings_path: Path,
    spellbook_dir: Optional[Path] = None,
    nim_available: bool = False,
    dry_run: bool = False,
) -> HookResult:
    """Install spellbook security hooks into a Claude Code settings file.

    Merges hook entries into PreToolUse and PostToolUse arrays. If a matcher
    already exists (e.g., user has their own Bash hook), the spellbook
    hook is appended to that entry's hooks list. Existing user hooks are
    never removed or replaced.

    If spellbook_dir is provided, $SPELLBOOK_DIR in hook paths is expanded
    to the actual absolute path so hooks work without environment variable
    expansion at runtime.

    NOTE: Claude Code only reads hooks from ~/.claude/settings.json (user-level),
    .claude/settings.json (project), and .claude/settings.local.json (project local).
    User-level ~/.claude/settings.local.json is NOT a supported hooks location.

    Args:
        settings_path: Path to the settings file (e.g. settings.json)
        spellbook_dir: Path to the spellbook installation directory. When provided,
            $SPELLBOOK_DIR is expanded to this path in all hook commands.
        nim_available: If True, use compiled Nim binary paths instead of shell scripts.
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
        _merge_hooks_for_phase(
            settings["hooks"][phase], hook_defs, spellbook_dir, nim_available=nim_available
        )

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
        message=f"hooks: security hooks registered in {settings_path.name}",
    )


def uninstall_hooks(settings_path: Path, spellbook_dir: Optional[Path] = None, dry_run: bool = False) -> HookResult:
    """Remove spellbook security hooks from a Claude Code settings file.

    Removes only spellbook-managed hook paths from all phases. User-defined
    hooks are preserved. If removing the spellbook hook leaves a matcher
    entry with no hooks, the entire entry is removed.

    Recognizes both legacy literal $SPELLBOOK_DIR paths and expanded absolute
    paths when spellbook_dir is provided, ensuring backward compatibility.

    Args:
        settings_path: Path to the settings file (e.g. settings.json)
        spellbook_dir: Path to the spellbook installation directory. When provided,
            hooks with expanded absolute paths are also recognized for removal.
        dry_run: If True, do not write any changes

    Returns:
        HookResult indicating success/failure and action taken
    """
    if not settings_path.exists():
        return HookResult(
            component="hooks",
            success=True,
            action="unchanged",
            message=f"hooks: {settings_path.name} not found, nothing to remove",
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
            message=f"hooks: {settings_path.name} has invalid JSON, skipping",
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
                if _is_spellbook_hook(hook, spellbook_dir):
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
            hooks_section[phase] = _clean_hooks_for_phase(hooks_section[phase], spellbook_dir)

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
        message=f"hooks: spellbook security hooks removed from {settings_path.name}",
    )
