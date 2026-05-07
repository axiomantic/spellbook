"""Transcript analyzer library for permissions.allow proposals.

Walks Claude Code JSONL session transcripts, extracts successful Bash tool
invocations, classifies them by safety category, and emits a JSON-serializable
proposal dict. The library NEVER writes to ``settings.json``. Callers may
write the proposal to a state file via :func:`write_proposed_list` or render
a human summary via :func:`print_summary`.

This module is the single source of truth for command classification used by:

* ``scripts/analyze_yolo_transcripts.py`` (CLI wrapper)
* ``skills/permissions-from-transcripts/SKILL.md`` (re-runnable LLM skill)

Category and bucketing definitions: see ``docs/security-arch/plan.md`` (sec. 7
and 15) and the WI-3 plan section "Tighten classification breadth".
"""

from __future__ import annotations

import json
import re
import shlex
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

# ---------------------------------------------------------------------------
# Runner tables (multi-token canonical "first tokens")
# ---------------------------------------------------------------------------

# Multi-word "first tokens" - when the leading word matches one of these
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
        "kubectl",
        "docker",
        "aws",
        "gcloud",
    }
)

# Four-word mutating forms - must match before three-word prefix collapse.
FOUR_WORD_RUNNERS: frozenset[tuple[str, str, str, str]] = frozenset(
    {
        ("acli", "jira", "workitem", "transition"),
        ("acli", "jira", "workitem", "edit"),
        ("acli", "jira", "workitem", "view"),
        ("acli", "jira", "workitem", "list"),
        ("acli", "jira", "auth", "status"),
    }
)

# Three-word runners. Resolve longest match first.
#
# Rule of thumb: list every gh/acli/etc subcommand we actually want to
# classify here so the bucket key carries enough specificity for safe
# allow/reject decisions. Listing a triple here does NOT classify it; the
# classification tables below decide that.
THREE_WORD_RUNNERS: frozenset[tuple[str, str, str]] = frozenset(
    {
        # acli jira (auth/workitem dispatch)
        ("acli", "jira", "workitem"),
        ("acli", "jira", "auth"),
        # gh pr - read-only
        ("gh", "pr", "view"),
        ("gh", "pr", "list"),
        ("gh", "pr", "diff"),
        ("gh", "pr", "status"),
        ("gh", "pr", "checks"),
        # gh pr - mutating
        ("gh", "pr", "create"),
        ("gh", "pr", "edit"),
        ("gh", "pr", "review"),
        ("gh", "pr", "ready"),
        ("gh", "pr", "close"),
        ("gh", "pr", "merge"),
        ("gh", "pr", "reopen"),
        # gh run - read-only
        ("gh", "run", "view"),
        ("gh", "run", "list"),
        ("gh", "run", "watch"),
        # gh run - mutating
        ("gh", "run", "rerun"),
        ("gh", "run", "cancel"),
        ("gh", "run", "delete"),
        # gh issue - read-only
        ("gh", "issue", "view"),
        ("gh", "issue", "list"),
        # gh issue - mutating
        ("gh", "issue", "create"),
        ("gh", "issue", "close"),
        ("gh", "issue", "edit"),
        ("gh", "issue", "reopen"),
        # gh repo - read-only
        ("gh", "repo", "view"),
        # gh repo - mutating
        ("gh", "repo", "create"),
        ("gh", "repo", "delete"),
        ("gh", "repo", "edit"),
    }
)

# Two-word special - e.g. ``uv run`` should bucket as ``uv run``.
TWO_WORD_SPECIALS: frozenset[tuple[str, str]] = frozenset(
    {
        ("uv", "run"),
        ("acli", "jira"),
    }
)

# ---------------------------------------------------------------------------
# Classification tables
# ---------------------------------------------------------------------------
#
# Each entry below is a canonical first-token (single word, two-word, three-
# word, or four-word). Membership decides the safety category of a bucket.
#
# Mutating commands are NEVER promoted to allowlist entries. They are kept
# in ``rejected`` for visibility only.

READ_ONLY_SAFE: frozenset[str] = frozenset(
    {
        "ls", "cat", "grep", "rg", "find", "fd",
        "git status", "git diff", "git log", "git show",
        "git branch", "git fetch", "git worktree",
        "jq", "head", "tail", "wc", "which", "pwd",
        "env", "stat", "file", "du", "df",
    }
)

