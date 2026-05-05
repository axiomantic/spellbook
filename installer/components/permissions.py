"""Install / manage spellbook-tracked entries in Claude Code's
``permissions.allow`` / ``permissions.deny`` / ``permissions.ask`` arrays.

WI-0 deliverable. Behaviour:

  1. Read the current ``settings.json`` (or treat as empty when missing).
  2. Read the per-config-dir managed set from the state file.
  3. Compute the desired managed set from arguments.
  4. Add desired-but-not-current entries to ``settings.json`` (preserving
     user-added entries).
  5. Remove entries that we used to manage but are no longer in the desired
     set (only if the entry is also still in ``settings.json``; user-added
     entries that happen to overlap are not affected because the state file
     is the authority on what we own).
  6. Atomically write ``settings.json`` via ``atomic_write_json``.
  7. Update the state file AFTER the settings.json write succeeds, so a
     crash mid-flight leaves the on-disk state file consistent with the
     last successfully-written ``settings.json``.

The function returns a ``HookResult`` mirroring ``install_hooks``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from spellbook.core.command_utils import atomic_write_json

from . import managed_permissions_state as _mps
from .hooks import HookResult

logger = logging.getLogger(__name__)


def install_permissions(
    settings_path: Path,
    spellbook_dir: Path,
    dry_run: bool,
    allow: Optional[List[str]] = None,
    deny: Optional[List[str]] = None,
    ask: Optional[List[str]] = None,
) -> HookResult:
    """Install / reconcile spellbook-managed permission entries.

    Args:
        settings_path: Path to the Claude Code settings file.
        spellbook_dir: Reserved for future use (parity with ``install_hooks``).
        dry_run: If True, no files are written.
        allow: Desired managed ``allow`` patterns. ``None`` -> empty list
            (mutable-default-safe).
        deny: Desired managed ``deny`` patterns.
        ask: Desired managed ``ask`` patterns.

    Returns:
        ``HookResult`` with ``component="permissions"``.
    """
    if dry_run:
        return HookResult(
            component="permissions",
            success=True,
            action="installed",
            message="permissions: would be installed (dry run)",
        )

    desired_allow = list(allow or [])
    desired_deny = list(deny or [])
    desired_ask = list(ask or [])

    config_dir = settings_path.parent

    try:
        existing_settings = _read_settings(settings_path)
    except json.JSONDecodeError as e:
        return HookResult(
            component="permissions",
            success=False,
            action="failed",
            message=(
                f"permissions: failed to parse {settings_path.name} - "
                f"JSON decode error: {e}"
            ),
        )
    except OSError as e:
        return HookResult(
            component="permissions",
            success=False,
            action="failed",
            message=f"permissions: failed to read {settings_path.name}: {e}",
        )

    try:
        prior_managed = _mps.reconcile(config_dir)
    except (ValueError, OSError) as e:
        return HookResult(
            component="permissions",
            success=False,
            action="failed",
            message=f"permissions: failed to read state file: {e}",
        )

    perms_section: Dict[str, List[str]] = dict(existing_settings.get("permissions", {}))
    for bucket, desired in (
        ("allow", desired_allow),
        ("deny", desired_deny),
        ("ask", desired_ask),
    ):
        current_list: List[str] = list(perms_section.get(bucket, []))
        prior_set = set(prior_managed.get(bucket, []))
        desired_set = set(desired)

        # Remove entries we previously managed but no longer want. We only
        # remove entries that match the prior managed set; entries the user
        # added (not in prior_managed) are preserved even if they happen to
        # match a desired entry's text.
        to_remove = prior_set - desired_set
        new_list = [e for e in current_list if e not in to_remove]

        # Add desired entries that are missing.
        existing_after_remove = set(new_list)
        for entry in desired:
            if entry not in existing_after_remove:
                new_list.append(entry)
                existing_after_remove.add(entry)

        perms_section[bucket] = new_list

    new_settings = dict(existing_settings)
    new_settings["permissions"] = perms_section

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(str(settings_path), new_settings)
    except (ValueError, OSError) as e:
        return HookResult(
            component="permissions",
            success=False,
            action="failed",
            message=f"permissions: write to {settings_path.name} failed: {e}",
        )

    try:
        _mps.update_managed_set(
            config_dir=config_dir,
            allow=desired_allow,
            deny=desired_deny,
            ask=desired_ask,
        )
    except (ValueError, OSError) as e:
        logger.warning(
            "permissions: settings.json updated but state-file write failed: %s",
            e,
        )

    return HookResult(
        component="permissions",
        success=True,
        action="installed",
        message=f"permissions: managed entries reconciled in {settings_path.name}",
    )


def _read_settings(settings_path: Path) -> dict:
    """Read settings.json; return {} when file is absent or empty."""
    if not settings_path.exists():
        return {}
    text = settings_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    return json.loads(text)
