#!/usr/bin/env python3
"""Bulk rename skills across the spellbook codebase.

Handles text replacement (kebab-case and snake_case) and file/directory renames
via `git mv`. Processes renames in specificity order to avoid clobbering.

Usage:
    # Dry run (default) - shows what would change
    python scripts/rename_skills.py

    # Actually apply changes
    python scripts/rename_skills.py --apply

    # Only run a specific rename
    python scripts/rename_skills.py --rename implementing-features
    python scripts/rename_skills.py --rename implementing-features --apply
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Order matters: longer/more-specific names MUST come first so that
# "advanced-code-review" is processed before "code-review", preventing
# the shorter pattern from clobbering the longer compound name.
RENAMES: list[tuple[str, str]] = [
    ("advanced-code-review", "deep-review"),
    ("requesting-code-review", "requesting-review"),
    ("code-review", "review"),
    ("implementing-features", "develop"),
]

# Names that must NOT be touched by the "code-review" rename pass.
# These are separate skills/entities whose names happen to contain
# "code-review" but are handled by their own rename entry or are
# being deleted separately.
CODE_REVIEW_PROTECTED: set[str] = {
    "advanced-code-review",
    "receiving-code-review",
    "requesting-code-review",
}

SKIP_DIRS: set[str] = {
    ".worktrees",
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

SKIP_FILES: set[str] = {
    "CHANGELOG.md",
    "rename_skills.py",
}

TEXT_EXTENSIONS: set[str] = {
    ".md",
    ".py",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".txt",
    ".cfg",
    ".ini",
    ".html",
    ".tsx",
    ".ts",
    ".js",
    ".jsx",
    ".css",
    ".sh",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def kebab_to_snake(s: str) -> str:
    return s.replace("-", "_")


@dataclass
class ContentChange:
    """Tracks a single content replacement within a file."""

    line_num: int
    old_line: str
    new_line: str


@dataclass
class FileChange:
    """Tracks all changes to a single file."""

    path: Path
    replacements: list[ContentChange] = field(default_factory=list)
    new_content: Optional[str] = None  # Full replaced content (for --apply)


@dataclass
class RenameOp:
    """A file or directory rename operation."""

    old_path: Path
    new_path: Path


@dataclass
class RenameResult:
    """All changes for a single skill rename."""

    old_name: str
    new_name: str
    file_renames: list[RenameOp] = field(default_factory=list)
    content_changes: list[FileChange] = field(default_factory=list)


# ---------------------------------------------------------------------------
# File enumeration
# ---------------------------------------------------------------------------


def iter_text_files(root: Path) -> list[Path]:
    """Walk the repo and yield text files eligible for content replacement."""
    results: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place so os.walk doesn't descend
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")
        ]

        for fname in filenames:
            if fname in SKIP_FILES:
                continue
            fpath = Path(dirpath) / fname
            if fpath.suffix in TEXT_EXTENSIONS:
                results.append(fpath)
    return results


# ---------------------------------------------------------------------------
# Pattern builders
# ---------------------------------------------------------------------------


def build_kebab_pattern(old_kebab: str) -> re.Pattern[str]:
    """Build a regex that matches the kebab-case skill name.

    Uses word boundaries to avoid partial matches inside longer compound
    names. For "code-review", we need extra protection: negative lookbehind
    for common prefixes that form separate skill names.
    """
    if old_kebab == "code-review":
        # Match "code-review" but NOT when preceded by "advanced-", "receiving-",
        # or "requesting-". Also not when preceded by another word char + hyphen
        # that would indicate a compound name we haven't listed.
        # Negative lookbehind for known prefixes:
        return re.compile(
            r"(?<!advanced-)(?<!receiving-)(?<!requesting-)(?<!\w)"
            + re.escape(old_kebab)
        )
    else:
        # For all others, a simple word-boundary on the left suffices.
        # We don't use \b on both sides because "implementing-features" already
        # contains hyphens and \b treats hyphen as a boundary. Instead, we use
        # negative lookbehind/lookahead for word chars.
        return re.compile(r"(?<!\w)" + re.escape(old_kebab) + r"(?!\w)")


def build_snake_pattern(old_snake: str) -> re.Pattern[str]:
    """Build a regex that matches the snake_case form."""
    if old_snake == "code_review":
        return re.compile(
            r"(?<!advanced_)(?<!receiving_)(?<!requesting_)(?<!\w)"
            + re.escape(old_snake)
            + r"(?!\w)"
        )
    else:
        return re.compile(r"(?<!\w)" + re.escape(old_snake) + r"(?!\w)")


# ---------------------------------------------------------------------------
# Content replacement
# ---------------------------------------------------------------------------


def compute_content_changes(
    files: list[Path],
    kebab_pat: re.Pattern[str],
    snake_pat: re.Pattern[str],
    new_kebab: str,
    new_snake: str,
) -> list[FileChange]:
    """Scan files for matches and compute replacements without writing."""
    changes: list[FileChange] = []

    for fpath in files:
        try:
            content = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        lines = content.split("\n")
        file_change = FileChange(path=fpath)
        modified = False

        new_lines: list[str] = []
        for i, line in enumerate(lines, start=1):
            new_line = kebab_pat.sub(new_kebab, line)
            new_line = snake_pat.sub(new_snake, new_line)
            if new_line != line:
                file_change.replacements.append(
                    ContentChange(line_num=i, old_line=line, new_line=new_line)
                )
                modified = True
            new_lines.append(new_line)

        if modified:
            file_change.new_content = "\n".join(new_lines)
            changes.append(file_change)

    return changes


# ---------------------------------------------------------------------------
# File/directory rename discovery
# ---------------------------------------------------------------------------


def discover_file_renames(old_kebab: str, new_kebab: str) -> list[RenameOp]:
    """Find files and directories that should be renamed via git mv.

    Checks:
      - skills/<old>/ directory
      - docs/skills/<old>.md
      - docs/diagrams/skills/<old>.md
      - docs/commands/<old>-*.md (sub-commands)
      - docs/diagrams/commands/<old>-*.md
      - commands/<old>-*.md
      - tests/ files with snake_case in the name
      - spellbook_mcp/ directories with snake_case name
    """
    ops: list[RenameOp] = []
    old_snake = kebab_to_snake(old_kebab)
    new_snake = kebab_to_snake(new_kebab)

    # --- Skill directory ---
    skill_dir = REPO_ROOT / "skills" / old_kebab
    if skill_dir.is_dir():
        ops.append(RenameOp(skill_dir, REPO_ROOT / "skills" / new_kebab))

    # --- Doc files ---
    for doc_dir in ["docs/skills", "docs/diagrams/skills"]:
        doc_file = REPO_ROOT / doc_dir / f"{old_kebab}.md"
        if doc_file.exists():
            ops.append(RenameOp(doc_file, REPO_ROOT / doc_dir / f"{new_kebab}.md"))

    # --- Command files and their docs (prefix match) ---
    # e.g. commands/code-review-give.md, commands/advanced-code-review-verify.md
    for cmd_dir in ["commands", "docs/commands", "docs/diagrams/commands"]:
        cmd_root = REPO_ROOT / cmd_dir
        if not cmd_root.is_dir():
            continue
        for entry in sorted(cmd_root.iterdir()):
            if not entry.is_file():
                continue
            name = entry.name
            # Exact match: <old>.md
            if name == f"{old_kebab}.md":
                ops.append(
                    RenameOp(entry, entry.parent / f"{new_kebab}.md")
                )
            # Sub-command match: <old>-<suffix>.md
            elif name.startswith(f"{old_kebab}-") and name.endswith(".md"):
                suffix = name[len(old_kebab) :]  # includes the leading hyphen
                ops.append(
                    RenameOp(entry, entry.parent / f"{new_kebab}{suffix}")
                )

    # --- Agent files ---
    for agent_dir in ["agents", "docs/agents", "docs/diagrams/agents"]:
        agent_root = REPO_ROOT / agent_dir
        if not agent_root.is_dir():
            continue
        for entry in sorted(agent_root.iterdir()):
            if not entry.is_file():
                continue
            name = entry.name
            # Files named after the skill (e.g. code-reviewer.md contains "code-review"
            # in the name but is actually "code-reviewer" - handle carefully)
            # We only rename exact prefix matches
            if name == f"{old_kebab}.md":
                ops.append(RenameOp(entry, entry.parent / f"{new_kebab}.md"))

    # --- Test files with snake_case names ---
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT / "tests"):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            # For "code_review" we need to be careful not to match
            # "advanced_code_review" or test directories named "test_code_review"
            if old_snake == "code_review":
                # Match test files that contain "code_review" but not
                # "advanced_code_review" or "requesting_code_review"
                if "code_review" in fname and not any(
                    prot in fname
                    for prot in ["advanced_code_review", "requesting_code_review", "receiving_code_review"]
                ):
                    new_fname = fname.replace(old_snake, new_snake)
                    if new_fname != fname:
                        old_path = Path(dirpath) / fname
                        new_path = Path(dirpath) / new_fname
                        ops.append(RenameOp(old_path, new_path))
            elif old_snake in fname:
                new_fname = fname.replace(old_snake, new_snake)
                if new_fname != fname:
                    old_path = Path(dirpath) / fname
                    new_path = Path(dirpath) / new_fname
                    ops.append(RenameOp(old_path, new_path))

    # --- Test directories with snake_case names ---
    for dirpath, dirnames, _filenames in os.walk(REPO_ROOT / "tests"):
        dirnames_copy = list(dirnames)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for dname in dirnames_copy:
            if old_snake == "code_review":
                if "code_review" in dname and not any(
                    prot in dname
                    for prot in ["advanced_code_review", "requesting_code_review", "receiving_code_review"]
                ):
                    new_dname = dname.replace(old_snake, new_snake)
                    if new_dname != dname:
                        old_path = Path(dirpath) / dname
                        new_path = Path(dirpath) / new_dname
                        ops.append(RenameOp(old_path, new_path))
            elif old_snake in dname:
                new_dname = dname.replace(old_snake, new_snake)
                if new_dname != dname:
                    old_path = Path(dirpath) / dname
                    new_path = Path(dirpath) / new_dname
                    ops.append(RenameOp(old_path, new_path))

    # --- Python source directories/files with snake_case names ---
    for src_dir in ["spellbook_mcp"]:
        src_root = REPO_ROOT / src_dir
        if not src_root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(src_root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            # Directories
            for dname in list(dirnames):
                if old_snake == "code_review":
                    if "code_review" in dname and not any(
                        prot in dname
                        for prot in ["advanced_code_review", "requesting_code_review", "receiving_code_review"]
                    ):
                        new_dname = dname.replace(old_snake, new_snake)
                        if new_dname != dname:
                            ops.append(
                                RenameOp(Path(dirpath) / dname, Path(dirpath) / new_dname)
                            )
                elif old_snake in dname:
                    new_dname = dname.replace(old_snake, new_snake)
                    if new_dname != dname:
                        ops.append(
                            RenameOp(Path(dirpath) / dname, Path(dirpath) / new_dname)
                        )
            # Files
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                if old_snake == "code_review":
                    if "code_review" in fname and not any(
                        prot in fname
                        for prot in ["advanced_code_review", "requesting_code_review", "receiving_code_review"]
                    ):
                        new_fname = fname.replace(old_snake, new_snake)
                        if new_fname != fname:
                            ops.append(
                                RenameOp(Path(dirpath) / fname, Path(dirpath) / new_fname)
                            )
                elif old_snake in fname:
                    new_fname = fname.replace(old_snake, new_snake)
                    if new_fname != fname:
                        ops.append(
                            RenameOp(Path(dirpath) / fname, Path(dirpath) / new_fname)
                        )

    # --- Pattern files ---
    patterns_dir = REPO_ROOT / "patterns"
    if patterns_dir.is_dir():
        for entry in sorted(patterns_dir.iterdir()):
            if not entry.is_file():
                continue
            name = entry.name
            if old_kebab in name:
                if old_kebab == "code-review":
                    # Protect compound names
                    if any(prot in name for prot in CODE_REVIEW_PROTECTED):
                        continue
                new_name = name.replace(old_kebab, new_kebab)
                if new_name != name:
                    ops.append(RenameOp(entry, entry.parent / new_name))

    # Deduplicate (same old_path might be discovered from multiple walks)
    seen: set[str] = set()
    deduped: list[RenameOp] = []
    for op in ops:
        key = str(op.old_path)
        if key not in seen:
            seen.add(key)
            deduped.append(op)

    return deduped


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def process_rename(old_kebab: str, new_kebab: str, apply: bool) -> RenameResult:
    """Process a single skill rename: discover changes, optionally apply."""
    old_snake = kebab_to_snake(old_kebab)
    new_snake = kebab_to_snake(new_kebab)

    result = RenameResult(old_name=old_kebab, new_name=new_kebab)

    # 1. Discover file/directory renames
    result.file_renames = discover_file_renames(old_kebab, new_kebab)

    # 2. Discover content changes
    text_files = iter_text_files(REPO_ROOT)
    kebab_pat = build_kebab_pattern(old_kebab)
    snake_pat = build_snake_pattern(old_snake)
    result.content_changes = compute_content_changes(
        text_files, kebab_pat, snake_pat, new_kebab, new_snake
    )

    if not apply:
        return result

    # 3. Apply content changes FIRST (before renames move files)
    for fc in result.content_changes:
        if fc.new_content is not None:
            fc.path.write_text(fc.new_content, encoding="utf-8")

    # 4. Apply file/directory renames via git mv
    # Sort by path depth descending so nested paths are renamed before parents.
    # Also, directories must be renamed after their contents are updated.
    # We do files first, then directories (sorted deepest first).
    file_ops = [op for op in result.file_renames if op.old_path.is_file()]
    dir_ops = [op for op in result.file_renames if op.old_path.is_dir()]
    # Sort dirs deepest first
    dir_ops.sort(key=lambda op: len(op.old_path.parts), reverse=True)

    for op in file_ops + dir_ops:
        if not op.old_path.exists():
            print(f"  WARNING: {op.old_path} does not exist, skipping git mv")
            continue
        if op.new_path.exists():
            print(
                f"  WARNING: {op.new_path} already exists, skipping git mv for {op.old_path}"
            )
            continue
        # Ensure parent directory exists
        op.new_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["git", "mv", str(op.old_path), str(op.new_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        if proc.returncode != 0:
            print(f"  ERROR: git mv failed: {proc.stderr.strip()}")
            print(f"    Command: {' '.join(cmd)}")

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

# ANSI color codes for terminal output
_BOLD = "\033[1m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _rel(path: Path) -> str:
    """Return path relative to repo root for display."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def print_result(result: RenameResult, apply: bool) -> None:
    """Print a summary of a rename operation."""
    mode = "APPLIED" if apply else "DRY RUN"
    print(f"\n{_BOLD}{_CYAN}{'=' * 72}{_RESET}")
    print(
        f"{_BOLD}{_CYAN}  {result.old_name} -> {result.new_name}  [{mode}]{_RESET}"
    )
    print(f"{_BOLD}{_CYAN}{'=' * 72}{_RESET}")

    # File renames
    if result.file_renames:
        print(f"\n  {_BOLD}File/directory renames ({len(result.file_renames)}):{_RESET}")
        for op in result.file_renames:
            exists_marker = "" if op.old_path.exists() else f" {_YELLOW}(not found){_RESET}"
            conflict_marker = ""
            if op.new_path.exists() and not apply:
                conflict_marker = f" {_YELLOW}(target exists!){_RESET}"
            print(
                f"    {_RED}- {_rel(op.old_path)}{_RESET}{exists_marker}"
            )
            print(
                f"    {_GREEN}+ {_rel(op.new_path)}{_RESET}{conflict_marker}"
            )
    else:
        print(f"\n  {_DIM}No file/directory renames needed.{_RESET}")

    # Content changes
    if result.content_changes:
        total_replacements = sum(len(fc.replacements) for fc in result.content_changes)
        print(
            f"\n  {_BOLD}Content changes ({len(result.content_changes)} files, "
            f"{total_replacements} replacements):{_RESET}"
        )
        for fc in result.content_changes:
            print(
                f"\n    {_BOLD}{_rel(fc.path)}{_RESET} "
                f"{_DIM}({len(fc.replacements)} replacement{'s' if len(fc.replacements) != 1 else ''}){_RESET}"
            )
            # Show up to 3 example changes per file
            shown = 0
            for change in fc.replacements:
                if shown >= 3:
                    remaining = len(fc.replacements) - shown
                    print(f"      {_DIM}... and {remaining} more{_RESET}")
                    break
                print(f"      L{change.line_num}:")
                print(f"        {_RED}- {change.old_line.strip()}{_RESET}")
                print(f"        {_GREEN}+ {change.new_line.strip()}{_RESET}")
                shown += 1
    else:
        print(f"\n  {_DIM}No content changes needed.{_RESET}")

    print()


