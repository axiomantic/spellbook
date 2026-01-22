"""
Symlink management for spellbook installation.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class SymlinkResult:
    """Result of a symlink operation."""

    source: Path
    target: Path
    success: bool
    action: str  # "created", "updated", "removed", "skipped", "failed"
    message: str


def is_dir_empty(path: Path) -> bool:
    """Check if a directory is empty."""
    try:
        return not any(path.iterdir())
    except (OSError, PermissionError):
        return False


def create_symlink(
    source: Path, target: Path, dry_run: bool = False, remove_empty_dirs: bool = True
) -> SymlinkResult:
    """
    Create a symlink from target to source.

    Args:
        source: The actual file/directory to link to
        target: Where the symlink will be created
        dry_run: If True, don't actually create the symlink
        remove_empty_dirs: If True, remove empty directories blocking symlink creation

    Returns SymlinkResult with status.
    """
    if not source.exists():
        return SymlinkResult(
            source=source,
            target=target,
            success=False,
            action="failed",
            message=f"Source does not exist: {source}",
        )

    if dry_run:
        if target.exists() or target.is_symlink():
            return SymlinkResult(
                source=source,
                target=target,
                success=True,
                action="updated",
                message=f"Would update symlink: {target.name}",
            )
        return SymlinkResult(
            source=source,
            target=target,
            success=True,
            action="created",
            message=f"Would create symlink: {target.name}",
        )

    try:
        # Ensure parent directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing (file, dir, or symlink)
        if target.is_symlink() or target.exists():
            if target.is_dir() and not target.is_symlink():
                # Handle existing directory
                if remove_empty_dirs and is_dir_empty(target):
                    # Empty directory - safe to remove
                    target.rmdir()
                    action = "updated"
                else:
                    # Non-empty directory - don't remove
                    return SymlinkResult(
                        source=source,
                        target=target,
                        success=False,
                        action="failed",
                        message=f"Target is a non-empty directory: {target}. Remove it manually to proceed.",
                    )
            else:
                target.unlink()
                action = "updated"
        else:
            action = "created"

        # Create symlink
        target.symlink_to(source)

        return SymlinkResult(
            source=source,
            target=target,
            success=True,
            action=action,
            message=f"{action.capitalize()} symlink: {target.name}",
        )

    except OSError as e:
        return SymlinkResult(
            source=source,
            target=target,
            success=False,
            action="failed",
            message=f"Failed to create symlink: {e}",
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
    if not target.exists() and not target.is_symlink():
        return SymlinkResult(
            source=verify_source or Path("."),
            target=target,
            success=True,
            action="skipped",
            message=f"Symlink does not exist: {target.name}",
        )

    if not target.is_symlink():
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
        if not str(actual_source).startswith(str(expected)):
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
        target.unlink()
        return SymlinkResult(
            source=actual_source,
            target=target,
            success=True,
            action="removed",
            message=f"Removed symlink: {target.name}",
        )
    except OSError as e:
        return SymlinkResult(
            source=actual_source,
            target=target,
            success=False,
            action="failed",
            message=f"Failed to remove symlink: {e}",
        )


def create_skill_symlinks(
    skills_source: Path,
    skills_target: Path,
    as_directories: bool = True,
    dry_run: bool = False,
) -> List[SymlinkResult]:
    """
    Create symlinks for all skills.

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
            target = skills_target / skill_name
            result = create_symlink(skill_dir, target, dry_run)
        else:
            # Flat .md file format (for OpenCode)
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                target = skills_target / f"{skill_name}.md"
                result = create_symlink(skill_file, target, dry_run)
            else:
                continue

        results.append(result)

    return results


def create_command_symlinks(
    commands_source: Path, commands_target: Path, dry_run: bool = False
) -> List[SymlinkResult]:
    """
    Create symlinks for all commands.

    Handles both:
    - Simple commands: .md files in commands root (e.g., commands/verify.md)
    - Complex commands: subdirectories with supporting files (e.g., commands/systematic-debugging/)

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
        result = create_symlink(cmd_file, target, dry_run)
        results.append(result)

    # Install command directories (subdirectories in commands/)
    for cmd_dir in commands_source.iterdir():
        if cmd_dir.is_dir():
            target = commands_target / cmd_dir.name
            result = create_symlink(cmd_dir, target, dry_run)
            results.append(result)

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
        if item.is_symlink():
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
        if not item.is_symlink():
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
            try:
                item.unlink()
                results.append(SymlinkResult(
                    source=raw_target,
                    target=item,
                    success=True,
                    action="removed",
                    message=f"Removed {reason} symlink: {item.name}",
                ))
            except OSError as e:
                results.append(SymlinkResult(
                    source=raw_target,
                    target=item,
                    success=False,
                    action="failed",
                    message=f"Failed to remove symlink: {e}",
                ))

    return results
