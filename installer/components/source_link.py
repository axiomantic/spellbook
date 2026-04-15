"""Stable-source symlink management for the spellbook installer.

Maintains a stable symlink at ``$SPELLBOOK_CONFIG_DIR/source`` that points
at the active spellbook source tree. All installed artifacts (hook
commands in settings.json, launchd plist working directories and
environment variables, daemon venv editable install, etc.) reference this
symlink path instead of the underlying worktree directory.

Re-installing from a different worktree just re-points the symlink; the
artifacts themselves never need to be rewritten to track a new path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from installer import config as _config
from installer.compat import create_link


SourceLinkAction = Literal[
    "created",
    "updated",
    "backed_up_and_linked",
    "unchanged",
    "failed",
]


class InstallError(RuntimeError):
    """Raised when an installer pre-check cannot be resolved automatically."""


@dataclass(frozen=True)
class SourceLinkResult:
    """Result of an :func:`ensure_source_link` operation."""

    link_path: Path
    target: Path
    action: SourceLinkAction
    backup_path: Optional[Path]
    message: str


def get_source_link_path() -> Path:
    """Return the absolute path of the stable source symlink."""
    return _config.get_spellbook_config_dir() / "source"


def _backup_timestamp() -> str:
    """Return the current UTC timestamp formatted for backup directory names."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def ensure_source_link(
    source_dir: Path,
    *,
    yes: bool = False,
    dry_run: bool = False,
) -> SourceLinkResult:
    """Create or update the stable source symlink.

    Behavior:
      * If the link already exists and points at ``source_dir`` (resolved):
        no-op, returns ``action="unchanged"``.
      * If the link exists but points elsewhere: unlink and recreate,
        returns ``action="updated"``.
      * If the link path exists as a real directory or file (not a symlink):
        when ``yes=True`` the existing path is renamed to
        ``<link_path.parent>/source.backup-<YYYYMMDD-HHMMSS>`` and the
        symlink is created, returning ``action="backed_up_and_linked"``.
        When ``yes=False`` an :class:`InstallError` is raised instructing
        the user to remove it manually or re-run with ``--yes``.
      * Otherwise (link path absent): create the symlink,
        returns ``action="created"``.

    ``dry_run=True`` reports what would happen without touching the
    filesystem.
    """
    link_path = get_source_link_path()
    target = source_dir.resolve()

    # Already a symlink?
    if link_path.is_symlink():
        current_target = Path(os.readlink(link_path))
        if not current_target.is_absolute():
            current_target = (link_path.parent / current_target).resolve()
        else:
            current_target = current_target.resolve()

        if current_target == target:
            return SourceLinkResult(
                link_path=link_path,
                target=target,
                action="unchanged",
                backup_path=None,
                message=f"Symlink already correct: {link_path} -> {target}",
            )

        if dry_run:
            return SourceLinkResult(
                link_path=link_path,
                target=target,
                action="updated",
                backup_path=None,
                message=(
                    f"[dry-run] Would update symlink: {link_path} -> {target}"
                ),
            )
        link_path.unlink()
        _create_symlink(target, link_path)
        return SourceLinkResult(
            link_path=link_path,
            target=target,
            action="updated",
            backup_path=None,
            message=f"Updated symlink: {link_path} -> {target}",
        )

    # Exists as real file/dir?
    if link_path.exists():
        if not yes:
            raise InstallError(
                f"{link_path} exists and is not a symlink. Remove it "
                f"manually or re-run with --yes to back it up "
                f"automatically."
            )
        backup_path = link_path.parent / f"source.backup-{_backup_timestamp()}"
        if dry_run:
            return SourceLinkResult(
                link_path=link_path,
                target=target,
                action="backed_up_and_linked",
                backup_path=backup_path,
                message=(
                    f"[dry-run] Would back up {link_path} to {backup_path} "
                    f"and create symlink: {link_path} -> {target}"
                ),
            )
        link_path.rename(backup_path)
        _create_symlink(target, link_path)
        return SourceLinkResult(
            link_path=link_path,
            target=target,
            action="backed_up_and_linked",
            backup_path=backup_path,
            message=(
                f"Backed up existing directory to {backup_path} and "
                f"created symlink: {link_path} -> {target}"
            ),
        )

    # Absent
    if dry_run:
        return SourceLinkResult(
            link_path=link_path,
            target=target,
            action="created",
            backup_path=None,
            message=f"[dry-run] Would create symlink: {link_path} -> {target}",
        )
    _create_symlink(target, link_path)
    return SourceLinkResult(
        link_path=link_path,
        target=target,
        action="created",
        backup_path=None,
        message=f"Created symlink: {link_path} -> {target}",
    )


def _create_symlink(target: Path, link_path: Path) -> None:
    """Create ``link_path`` -> ``target`` using the cross-platform helper.

    ``installer.compat.create_link`` handles Windows junction fallback when
    real symlinks are unavailable.
    """
    link_path.parent.mkdir(parents=True, exist_ok=True)
    result = create_link(source=target, target=link_path)
    if not result.success:
        raise InstallError(
            f"Failed to create source symlink {link_path} -> {target}: "
            f"{result.message}"
        )
