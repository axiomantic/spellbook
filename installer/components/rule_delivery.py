"""Rule module delivery, deselection, and legacy cleanup.

Two delivery mechanisms, chosen by what the harness can actually read:

- **Directory-capable** harnesses (``claude_code``, ``antigravity``,
  ``opencode``) receive one real symlink per selected module, so module
  identity survives at the destination.
- **Flat** harnesses (``codex``, ``forgecode``, ``gemini``, ``pi``) receive a
  generated concatenation written at the harness's real instruction path.

Deselection is a first-class operation in both. Unchecking a module removes its
symlink on a directory harness and regenerates the artifact without it on a
flat one. Without that, the installer reports a module as declined while the
harness keeps loading it.

Every legacy-artifact probe uses ``os.path.lexists`` rather than
``Path.exists()``. ``exists()`` follows symlinks and returns False for a broken
one, so a user upgrading across the monolith's deletion -- whose sidecar links
all dangle -- would be misclassified as a fresh install and keep the dead links
forever.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from .rule_bundle import BundleResult, generate_bundle
from .rule_modules import RuleModule
from .symlinks import create_symlink

# Every installed module file matches this. Used to find stale files to remove
# on deselection and on uninstall, without touching a user's own rule files.
INSTALLED_GLOB = "??-spellbook-*.md"

# The mandatory core module, whose presence is what every delivery check reads
# as "rules actually arrived". One literal, one import site.
CORE_MODULE_GLOB = "??-spellbook-core.md"

# Wrapper markers for ForgeCode's preserve-or-merge case, where spellbook must
# own AGENTS.md but a user file may already be there. Distinct from the legacy
# SPELLBOOK:START/END demarcation so the two never collide.
MERGE_START = "<!-- SPELLBOOK:RULES:START -->"
MERGE_END = "<!-- SPELLBOOK:RULES:END -->"


@dataclass
class DeliveryOutcome:
    """What one platform's rule delivery did."""

    success: bool
    action: str
    message: str
    installed: List[Path] = field(default_factory=list)
    removed: List[Path] = field(default_factory=list)
    bundle: Optional[BundleResult] = None
    notes: List[str] = field(default_factory=list)


