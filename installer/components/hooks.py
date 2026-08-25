"""
Claude Code hook registration for the unified spellbook hook.

Manages hook entries in Claude Code settings files that point to
the unified Python hook entrypoint (spellbook_hook.py), which handles
all security, notification, memory, and compaction hooks internally.

Every phase uses a single hook command:
  $SPELLBOOK_DIR/hooks/spellbook_hook.py

The unified hook dispatches internally based on event type and tool name:
  PreToolUse: bash-gate, spawn-guard, state-sanitize
  PostToolUse: audit-log, canary-check, memory-inject, notify, capture
  UserPromptSubmit: autonomous-mode escape phrase, agent2agent notify floor
  Stop: autonomous-mode turn-end enforcement (returns a block/allow decision)
  SessionStart: post-compaction recovery

Phases spellbook once registered and no longer does are listed in
``_RETIRED_HOOK_PHASES`` and swept out of existing settings files on install.

Note: Catch-all hooks omit the ``matcher`` field entirely rather than
using ``".*"`` or ``"*"``.  Claude Code documentation states: "Use ``*``,
``""``, or omit ``matcher`` entirely to match all occurrences."  In
practice, omitting the field is the most reliable approach.
"""

import json
import logging
import platform as _platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from spellbook.core.command_utils import atomic_write_json

from .. import config as _config
from . import source_link as _source_link

logger = logging.getLogger(__name__)

# Hook definitions grouped by phase. Each phase maps to a list of matcher entries.
# All hooks MUST use the object format {type, command, ...}. Plain string hooks
# are no longer accepted by Claude Code (as of ~v2.1).
# Paths use $SPELLBOOK_DIR which the hooks resolve at runtime.
#
# The unified hook (spellbook_hook.py) handles ALL hook logic internally,
# dispatching to handler functions based on event type and tool name.
# NO async: security gates in PreToolUse must block to reject dangerous commands.
# PostToolUse handlers that don't need to block (audit, notify, capture)
# use internal daemon threads via _fire_and_forget().
HOOK_DEFINITIONS: Dict[str, List[Dict]] = {
    "PreToolUse": [
        {
            # Unified hook handles: bash-gate, spawn-guard, state-sanitize,
            # and state-sanitize.
            # NO async: security gates must block to reject dangerous commands.
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py",
                    "timeout": 15,
                },
            ],
        },
    ],
    "PostToolUse": [
        {
            # Unified hook handles: audit-log, canary-check, memory-inject,
            # notify-on-complete, memory-capture, and depth reminder.
            # NO async: canary-check and memory-inject are synchronous (inject
            # content into LLM context via stdout). Fire-and-forget handlers
            # (audit, notify, capture) use internal daemon threads.
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py",
                    "timeout": 15,
                },
            ],
        },
    ],
    "UserPromptSubmit": [
        {
            # Unified hook handles: autonomous-mode escape phrase (clears the
            # autonomous record), and the agent2agent per-turn notify floor.
            # NO async: the escape-phrase clear must complete before the Stop
            # hook fires at the end of this same turn.
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py",
                    "timeout": 10,
                },
            ],
        },
    ],
    "Stop": [
        {
            # Unified hook handles: autonomous-mode turn-end enforcement.
            # NO async: this hook returns a block/allow decision, so Claude Code
            # must wait for it. Timeout kept small -- the handler only reads
            # local state and the transcript.
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py",
                    "timeout": 5,
                },
            ],
        },
    ],
    "SessionStart": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": "$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python $SPELLBOOK_DIR/hooks/spellbook_hook.py",
                    "timeout": 10,
                },
            ],
        },
    ],
}

# All phases that contain spellbook hooks
_HOOK_PHASES = list(HOOK_DEFINITIONS.keys())

# Phases spellbook registered in an earlier version and no longer does.
# Dropping a phase from HOOK_DEFINITIONS is not enough on its own: _HOOK_PHASES
# derives from HOOK_DEFINITIONS, so neither the install merge pass nor the
# uninstall pass would ever look at the phase again, and the stale entry would
# sit in every existing operator's settings file forever -- spawning a
# subprocess on every occurrence of the event and reading, to anyone who opens
# the file, as a working mechanism.
#
# PreCompact: registered from the start, never handled. `dispatch()` has no
# PreCompact branch, so the event always fell through to the no-op default.
# The workflow-state save it advertised belonged to tooling that was removed.
_RETIRED_HOOK_PHASES = ("PreCompact",)

# Prefix used to identify spellbook-managed hook paths
_SPELLBOOK_HOOK_PREFIX = "$SPELLBOOK_DIR/hooks/"

