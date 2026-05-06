#!/usr/bin/env python3
"""Analyze YOLO session transcripts and propose a permissions.allow list.

Thin CLI wrapper around :mod:`spellbook.gates.transcript_analyzer`. The
classification + bucketing logic lives in that library so the same code
backs both this script and the ``permissions-from-transcripts`` skill.

Scans Claude Code JSONL session transcripts for Bash tool invocations,
classifies the commands by safety category (read-only, search/inspect,
build/test, file/cache, local git mutation, or MUTATING), and emits a
proposed ``permissions.allow`` array of gitignore-style patterns.

The script NEVER writes to ``settings.json``. It writes a machine-readable
proposal to ``~/.local/spellbook/state/proposed_allow_list.json`` and a
human-readable summary to stdout. The orchestrator (or user) is expected
to review the proposal before piping it into the install_permissions
helper.

See ``docs/security-arch/plan.md`` (sec. 7, sec. 15) for category and
bucketing definitions.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make the spellbook package importable when this script runs from a checkout
# where ``uv run`` or direct ``python`` invocation hasn't already installed
# the package.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from spellbook.gates.transcript_analyzer import (  # noqa: E402  (sys.path bootstrap above)
    BUILD_TEST_IDEMPOTENT,
    BashRecord,
    BucketEntry,
    CATEGORY_ORDER,
    Categorized,
    FOUR_WORD_RUNNERS,
    LOCAL_FILE_CACHE,
    LOCAL_GIT_MUTATION,
    MULTI_WORD_RUNNERS,
    MUTATING,
    READ_ONLY_SAFE,
    SEARCH_INSPECT,
    THREE_WORD_RUNNERS,
    TWO_WORD_SPECIALS,
    bucket_and_classify,
    bucket_key,
    classify,
    extract_bash_commands,
    print_summary,
    render_proposed_list,
    write_proposed_list,
)

# Re-export the underscored alias used by older callers / tests.
_classify = classify

__all__ = [
    "BUILD_TEST_IDEMPOTENT",
    "BashRecord",
    "BucketEntry",
    "CATEGORY_ORDER",
    "Categorized",
    "DEFAULT_CONFIG_DIRS",
    "DEFAULT_OUTPUT_PATH",
    "FOUR_WORD_RUNNERS",
    "LOCAL_FILE_CACHE",
    "LOCAL_GIT_MUTATION",
    "MULTI_WORD_RUNNERS",
    "MUTATING",
    "READ_ONLY_SAFE",
    "SEARCH_INSPECT",
    "THREE_WORD_RUNNERS",
    "TWO_WORD_SPECIALS",
    "bucket_and_classify",
    "bucket_key",
    "classify",
    "extract_bash_commands",
    "main",
    "print_summary",
    "render_proposed_list",
    "write_proposed_list",
]


DEFAULT_OUTPUT_PATH = Path.home() / ".local" / "spellbook" / "state" / "proposed_allow_list.json"
DEFAULT_CONFIG_DIRS: tuple[Path, ...] = (
    Path.home() / ".claude-work" / "projects",
    Path.home() / ".claude" / "projects",
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scan Claude Code session transcripts for Bash commands and propose "
            "a permissions.allow array. NEVER writes settings.json."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Only consider records timestamped within the last N days (default: 30).",
    )
    parser.add_argument(
        "--include-mutating",
        action="store_true",
        help=(
            "Include mutating commands in the stdout/JSON output for visibility. "
            "Mutating commands are STILL kept under rejected_mutating and never "
            "promoted to the allowlist."
        ),
    )
    parser.add_argument(
        "--config-dir",
        action="append",
        type=Path,
        default=None,
        help=(
            "Root directory to scan (repeatable). Defaults to BOTH "
            "~/.claude-work/projects/ AND ~/.claude/projects/ when none passed."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Skip writing the proposal JSON. Stdout summary is still printed. "
            "Useful when seeding the allow list interactively from a skill."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    roots: list[Path]
    if args.config_dir:
        roots = list(args.config_dir)
    else:
        roots = [p for p in DEFAULT_CONFIG_DIRS if p.exists()]
        if not roots:
            print("No transcript roots found. Tried:", file=sys.stderr)
            for p in DEFAULT_CONFIG_DIRS:
                print(f"  {p}", file=sys.stderr)
            return 1

    since = datetime.now(timezone.utc) - timedelta(days=args.days)

    records: list[BashRecord] = []
    for root in roots:
        if not root.exists():
            print(f"warning: root does not exist, skipping: {root}", file=sys.stderr)
            continue
        records.extend(extract_bash_commands(root, since=since))

    categorized = bucket_and_classify(records)
    proposal = render_proposed_list(
        categorized,
        scanned_roots=[str(r) for r in roots],
        since=since,
        days=args.days,
        include_mutating=args.include_mutating,
    )

    if args.dry_run:
        print_summary(proposal, include_mutating=args.include_mutating)
        print("\n# --dry-run set; proposal NOT written.", file=sys.stderr)
        return 0

    write_proposed_list(proposal, args.output)
    print_summary(proposal, include_mutating=args.include_mutating)
    print(f"\n# Proposal written to: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
