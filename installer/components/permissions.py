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

    # Pass 1: remove entries we previously managed but no longer want. We only
    # remove entries that match the prior managed set; entries the user added
    # (not in prior_managed) are preserved even if they happen to match a
    # desired entry's text.
    bucket_state: Dict[str, List[str]] = {}
    for bucket, desired in (
        ("allow", desired_allow),
        ("deny", desired_deny),
        ("ask", desired_ask),
    ):
        current_list: List[str] = list(perms_section.get(bucket, []))
        prior_set = set(prior_managed.get(bucket, []))
        desired_set = set(desired)
        to_remove = prior_set - desired_set
        bucket_state[bucket] = [e for e in current_list if e not in to_remove]

    # Pass 2: add desired-but-missing entries, with §14 conflict warn-and-skip.
    # If a desired entry already exists in a DIFFERENT bucket as a user-added
    # (non-managed) entry, we warn and refuse to add the spellbook copy --
    # leaving the same string in two buckets would give Claude Code an
    # undefined-precedence settings file.
    skipped_conflicts: List[str] = []
    for bucket, desired in (
        ("allow", desired_allow),
        ("deny", desired_deny),
        ("ask", desired_ask),
    ):
        existing_after_remove = set(bucket_state[bucket])
        for entry in desired:
            if entry in existing_after_remove:
                continue

            # Look for a conflicting non-managed entry in the OTHER buckets.
            conflict_bucket = _find_conflict_bucket(
                entry, bucket, bucket_state, prior_managed
            )
            if conflict_bucket is not None:
                logger.warning(
                    "permissions: %r exists in %r as a user-added entry; "
                    "skipping spellbook addition to %r to avoid cross-bucket "
                    "conflict (per design §14)",
                    entry,
                    conflict_bucket,
                    bucket,
                )
                skipped_conflicts.append(
                    f"{entry!r} ({conflict_bucket} -> {bucket})"
                )
                continue

            bucket_state[bucket].append(entry)
            existing_after_remove.add(entry)

    for bucket in ("allow", "deny", "ask"):
        perms_section[bucket] = bucket_state[bucket]

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

    # Record only the entries we actually wrote, NOT the originally-desired
    # set. If we skipped some due to cross-bucket conflicts (§14), they are
    # not under our management; the user owns them in the other bucket.
    managed_allow = [e for e in desired_allow if e in bucket_state["allow"]]
    managed_deny = [e for e in desired_deny if e in bucket_state["deny"]]
    managed_ask = [e for e in desired_ask if e in bucket_state["ask"]]

    try:
        _mps.update_managed_set(
            config_dir=config_dir,
            allow=managed_allow,
            deny=managed_deny,
            ask=managed_ask,
        )
    except (ValueError, OSError) as e:
        logger.warning(
            "permissions: settings.json updated but state-file write failed: %s",
            e,
        )

    if skipped_conflicts:
        message = (
            f"permissions: managed entries reconciled in {settings_path.name}; "
            f"skipped {len(skipped_conflicts)} cross-bucket conflict(s): "
            f"{', '.join(skipped_conflicts)}"
        )
    else:
        message = f"permissions: managed entries reconciled in {settings_path.name}"

    return HookResult(
        component="permissions",
        success=True,
        action="installed",
        message=message,
    )


def _find_conflict_bucket(
    entry: str,
    target_bucket: str,
    bucket_state: Dict[str, List[str]],
    prior_managed: Dict[str, List[str]],
) -> Optional[str]:
    """Return the name of an OTHER bucket that already holds ``entry`` as a
    user-added (non-spellbook-managed) value, or None if no conflict.

    A conflict exists when the same permission string sits in a different
    bucket *and* spellbook does not own it there (i.e. it was not in the
    prior-managed snapshot for that bucket). User-added entries that happen
    to overlap a desired managed value MUST NOT be silently displaced or
    duplicated; per design §14 the spellbook addition is skipped with a
    warning.
    """
    for other_bucket in ("allow", "deny", "ask"):
        if other_bucket == target_bucket:
            continue
        if entry not in bucket_state.get(other_bucket, []):
            continue
        if entry in prior_managed.get(other_bucket, []):
            # We previously managed this in the other bucket; it will be
            # removed there in a future reconcile (or already was, in pass 1).
            # Either way, it's our entry, not the user's -- not a conflict.
            continue
        return other_bucket
    return None


def _read_settings(settings_path: Path) -> dict:
    """Read settings.json; return {} when file is absent or empty."""
    if not settings_path.exists():
        return {}
    text = settings_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    return json.loads(text)
