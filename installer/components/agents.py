"""Agents installer component.

Claude Code 2.1.x does not auto-discover agents from ``$SPELLBOOK_DIR``;
discovery is limited to ``$CLAUDE_CONFIG_DIR/agents/``,
``<cwd>/.claude/agents/``, and plugin sources. This component populates
``$CLAUDE_CONFIG_DIR/agents/`` by symlinking each top-level
``$SPELLBOOK_DIR/agents/*.md`` to a same-named target file, keeping
``$SPELLBOOK_DIR/agents/*.md`` as the single source of truth.

Diverges from ``create_skill_symlinks`` / ``create_command_symlinks`` in two
ways:

1. **Skip+warn on user-authored target files** -- if the target is a regular
   file, or a symlink that points to a non-spellbook path, do NOT clobber.
2. **Source narrowing on uninstall** -- only remove symlinks at the target
   dir whose ``resolve()`` points back into ``$SPELLBOOK_DIR/agents/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from installer.components.symlinks import (
    SymlinkResult,
    create_symlink,
    remove_symlink,
)


def _resolve_in(child: Path, parent: Path) -> bool:
    """Return True iff ``child`` (resolved) lies within ``parent`` (resolved).

    Uses ``Path.resolve()`` on both sides; tolerates either being unreachable
    by returning False.
    """
    try:
        child_resolved = child.resolve()
        parent_resolved = parent.resolve()
    except (OSError, RuntimeError):
        return False
    try:
        child_resolved.relative_to(parent_resolved)
        return True
    except ValueError:
        return False


def install_agents(
    spellbook_dir: Path,
    config_dir: Path,
    dry_run: bool = False,
) -> List[SymlinkResult]:
    """Symlink each ``$SPELLBOOK_DIR/agents/*.md`` to ``$CLAUDE_CONFIG_DIR/agents/<basename>.md``.

    Idempotence precedence per target file:

    1. Target is a symlink whose ``resolve()`` == source -> ``action="unchanged"``
    2. Target is a broken symlink (or symlink to a stale spellbook source path)
       -> ``action="replaced"``
    3. Target is a symlink pointing into a non-spellbook path -> ``action="skipped"``
    4. Target is a regular file (user-authored) -> ``action="skipped"``
    5. Target does not exist -> ``action="installed"``

    Cases 3 and 4 must NEVER clobber the user's file. Caller is responsible
    for pre-creating ``config_dir/agents/``.

    Args:
        spellbook_dir: Repo root containing the ``agents/`` subdirectory.
        config_dir: Claude config dir whose ``agents/`` subdir we populate.
        dry_run: If True, report intended actions without filesystem writes.

    Returns:
        List[SymlinkResult] -- one per source agent file, OR a single entry
        with ``action="skipped"`` and ``message="no source agents"`` when no
        source files were found.
    """
    agents_source_dir = spellbook_dir / "agents"
    agents_target_dir = config_dir / "agents"

    sources: List[Path] = []
    if agents_source_dir.exists() and agents_source_dir.is_dir():
        sources = sorted(p for p in agents_source_dir.glob("*.md") if p.is_file())

    if not sources:
        return [
            SymlinkResult(
                source=agents_source_dir,
                target=agents_target_dir,
                success=True,
                action="skipped",
                message="no source agents",
            )
        ]

    results: List[SymlinkResult] = []
    for source in sources:
        target = agents_target_dir / source.name
        results.append(_install_one(source, target, agents_source_dir, dry_run))
    return results


def _install_one(
    source: Path,
    target: Path,
    agents_source_dir: Path,
    dry_run: bool,
) -> SymlinkResult:
    """Install (or skip) a single agent file according to the precedence rules."""
    name = source.name

    # Branches 1, 3, 4: target already exists in some form.
    if target.is_symlink():
        # Resolve strictly to distinguish good/broken/elsewhere.
        try:
            resolved = target.resolve(strict=True)
        except (OSError, RuntimeError):
            # Branch 2 (broken symlink): fall through to replace.
            return _do_install(source, target, dry_run, replacing=True)
        if resolved == source.resolve():
            # Branch 1: already correct.
            return SymlinkResult(
                source=source,
                target=target,
                success=True,
                action="unchanged",
                message=f"already linked: {name}",
            )
        # Symlink to somewhere that resolves successfully. If it points
        # into the spellbook agents dir but at a different basename or a
        # stale source, treat it as a stale spellbook symlink to replace;
        # otherwise it's a user symlink and we skip+warn.
        if _resolve_in(resolved, agents_source_dir):
            # Stale spellbook symlink (e.g. worktree changed and the old
            # source path no longer matches this source's basename).
            return _do_install(source, target, dry_run, replacing=True)
        return SymlinkResult(
            source=source,
            target=target,
            success=True,
            action="skipped",
            message=f"user symlink preserved: {name} -> {resolved}",
        )
    if target.exists():
        # Branch 4: regular file (or directory) authored by the user.
        return SymlinkResult(
            source=source,
            target=target,
            success=True,
            action="skipped",
            message=f"user file preserved: {name}",
        )

    # Branch 5: target missing -> create.
    return _do_install(source, target, dry_run, replacing=False)


def _do_install(
    source: Path,
    target: Path,
    dry_run: bool,
    replacing: bool,
) -> SymlinkResult:
    """Delegate to ``create_symlink`` and translate its action label.

    ``create_symlink`` (via ``create_link``) reports ``"created"`` or
    ``"updated"``; this component reports ``"installed"`` or ``"replaced"``.
    """
    raw = create_symlink(source, target, dry_run=dry_run)
    name = source.name
    if not raw.success:
        return raw  # propagate failure as-is
    action = "replaced" if replacing else "installed"
    return SymlinkResult(
        source=raw.source,
        target=raw.target,
        success=True,
        action=action,
        message=f"{action} symlink: {name}",
    )


def uninstall_agents(
    config_dir: Path,
    spellbook_dir: Path,
    dry_run: bool = False,
) -> List[SymlinkResult]:
    """Remove symlinks at ``$CLAUDE_CONFIG_DIR/agents/*.md`` whose ``resolve()``
    points back into ``$SPELLBOOK_DIR/agents/``.

    User-authored files (regular files, or symlinks pointing elsewhere) are
    preserved.

    Returns:
        List[SymlinkResult] -- one entry per inspected ``.md`` file at the
        target dir. If the target dir does not exist, returns a single entry
        with ``action="unchanged"``.
    """
    agents_source_dir = spellbook_dir / "agents"
    agents_target_dir = config_dir / "agents"

    if not agents_target_dir.exists():
        return [
            SymlinkResult(
                source=agents_source_dir,
                target=agents_target_dir,
                success=True,
                action="unchanged",
                message="no agents dir to clean",
            )
        ]

    results: List[SymlinkResult] = []
    for entry in sorted(agents_target_dir.glob("*.md")):
        if not entry.is_symlink():
            # User-authored regular file: preserve, do not record.
            continue
        # Determine if this symlink resolves into the spellbook agents dir.
        try:
            resolved = entry.resolve(strict=True)
        except (OSError, RuntimeError):
            # Broken symlink: only remove if its raw target lies inside the
            # spellbook agents dir; otherwise it's not ours.
            try:
                raw_target = Path(entry.readlink())
            except OSError:
                continue
            if raw_target.is_absolute() and _resolve_in(raw_target.parent, agents_source_dir):
                results.append(remove_symlink(entry, dry_run=dry_run))
            continue
        if _resolve_in(resolved, agents_source_dir):
            results.append(
                remove_symlink(entry, verify_source=agents_source_dir, dry_run=dry_run)
            )
        # Symlink to a non-spellbook path: preserve, do not record.
    return results
