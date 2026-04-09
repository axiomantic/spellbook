#!/usr/bin/env python3
"""Migrate spellbook imports to the new spellbook package structure.

Usage:
    python scripts/migrate_imports.py --dry-run          # Preview all changes
    python scripts/migrate_imports.py                    # Apply to all .py/.md files
    python scripts/migrate_imports.py --file path/to.py  # Migrate a single file
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

# Map old module paths to new ones.
# Only includes modules that have actually been moved to the new package.
MODULE_MAP: dict[str, str] = {
    # Core modules
    "spellbook.core.db": "spellbook.core.db",
    "spellbook.core.config": "spellbook.core.config",
    "spellbook.core.auth": "spellbook.core.auth",
    "spellbook.core.path_utils": "spellbook.core.path_utils",
    "spellbook.core.models": "spellbook.core.models",
    # Health
    "spellbook.health.checker": "spellbook.health.checker",
    "spellbook.health.metrics": "spellbook.health.metrics",
    # Memory
    "spellbook.memory.tools": "spellbook.memory.tools",
    "spellbook.memory.store": "spellbook.memory.store",
    "spellbook.memory.consolidation": "spellbook.memory.consolidation",
    # Sessions
    "spellbook.sessions.parser": "spellbook.sessions.parser",
    "spellbook.sessions.resume": "spellbook.sessions.resume",
    "spellbook.sessions.watcher": "spellbook.sessions.watcher",
    "spellbook.sessions.injection": "spellbook.sessions.injection",
    "spellbook.sessions.soul_extractor": "spellbook.sessions.soul_extractor",
    "spellbook.sessions.skill_analyzer": "spellbook.sessions.skill_analyzer",
    "spellbook.sessions.compaction": "spellbook.sessions.compaction",
    # Notifications
    "spellbook.notifications.tts": "spellbook.notifications.tts",
    "spellbook.notifications.notify": "spellbook.notifications.notify",
    # Updates
    "spellbook.updates.tools": "spellbook.updates.tools",
    "spellbook.updates.watcher": "spellbook.updates.watcher",
    # Experiments
    "spellbook.experiments.ab_test": "spellbook.experiments.ab_test",
    # MCP server
    "spellbook.mcp.server": "spellbook.mcp.server",
    # Subpackages: prefix swap (order matters, longer first in sorted keys)
    "spellbook.security": "spellbook.gates",
    "spellbook.forged": "spellbook.forged",
    "spellbook.fractal": "spellbook.fractal",
    "spellbook.code_review": "spellbook.code_review",
    "spellbook.pr_distill": "spellbook.pr_distill",
    "spellbook.coordination": "spellbook.coordination",
    "spellbook.admin": "spellbook.admin",
    "spellbook.extractors": "spellbook.extractors",
    "spellbook.session": "spellbook.session",
}

# Sort keys by length (longest first) to prevent partial replacements.
_SORTED_KEYS = sorted(MODULE_MAP.keys(), key=len, reverse=True)

# Fallback regex for any remaining spellbook references not in the map.
_FALLBACK_RE = re.compile(r"\bspellbook_mcp\b")


class Change(NamedTuple):
    """A single line change in a file."""

    lineno: int
    old: str
    new: str


def rewrite_line(line: str) -> str:
    """Rewrite a single line, replacing spellbook references.

    Applies MODULE_MAP replacements (longest key first), then falls back
    to a regex substitution for any remaining spellbook occurrences.
    """
    result = line
    for old_path in _SORTED_KEYS:
        new_path = MODULE_MAP[old_path]
        # Use word-boundary-aware replacement to avoid partial matches.
        # We match the old_path followed by a word boundary (dot, space, quote, etc.)
        # or end of string.
        pattern = re.compile(re.escape(old_path) + r"(?=\b|\.)")
        result = pattern.sub(new_path, result)

    # Fallback: catch any remaining spellbook_mcp references
    result = _FALLBACK_RE.sub("spellbook", result)

    # Post-fallback security -> gates rename (handles inputs like
    # spellbook_mcp.security.check which normalize to spellbook.security.*).
    result = re.sub(r"\bspellbook\.security(?=\b|\.)", "spellbook.gates", result)
    return result


def migrate_file(filepath: str, *, dry_run: bool = False) -> list[Change]:
    """Migrate a single file, rewriting spellbook references.

    Args:
        filepath: Path to the file to migrate.
        dry_run: If True, report changes without writing.

    Returns:
        List of Change objects describing modifications.
    """
    path = Path(filepath)
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    changes: list[Change] = []
    new_lines: list[str] = []

    for i, line in enumerate(lines, start=1):
        new_line = rewrite_line(line)
        if new_line != line:
            changes.append(Change(lineno=i, old=line, new=new_line))
        new_lines.append(new_line)

    if changes and not dry_run:
        path.write_text("".join(new_lines), encoding="utf-8")

    return changes


# Directories to skip when scanning the whole project.
_SKIP_DIRS = {".worktrees", ".git", "__pycache__", "node_modules", ".venv", "venv"}


def find_files(root: Path) -> list[Path]:
    """Find all .py and .md files under root, skipping excluded directories."""
    results: list[Path] = []
    for child in sorted(root.iterdir()):
        if child.name in _SKIP_DIRS:
            continue
        if child.is_dir():
            results.extend(find_files(child))
        elif child.is_file() and child.suffix in (".py", ".md"):
            results.append(child)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate spellbook imports to the new spellbook package."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without modifying files.",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Migrate a single file instead of the whole project.",
    )
    args = parser.parse_args(argv)

    if args.file:
        files = [Path(args.file)]
    else:
        root = Path(__file__).resolve().parents[1]
        files = find_files(root)

    total_changes = 0
    files_changed = 0

    for filepath in files:
        changes = migrate_file(str(filepath), dry_run=args.dry_run)
        if changes:
            files_changed += 1
            total_changes += len(changes)
            action = "Would change" if args.dry_run else "Changed"
            print(f"\n{action}: {filepath}")
            for c in changes:
                print(f"  L{c.lineno}: {c.old.rstrip()}")
                print(f"     -> {c.new.rstrip()}")

    summary_verb = "would be changed" if args.dry_run else "changed"
    print(f"\n{total_changes} line(s) in {files_changed} file(s) {summary_verb}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
