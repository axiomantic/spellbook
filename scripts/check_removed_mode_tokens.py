#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Grep gate: forbid tier-classifier tokens and removed execution-mode vocabulary.

Implements the develop-rework design §10.2 / IMP-4 widened verification gate.
Scans every Markdown file under ``skills/`` + ``commands/`` + ``agents/`` for two
classes of forbidden tokens and FAILS (exit 1) on any non-allowlisted match:

(a) Tier-as-classifier tokens:  ``\\b(TRIVIAL|SIMPLE|STANDARD|COMPLEX)\\b``
    Case-sensitive uppercase, so ordinary lowercase prose
    ("complex"/"simple"/"standard") is excluded by the word-boundary pattern.

(b) Removed execution-mode vocabulary:
    ``\\b(work_items|sub_orchestrators|execution_mode)\\b``.

Allowlisting is CONTENT/SYMBOL-anchored (design N-2): each allowlist entry pairs
a repo-relative path glob with an anchor substring that MUST appear on the matched
line for the match to be suppressed. Path-only entries (anchor ``None``) suppress
every match in a file -- used only for the archived sub-orchestrator body. Line
numbers are NEVER used as anchors; they rot as files shift.

Usage:
    uv run scripts/check_removed_mode_tokens.py [REPO_ROOT]

Exit codes:
    0 - no non-allowlisted forbidden tokens
    1 - one or more violations (printed as ``path:line: [class] token | text``)