def backup_path_for(path: Path) -> Path:
    """Timestamped backup path, matching the existing demarcation convention."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.parent / f"{path.name}.backup.{timestamp}"


def backup_file(path: Path, dry_run: bool = False) -> Optional[Path]:
    """Back up a real file before spellbook takes over its path.

    Returns None when there is nothing to copy, which includes the dangling
    symlink case: the link's target is already gone, so no bytes exist to
    preserve and the caller records the recorded target instead.
    """
    if not os.path.lexists(path):
        return None
    target = backup_path_for(path)
    if dry_run:
        return target
    if path.is_symlink():
        return None
    try:
        shutil.copy2(path, target)
    except OSError:
        return None
    return target


# ---------------------------------------------------------------------------
# Directory-capable delivery
# ---------------------------------------------------------------------------


def install_module_symlinks(
    rules_dir: Path,
    target_dir: Path,
    selected: Sequence[RuleModule],
    dry_run: bool = False,
) -> DeliveryOutcome:
    """Symlink each selected module into ``target_dir`` and prune the rest.

    Pruning is what makes deselection real: any ``XX-spellbook-*.md`` in the
    directory that is not in the current selection is removed, so unchecking a
    module stops the harness loading it.
    """
    installed: List[Path] = []
    removed: List[Path] = []
    failures: List[str] = []

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    wanted = {module.installed_name: module for module in selected}

    if target_dir.is_dir():
        for existing in sorted(target_dir.glob(INSTALLED_GLOB)):
            if existing.name in wanted:
                continue
            removed.append(existing)
            if not dry_run:
                try:
                    existing.unlink()
                except OSError as exc:
                    failures.append(f"{existing.name}: {exc}")

    for name, module in sorted(wanted.items()):
        source = rules_dir / module.source_name
        result = create_symlink(source, target_dir / name, dry_run=dry_run)
        if result.success:
            installed.append(target_dir / name)
        else:
            failures.append(f"{name}: {result.message}")

    if failures:
        return DeliveryOutcome(
            success=False,
            action="failed",
            message=f"rule modules: {len(failures)} failed ({'; '.join(failures[:3])})",
            installed=installed,
            removed=removed,
        )

    detail = f"{len(installed)} linked"
    if removed:
        detail += f", {len(removed)} removed"
    return DeliveryOutcome(
        success=True,
        action="installed",
        message=f"rule modules: {detail}",
        installed=installed,
        removed=removed,
    )


def remove_module_symlinks(
    target_dir: Path, dry_run: bool = False, failures: Optional[List[str]] = None
) -> List[Path]:
    """Remove every installed rule module file from a rules directory.

    Only paths actually removed are returned. A file that could not be unlinked
    is appended to ``failures`` instead of being reported as removed: a rule
    still on disk still loads, so counting it as gone is a false uninstall.
    """
    removed: List[Path] = []
    if not target_dir.is_dir():
        return removed
    for existing in sorted(target_dir.glob(INSTALLED_GLOB)):
        if not dry_run:
            try:
                existing.unlink()
            except OSError as exc:
                if failures is not None:
                    failures.append(f"{existing}: {exc}")
                continue
        removed.append(existing)
    return removed


# ---------------------------------------------------------------------------
# Flat delivery
# ---------------------------------------------------------------------------


def _split_merged(content: str) -> tuple[str, bool, bool]:
    """Split a merged artifact into the user's part, ours-found, and damaged.

    ``damaged`` means the region opened and never closed. Everything after
    ``MERGE_START`` is then unattributable -- it may be spellbook's truncated
    output, or it may be the user's own text that a hand edit stranded below a
    stray marker -- so the split cannot be trusted and the caller must preserve
    the bytes before rewriting.
    """
    start = content.find(MERGE_START)
    if start == -1:
        return content, False, False
    end = content.find(MERGE_END, start)
    if end == -1:
        return content[:start].rstrip(), True, True
    tail = content[end + len(MERGE_END) :].strip()
    head = content[:start].rstrip()
    if tail:
        head = f"{head}\n\n{tail}" if head else tail
    return head, True, False


def _is_generated_bundle(path: Path) -> bool:
    """Whether a file is one spellbook generated, identified by its own marker."""
    from .rule_bundle import MODULE_MARKER_PREFIX

    try:
        return MODULE_MARKER_PREFIX in path.read_text(encoding="utf-8")
    except OSError:
        return False


def write_bundle(
    path: Path,
    bundle: BundleResult,
    dry_run: bool = False,
    preserve_existing: bool = False,
) -> DeliveryOutcome:
    """Write a generated bundle at a flat harness's real instruction path.

    A real file, not a symlink into the checkout: a symlink would recreate the
    one-file-everything-points-at shape the module split removes, and the
    preserve-or-merge case below cannot be a symlink at all.

    With ``preserve_existing`` (ForgeCode, Codex, Pi), a pre-existing
    non-spellbook file is never replaced. Its bytes are kept first, verbatim,
    and the generated bundle follows inside a demarcated region that later
    installs replace in place.
    """
    notes: List[str] = []
    existing_is_real = os.path.lexists(path) and not path.is_symlink()

    if preserve_existing:
        # Unconditional, including when nothing is at the path yet. Writing a
        # bare bundle here instead would leave the artifact unmarked, and the
        # next install would read spellbook's own output back as user content
        # and prepend it verbatim -- doubling the whole ruleset, permanently.
        current = ""
        if existing_is_real:
            try:
                current = path.read_text(encoding="utf-8")
            except OSError as exc:
                return DeliveryOutcome(
                    success=False,
                    action="failed",
                    message=f"rule bundle: cannot read {path}: {exc}",
                )

        user_content, had_ours, damaged = _split_merged(current)
        if not had_ours:
            # Back up UNCONDITIONALLY, before deciding whether the bytes count
            # as user content. ``_is_generated_bundle`` is a substring test for
            # spellbook's own module marker, and a user file that merely quotes
            # or embeds that marker -- e.g. one written below an older bare,
            # unmarked bundle -- classified as self-generated and was discarded
            # with no copy on disk. Classification decides what is PRESERVED
            # in place; it must never decide whether a copy exists.
            #
            # This fires at most once per path: every later install finds the
            # merge markers, so had_ours is True and this branch is skipped.
            if existing_is_real:
                backup = backup_file(path, dry_run=dry_run)
                if backup is not None:
                    notes.append(f"backed up existing {path.name} to {backup.name}")
            if not user_content.strip() or _is_generated_bundle(path):
                # Empty, or an unmarked bundle spellbook itself wrote. Neither
                # is user content, so neither is preserved in place.
                user_content = ""
        elif damaged:
            # An unterminated region. The split kept only the head, so anything
            # stranded below MERGE_START is about to be dropped. Preserve the
            # whole file first -- this is the one shape where the artifact
            # cannot be reconstructed from the rewrite.
            backup = backup_file(path, dry_run=dry_run)
            if backup is not None:
                notes.append(
                    f"backed up damaged {path.name} to {backup.name} "
                    "(unterminated spellbook region)"
                )

        merged = user_content.rstrip()
        block = f"{MERGE_START}\n{bundle.content.rstrip()}\n{MERGE_END}\n"
        content = f"{merged}\n\n{block}" if merged else block
        action = "updated" if os.path.lexists(path) else "created"
    else:
        # Back up a user's real file once, before spellbook first takes over
        # this path -- but never back up spellbook's own prior output. Without
        # the banner check every reinstall would drop another timestamped copy
        # of a generated file beside it, forever.
        if existing_is_real and not _is_generated_bundle(path):
            backup = backup_file(path, dry_run=dry_run)
            if backup is not None:
                notes.append(f"backed up existing {path.name} to {backup.name}")
        content = bundle.content
        action = "updated" if os.path.lexists(path) else "created"

    if dry_run:
        return DeliveryOutcome(
            success=True,
            action=action,
            message=f"rule bundle: would write {len(bundle.included_ids)} modules to {path}",
            bundle=bundle,
            notes=notes,
        )

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            path.unlink()
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        return DeliveryOutcome(
            success=False,
            action="failed",
            message=f"rule bundle: failed to write {path}: {exc}",
            bundle=bundle,
        )

    return DeliveryOutcome(
        success=True,
        action=action,
        message=(
            f"rule bundle: {len(bundle.included_ids)} modules, "
            f"{bundle.size_bytes} bytes -> {path.name}"
        ),
        installed=[path],
        bundle=bundle,
        notes=notes,
    )


def remove_bundle(
    path: Path, dry_run: bool = False, preserve_existing: bool = False
) -> Optional[Path]:
    """Remove a generated bundle, or only spellbook's region within it.

    Never unlinks a path spellbook did not generate. The instruction paths this
    operates on (``~/.codex/AGENTS.md``, ``~/.pi/agent/AGENTS.md``,
    forge's ``AGENTS.md``) are files a user may own outright, and uninstall runs
    against a platform whose config dir merely exists -- so an unconditional
    unlink here deletes a user's own global instructions even on a machine
    spellbook never installed to.
    """
    if not os.path.lexists(path):
        return None

    if preserve_existing and not path.is_symlink():
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            return None
        user_content, had_ours, damaged = _split_merged(current)
        if had_ours:
            if damaged:
                # Same unattributable-tail shape as write_bundle. Uninstall is
                # the last chance to keep those bytes, so copy before rewriting.
                backup_file(path, dry_run=dry_run)
            if not dry_run:
                if user_content.strip():
                    path.write_text(user_content.rstrip() + "\n", encoding="utf-8")
                else:
                    path.unlink()
            return path
        return None

    if not path.is_symlink() and not _is_generated_bundle(path):
        return None

    if not dry_run:
        try:
            path.unlink()
        except OSError:
            return None
    return path


def build_bundle_for(
    modules: Sequence[RuleModule],
    version: str,
    platform: str,
    cap: Optional[int] = None,
) -> BundleResult:
    """Thin re-export so platform installers import one delivery module."""
    return generate_bundle(modules, version, platform, cap=cap)


# ---------------------------------------------------------------------------
# Legacy artifacts
# ---------------------------------------------------------------------------


def remove_legacy_artifacts(
    paths: Sequence[Path],
    dry_run: bool = False,
    failures: Optional[List[str]] = None,
) -> List[Path]:
    """Remove retired sidecars, dangling or not.

    This is the step that prevents double-loading: a user who keeps both the
    retired monolith sidecar and the module set gets every rule twice.

    As in ``remove_module_symlinks``, a path that could not be unlinked is
    recorded in ``failures`` rather than reported as removed.
    """
    removed: List[Path] = []
    for path in paths:
        if not os.path.lexists(path):
            continue
        if not dry_run:
            try:
                path.unlink()
            except OSError as exc:
                if failures is not None:
                    failures.append(f"{path}: {exc}")
                continue
        removed.append(path)
    return removed
