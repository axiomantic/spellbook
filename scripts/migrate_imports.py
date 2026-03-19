#!/usr/bin/env python3
"""Migrate spellbook_mcp imports to the new spellbook package structure.

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
    "spellbook_mcp.db": "spellbook.core.db",
    "spellbook_mcp.config_tools": "spellbook.core.config",
    "spellbook_mcp.auth": "spellbook.core.auth",
    "spellbook_mcp.path_utils": "spellbook.core.path_utils",
    "spellbook_mcp.models": "spellbook.core.models",
    # Health
    "spellbook_mcp.health": "spellbook.health.checker",
    "spellbook_mcp.metrics": "spellbook.health.metrics",
    # Memory
    "spellbook_mcp.memory_tools": "spellbook.memory.tools",
    "spellbook_mcp.memory_store": "spellbook.memory.store",
    "spellbook_mcp.memory_consolidation": "spellbook.memory.consolidation",
    # Sessions
    "spellbook_mcp.session_ops": "spellbook.sessions.parser",
    "spellbook_mcp.resume": "spellbook.sessions.resume",
    "spellbook_mcp.watcher": "spellbook.sessions.watcher",
    "spellbook_mcp.injection": "spellbook.sessions.injection",
    "spellbook_mcp.soul_extractor": "spellbook.sessions.soul_extractor",
    "spellbook_mcp.skill_analyzer": "spellbook.sessions.skill_analyzer",
    "spellbook_mcp.compaction_detector": "spellbook.sessions.compaction",
    # Notifications
    "spellbook_mcp.tts": "spellbook.notifications.tts",
    "spellbook_mcp.notify": "spellbook.notifications.notify",
    # Updates
    "spellbook_mcp.update_tools": "spellbook.updates.tools",
    "spellbook_mcp.update_watcher": "spellbook.updates.watcher",
    # Experiments
    "spellbook_mcp.ab_test": "spellbook.experiments.ab_test",
    # MCP server
    "spellbook_mcp.server": "spellbook.mcp.server",
    # Subpackages: prefix swap (order matters, longer first in sorted keys)
    "spellbook_mcp.security": "spellbook.security",
    "spellbook_mcp.forged": "spellbook.forged",
    "spellbook_mcp.fractal": "spellbook.fractal",
    "spellbook_mcp.code_review": "spellbook.code_review",
    "spellbook_mcp.pr_distill": "spellbook.pr_distill",
    "spellbook_mcp.coordination": "spellbook.coordination",
    "spellbook_mcp.admin": "spellbook.admin",
    "spellbook_mcp.extractors": "spellbook.extractors",
    "spellbook_mcp.session": "spellbook.session",
}

# Sort keys by length (longest first) to prevent partial replacements.
_SORTED_KEYS = sorted(MODULE_MAP.keys(), key=len, reverse=True)

# Fallback regex for any remaining spellbook_mcp references not in the map.
_FALLBACK_RE = re.compile(r"\bspellbook_mcp\b")


class Change(NamedTuple):
    """A single line change in a file."""

    lineno: int
    old: str
    new: str


def rewrite_line(line: str) -> str:
    """Rewrite a single line, replacing spellbook_mcp references.

    Applies MODULE_MAP replacements (longest key first), then falls back
    to a regex substitution for any remaining spellbook_mcp occurrences.
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
    return result


def migrate_file(filepath: str, *, dry_run: bool = False) -> list[Change]:
    """Migrate a single file, rewriting spellbook_mcp references.

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
        description="Migrate spellbook_mcp imports to the new spellbook package."
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