# Search/inspect commands: side-effect-free remote queries.
#
# Note on ``gh api``: the plan recommended leaving ``gh api`` unclassified
# because it can issue arbitrary HTTP methods, including POST/PATCH/DELETE
# that mutate the remote state. We choose the safer option here and do NOT
# include it in SEARCH_INSPECT - the proposed allowlist must not be seeded
# with a tool capable of arbitrary mutation. Operators who want to allow
# ``gh api -X GET ...`` can add a more specific pattern by hand.
#
# kubectl / docker / aws / gcloud are intentionally not blanket-allowed.
# Their surface area is too sprawling to classify safely here. We add only
# the highest-confidence read-only triples we routinely observe; everything
# else falls through to "unclassified" for manual review.
SEARCH_INSPECT: frozenset[str] = frozenset(
    {
        # gh pr (read-only triples)
        "gh pr view",
        "gh pr list",
        "gh pr diff",
        "gh pr status",
        "gh pr checks",
        # gh run (read-only triples)
        "gh run view",
        "gh run list",
        "gh run watch",
        # gh issue (read-only triples)
        "gh issue view",
        "gh issue list",
        # gh repo (read-only triples)
        "gh repo view",
        # acli jira read-only forms
        "acli jira",
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
        "git stash", "git restore",
        # ``git worktree`` mutating subcommands. The first-token resolver
        # (``_resolve_first_token``) produces a 3-word key like
        # ``git worktree add`` for these so they bypass the bare
        # ``git worktree`` READ_ONLY_SAFE entry.
        "git worktree add",
        "git worktree remove",
        "git worktree move",
        "git worktree prune",
        "git worktree repair",
        "git worktree unlock",
        "git worktree lock",
        # ``git branch`` mutating forms. The first-token resolver collapses
        # any of ``-d``/``-D``/``-m``/``-M``/``-c``/``-C`` (and any
        # non-flag positional, which would *create* a branch) to the
        # canonical key ``git branch -d`` — we keep one mutating key per
        # runner rather than enumerating every flag spelling.
        "git branch -d",
    }
)