def print_summary(results: list[RenameResult], apply: bool) -> None:
    """Print a final summary across all renames."""
    print(f"{_BOLD}{'=' * 72}{_RESET}")
    mode = "APPLIED" if apply else "DRY RUN SUMMARY"
    print(f"{_BOLD}  {mode}{_RESET}")
    print(f"{_BOLD}{'=' * 72}{_RESET}")

    total_file_renames = 0
    total_content_files = 0
    total_replacements = 0

    for r in results:
        n_renames = len(r.file_renames)
        n_files = len(r.content_changes)
        n_replacements = sum(len(fc.replacements) for fc in r.content_changes)
        total_file_renames += n_renames
        total_content_files += n_files
        total_replacements += n_replacements
        print(
            f"  {r.old_name} -> {r.new_name}: "
            f"{n_renames} path renames, {n_files} files modified "
            f"({n_replacements} replacements)"
        )

    print(f"\n  {_BOLD}Total: {total_file_renames} path renames, "
          f"{total_content_files} files modified, "
          f"{total_replacements} replacements{_RESET}")

    if not apply:
        print(f"\n  {_YELLOW}This was a dry run. Use --apply to execute.{_RESET}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bulk rename skills across the spellbook codebase.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Dry run: show all renames
  %(prog)s --apply                      # Apply all renames
  %(prog)s --rename implementing-features       # Dry run for one skill
  %(prog)s --rename code-review --apply         # Apply one skill rename
""",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform the changes (default is dry run)",
    )
    parser.add_argument(
        "--rename",
        metavar="NAME",
        help="Only process a specific rename (old kebab-case name)",
    )
    args = parser.parse_args()

    # Filter to a single rename if requested
    renames = RENAMES
    if args.rename:
        renames = [(old, new) for old, new in RENAMES if old == args.rename]
        if not renames:
            valid = ", ".join(old for old, _ in RENAMES)
            print(f"Error: unknown rename '{args.rename}'. Valid names: {valid}")
            return 1

    # Verify we're in a git repo
    git_check = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if git_check.returncode != 0:
        print("Error: not inside a git repository")
        return 1

    # Check for uncommitted changes if applying
    if args.apply:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if status.stdout.strip():
            print(
                "WARNING: You have uncommitted changes. It is recommended to "
                "commit or stash them before running with --apply so you can "
                "easily revert if needed."
            )
            response = input("Continue anyway? [y/N] ").strip().lower()
            if response != "y":
                print("Aborted.")
                return 1

    results: list[RenameResult] = []
    for old_kebab, new_kebab in renames:
        print(f"\n{'>' * 40}")
        print(f"Processing: {old_kebab} -> {new_kebab}")
        print(f"{'>' * 40}")
        result = process_rename(old_kebab, new_kebab, apply=args.apply)
        print_result(result, apply=args.apply)
        results.append(result)

    print_summary(results, apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
