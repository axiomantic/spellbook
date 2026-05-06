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

    # Snapshot the pre-modification bucket contents BEFORE we mutate anything.
    # Used after the write to distinguish entries spellbook actually added
    # (absent before, present after) from entries the user had already added
    # by hand and that happened to overlap our desired set. Recording the
    # latter as "managed" would silently transfer ownership and let a future
    # uninstall delete the user's entry. See GEM-M3 / design §14.
    pre_existing: Dict[str, set] = {
        bucket: set(perms_section.get(bucket, []))
        for bucket in ("allow", "deny", "ask")
    }

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

    # Record only the entries we ACTUALLY OWN, NOT the originally-desired
    # set. An entry is ours iff it ended up in the final bucket AND either:
    #   (a) we added it now (it was NOT in the bucket before this install), OR
    #   (b) we already managed it in the prior state (still ours from a
    #       previous install).
    # Entries the user had added by hand (in `pre_existing` but not in
    # `prior_managed`) are NEVER recorded as managed even when they overlap
    # the desired set -- otherwise a future uninstall would delete the
    # user's entry. See GEM-M3 / design §14.
    def _own(bucket: str, desired: List[str]) -> List[str]:
        prior_managed_set = set(prior_managed.get(bucket, []))
        pre_set = pre_existing[bucket]
        result: List[str] = []
        for entry in desired:
            if entry not in bucket_state[bucket]:
                # Skipped (e.g. cross-bucket conflict); not in final bucket.
                continue
            we_added_it = entry not in pre_set
            we_already_managed_it = entry in prior_managed_set
            if we_added_it or we_already_managed_it:
                result.append(entry)
        return result

    managed_allow = _own("allow", desired_allow)
    managed_deny = _own("deny", desired_deny)
    managed_ask = _own("ask", desired_ask)

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


def uninstall_permissions(
    settings_path: Path,
    spellbook_dir: Path,
    dry_run: bool,
) -> HookResult:
    """Remove spellbook-managed permission entries from a settings file.

    Reads the per-config-dir state file to find the entries spellbook owns,
    removes ONLY those entries from ``settings.json`` (preserving user-added
    entries), and clears the managed sets in the state file.

    Args:
        settings_path: Path to the Claude Code settings file.
        spellbook_dir: Reserved for future use (parity with ``install_hooks``).
        dry_run: If True, no files are written; returns success without I/O.

    Returns:
        ``HookResult`` with ``component="permissions"``.
    """
    if dry_run:
        return HookResult(
            component="permissions",
            success=True,
            action="removed",
            message=(
                f"permissions: would uninstall managed entries from "
                f"{settings_path.name} (dry run)"
            ),
        )

    config_dir = settings_path.parent

    try:
        prior_managed = _mps.reconcile(config_dir)
    except (ValueError, OSError) as e:
        return HookResult(
            component="permissions",
            success=False,
            action="failed",
            message=f"permissions: failed to read state file: {e}",
        )

    has_managed = any(prior_managed.get(b) for b in ("allow", "deny", "ask"))

    if not settings_path.exists():
        # No settings file but state may carry stale entries; clear state.
        if has_managed:
            try:
                _mps.update_managed_set(
                    config_dir=config_dir, allow=[], deny=[], ask=[]
                )
            except (ValueError, OSError) as e:
                logger.warning(
                    "permissions: failed to clear state file: %s", e
                )
        return HookResult(
            component="permissions",
            success=True,
            action="unchanged",
            message=(
                f"permissions: {settings_path.name} not present; "
                f"cleared managed state"
            ),
        )

    if not has_managed:
        return HookResult(
            component="permissions",
            success=True,
            action="unchanged",
            message="permissions: no managed entries recorded; nothing to uninstall",
        )

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

    perms_section: Dict[str, List[str]] = dict(existing_settings.get("permissions", {}))
    removed_total = 0
    new_perms: Dict[str, List[str]] = {}
    for bucket in ("allow", "deny", "ask"):
        current_list = list(perms_section.get(bucket, []))
        managed_set = set(prior_managed.get(bucket, []))
        kept = [e for e in current_list if e not in managed_set]
        removed_total += len(current_list) - len(kept)
        new_perms[bucket] = kept

    new_settings = dict(existing_settings)

    # If the resulting permissions section is fully empty AND the original
    # settings did NOT have a permissions key (we created it during install
    # with empty/managed lists), remove the key entirely so uninstall is a
    # true revert. Otherwise keep the (now-trimmed) section.
    all_empty = all(len(new_perms[b]) == 0 for b in ("allow", "deny", "ask"))
    if all_empty:
        new_settings.pop("permissions", None)
    else:
        new_settings["permissions"] = new_perms

    try:
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
            config_dir=config_dir, allow=[], deny=[], ask=[]
        )
    except (ValueError, OSError) as e:
        logger.warning(
            "permissions: settings.json updated but state-file clear failed: %s", e
        )

    return HookResult(
        component="permissions",
        success=True,
        action="removed",
        message=(
            f"permissions: removed {removed_total} managed entr"
            f"{'y' if removed_total == 1 else 'ies'} from {settings_path.name}"
        ),
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