def _get_hook_path_for_platform(hook_path: str) -> str:
    """Resolve hook path based on platform.

    On Windows:
    - .sh hooks become .ps1 hooks wrapped in PowerShell invocation
    - .py hooks use their .ps1 wrapper (which delegates to the .py script)
    - Commands with a venv python prefix (e.g. ``$SPELLBOOK_CONFIG_DIR/daemon-venv/bin/python
      $SPELLBOOK_DIR/hooks/spellbook_hook.py``) strip the prefix and use
      just the .ps1 wrapper, since the PS1 wrapper handles Python discovery itself.
    On Unix, returns the original path unchanged.
    """
    if sys.platform == "win32":
        # Handle venv-prefixed commands: extract the .py path and convert to .ps1
        # The PS1 wrapper handles Python invocation itself, so the venv prefix is dropped.
        if " " in hook_path and hook_path.endswith(".py"):
            # Split on last space to get the .py script path
            py_path = hook_path.rsplit(" ", 1)[-1]
            if py_path.endswith(".py"):
                ps1_path = py_path.replace(".py", ".ps1")
                return f"powershell -ExecutionPolicy Bypass -File {ps1_path}"
        if hook_path.endswith(".sh"):
            ps1_path = hook_path.replace(".sh", ".ps1")
            return f"powershell -ExecutionPolicy Bypass -File {ps1_path}"
        elif hook_path.endswith(".py"):
            # Use the .ps1 wrapper which delegates to the .py script
            ps1_path = hook_path.replace(".py", ".ps1")
            return f"powershell -ExecutionPolicy Bypass -File {ps1_path}"
    return hook_path