"""

from __future__ import annotations

import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Directories scanned (repo-relative). The design scopes the gate to
# skills/ + commands/; agents/ is included as a strict superset so a future
# tier/removed-mode token cannot creep into a narrowing-role agent unnoticed.
SCAN_DIRS = ("skills", "commands", "agents")

# Token classes. Patterns are case-sensitive; tier tokens are uppercase-only
# so lowercase prose is naturally excluded by the word boundaries.
TIER_PATTERN = re.compile(r"\b(TRIVIAL|SIMPLE|STANDARD|COMPLEX)\b")
REMOVED_MODE_PATTERN = re.compile(r"\b(work_items|sub_orchestrators|execution_mode)\b")

TOKEN_PATTERNS = (
    ("tier", TIER_PATTERN),
    ("removed-mode", REMOVED_MODE_PATTERN),
)


@dataclass(frozen=True)
class AllowEntry:
    """A content/symbol-anchored allowlist entry (design N-2).

    ``path_glob`` is matched against the repo-relative POSIX path with
    ``fnmatch``. ``anchor`` is a literal substring that must appear on the
    offending line for the match to be suppressed; ``None`` suppresses every
    match in the file (path-only, used for archived historical bodies).
    """

    path_glob: str
    anchor: str | None
    reason: str


# --- Allowlist (a): tier tokens that are genuine false positives -------------
#
# Anchored on content/symbol, never line numbers (design N-2).
ALLOWLIST_TIER: tuple[AllowEntry, ...] = (
    AllowEntry(
        path_glob="skills/debugging/SKILL.md",
        anchor="If SIMPLE:",
        reason="debugging's own bug-complexity language, unrelated to develop tiers",
    ),
    AllowEntry(
        path_glob="commands/simplify-analyze.md",
        anchor="$COMPLEXITY",
        reason="$COMPLEXITY shell variable in the simplify command",
    ),
    AllowEntry(
        path_glob="skills/dispatching-sub-orchestrators/ARCHIVE.md",
        anchor=None,
        reason="archived sub-orchestrator body (historical), path-allowlisted",
    ),
)

# --- Allowlist (b): removed-mode vocabulary that legitimately survives --------
#
# work_items / sub_orchestrators are NEVER blanket-allowlisted as develop
# routing vocabulary. The two anchored exceptions below are:
#   * the deprecation STUB naming what was removed (design §9.1), and
#   * a pre-existing, out-of-scope pseudocode loop variable in fixing-tests.
# execution_mode is RETAINED (Tasks 16/17) as the kept direct/delegated field
# name; its surviving sites are allowlisted with tight content anchors.
ALLOWLIST_REMOVED_MODE: tuple[AllowEntry, ...] = (
    # execution_mode -- retained field name (direct/delegated) in develop.
    AllowEntry(
        path_glob="skills/develop/SKILL.md",
        anchor='execution_mode?: "delegated" | "direct"',
        reason="retained routing field type annotation (delegated/direct only)",
    ),
    AllowEntry(
        path_glob="skills/develop/SKILL.md",
        anchor="**Execution mode (single-orchestrator only):**",
        reason="retained routing field prose (direct/delegated only)",
    ),
    # execution_mode -- retained field name in feature-implement routing table.
    AllowEntry(
        path_glob="commands/feature-implement.md",
        anchor="| execution_mode | Phase 4 Path |",
        reason="retained routing field column header (direct/delegated only)",
    ),
    # Deprecation stub naming the removed sub_orchestrators / work_items modes.
    AllowEntry(
        path_glob="skills/dispatching-sub-orchestrators/SKILL.md",
        anchor=None,
        reason="deprecation stub banner names the removed modes (design §9.1)",
    ),
    # Archived historical body.
    AllowEntry(
        path_glob="skills/dispatching-sub-orchestrators/ARCHIVE.md",
        anchor=None,
        reason="archived sub-orchestrator body (historical), path-allowlisted",
    ),
    # Pre-existing, out-of-scope pseudocode loop variable (see module docstring
    # and DEVIATION note): fixing-tests uses ``work_items`` as a local loop var
    # in batch-processing pseudocode. It is NOT develop's removed routing
    # vocabulary and predates this branch (present at merge-base). Anchored on
    # the exact loop expression so any OTHER work_items use in the file still
    # fails.
    AllowEntry(
        path_glob="skills/fixing-tests/SKILL.md",
        anchor="FOR item IN work_items[priority]",
        reason="pre-existing local loop variable in batch pseudocode, out of scope",
    ),
)

ALLOWLIST_BY_CLASS: dict[str, tuple[AllowEntry, ...]] = {
    "tier": ALLOWLIST_TIER,
    "removed-mode": ALLOWLIST_REMOVED_MODE,
}


@dataclass(frozen=True)
class Violation:
    """A forbidden, non-allowlisted token occurrence."""

    path: str  # repo-relative POSIX path
    lineno: int  # 1-based
    token: str
    token_class: str  # "tier" | "removed-mode"
    line: str  # the full source line, stripped of trailing newline


def _is_allowlisted(rel_path: str, line: str, token_class: str) -> bool:
    """Return True if ``rel_path``/``line`` is allowlisted for ``token_class``."""
    for entry in ALLOWLIST_BY_CLASS.get(token_class, ()):
        if not fnmatch.fnmatch(rel_path, entry.path_glob):
            continue
        if entry.anchor is None or entry.anchor in line:
            return True
    return False


def _iter_markdown_files(repo_root: Path):
    """Yield Markdown files under the scanned dirs, in deterministic order."""
    for scan_dir in SCAN_DIRS:
        base = repo_root / scan_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if path.is_file():
                yield path


def find_violations(repo_root: Path) -> list[Violation]:
    """Scan ``repo_root`` and return all non-allowlisted forbidden tokens.

    Deterministic order: by file path, then line number, then token-class order
    (tier before removed-mode). One Violation per (line, token-class) match.
    """
    repo_root = Path(repo_root)
    violations: list[Violation] = []
    for path in _iter_markdown_files(repo_root):
        rel_path = path.relative_to(repo_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            for token_class, pattern in TOKEN_PATTERNS:
                match = pattern.search(raw_line)
                if match is None:
                    continue
                if _is_allowlisted(rel_path, raw_line, token_class):
                    continue
                violations.append(
                    Violation(
                        path=rel_path,
                        lineno=lineno,
                        token=match.group(1),
                        token_class=token_class,
                        line=raw_line,
                    )
                )
    return violations


def format_violation(v: Violation) -> str:
    """Render a violation as an actionable ``path:line: [class] token | text``."""
    return f"{v.path}:{v.lineno}: [{v.token_class}] {v.token} | {v.line.strip()}"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        repo_root = Path(argv[0]).resolve()
    else:
        repo_root = Path(__file__).resolve().parent.parent

    violations = find_violations(repo_root)
    if violations:
        print(
            f"Found {len(violations)} non-allowlisted forbidden token(s) "
            f"under {'/'.join(SCAN_DIRS)}:",
            file=sys.stderr,
        )
        for v in violations:
            print("  " + format_violation(v), file=sys.stderr)
        print(
            "\nTier tokens (TRIVIAL/SIMPLE/STANDARD/COMPLEX) and removed-mode "
            "vocabulary (work_items/sub_orchestrators/execution_mode) are "
            "forbidden as live vocabulary. If a match is a genuine false "
            "positive, add a content-anchored allowlist entry in "
            "scripts/check_removed_mode_tokens.py (never a line number).",
            file=sys.stderr,
        )
        return 1

    print(f"OK: no non-allowlisted tier or removed-mode tokens under {'/'.join(SCAN_DIRS)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
