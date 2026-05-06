#!/usr/bin/env python3
"""Analyze YOLO session transcripts and propose a permissions.allow list.

Scans Claude Code JSONL session transcripts for Bash tool invocations,
classifies the commands by safety category (read-only, search/inspect,
build/test, file/cache, local git mutation, or MUTATING), and emits a
proposed ``permissions.allow`` array of gitignore-style patterns.

The script NEVER writes to ``settings.json``. It writes a machine-readable
proposal to ``~/.local/spellbook/state/proposed_allow_list.json`` and a
human-readable summary to stdout. The orchestrator (or user) is expected
to review the proposal before piping it into the install_permissions
helper.

See ``docs/security-arch/plan.md`` (§7, §15) for category and bucketing
definitions.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

# Multi-word "first tokens" — when the leading word matches one of these
# runners and a second token follows, we treat the first two tokens as the
# bucket key. Keep ordered most-specific first if any prefixes overlap.
MULTI_WORD_RUNNERS: frozenset[str] = frozenset(
    {
        "git",
        "gh",
        "npm",
        "pnpm",
        "yarn",
        "cargo",
        "uv",
        "acli",
    }
)

# Four-word mutating forms — must match before three-word prefix collapse.
FOUR_WORD_RUNNERS: frozenset[tuple[str, str, str, str]] = frozenset(
    {
        ("acli", "jira", "workitem", "transition"),
        ("acli", "jira", "workitem", "edit"),
        ("acli", "jira", "workitem", "view"),
        ("acli", "jira", "workitem", "list"),
        ("acli", "jira", "auth", "status"),
    }
)

# Three-word runners (rare, but ``acli jira workitem``, ``gh pr merge`` etc.
# matter for reject classification). We resolve longest match first.
THREE_WORD_RUNNERS: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("acli", "jira", "workitem"),
        ("acli", "jira", "auth"),
        ("gh", "pr", "merge"),
        ("gh", "pr", "close"),
        ("gh", "pr", "view"),
        ("gh", "pr", "list"),
        ("gh", "pr", "diff"),
        ("gh", "pr", "create"),
        ("gh", "run", "view"),
        ("gh", "run", "list"),
    }
)

# Two-word special — e.g. ``uv run`` should bucket as ``uv run``.
TWO_WORD_SPECIALS: frozenset[tuple[str, str]] = frozenset(
    {
        ("uv", "run"),
        ("acli", "jira"),
    }
)

# Categories below produce allowlist entries. Each value is the list of
# acceptable first-tokens (already in their canonical multi/three-word form).
READ_ONLY_SAFE: frozenset[str] = frozenset(
    {
        "ls", "cat", "grep", "rg", "find", "fd",
        "git status", "git diff", "git log", "git show",
        "git branch", "git fetch", "git worktree",
        "jq", "head", "tail", "wc", "which", "pwd",
        "env", "stat", "file", "du", "df",
    }
)

SEARCH_INSPECT: frozenset[str] = frozenset(
    {
        "gh pr view", "gh pr list", "gh pr diff", "gh pr create",
        "gh run view", "gh run list",
        "gh api",
        "acli jira",
        # Four-word acli forms — listed explicitly so the direct membership
        # check fires before any prefix-loop fallback. Mutating four-word
        # forms (transition, edit) are intentionally absent here.
        "acli jira workitem view",
        "acli jira workitem list",
        "acli jira auth status",
    }
)

BUILD_TEST_IDEMPOTENT: frozenset[str] = frozenset(
    {
        "npm", "pnpm", "yarn",
        "pytest", "uv run",
        "cargo", "tsc",
    }
)

LOCAL_FILE_CACHE: frozenset[str] = frozenset(
    {
        "mkdir -p", "touch", "chmod", "cp", "mv",
    }
)

LOCAL_GIT_MUTATION: frozenset[str] = frozenset(
    {
        "git add", "git commit", "git checkout",
        "git stash", "git restore", "git worktree add",
    }
)

# Mutating: NEVER allowlisted. Recorded under ``rejected_mutating`` only.
MUTATING: frozenset[str] = frozenset(
    {
        "git push", "gh pr merge", "gh pr close",
        "acli jira workitem transition", "acli jira workitem edit",
    }
)

# Category display order for stdout grouping.
CATEGORY_ORDER: tuple[str, ...] = (
    "read_only_safe",
    "search_inspect",
    "build_test_idempotent",
    "local_file_cache",
    "local_git_mutation",
)


@dataclass(frozen=True)
class BashRecord:
    """A successful Bash tool invocation extracted from a transcript."""

    command: str
    timestamp: datetime
    session_id: str
    is_sidechain: bool
    source_file: Path


@dataclass
class BucketEntry:
    """An aggregated bucket of equivalent commands."""

    pattern: str
    first_token: str
    flags: tuple[str, ...]
    count: int = 0
    examples: list[str] = field(default_factory=list)

    def add_example(self, command: str) -> None:
        if len(self.examples) < 3 and command not in self.examples:
            self.examples.append(command)
        self.count += 1


@dataclass
class Categorized:
    """Result of bucketing + classifying records."""

    by_category: dict[str, list[BucketEntry]]
    rejected: list[BucketEntry]
    unclassified: list[BucketEntry]


def _parse_timestamp(raw: str) -> datetime | None:
    """Parse RFC3339/ISO8601 timestamps; return None on malformed input."""
    if not raw:
        return None
    # Python's fromisoformat handles ``+00:00`` but historically not ``Z``.
    # Normalize trailing ``Z`` for compatibility on 3.10.
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _iter_jsonl(path: Path) -> Iterator[dict]:
    """Yield decoded JSON objects line-by-line; skip malformed lines silently."""
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def _bash_invocations_in_record(record: dict) -> Iterator[tuple[str, str]]:
    """Yield ``(tool_use_id, command)`` for every Bash tool_use in an assistant record."""
    if record.get("type") != "assistant":
        return
    message = record.get("message")
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if not isinstance(content, list):
        return
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tool_use":
            continue
        if item.get("name") != "Bash":
            continue
        tool_id = item.get("id")
        cmd_input = item.get("input")
        if not isinstance(tool_id, str) or not isinstance(cmd_input, dict):
            continue
        command = cmd_input.get("command")
        if isinstance(command, str) and command.strip():
            yield tool_id, command


def _tool_results_in_record(record: dict) -> Iterator[tuple[str, bool]]:
    """Yield ``(tool_use_id, is_error)`` for every tool_result in a user record."""
    if record.get("type") != "user":
        return
    message = record.get("message")
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if not isinstance(content, list):
        return
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tool_result":
            continue
        tool_use_id = item.get("tool_use_id")
        if not isinstance(tool_use_id, str):
            continue
        is_error = bool(item.get("is_error", False))
        yield tool_use_id, is_error


def _extract_from_file(path: Path, since: datetime) -> Iterator[BashRecord]:
    """Extract successful Bash records from a single JSONL transcript.

    A Bash invocation is yielded ONLY when it has a paired ``tool_result``
    whose ``is_error`` is false-or-absent. Tool uses without any matching
    tool_result (e.g. interrupted sessions where the assistant emitted a
    Bash call but the user side never landed) are excluded — we cannot
    confirm the command succeeded, so it must not seed the allowlist.
    """
    pending: dict[str, BashRecord] = {}
    # Maps tool_use_id -> is_error for any tool_result we observed.
    result_status: dict[str, bool] = {}

    for record in _iter_jsonl(path):
        ts_raw = record.get("timestamp")
        ts = _parse_timestamp(ts_raw) if isinstance(ts_raw, str) else None
        if ts is None:
            # No timestamp -> we cannot apply the days filter, drop it.
            continue
        if ts < since:
            continue

        record_type = record.get("type")
        if record_type == "assistant":
            session_id = record.get("sessionId") or ""
            is_sidechain = bool(record.get("isSidechain", False))
            for tool_id, command in _bash_invocations_in_record(record):
                pending[tool_id] = BashRecord(
                    command=command,
                    timestamp=ts,
                    session_id=session_id if isinstance(session_id, str) else "",
                    is_sidechain=is_sidechain,
                    source_file=path,
                )
        elif record_type == "user":
            for tool_use_id, is_error in _tool_results_in_record(record):
                # Keep the most pessimistic outcome: if any paired result
                # reports an error, treat the invocation as failed.
                if tool_use_id in result_status:
                    result_status[tool_use_id] = result_status[tool_use_id] or is_error
                else:
                    result_status[tool_use_id] = is_error

    for tool_id, br in pending.items():
        # Require an explicit, non-error tool_result. Unpaired tool_uses
        # (interrupted sessions) are dropped.
        if tool_id not in result_status:
            continue
        if result_status[tool_id]:
            continue
        yield br


def extract_bash_commands(root: Path, since: datetime) -> Iterator[BashRecord]:
    """Walk a Claude Code project root and yield successful Bash records.

    Glob layout (Claude Code 2.x):

    * Main session:  ``<root>/<project-encoded>/<session-uuid>.jsonl``
    * Subagent:      ``<root>/<project-encoded>/<session-uuid>/subagents/agent-*.jsonl``

    ``root`` may be either the top-level ``projects/`` directory (containing
    multiple ``<project-encoded>/`` subdirs) OR a directory that itself
    contains the per-project subdirs of a fixture. We treat ``root`` as the
    parent of the per-project encoded dirs.
    """
    if not root.exists() or not root.is_dir():
        return

    # Main sessions: <root>/<project>/<file>.jsonl
    for jsonl in root.glob("*/*.jsonl"):
        yield from _extract_from_file(jsonl, since)

    # Subagent sessions: <root>/<project>/<session>/subagents/<file>.jsonl
    for jsonl in root.glob("*/*/subagents/*.jsonl"):
        yield from _extract_from_file(jsonl, since)


def _safe_split(command: str) -> list[str]:
    """Tokenize a command string, falling back to whitespace split on bad shell quoting."""
    try:
        return shlex.split(command)
    except ValueError:
        # Unmatched quotes etc. Fall back to a permissive split.
        return re.split(r"\s+", command.strip())


def _resolve_first_token(tokens: list[str]) -> str:
    """Compute the canonical first-token for bucketing.

    Rules:
    * If the first four tokens match a known four-word runner, use them.
    * Else if the first three tokens match a known three-word runner, use them.
    * Else if the first two tokens match a two-word special, use them.
    * Else if the first token is a known multi-word runner and a second token
      exists (and is not flag-shaped), use the first two tokens.
    * Else use the single first token.

    The first-token may include ``-flag`` style tokens when they are part of
    the canonical runner key (e.g. ``mkdir -p`` is bucketed as a single
    first-token-with-flag because users overwhelmingly invoke it with -p).
    """
    if not tokens:
        return ""
    first = tokens[0]

    if len(tokens) >= 4:
        quad = (tokens[0], tokens[1], tokens[2], tokens[3])
        if quad in FOUR_WORD_RUNNERS:
            return " ".join(quad)

    if len(tokens) >= 3:
        triple = (tokens[0], tokens[1], tokens[2])
        if triple in THREE_WORD_RUNNERS:
            return " ".join(triple)

    if len(tokens) >= 2:
        pair = (tokens[0], tokens[1])
        if pair in TWO_WORD_SPECIALS:
            return " ".join(pair)

    if first in MULTI_WORD_RUNNERS and len(tokens) >= 2:
        second = tokens[1]
        # If the second token is flag-shaped (starts with ``-``), don't fold
        # it into the first-token; the runner is being used "raw" (e.g.
        # ``git --version``).
        if not second.startswith("-"):
            return f"{first} {second}"

    # ``mkdir -p`` etc. — runners with mandatory flags. Detect by table:
    if first == "mkdir" and len(tokens) >= 2 and tokens[1] == "-p":
        return "mkdir -p"

    return first


def _flag_tokens(tokens: list[str], first_token_word_count: int) -> tuple[str, ...]:
    """Return sorted -flag tokens after the first-token portion."""
    flags = [t for t in tokens[first_token_word_count:] if t.startswith("-")]
    return tuple(sorted(set(flags)))


def bucket_key(command: str) -> tuple[str, tuple[str, ...]]:
    """Compute the ``(first-token, sorted flag-tokens)`` bucket key."""
    tokens = _safe_split(command)
    first_token = _resolve_first_token(tokens)
    word_count = len(first_token.split()) if first_token else 0
    flags = _flag_tokens(tokens, word_count)
    return first_token, flags


def _classify(first_token: str) -> str:
    """Return a category name for a first-token, or ``"unclassified"``.

    Membership tables use longest-prefix matching: e.g. ``git status`` is in
    READ_ONLY_SAFE while ``git push`` is in MUTATING and ``git add`` is in
    LOCAL_GIT_MUTATION.
    """
    if first_token in MUTATING:
        return "mutating"
    # Three-word mutating like "acli jira workitem transition" — match by
    # prefix on the longer string.
    for mut in MUTATING:
        if first_token.startswith(mut + " "):
            return "mutating"
    if first_token in READ_ONLY_SAFE:
        return "read_only_safe"
    if first_token in SEARCH_INSPECT:
        return "search_inspect"
    # gh pr / gh run / gh api: also handle the longer keys present in the
    # search/inspect group.
    for sp in SEARCH_INSPECT:
        if first_token.startswith(sp + " "):
            return "search_inspect"
    if first_token in BUILD_TEST_IDEMPOTENT:
        return "build_test_idempotent"
    if first_token in LOCAL_FILE_CACHE:
        return "local_file_cache"
    if first_token in LOCAL_GIT_MUTATION:
        return "local_git_mutation"
    return "unclassified"


def bucket_and_classify(records: Iterable[BashRecord]) -> Categorized:
    """Group records into buckets keyed by ``(first-token, flags)`` and classify each bucket."""
    buckets: dict[tuple[str, tuple[str, ...]], BucketEntry] = {}

    for rec in records:
        first_token, flags = bucket_key(rec.command)
        if not first_token:
            continue
        key = (first_token, flags)
        if key not in buckets:
            pattern = f"Bash({first_token}:*)"
            buckets[key] = BucketEntry(
                pattern=pattern,
                first_token=first_token,
                flags=flags,
            )
        buckets[key].add_example(rec.command)

    by_category: dict[str, list[BucketEntry]] = defaultdict(list)
    rejected: list[BucketEntry] = []
    unclassified: list[BucketEntry] = []

    # Deduplicate patterns ACROSS flag-variants per category: many users hit
    # ``ls``, ``ls -la``, ``ls -1`` — these all bucket to first-token ``ls``
    # and produce identical pattern strings. Collapse here.
    pattern_seen: dict[str, BucketEntry] = {}
    for entry in buckets.values():
        category = _classify(entry.first_token)
        existing = pattern_seen.get(entry.pattern)
        if existing is None:
            pattern_seen[entry.pattern] = entry
            target = entry
            if category == "mutating":
                rejected.append(target)
            elif category == "unclassified":
                unclassified.append(target)
            else:
                by_category[category].append(target)
        else:
            existing.count += entry.count
            for ex in entry.examples:
                if ex not in existing.examples and len(existing.examples) < 3:
                    existing.examples.append(ex)

    # Sort each category list by count descending then pattern.
    for entries in by_category.values():
        entries.sort(key=lambda e: (-e.count, e.pattern))
    rejected.sort(key=lambda e: (-e.count, e.pattern))
    unclassified.sort(key=lambda e: (-e.count, e.pattern))

    return Categorized(by_category=dict(by_category), rejected=rejected, unclassified=unclassified)


def _entry_to_dict(entry: BucketEntry) -> dict[str, object]:
    return {
        "pattern": entry.pattern,
        "count": entry.count,
        "examples": list(entry.examples),
    }


def render_proposed_list(
    categorized: Categorized,
    *,
    scanned_roots: list[str],
    since: datetime,
    days: int,
    include_mutating: bool = False,
) -> dict[str, object]:
    """Render the categorized buckets to a JSON-serializable proposal dict."""
    categories: dict[str, list[dict]] = {}
    for cat in CATEGORY_ORDER:
        entries = categorized.by_category.get(cat, [])
        if entries:
            categories[cat] = [_entry_to_dict(e) for e in entries]

    rejected = [_entry_to_dict(e) for e in categorized.rejected]

    proposal: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scanned_roots": scanned_roots,
        "days": days,
        "since": since.isoformat().replace("+00:00", "Z"),
        "categories": categories,
        "rejected_mutating": rejected,
        "include_mutating": include_mutating,
    }
    if categorized.unclassified:
        proposal["unclassified"] = [_entry_to_dict(e) for e in categorized.unclassified]
    return proposal


def write_proposed_list(proposal: dict[str, object], output_path: Path) -> None:
    """Write the proposal dict as pretty JSON, creating parent dirs as needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def print_summary(proposal: dict[str, object], include_mutating: bool) -> None:
    """Print a human-readable summary to stdout, grouped by category."""
    print(f"# Proposed permissions.allow (generated {proposal['generated_at']})")
    print(f"# Scanned roots: {', '.join(proposal['scanned_roots'])}")
    print(f"# Window: last {proposal['days']} days (since {proposal['since']})")
    print()

    total_allow = 0
    for cat in CATEGORY_ORDER:
        entries = proposal["categories"].get(cat, [])
        if not entries:
            continue
        print(f"## {cat} ({len(entries)} entries)")
        for entry in entries:
            example = entry["examples"][0] if entry["examples"] else ""
            print(f'  - {entry["pattern"]:<40} count={entry["count"]:>4}  e.g. {example!r}')
            total_allow += 1
        print()

    print(f"# Total allowlist patterns: {total_allow}")
    print()

    rejected = proposal["rejected_mutating"]
    if rejected:
        print(f"## REJECTED — mutating commands (will NOT be added to allowlist) [{len(rejected)} entries]")
        for entry in rejected:
            example = entry["examples"][0] if entry["examples"] else ""
            print(f'  - {entry["pattern"]:<40} count={entry["count"]:>4}  e.g. {example!r}')
        if include_mutating:
            print("  (--include-mutating is set: these are visible here but were NOT promoted into any allow category)")
        print()

    if proposal.get("unclassified"):
        print(f"## UNCLASSIFIED — review manually [{len(proposal['unclassified'])} entries]")
        for entry in proposal["unclassified"]:
            example = entry["examples"][0] if entry["examples"] else ""
            print(f'  - {entry["pattern"]:<40} count={entry["count"]:>4}  e.g. {example!r}')


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

    write_proposed_list(proposal, args.output)
    print_summary(proposal, include_mutating=args.include_mutating)
    print(f"\n# Proposal written to: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