def _transform_hook_for_platform(
    hook: Union[str, Dict[str, Any]],
) -> Union[str, Dict[str, Any]]:
    """Transform a hook entry's path for the current platform."""
    if isinstance(hook, str):
        return _get_hook_path_for_platform(hook)
    transformed = dict(hook)
    if "command" in transformed:
        transformed["command"] = _get_hook_path_for_platform(
            transformed["command"]
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

    Handles plain string hooks, object-format hooks with a 'command' key,
    and PowerShell invocation wrappers (extracts path after '-File').
    """
    if isinstance(hook, str):
        path = hook
    else:
        path = hook.get("command", "")
    # Extract path from PowerShell invocation wrapper
    ps_prefix = "powershell -ExecutionPolicy Bypass -File "
    if path.startswith(ps_prefix):
        path = path[len(ps_prefix):]
    return path


def _is_spellbook_hook(hook: Union[str, Dict[str, Any]], spellbook_dir: Optional[Path] = None) -> bool:
    """Check if a hook is managed by spellbook.

    Detection order:
      1. Object hooks carrying the ``spellbook_managed: True`` marker are
         always recognized, regardless of the baked-in command path. This
         is the authoritative mechanism for current-generation entries.
      2. Legacy fallback: string hooks or object hooks whose command path
         contains ``$SPELLBOOK_DIR/hooks/`` (literal) or the expanded
         absolute ``<spellbook_dir>/hooks/`` prefix. On Windows, path
         separators are normalized before comparison so both forward and
         back slashes match.

    The managed-marker check is critical: when the installer runs from a
    different worktree, the baked-in path will differ from every known
    prefix. Without the marker, stale entries accumulate.
    """
    # Primary: explicit managed marker on object hooks.
    if isinstance(hook, dict) and hook.get("spellbook_managed") is True:
        return True

    path = _get_hook_path(hook)
    # Normalize to forward slashes for consistent comparison across platforms
    normalized_path = path.replace("\\", "/")
    # Check both starts-with (legacy bare path) and contains (venv python prefix)
    if _SPELLBOOK_HOOK_PREFIX in normalized_path:
        return True
    # Recognize the stable symlink prefix so re-install from any worktree
    # cleans up prior entries. This check does not depend on spellbook_dir.
    try:
        symlink_prefix = str(_source_link.get_source_link_path()).replace("\\", "/") + "/hooks/"
        if symlink_prefix in normalized_path:
            return True
    except Exception as exc:
        logger.debug(
            "source symlink prefix lookup failed during hook detection: %s",
            exc,
            exc_info=True,
        )
    if spellbook_dir is not None:
        # Normalize spellbook_dir to forward slashes as well
        expanded_prefix = str(spellbook_dir).replace("\\", "/") + "/hooks/"
        if expanded_prefix in normalized_path:
            return True
    return False


def _is_legacy_hook(hook: Union[str, Dict[str, Any]], spellbook_dir: Optional[Path] = None) -> bool:
    """Check if a hook is a legacy format that should be cleaned up.

    Detects:
    - Nim binary paths (contain /hooks/nim/bin/)
    - Old Python wrapper hooks (.py files in the spellbook hooks directory,
      EXCLUDING the unified spellbook_hook.py which is the current entrypoint)

    Does NOT match current .sh, .ps1, or the unified spellbook_hook.py hook.
    """
    path = _get_hook_path(hook)
    normalized = path.replace("\\", "/")

    # Never treat the unified hook as legacy
    if "spellbook_hook.py" in normalized or "spellbook_hook.ps1" in normalized:
        return False

    # Nim binary paths (either $SPELLBOOK_DIR or expanded)
    if "/hooks/nim/bin/" in normalized:
        return True

    # Old Python wrapper hooks with $SPELLBOOK_DIR prefix
    if normalized.startswith(_SPELLBOOK_HOOK_PREFIX) and normalized.endswith(".py"):
        return True

    # Old Python wrapper hooks with expanded absolute path
    if spellbook_dir is not None:
        expanded_prefix = str(spellbook_dir).replace("\\", "/") + "/hooks/"
        if normalized.startswith(expanded_prefix) and normalized.endswith(".py"):
            return True
        # Nim binary with expanded path
        expanded_nim = str(spellbook_dir).replace("\\", "/") + "/hooks/nim/bin/"
        if expanded_nim in normalized:
            return True

    return False


def _cleanup_legacy_hooks(settings: Dict, spellbook_dir: Optional[Path] = None) -> None:
    """Remove legacy Nim and .py hook entries from all phases in settings.

    Scans all hook phases for entries containing Nim binary paths or
    .py wrapper paths. Removes those entries, dropping empty matcher
    groups. This must run BEFORE new hook registration because old
    and new command strings differ and won't deduplicate.
    """
    hooks_section = settings.get("hooks", {})
    for phase in _HOOK_PHASES:
        phase_entries = hooks_section.get(phase, [])
        if not phase_entries:
            continue
        cleaned = []
        for entry in phase_entries:
            hooks_list = entry.get("hooks", [])
            remaining = [h for h in hooks_list if not _is_legacy_hook(h, spellbook_dir)]
            if remaining:
                new_entry: Dict[str, Any] = {"hooks": remaining}
                if "matcher" in entry:
                    new_entry["matcher"] = entry["matcher"]
                cleaned.append(new_entry)
        hooks_section[phase] = cleaned


def _expand_spellbook_dir(hook: Union[str, Dict[str, Any]], spellbook_dir: Path) -> Union[str, Dict[str, Any]]:
    """Replace $SPELLBOOK_DIR and $SPELLBOOK_CONFIG_DIR with actual paths.

    $SPELLBOOK_DIR expands to the STABLE SOURCE SYMLINK path
    (``$SPELLBOOK_CONFIG_DIR/source``), not ``spellbook_dir`` itself. The
    symlink is the indirection point: artifacts reference it, and
    re-installing from a different worktree just re-points the symlink
    instead of rewriting every artifact. ``spellbook_dir`` is retained in
    the signature for backward compatibility and for callers that need to
    detect legacy path-based entries during cleanup.

    On Windows, also replaces ``daemon-venv/bin/python`` with
    ``daemon-venv/Scripts/python.exe`` so the venv Python resolves correctly.
    """
    spellbook_str = str(_source_link.get_source_link_path())
    config_str = str(_config.get_spellbook_config_dir())
    # spellbook_dir is intentionally not used for substitution anymore; keep
    # the reference to satisfy static analysis.
    _ = spellbook_dir

    def _expand(s: str) -> str:
        result = s.replace("$SPELLBOOK_DIR", spellbook_str).replace(
            "$SPELLBOOK_CONFIG_DIR", config_str
        )
        if _platform.system() == "Windows":
            result = result.replace("daemon-venv/bin/python", "daemon-venv/Scripts/python.exe")
        return result

    if isinstance(hook, str):
        return _expand(hook)
    expanded = dict(hook)
    if "command" in expanded:
        expanded["command"] = _expand(expanded["command"])
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


def _tag_as_managed(
    hook: Union[str, Dict[str, Any]], phase: Optional[str]
) -> Dict[str, Any]:
    """Return a new hook dict tagged with the spellbook-managed markers.

    String hooks are promoted to object form. The tags let future installs
    identify and replace existing spellbook-written entries even when the
    baked-in command path no longer matches any known prefix (e.g. because
    the user ran the installer from a different worktree).
    """
    if isinstance(hook, str):
        obj: Dict[str, Any] = {"type": "command", "command": hook}
    else:
        obj = dict(hook)
    obj["spellbook_managed"] = True
    if phase is not None:
        obj["spellbook_hook_id"] = phase
    return obj


def _strip_managed_from_all_phases(
    phase_entries: List[Dict],
    spellbook_dir: Optional[Path] = None,
) -> None:
    """Remove every spellbook-managed hook from ``phase_entries`` in-place.

    Entries whose hooks list becomes empty are dropped. User-authored
    hooks (no ``spellbook_managed`` marker and no spellbook path prefix)
    are preserved. Entry-level fields (``timeout``, ``async``, etc.) on
    mixed entries (some spellbook, some user hooks) are retained.

    If ``spellbook_dir`` is provided, legacy path-based hook entries
    whose command contains the current worktree path are also removed.
    """
    cleaned_entries: List[Dict] = []
    for entry in phase_entries:
        filtered = [
            h for h in entry.get("hooks", [])
            if not _is_spellbook_hook(h, spellbook_dir)
        ]
        if filtered:
            cleaned = dict(entry)
            cleaned["hooks"] = filtered
            cleaned_entries.append(cleaned)
    phase_entries.clear()
    phase_entries.extend(cleaned_entries)


def _phase_for_hook_defs(hook_defs: List[Dict]) -> Optional[str]:
    """Recover the phase id (PreToolUse, PostToolUse, ...) for a hook_defs list."""
    for phase, defs in HOOK_DEFINITIONS.items():
        if defs is hook_defs:
            return phase
    return None


def _merge_hooks_for_phase(
    phase_entries: List[Dict],
    hook_defs: List[Dict],
    spellbook_dir: Optional[Path] = None,
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
    # Strip every existing spellbook-managed hook from this phase before
    # merging in fresh ones. This is the critical dedup: stale entries
    # baked with a prior worktree's absolute path are identified via the
    # ``spellbook_managed`` marker and removed regardless of path.
    _strip_managed_from_all_phases(phase_entries, spellbook_dir)

    phase_id = _phase_for_hook_defs(hook_defs)

    for hook_def in hook_defs:
        matcher = _matcher_key(hook_def)
        is_catchall = matcher is None

        # Transform hook paths for the current platform (.sh -> .ps1 on Windows)
        spellbook_hooks = [
            _transform_hook_for_platform(h) for h in hook_def["hooks"]
        ]
        # Expand $SPELLBOOK_DIR to actual path if provided
        if spellbook_dir is not None:
            spellbook_hooks = [_expand_spellbook_dir(h, spellbook_dir) for h in spellbook_hooks]

        # Tag every outgoing spellbook hook with the managed markers.
        spellbook_hooks = [_tag_as_managed(h, phase_id) for h in spellbook_hooks]

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


def _remove_retired_phases(settings: Dict, spellbook_dir: Optional[Path] = None) -> List[str]:
    """Strip spellbook hooks from phases spellbook no longer registers.

    Removes ONLY hooks that _is_spellbook_hook recognizes. An operator's own
    unrelated hook in a retired phase is preserved, and the phase key is
    deleted only when nothing is left in it.

    Returns the phases that were modified, so a caller can report a migration
    that actually did something rather than one that merely ran.
    """
    hooks_section = settings.get("hooks")
    if not isinstance(hooks_section, dict):
        return []

    modified: List[str] = []
    for phase in _RETIRED_HOOK_PHASES:
        entries = hooks_section.get(phase)
        if not isinstance(entries, list):
            continue
        cleaned = _clean_hooks_for_phase(entries, spellbook_dir)
        if cleaned == entries:
            continue
        modified.append(phase)
        if cleaned:
            hooks_section[phase] = cleaned
        else:
            del hooks_section[phase]
    return modified


# Claude Code stops honoring a Stop hook's block decision after
# CLAUDE_CODE_STOP_HOOK_BLOCK_CAP consecutive blocks (default 8) and ends the
# turn regardless. Spellbook's Stop hook is designed to block repeatedly and
# bounds itself with a rolling-window valve
# (spellbook.core.autonomous.thrash_valve_open), so the harness cap would only
# cut enforcement short at an arbitrary count. The documented way to lift it is
# verbatim: "Set to `0` to disable the cap." It is an ordinary settings key and
# follows the same precedence rules as any other.
STOP_HOOK_BLOCK_CAP_KEY = "CLAUDE_CODE_STOP_HOOK_BLOCK_CAP"
STOP_HOOK_BLOCK_CAP_VALUE = "0"


def _install_managed_env(settings: Dict) -> None:
    """Write the spellbook-owned entries into the settings ``env`` block.

    Other ``env`` entries are left untouched, and an existing ``env`` that is
    not an object is replaced rather than crashed on -- the same tolerance
    the hook phases get.
    """
    env = settings.get("env")
    if not isinstance(env, dict):
        env = {}
    env[STOP_HOOK_BLOCK_CAP_KEY] = STOP_HOOK_BLOCK_CAP_VALUE
    settings["env"] = env


def _remove_managed_env(settings: Dict) -> bool:
    """Remove the spellbook-owned ``env`` entries. Returns whether anything changed.

    Only a value spellbook itself wrote is removed. An operator who set the
    cap to their own value owns that key now, exactly as
    ``_clean_hooks_for_phase`` leaves a foreign hook alone; uninstall must not
    silently revert a deliberate setting. The ``env`` object is dropped when
    removing our key empties it, so uninstall leaves no residue.
    """
    env = settings.get("env")
    if not isinstance(env, dict):
        return False
    if env.get(STOP_HOOK_BLOCK_CAP_KEY) != STOP_HOOK_BLOCK_CAP_VALUE:
        return False
    del env[STOP_HOOK_BLOCK_CAP_KEY]
    if env:
        settings["env"] = env
    else:
        del settings["env"]
    return True


def install_hooks(
    settings_path: Path,
    spellbook_dir: Optional[Path] = None,
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

    # On Windows, verify PowerShell is available before registering hooks.
    # Without PowerShell, .ps1 hooks cannot execute.
    if sys.platform == "win32":
        import shutil
        if not shutil.which("powershell"):
            return HookResult(
                component="hooks",
                success=True,
                action="skipped",
                message="PowerShell not found on PATH; hook registration skipped",
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

    # Clean up legacy Nim and .py hook entries before registering new ones
    _cleanup_legacy_hooks(settings, spellbook_dir)

    # Sweep phases spellbook used to register. _HOOK_PHASES no longer lists
    # them, so nothing else in this module would ever touch them again.
    retired = _remove_retired_phases(settings, spellbook_dir)
    if retired:
        logger.info("Removed retired spellbook hook phases: %s", ", ".join(retired))

    # Clean up old per-tool spellbook hooks (e.g. bash-gate.sh with "Bash" matcher)
    # that are now superseded by the unified catch-all hook.
    # _cleanup_legacy_hooks only handles Nim/.py; this handles old .sh hooks too.
    for phase in HOOK_DEFINITIONS:
        if phase in settings["hooks"]:
            settings["hooks"][phase] = _clean_hooks_for_phase(
                settings["hooks"][phase], spellbook_dir
            )

    # Merge hooks for each phase
    for phase, hook_defs in HOOK_DEFINITIONS.items():
        if phase not in settings["hooks"]:
            settings["hooks"][phase] = []
        _merge_hooks_for_phase(
            settings["hooks"][phase], hook_defs, spellbook_dir
        )

    # The Stop hook and the disabled harness block cap are one change: with the
    # cap at its default the hook's own valve would rarely be what ends a block
    # loop, and the cap alone would cut enforcement short at an arbitrary count.
    _install_managed_env(settings)

    # Write back atomically (Windows transient-error retry on os.replace).
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(str(settings_path), settings)

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

    # Evaluated BEFORE the "nothing to remove" early return below, which only
    # counts hooks. A settings file holding the env entry and no hooks still
    # has spellbook state in it, and returning "unchanged" would strand it.
    env_removed = _remove_managed_env(settings)

    hooks_section = settings.get("hooks", {})

    # Check if there are any spellbook hooks to remove across all phases,
    # including phases spellbook no longer registers.
    has_spellbook_hooks = False
    for phase in (*_HOOK_PHASES, *_RETIRED_HOOK_PHASES):
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
        if env_removed:
            atomic_write_json(str(settings_path), settings)
            return HookResult(
                component="hooks",
                success=True,
                action="removed",
                message=f"hooks: spellbook env settings removed from {settings_path.name}",
            )
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
    _remove_retired_phases(settings, spellbook_dir)

    # Write back atomically (Windows transient-error retry on os.replace).
    atomic_write_json(str(settings_path), settings)

    return HookResult(
        component="hooks",
        success=True,
        action="removed",
        message=f"hooks: spellbook security hooks removed from {settings_path.name}",
    )
