"""
Symlink management for spellbook installation.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from installer.compat import (
    create_link,
    is_junction,
    normalize_path_for_comparison,
    remove_link,
    get_config_dir,
)


@dataclass
class SymlinkResult:
    """Result of a symlink operation."""

    source: Path
    target: Path
    success: bool
    action: str  # "created", "updated", "removed", "skipped", "failed"
    message: str


def create_symlink(
    source: Path, target: Path, dry_run: bool = False, remove_empty_dirs: bool = True
) -> SymlinkResult:
    """
    Create a symlink from target to source.

    Delegates to create_link() from compat module, which handles
    cross-platform link creation (symlink -> junction -> copy fallback on Windows).

    Args:
        source: The actual file/directory to link to
        target: Where the symlink will be created
        dry_run: If True, don't actually create the symlink
        remove_empty_dirs: If True, remove empty directories blocking symlink creation

    Returns SymlinkResult with status.
    """
    result = create_link(source, target, dry_run=dry_run, remove_empty_dirs=remove_empty_dirs)
    return SymlinkResult(
        source=result.source,
        target=result.target,
        success=result.success,
        action=result.action,
        message=result.message,
    )


def remove_symlink(
    target: Path, verify_source: Optional[Path] = None, dry_run: bool = False
) -> SymlinkResult:
    """
    Remove a symlink, optionally verifying it points to expected source.

    Args:
        target: The symlink to remove
        verify_source: If provided, only remove if symlink points here
        dry_run: If True, don't actually remove

    Returns SymlinkResult with status.
    """
    if not target.exists() and not target.is_symlink() and not is_junction(target):
        return SymlinkResult(
            source=verify_source or Path("."),
            target=target,
            success=True,
            action="skipped",
            message=f"Symlink does not exist: {target.name}",
        )

    if not target.is_symlink() and not is_junction(target):
        return SymlinkResult(
            source=verify_source or Path("."),
            target=target,
            success=False,
            action="failed",
            message=f"Not a symlink: {target}",
        )

    actual_source = target.resolve()

    if verify_source:
        # Check if symlink points to expected location
        expected = verify_source.resolve()
        actual_norm = normalize_path_for_comparison(actual_source)
        expected_norm = normalize_path_for_comparison(expected)
        if not actual_norm.startswith(expected_norm):
            return SymlinkResult(
                source=actual_source,
                target=target,
                success=True,
                action="skipped",
                message=f"Symlink points elsewhere: {target.name}",
            )

    if dry_run:
        return SymlinkResult(
            source=actual_source,
            target=target,
            success=True,
            action="removed",
            message=f"Would remove symlink: {target.name}",
        )

    try:
        removed = remove_link(target)
        if removed:
            return SymlinkResult(
                source=actual_source,
                target=target,
                success=True,
                action="removed",
                message=f"Removed symlink: {target.name}",
            )
        return SymlinkResult(
            source=actual_source,
            target=target,
            success=False,
            action="failed",
            message=f"Failed to remove symlink: {target.name}",
        )
    except OSError as e:
        return SymlinkResult(
            source=actual_source,
            target=target,
            success=False,
            action="failed",
            message=f"Failed to remove symlink: {e}",
        )


def _get_link_manifest_path() -> Path:
    """Get the path to the link manifest file."""
    return get_config_dir("spellbook") / "link_manifest.json"


def _update_link_manifest(source: Path, target: Path, link_mode: str) -> None:
    """Track copy-mode links for re-copy during updates.

    Records entries where link_mode == "copy" so that --update-only runs
    can re-copy stale entries. Entries using symlink or junction mode are
    removed from the manifest since they don't need re-copying.

    Args:
        source: The actual file/directory that was linked to.
        target: Where the link was created.
        link_mode: The link mode used ("symlink", "junction", or "copy").
    """
    manifest_path = _get_link_manifest_path()
    manifest: dict = {"links": []}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = {"links": []}

    # Deduplicate: remove existing entry for this target
    manifest["links"] = [
        e for e in manifest["links"] if e.get("target") != str(target)
    ]

    # Only record copy-mode links (symlinks/junctions auto-update)
    if link_mode == "copy":
        manifest["links"].append({
            "source": str(source),
            "target": str(target),
            "link_mode": link_mode,
        })

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def create_skill_symlinks(
    skills_source: Path,
    skills_target: Path,
    as_directories: bool = True,
    dry_run: bool = False,
) -> List[SymlinkResult]:
    """
    Create symlinks for all skills.

    On Windows where symlinks may fall back to copy mode, entries are
    tracked in a link manifest so that --update-only runs can re-copy
    stale content.

    Args:
        skills_source: Source skills directory (e.g., spellbook/skills)
        skills_target: Target skills directory (e.g., ~/.claude/skills)
        as_directories: If True, symlink skill directories; if False, symlink SKILL.md files
        dry_run: If True, don't actually create symlinks

    Returns list of SymlinkResult.
    """
    results = []

    if not skills_source.exists():
        return results

    for skill_dir in skills_source.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_name = skill_dir.name

        if as_directories:
            source = skill_dir
            target = skills_target / skill_name
        else:
            # Flat .md file format (for OpenCode)
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                source = skill_file
                target = skills_target / f"{skill_name}.md"
            else:
                continue

        link_result = create_link(source, target, dry_run=dry_run)
        result = SymlinkResult(
            source=link_result.source,
            target=link_result.target,
            success=link_result.success,
            action=link_result.action,
            message=link_result.message,
        )
        results.append(result)

        # Track copy-mode links in manifest for re-copy during updates
        if not dry_run and link_result.success:
            _update_link_manifest(source, target, link_result.link_mode)

    return results


def create_command_symlinks(
    commands_source: Path, commands_target: Path, dry_run: bool = False
) -> List[SymlinkResult]:
    """
    Create symlinks for all commands.

    Handles both:
    - Simple commands: .md files in commands root (e.g., commands/verify.md)
    - Complex commands: subdirectories with supporting files (e.g., commands/systematic-debugging/)

    On Windows where symlinks may fall back to copy mode, entries are
    tracked in a link manifest so that --update-only runs can re-copy
    stale content.

    Args:
        commands_source: Source commands directory
        commands_target: Target commands directory
        dry_run: If True, don't actually create symlinks

    Returns list of SymlinkResult.
    """
    results = []

    if not commands_source.exists():
        return results

    # Install simple command files (.md files in commands root)
    for cmd_file in commands_source.glob("*.md"):
        target = commands_target / cmd_file.name
        link_result = create_link(cmd_file, target, dry_run=dry_run)
        result = SymlinkResult(
            source=link_result.source,
            target=link_result.target,
            success=link_result.success,
            action=link_result.action,
            message=link_result.message,
        )
        results.append(result)
        if not dry_run and link_result.success:
            _update_link_manifest(cmd_file, target, link_result.link_mode)

    # Install command directories (subdirectories in commands/)
    for cmd_dir in commands_source.iterdir():
        if cmd_dir.is_dir():
            target = commands_target / cmd_dir.name
            link_result = create_link(cmd_dir, target, dry_run=dry_run)
            result = SymlinkResult(
                source=link_result.source,
                target=link_result.target,
                success=link_result.success,
                action=link_result.action,
                message=link_result.message,
            )
            results.append(result)
            if not dry_run and link_result.success:
                _update_link_manifest(cmd_dir, target, link_result.link_mode)

    return results


def remove_spellbook_symlinks(
    target_dir: Path, spellbook_dir: Path, dry_run: bool = False
) -> List[SymlinkResult]:
    """
    Remove all symlinks in target_dir that point to spellbook_dir.

    Args:
        target_dir: Directory containing symlinks to check
        spellbook_dir: Only remove symlinks pointing to this directory
        dry_run: If True, don't actually remove

    Returns list of SymlinkResult.
    """
    results = []

    if not target_dir.exists():
        return results

    for item in target_dir.iterdir():
        if item.is_symlink() or is_junction(item):
            result = remove_symlink(item, verify_source=spellbook_dir, dry_run=dry_run)
            if result.action != "skipped":
                results.append(result)

    return results


def cleanup_spellbook_symlinks(
    target_dir: Path, dry_run: bool = False
) -> List[SymlinkResult]:
    """
    Remove symlinks that were created by spellbook (point to spellbook or are broken).

    Use this before reinstalling to clean up orphaned symlinks from
    renamed or removed skills/commands. This handles:
    - Symlinks pointing to any path containing "spellbook"
    - Broken symlinks (targets no longer exist)

    User-created symlinks pointing to non-spellbook locations are preserved.

    Args:
        target_dir: Directory to clean up (e.g., ~/.claude/skills)
        dry_run: If True, don't actually remove

    Returns list of SymlinkResult for removed symlinks.
    """
    results = []

    if not target_dir.exists():
        return results

    for item in target_dir.iterdir():
        if not item.is_symlink() and not is_junction(item):
            continue

        # Check if symlink target exists
        try:
            target_path = item.resolve(strict=True)
            target_exists = True
        except (OSError, FileNotFoundError):
            target_exists = False
            target_path = None

        # Get the raw link target for logging
        try:
            raw_target = Path(item.readlink())
        except OSError:
            raw_target = Path("(unreadable)")

        # Decide whether to remove this symlink
        should_remove = False
        reason = ""

        if not target_exists:
            # Broken symlink - always remove
            should_remove = True
            reason = "broken"
        else:
            # Check if it points to a spellbook directory
            target_str = str(target_path).lower()
            if "spellbook" in target_str:
                should_remove = True
                reason = "spellbook"

        if not should_remove:
            # Skip user symlinks
            continue

        if dry_run:
            results.append(SymlinkResult(
                source=raw_target,
                target=item,
                success=True,
                action="removed",
                message=f"Would remove {reason} symlink: {item.name}",
            ))
        else:
            removed = remove_link(item)
            if removed:
                results.append(SymlinkResult(
                    source=raw_target,
                    target=item,
                    success=True,
                    action="removed",
                    message=f"Removed {reason} symlink: {item.name}",
                ))
            else:
                results.append(SymlinkResult(
                    source=raw_target,
                    target=item,
                    success=False,
                    action="failed",
                    message=f"Failed to remove symlink: {item.name}",
                ))

    return results