# Mutating: NEVER allowlisted. Recorded under ``rejected_mutating`` only.
MUTATING: frozenset[str] = frozenset(
    {
        # git remote mutation
        "git push",
        # gh pr mutation
        "gh pr create",
        "gh pr edit",
        "gh pr review",
        "gh pr ready",
        "gh pr close",
        "gh pr merge",
        "gh pr reopen",
        # gh run mutation
        "gh run rerun",
        "gh run cancel",
        "gh run delete",
        # gh issue mutation
        "gh issue create",
        "gh issue close",
        "gh issue edit",
        "gh issue reopen",
        # gh repo mutation
        "gh repo create",
        "gh repo delete",
        "gh repo edit",
        # acli jira mutation
        "acli jira workitem transition",
        "acli jira workitem edit",
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


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# JSONL extraction
# ---------------------------------------------------------------------------


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
    Bash call but the user side never landed) are excluded - we cannot
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


# ---------------------------------------------------------------------------
# Bucketing + classification
# ---------------------------------------------------------------------------


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
            # ``git worktree`` and ``git branch`` are flag/subcommand-blind
            # without further inspection: ``git worktree list`` is read-only
            # but ``git worktree add /tmp/x`` is mutating. Same for
            # ``git branch`` (read-only) vs ``git branch -d feature``
            # (mutating). Resolve a more specific first-token here so
            # ``classify`` sees the mutating intent.
            if first == "git" and second == "worktree" and len(tokens) >= 3:
                third = tokens[2]
                if third in {
                    "add", "remove", "move", "prune", "repair",
                    "unlock", "lock",
                }:
                    return f"git worktree {third}"
                # ``git worktree list`` and any ``--list``/``--porcelain``
                # form remain bucketed as the safe parent.
                return f"{first} {second}"
            if first == "git" and second == "branch":
                rest = tokens[2:]
                # No further args: ``git branch`` (lists local branches).
                if not rest:
                    return "git branch"
                # Mutating short flags. ``-d``/``-D`` delete,
                # ``-m``/``-M`` rename, ``-c``/``-C`` copy.
                _MUTATING_BRANCH_FLAGS = {
                    "-d", "-D", "-m", "-M", "-c", "-C",
                    "--delete", "--move", "--copy",
                }
                for tok in rest:
                    if tok in _MUTATING_BRANCH_FLAGS:
                        return "git branch -d"
                # Cycle-7 F4: ``git branch --list 'pattern'`` and
                # ``git branch -l 'pattern'`` are read-only — the positional
                # is a glob filter, NOT a new branch name. Without this
                # special-case the positional-arg check below would
                # misclassify the filtered listing as branch creation.
                if "--list" in rest or "-l" in rest:
                    return "git branch"
                # Cycle-8 F2: read-only flags that take a SEPARATE-arg
                # value. ``git branch --contains HEAD~1`` is read-only,
                # but the bare positional check below would treat
                # ``HEAD~1`` as a new-branch name and misclassify it as
                # mutating. Consume the flag's argument up front so the
                # subsequent positional check only sees true positionals.
                # ``--key=value`` form does not consume a separate slot
                # and is naturally handled by the dash-prefix filter.
                _GIT_BRANCH_READONLY_ARG_FLAGS = {
                    "--contains", "--no-contains",
                    "--merged", "--no-merged",
                    "--points-at",
                    "--sort",
                    "--format",
                    "--column", "--no-column",
                }
                # Walk ``rest`` and build a positional list, skipping the
                # arg slot following any read-only-arg-taking flag.
                positional: list[str] = []
                skip_next = False
                for tok in rest:
                    if skip_next:
                        skip_next = False
                        continue
                    if tok in _GIT_BRANCH_READONLY_ARG_FLAGS:
                        skip_next = True
                        continue
                    if not tok.startswith("-"):
                        positional.append(tok)
                if positional:
                    # Non-flag positional under ``git branch`` (without
                    # ``--list``/``-l`` or a read-only arg-taking flag)
                    # either creates a branch (``git branch newname``)
                    # or starts a branch from a ref; both mutate.
                    return "git branch -d"
                return "git branch"
            return f"{first} {second}"

    # ``mkdir -p`` etc. - runners with mandatory flags. Detect by table:
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


def classify(first_token: str) -> str:
    """Return a category name for a first-token, or ``"unclassified"``.

    Membership tables use longest-prefix matching: e.g. ``git status`` is in
    READ_ONLY_SAFE while ``git push`` is in MUTATING and ``git add`` is in
    LOCAL_GIT_MUTATION.
    """
    if first_token in MUTATING:
        return "mutating"
    # Three-word mutating like "acli jira workitem transition" - match by
    # prefix on the longer string.
    for mut in MUTATING:
        if first_token.startswith(mut + " "):
            return "mutating"
    if first_token in READ_ONLY_SAFE:
        return "read_only_safe"
    if first_token in SEARCH_INSPECT:
        return "search_inspect"
    # gh pr / gh run: also handle the longer keys present in the
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


# Backward-compatible private alias retained for any in-tree callers that
# imported the underscored name from the script module.
_classify = classify


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
    # ``ls``, ``ls -la``, ``ls -1`` - these all bucket to first-token ``ls``
    # and produce identical pattern strings. Collapse here.
    pattern_seen: dict[str, BucketEntry] = {}
    for entry in buckets.values():
        category = classify(entry.first_token)
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


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


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
        print(f"## REJECTED - mutating commands (will NOT be added to allowlist) [{len(rejected)} entries]")
        for entry in rejected:
            example = entry["examples"][0] if entry["examples"] else ""
            print(f'  - {entry["pattern"]:<40} count={entry["count"]:>4}  e.g. {example!r}')
        if include_mutating:
            print("  (--include-mutating is set: these are visible here but were NOT promoted into any allow category)")
        print()

    if proposal.get("unclassified"):
        print(f"## UNCLASSIFIED - review manually [{len(proposal['unclassified'])} entries]")
        for entry in proposal["unclassified"]:
            example = entry["examples"][0] if entry["examples"] else ""
            print(f'  - {entry["pattern"]:<40} count={entry["count"]:>4}  e.g. {example!r}')


__all__ = [
    "BUILD_TEST_IDEMPOTENT",
    "BashRecord",
    "BucketEntry",
    "CATEGORY_ORDER",
    "Categorized",
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
    "print_summary",
    "render_proposed_list",
    "write_proposed_list",
]
