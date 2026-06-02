#!/usr/bin/env python3
"""Round up scattered Claude Code worktree sessions: scan, group, reorient, launch.

Self-contained, stdlib-only helper. Imports NOTHING from the spellbook source tree
(design §3.2, §14). In particular, spellbook's `path_utils.encode_cwd` is deliberately
NOT reused: it defaults `resolve_git_root=True` (collapses a worktree to its main repo
root) and ends in `.lstrip('-')` (strips the leading dash, producing the OLD form).
Both behaviors are wrong for Claude Code's per-literal-cwd, leading-dash project dirs,
so this module defines its own `encode_cwd_literal` (design §8.4). Likewise
`distill_session.load_jsonl` is NOT reused: it raises on the first malformed line and
on a missing file, which is wrong for a best-effort scan; `_read_session` here is
tolerant and never raises (design §5.4).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

SCHEMA_VERSION = 1

# Disambiguator-stripping regex (design §7.2). Non-greedy base, single trailing token
# that is a single letter, a 2-8 char lowercase word, or a run of digits.
DISAMBIGUATOR = re.compile(r"^(?P<base>.+?)[-_](?P<tag>[a-z]|[a-z]{2,8}|\d+)$")

# UUID pattern for session filenames (8-4-4-4-12 hex).
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


# ---------------------------------------------------------------------------
# Task 3: encoding + read-side both-forms project-dir matcher
# ---------------------------------------------------------------------------
def encode_cwd_literal(path: str) -> str:
    """Encode an absolute cwd to Claude Code's project-dir name (design §8.4).

    VERIFIED RULE (Bug A): Claude Code replaces EVERY character that is not in
    `[A-Za-z0-9]` with a single '-'. Runs of separators are NOT collapsed (each
    char maps to its own dash). The leading '/' thus becomes the leading dash,
    which is KEPT. NO git-root resolution. So a DOT, underscore, space, colon,
    backslash, etc. all become dashes too -- replacing only '/' (the prior
    behavior) was incomplete and produced project dirs that do not exist on disk.

    Empirically confirmed against 40 real project dirs under ~/.claude/projects/
    and ~/.claude-work/projects/ matched to the first `cwd` recorded inside their
    sessions (0 mismatches). Key evidence:
      - `/Users/eek/Development/styleseat.github`
          -> `-Users-eek-Development-styleseat-github`   (dot -> dash)
      - `/Users/eek/Development/nim-typestates/.claude/worktrees/v0.5-bundle`
          -> `-Users-eek-Development-nim-typestates--claude-worktrees-v0-5-bundle`
        The `/.` run yields TWO adjacent dashes -> runs are NOT collapsed
        (per-char `re.sub(r'[^A-Za-z0-9]', '-', ...)`, not the collapsing form).

    `/Users/eek/Development/x` -> `-Users-eek-Development-x`.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def _find_project_dir(projects_root: str, cwd: str) -> str | None:
    """Return the existing project dir for `cwd`, trying both encoding forms.

    Tries the leading-dash form first, then the stripped form. Returns the first
    `os.path.isdir` hit under `projects_root`, else None. Thin I/O (design §8.4).
    """
    leading = encode_cwd_literal(cwd)
    for name in (leading, leading.lstrip("-")):
        # Finding 3: cwd="/" encodes to "-", whose lstrip("-") is "". Joining an empty
        # name yields projects_root itself, which isdir -> a false positive. Skip empties.
        if not name:
            continue
        candidate = os.path.join(projects_root, name)
        if os.path.isdir(candidate):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Task 4: tolerant JSONL reader
# ---------------------------------------------------------------------------
def _read_session(path: str) -> list[dict[str, Any]]:
    """Read a session JSONL tolerantly (design §5.4). NEVER raises.

    - Reads line-by-line; skips lines that fail `json.loads` (JSONDecodeError).
    - On FileNotFoundError / OSError: returns [].
    - Opens with errors='replace' so binary garbage decodes (then fails JSON parse
      and is skipped) rather than raising at read time.
    """
    records = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    # HIGH Fix 1: a valid-JSON-but-non-object line (bare number / array /
                    # string / bool) would survive json.loads yet break downstream `.get()`
                    # calls in build_session_record. Only append dict records.
                    if isinstance(obj, dict):
                        records.append(obj)
                except json.JSONDecodeError:
                    continue
    except (FileNotFoundError, OSError):
        return []
    return records


# ---------------------------------------------------------------------------
# Task 5: SessionRecord extraction
# ---------------------------------------------------------------------------
def build_session_record(
    uuid: str,
    config_dir: str,
    jsonl_path: str,
    sidecar_dir: str | None,
    encoded_cwd_current: str,
    records: list[dict[str, Any]],
    file_mtime_iso: str | None,
) -> dict[str, Any]:
    """Build a SessionRecord dict from parsed JSONL records (design §4.1, §5.5, §6.2).

    Title precedence uses the CONFIRMED field names: `customTitle`, then `agentName`,
    then `aiTitle` (title_source records which fired). `git_branch_dominant` is the
    most-common non-`HEAD` `gitBranch`; ties break to the LAST-SEEN non-HEAD value in
    file order; `HEAD` is never selected. `appears_running` is set False here; the scan
    wrapper (Task 13) overrides it via the lock/mtime signals.
    """
    cwds = [r.get("cwd") for r in records if isinstance(r.get("cwd"), str)]
    launch_cwd = cwds[0] if cwds else None
    last_cwd = cwds[-1] if cwds else None

    # Branch-dominant with last-seen tie-break (design §6.2, I3).
    raw_values = []
    counts = Counter()
    last_index = {}
    for i, r in enumerate(records):
        b = r.get("gitBranch")
        if not isinstance(b, str):
            continue
        if b not in raw_values:
            raw_values.append(b)
        if b == "HEAD":
            continue
        counts[b] += 1
        last_index[b] = i
    git_branch_dominant = None
    if counts:
        max_count = max(counts.values())
        tied = [b for b, c in counts.items() if c == max_count]
        git_branch_dominant = max(tied, key=lambda b: last_index[b])

    # Title precedence: customTitle -> agentName -> aiTitle. Precedence applies
    # across the whole session: a higher-precedence field on any record wins over
    # a lower-precedence field on an earlier record. Within a field, the latest
    # (reversed-scan) value wins.
    title = None
    title_source = None
    for field in ("customTitle", "agentName", "aiTitle"):
        for r in reversed(records):
            val = r.get(field)
            if val and isinstance(val, str):
                title = val
                title_source = field
                break
        if title is not None:
            break

    # Last internal timestamp. Robustness: a record's `timestamp` is normally an
    # ISO-8601 STRING, but some sources emit a NUMERIC epoch value (seconds or ms).
    # A numeric ts would later break `max(file_mtime_iso, last_internal_ts)` (str vs
    # number) and `_parse_iso(recency_ts)` during lookback filtering. Convert numbers
    # to an ISO-8601 UTC string; use strings as-is; skip anything else. "Last
    # non-empty timestamp in file order wins" is preserved.
    last_internal_ts = None
    for r in records:
        ts = r.get("timestamp")
        if not ts:
            continue
        if isinstance(ts, str):
            last_internal_ts = ts
        elif isinstance(ts, (int, float)) and not isinstance(ts, bool):
            try:
                # Heuristic: values > 1e11 are milliseconds; divide to seconds.
                seconds = ts / 1000.0 if ts > 1e11 else ts
                last_internal_ts = datetime.fromtimestamp(seconds, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            except (ValueError, OverflowError, OSError):
                continue
        # else: non-str/non-number -> skip

    # recency = max(file_mtime, last_internal_ts) by CHRONOLOGICAL comparison.
    # A lexicographic max() misorders when sub-second precision or tz designators
    # differ (e.g. "...:00Z" sorts after "...:00.123Z" because 'Z'(90) > '.'(46),
    # but the latter is chronologically newer). Parse to aware datetimes via
    # _parse_iso; fall back to lexicographic max only if parsing fails.
    if file_mtime_iso and last_internal_ts:
        try:
            recency_ts = (
                file_mtime_iso
                if _parse_iso(file_mtime_iso) >= _parse_iso(last_internal_ts)
                else last_internal_ts
            )
        except (ValueError, TypeError):
            recency_ts = max(file_mtime_iso, last_internal_ts)
    else:
        recency_ts = file_mtime_iso or last_internal_ts

    return {
        "uuid": uuid,
        "config_dir": config_dir,
        "jsonl_path": jsonl_path,
        "sidecar_dir": sidecar_dir,
        "encoded_cwd_current": encoded_cwd_current,
        "launch_cwd": launch_cwd,
        "last_cwd": last_cwd,
        "git_branch_dominant": git_branch_dominant,
        "git_branch_raw_values": raw_values,
        "title": title,
        "title_source": title_source,
        "last_internal_ts": last_internal_ts,
        "file_mtime": file_mtime_iso,
        "recency_ts": recency_ts,
        "appears_running": False,
        "message_count": len(records),
    }


# ---------------------------------------------------------------------------
# Task 6: title-group extraction
# ---------------------------------------------------------------------------
def strip_disambiguator(title: str) -> str:
    """Strip a single trailing disambiguator token from a title (design §7.2).

    Lowercase, apply DISAMBIGUATOR ONCE (non-greedy, $-anchored). If it matches and
    the base is >=1 char, return the base; else return the lowercased title unchanged.
    Only the FINAL token is eligible, so mid-string tokens (e.g. `2957`) are untouched.
    """
    lowered = title.lower()
    m = DISAMBIGUATOR.match(lowered)
    if m:
        base = m.group("base")
        if len(base) >= 1:
            return base
    return lowered


def compute_group_key(session: dict[str, Any]) -> tuple[str | None, str]:
    """Compute (group_key, group_key_source) for a session (design §7.1).

    Precedence: (1) non-null title -> (strip_disambiguator(title), 'title_prefix');
    (2) resolved_workspace -> (workspace, 'resolved_workspace');
    (3) else (encoded_cwd_current, 'encoded_project_dir').
    """
    title = session.get("title")
    if title:
        return (strip_disambiguator(title), "title_prefix")
    workspace = session.get("resolved_workspace")
    if workspace:
        return (workspace, "resolved_workspace")
    return (session.get("encoded_cwd_current"), "encoded_project_dir")


# ---------------------------------------------------------------------------
# Task 7: worktree enumeration + branch index
# ---------------------------------------------------------------------------
def _git_branch(dir_path: str) -> str | None:
    """Return the current branch of `dir_path` via git, or None on failure.

    Thin I/O wrapper (`git -C <dir> rev-parse --abbrev-ref HEAD`). Not unit-tested
    directly; `build_worktree_index` takes an injectable `branch_of` callable instead.
    """
    try:
        out = subprocess.run(
            ["git", "-C", dir_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            # MEDIUM Fix 4: bound the git call so a stuck repo can't hang enumeration.
            timeout=5.0,
        )
    # subprocess.TimeoutExpired is raised by the timeout above and is NOT suppressed by
    # check=False; fold it (and the existing OSError/SubprocessError) into the graceful
    # "branch unknown" path so a hung git returns None instead of crashing the scan.
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    branch = out.stdout.strip()
    return branch or None


def _has_git(dir_path: str) -> bool:
    """True if `dir_path` contains a `.git` file or directory."""
    return os.path.exists(os.path.join(dir_path, ".git"))


def _safe_listdir(path: str) -> list[str]:
    """os.listdir that returns [] instead of raising on OSError (Finding 4).

    `os.path.isdir` can pass for a dir that is then unreadable (no read permission,
    TOCTOU removal, etc.); listing it would crash the whole scan. Treat such a dir
    as empty so enumeration degrades gracefully.
    """
    try:
        return os.listdir(path)
    except OSError:
        return []


def enumerate_worktree_dirs(worktrees_root: str, repos_root: str) -> list[str]:
    """Enumerate candidate worktree dirs on disk (design §6.1).

    Returns absolute dir paths for: (1) each workspace root under `worktrees_root`;
    (2) each `<workspace>/<project>` subdir that has a `.git` file/dir; (3) each
    `<project>` under `repos_root` that is a git repo. Filesystem listing only.
    """
    dirs = []
    if os.path.isdir(worktrees_root):
        for workspace in sorted(_safe_listdir(worktrees_root)):
            ws_path = os.path.join(worktrees_root, workspace)
            if not os.path.isdir(ws_path):
                continue
            dirs.append(ws_path)  # workspace root
            for project in sorted(_safe_listdir(ws_path)):
                proj_path = os.path.join(ws_path, project)
                if os.path.isdir(proj_path) and _has_git(proj_path):
                    dirs.append(proj_path)
    if os.path.isdir(repos_root):
        for project in sorted(_safe_listdir(repos_root)):
            proj_path = os.path.join(repos_root, project)
            # Skip the worktrees_root itself if it lives under repos_root.
            if os.path.realpath(proj_path) == os.path.realpath(worktrees_root):
                continue
            if os.path.isdir(proj_path) and _has_git(proj_path):
                dirs.append(proj_path)
    return dirs


def build_worktree_index(
    dirs: list[str], branch_of: Callable[[str], str | None], worktrees_root: str
) -> dict[str, Any]:
    """Build branch/workspace maps over candidate dirs (design §6.1).

    `branch_of` is an injectable callable (dir -> branch|None). Returns:
      branch_to_dirs:    {branch: [dir, ...]}
      dir_to_branch:     {dir: branch}
      workspace_root_of: {dir: workspace_root_dir_or_None}

    workspace_root_of(dir): the `worktrees_root/<workspace>` ancestor if `dir` is under
    worktrees_root; the dir itself if it IS a workspace root; None for main repos.
    """
    branch_to_dirs = {}
    dir_to_branch = {}
    workspace_root_of = {}

    wt_root_abs = os.path.realpath(worktrees_root)
    for d in dirs:
        branch = branch_of(d)
        if branch is not None:
            dir_to_branch[d] = branch
            branch_to_dirs.setdefault(branch, []).append(d)
        workspace_root_of[d] = _workspace_root_of(d, wt_root_abs)
    return {
        "branch_to_dirs": branch_to_dirs,
        "dir_to_branch": dir_to_branch,
        "workspace_root_of": workspace_root_of,
    }


def _workspace_root_of(d: str, wt_root_abs: str) -> str | None:
    """Resolve the workspace-root dir for `d`, or None for main repos."""
    d_abs = os.path.realpath(d)
    if d_abs == wt_root_abs:
        return None  # the worktrees root itself is not a workspace
    prefix = wt_root_abs + os.sep
    if not d_abs.startswith(prefix):
        return None  # main repo, not under worktrees root
    rel = d_abs[len(prefix):]
    workspace = rel.split(os.sep, 1)[0]
    return os.path.join(wt_root_abs, workspace)


# ---------------------------------------------------------------------------
# Task 8: worktree derivation (Phase A)
# ---------------------------------------------------------------------------
def _dir_mtime_for_tiebreak(d: str) -> float:
    """mtime of `<dir>/.git` (file or dir), fallback `<dir>` st_mtime (design §6.2)."""
    git_path = os.path.join(d, ".git")
    try:
        return os.path.getmtime(git_path)
    except OSError:
        try:
            return os.path.getmtime(d)
        except OSError:
            return 0.0


def derive_worktree(session: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    """Resolve a session's worktree via the §6.2 fallback chain (Phase A only).

    Phase A = git_branch (high) -> cwd (medium) -> UNRESOLVED. The group_plurality
    step (low) is Phase B and lives in `group_sessions` (Task 9); this function
    returns UNRESOLVED for sessions that need it. Returns a dict with
    resolved_worktree_dir, resolved_workspace, workspace_root_dir, resolve_confidence,
    resolve_signal, open_dir, launch_cd_target, warning.

    DISPLAY/REORIENT-TARGET vs LAUNCH cd-target (C2; SPIKE Decision A; design §9.3).
    `resolved_worktree_dir`/`workspace_root_dir`/`open_dir` describe WHERE the session
    belongs (display) and WHERE a reorient would move it (reorient target). They are
    deliberately distinct from `launch_cd_target`, the literal path a `launch` pane must
    `cd` into. Resume is cwd-scoped: the jsonl lives under
    `$CONFIG/projects/<encoded(cwd)>/`, so the cd target MUST encode to the path that
    created the storage dir the jsonl CURRENTLY lives in (`encoded_cwd_current`), NOT the
    resolved worktree dir. `launch_cd_target` is therefore derived from the CURRENT
    storage project dir via `_resolve_launch_cd_target` (Fix 1): for a never-reoriented
    session the storage dir encodes its own `launch_cwd` (so the target == launch_cwd);
    for a session reoriented in a PREVIOUS run the storage dir encodes the NEW worktree
    dir (so the target follows the storage dir, not the stale internal cwd); when nothing
    matches it falls back to `launch_cwd`. For a session reoriented THIS run, the value is
    overridden to the new target dir via `apply_reorient_launch_overrides` (wired into the
    `launch` step via `--reorient-summary`; see `execute_launch`).
    """
    branch_to_dirs = index["branch_to_dirs"]
    dir_to_branch = index["dir_to_branch"]
    workspace_root_of = index["workspace_root_of"]

    resolved_dir = None
    confidence = "unresolved"
    signal = "unresolved"
    warning = None

    b = session.get("git_branch_dominant")
    last_cwd = session.get("last_cwd")
    launch_cwd = session.get("launch_cwd")

    # Step 1: git_branch (high).
    if b is not None and b in branch_to_dirs:
        candidates = branch_to_dirs[b]
        if len(candidates) == 1:
            resolved_dir = candidates[0]
            confidence = "high"
            signal = "git_branch"
        else:
            # Multiple dirs (AMBIGUOUS branch): prefer a cwd that is one of the
            # branch candidates (high), else defer.
            resolved_dir = None
            for cwd in (last_cwd, launch_cwd):
                if cwd in candidates:
                    resolved_dir = cwd
                    break
            if resolved_dir is not None:
                confidence = "high"
                signal = "git_branch"
            elif _cwd_is_known_repo(last_cwd, launch_cwd, dir_to_branch, index):
                # Bug B: the dominant branch maps to MORE THAN ONE dir, but the
                # session's own cwd is itself a known repo/worktree dir (just not
                # one of the branch candidates -- e.g. a session in nim-skills on
                # the common branch 'master', which also maps to styleseat & co.).
                # PREFER the cwd resolution over the branch mtime/slug tiebreak;
                # leave resolved_dir None so Step 2 (cwd, medium) resolves it.
                # This avoids a false high-ish resolution to an unrelated repo.
                resolved_dir = None
            else:
                # No usable cwd: fall back to the branch tiebreak, but the result
                # is genuinely ambiguous, so confidence is LOW (Bug B), with a
                # warning. Prefer the dir whose workspace slug == branch first.
                slug_match = None
                for cand in candidates:
                    ws_root = workspace_root_of.get(cand)
                    slug = os.path.basename(ws_root) if ws_root else os.path.basename(cand)
                    if slug == b:
                        slug_match = cand
                        break
                if slug_match is not None:
                    resolved_dir = slug_match
                else:
                    # Most recently modified worktree dir (total tiebreak).
                    resolved_dir = max(candidates, key=_dir_mtime_for_tiebreak)
                confidence = "low"
                signal = "git_branch"
                warning = (
                    "branch %r maps to multiple worktree dirs and the session cwd is "
                    "not a known repo; chose %s by tiebreak (low confidence)"
                    % (b, resolved_dir)
                )

    # Step 2: cwd (medium).
    if resolved_dir is None:
        for cwd in (last_cwd, launch_cwd):
            if cwd is None:
                continue
            if cwd in dir_to_branch or _is_under_worktrees(cwd, index):
                resolved_dir = cwd
                confidence = "medium"
                signal = "cwd"
                break

    # Build outputs.
    if resolved_dir is not None:
        workspace_root_dir = workspace_root_of.get(resolved_dir)
        if workspace_root_dir is not None:
            resolved_workspace = os.path.basename(workspace_root_dir)
        else:
            resolved_workspace = os.path.basename(resolved_dir)
        open_dir = resolved_dir
    else:
        workspace_root_dir = None
        resolved_workspace = None
        open_dir = launch_cwd

    return {
        "resolved_worktree_dir": resolved_dir,
        "resolved_workspace": resolved_workspace,
        "workspace_root_dir": workspace_root_dir,
        "resolve_confidence": confidence,
        "resolve_signal": signal,
        "open_dir": open_dir,
        # Fix 1: launch cd-target is the real dir whose encoding matches the CURRENT
        # storage project dir (handles previously-reoriented sessions), falling back to
        # launch_cwd. A same-run reorient overrides it (apply_reorient_launch_overrides).
        "launch_cd_target": _resolve_launch_cd_target(session, index),
        "warning": warning,
    }


def _resolve_launch_cd_target(session: dict[str, Any], index: dict[str, Any]) -> str | None:
    """Resolve the launch cd-target from the CURRENT storage project dir (Fix 1).

    Resume is cwd-scoped: the jsonl lives under `$CONFIG/projects/<encode(cwd)>/`, so
    a launch pane MUST `cd` into the real dir whose `encode_cwd_literal(dir)` equals the
    basename of the project dir the jsonl CURRENTLY lives in (`encoded_cwd_current`).
    Deriving the target from the jsonl's INTERNAL first cwd (`launch_cwd`) is correct
    only for never-reoriented sessions; for a session reoriented in a PREVIOUS run the
    storage dir encodes the NEW path while launch_cwd is the STALE old one, so
    `cd launch_cwd` looks in the wrong project dir and `--resume` fails.

    Candidates = every enumerated real dir we already know about (worktree dirs,
    workspace roots, main repos — all keys of `workspace_root_of`) PLUS the session's
    own `launch_cwd`. Pick the candidate whose `encode_cwd_literal` matches
    `encoded_cwd_current`, normalizing the leading-dash form on BOTH sides so a match is
    found regardless of dash form. Fall back to `launch_cwd` when nothing matches
    (preserves the prior behavior for never-reoriented sessions and as a safe default).
    """
    launch_cwd = session.get("launch_cwd")
    current = session.get("encoded_cwd_current")
    if not current:
        return launch_cwd

    target_norm = current.lstrip("-")
    candidates = list(index.get("workspace_root_of", {}).keys())
    if launch_cwd:
        candidates.append(launch_cwd)
    for cand in candidates:
        if cand and encode_cwd_literal(cand).lstrip("-") == target_norm:
            return cand
    return launch_cwd


def _is_under_worktrees(cwd: str | None, index: dict[str, Any]) -> bool:
    """True if `cwd` is a known dir under the worktrees root in the index.

    Conservative: only treats a cwd as worktree-resolvable when it appears in the
    index's workspace_root_of map (i.e. it was enumerated on disk).
    """
    return cwd in index.get("workspace_root_of", {})


def _cwd_is_known_repo(
    last_cwd: str | None,
    launch_cwd: str | None,
    dir_to_branch: dict[str, str],
    index: dict[str, Any],
) -> bool:
    """True if last_cwd OR launch_cwd is a known repo/worktree dir (Bug B).

    "Known" matches the Step-2 cwd resolution criteria EXACTLY: the cwd appears in
    `dir_to_branch` (an enumerated git repo) or under the worktrees root
    (`_is_under_worktrees`). Used by the ambiguous-branch path to decide whether to
    defer to the cwd resolution instead of the branch mtime/slug tiebreak.
    """
    for cwd in (last_cwd, launch_cwd):
        if cwd is None:
            continue
        if cwd in dir_to_branch or _is_under_worktrees(cwd, index):
            return True
    return False


# ---------------------------------------------------------------------------
# Task 9: grouping assembly + Phase-B group-plurality
# ---------------------------------------------------------------------------
def group_sessions(
    sessions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Assemble groups and run Phase-B group-plurality resolution (design §6.4, §7.3).

    Input: sessions already enriched by `derive_worktree` (Phase A). Computes group
    keys, resolves still-UNRESOLVED sessions via same-group plurality
    (confidence='low', signal='group_plurality'), and builds GroupRecords. Returns
    `(group_records, updated_sessions)`.
    """
    # Compute group keys on every session.
    for s in sessions:
        key, source = compute_group_key(s)
        s["group_key"] = key
        s["group_key_source"] = source

    # Bucket by group key.
    by_group = {}
    for s in sessions:
        by_group.setdefault(s["group_key"], []).append(s)

    # Phase B: resolve unresolved sessions via plurality among resolved peers.
    for key, members in by_group.items():
        resolved_peers = [m for m in members if m.get("resolve_confidence") != "unresolved"]
        if not resolved_peers:
            continue
        ws_counts = Counter(
            m.get("resolved_workspace") for m in resolved_peers if m.get("resolved_workspace")
        )
        if not ws_counts:
            continue
        max_count = max(ws_counts.values())
        plurality = [w for w, c in ws_counts.items() if c == max_count]
        if len(plurality) != 1:
            continue  # no unique plurality
        chosen_ws = plurality[0]
        peers_in_ws = [m for m in resolved_peers if m.get("resolved_workspace") == chosen_ws]
        # If all peers in the chosen workspace agree on one repo subdir, adopt it too.
        subdirs = {m.get("resolved_worktree_dir") for m in peers_in_ws}
        chosen_subdir = next(iter(subdirs)) if len(subdirs) == 1 else None
        chosen_ws_root = next(
            (m.get("workspace_root_dir") for m in peers_in_ws if m.get("workspace_root_dir")),
            None,
        )
        for m in members:
            if m.get("resolve_confidence") != "unresolved":
                continue
            m["resolved_workspace"] = chosen_ws
            m["workspace_root_dir"] = chosen_ws_root
            m["resolved_worktree_dir"] = chosen_subdir if chosen_subdir else chosen_ws_root
            m["resolve_confidence"] = "low"
            m["resolve_signal"] = "group_plurality"
            m["open_dir"] = m.get("resolved_worktree_dir") or m.get("launch_cwd")
            # C2: group-plurality resolution is NOT a reorient; the session has not
            # moved, so its launch cd-target stays launch_cwd (default if unset).
            m.setdefault("launch_cd_target", m.get("launch_cwd"))

    # Build GroupRecords.
    group_records = []
    for key in sorted(by_group.keys(), key=lambda k: (k is None, k)):
        members = by_group[key]
        ordered = sorted(members, key=lambda m: (m.get("recency_ts") or ""), reverse=True)
        distinct = sorted(
            {m.get("resolved_worktree_dir") for m in members if m.get("resolved_worktree_dir")}
        )
        group_records.append(
            {
                "group_key": key,
                "group_key_source": members[0].get("group_key_source"),
                "sessions": [m["uuid"] for m in ordered],
                "session_count": len(members),
                "distinct_worktrees": distinct,
            }
        )
    return group_records, sessions


# ---------------------------------------------------------------------------
# Task 10: reorient PLAN generation (pure, no mutation)
# ---------------------------------------------------------------------------
def build_reorient_plan(
    sessions_by_uuid: dict[str, dict[str, Any]],
    decisions: list[dict[str, Any]],
    path_exists: Callable[[str], bool],
) -> list[dict[str, Any]]:
    """Compute MovePlans without mutating anything (design §8.1-§8.8, §4.4).

    `decisions`: [{"uuid","config_dir","target": "repo_subdir"|"workspace_root"|"skip"}].
    `path_exists`: injectable callable (path -> bool); default os.path.exists at call
    sites. Each returned MovePlan dict carries uuid, config_dir, old/new jsonl+sidecar,
    old/new project dir, target_kind, sidecar_present, collision, running, skipped,
    skip_reason. skip_reason for an explicit skip is EXACTLY 'user_skip'.
    """
    plans = []
    for decision in decisions:
        uuid = decision["uuid"]
        config_dir = decision["config_dir"]
        target = decision["target"]
        session = sessions_by_uuid.get(uuid, {})

        old_jsonl = session.get("jsonl_path")
        old_project_dir = os.path.dirname(old_jsonl) if old_jsonl else None
        sidecar_dir = session.get("sidecar_dir")
        sidecar_present = bool(sidecar_dir)

        base = {
            "uuid": uuid,
            "config_dir": config_dir,
            "old_jsonl": old_jsonl,
            "new_jsonl": None,
            "old_sidecar": sidecar_dir,
            "new_sidecar": None,
            "old_project_dir": old_project_dir,
            "new_project_dir": None,
            "target_kind": None,
            "sidecar_present": sidecar_present,
            "collision": False,
            "running": False,
            "skipped": False,
            "skip_reason": None,
        }

        # HIGH Fix (safety invariant): reorient must NEVER cross
        # ~/.claude <-> ~/.claude-work. If the decision's config_dir differs from the
        # session's actual config_dir, refuse the move at plan-build time.
        if session.get("config_dir") and (
            os.path.realpath(os.path.expanduser(os.path.expandvars(config_dir)))
            != os.path.realpath(os.path.expanduser(os.path.expandvars(session["config_dir"])))
        ):
            base["skipped"] = True
            base["skip_reason"] = "cross_config_dir"
            plans.append(base)
            continue

        # Explicit user skip.
        if target == "skip":
            base["skipped"] = True
            base["skip_reason"] = "user_skip"
            plans.append(base)
            continue

        # Unresolved sessions cannot be reoriented.
        if session.get("resolve_confidence") == "unresolved" or not session:
            base["skipped"] = True
            base["skip_reason"] = "unresolved"
            plans.append(base)
            continue

        # Running sessions are refused.
        if session.get("appears_running"):
            base["skipped"] = True
            base["running"] = True
            base["skip_reason"] = "running"
            plans.append(base)
            continue

        # Resolve the target dir.
        if target == "workspace_root":
            target_dir = session.get("workspace_root_dir")
            base["target_kind"] = "workspace_root"
            if not target_dir:
                base["skipped"] = True
                base["skip_reason"] = "no_workspace_root"
                plans.append(base)
                continue
        elif target == "repo_subdir":
            target_dir = session.get("resolved_worktree_dir")
            base["target_kind"] = "repo_subdir"
            # Finding 2: resolved_worktree_dir can be None under Phase-B group-plurality
            # resolution. A None target_dir would crash encode_cwd_literal -> re.sub;
            # emit a skipped plan instead (mirrors the workspace_root None guard above).
            if not target_dir:
                base["skipped"] = True
                base["skip_reason"] = "no_repo_subdir"
                plans.append(base)
                continue
        else:
            base["skipped"] = True
            base["skip_reason"] = "unknown_target"
            plans.append(base)
            continue

        new_project_dir = os.path.join(config_dir, "projects", encode_cwd_literal(target_dir))
        base["new_project_dir"] = new_project_dir

        # Already-correct skip (I2).
        # MEDIUM Fix 2: old_project_dir may be the STRIPPED encoding (no leading dash)
        # for older Claude sessions, while new_project_dir is built via encode_cwd_literal
        # (canonical leading-dash form). Compare the project-dir basenames with leading
        # dashes stripped from BOTH so the SAME path under either encoding is recognized
        # as already-correct and skipped.
        if old_project_dir and os.path.basename(new_project_dir).lstrip("-") == os.path.basename(
            old_project_dir
        ).lstrip("-"):
            base["skipped"] = True
            base["skip_reason"] = "already_correct"
            plans.append(base)
            continue

        new_jsonl = os.path.join(new_project_dir, uuid + ".jsonl")
        new_sidecar = os.path.join(new_project_dir, uuid) if sidecar_present else None
        base["new_jsonl"] = new_jsonl
        base["new_sidecar"] = new_sidecar

        # Collision check (§8.8).
        collision = path_exists(new_jsonl) or (sidecar_present and path_exists(new_sidecar))
        if collision:
            base["collision"] = True
            base["skipped"] = True
            base["skip_reason"] = "collision"
            plans.append(base)
            continue

        plans.append(base)
    return plans


# ---------------------------------------------------------------------------
# Task 11: AppleScript generation
# ---------------------------------------------------------------------------
def _escape_applescript(s: str) -> str:
    """Escape a string for an AppleScript double-quoted literal (design §9.5).

    Backslash first, then double-quote. Raises ValueError on newline / control chars
    (caller rejects that item) rather than emitting unsafe script.
    """
    if any(ord(c) < 0x20 for c in s):
        raise ValueError("control character in AppleScript literal: %r" % s)
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_pane_command(
    session: dict[str, Any], default_config_dir: str, explicit_config_env: bool
) -> str | None:
    """Build the pane resume command (SPIKE Decision A; design §9.3, §9.4).

    Returns:
      `cd <cd_target> && CLAUDE_CONFIG_DIR=<config_dir> claude
       --dangerously-skip-permissions --resume <uuid>`
    or None when there is no usable cd-target (I-launch-1).

    C1 — ALWAYS emit the CLAUDE_CONFIG_DIR prefix. The spike found this machine's
    ambient `CLAUDE_CONFIG_DIR` is `~/.claude-work`, so EVERY pane (including
    `~/.claude` sessions) must override it explicitly to the session's own config_dir;
    leaving it unset would inherit the wrong store. The `default_config_dir` /
    `explicit_config_env` args are retained for signature stability but no longer gate
    the prefix.

    C2 — cd_target is the session's LAUNCH cd-target (`launch_cd_target`), derived from
    the session's CURRENT storage dir (Fix 1) for a non-same-run-reoriented session, and
    the new target dir for a session reoriented THIS run (set via
    `apply_reorient_launch_overrides`, wired through `execute_launch --reorient-summary`).
    Resume is cwd-scoped, so the cd target must encode to the storage dir holding the jsonl.

    I-launch-1 — if the cd_target is falsy (unresolved + null launch_cwd), return None
    so the caller can SKIP the pane and warn rather than emit `cd None && ...`.
    """
    cd_target = session.get("launch_cd_target")
    if not cd_target:
        return None
    uuid = session["uuid"]
    # MEDIUM Fix 3: a missing/None config_dir must fall back to default_config_dir so the
    # prefix never becomes CLAUDE_CONFIG_DIR='' (which would inherit the wrong store).
    config_dir = session.get("config_dir") or default_config_dir
    # C1: unconditional prefix using the session's own config_dir.
    # MEDIUM Fix 1: shell-safe quoting of paths (spaces/special chars) via shlex.quote.
    prefix = "CLAUDE_CONFIG_DIR=%s " % shlex.quote(config_dir)
    return "cd %s && %sclaude --dangerously-skip-permissions --resume %s" % (
        shlex.quote(cd_target),
        prefix,
        uuid,
    )


def render_applescript(
    groups: list[dict[str, Any]],
    sessions_by_uuid: dict[str, dict[str, Any]],
    *,
    default_config_dir: str,
    explicit_config_env: bool = False,
    warnings: list[str] | None = None,
) -> str:
    """Render the Ghostty AppleScript (design §9.1, §9.2). Pure string output.

    One `tell application "Ghostty"` window per group. Layout (design §9.2):
      1 session  -> single pane (no split).
      2 sessions -> split base direction right.
      3 sessions -> pane1 base; split pane1 right -> pane2; split pane1 down -> pane3.
      4 sessions -> split right then split each side down.
      5+ sessions -> all subsequent splits down off the base pane (column).
    Each pane: `input text "<cmd>" to <terminal>` then `send key "enter" to <terminal>`,
    with `delay 0.3` between. Sessions are taken in GroupRecord order (recency-desc).

    NATIVE API (Ghostty >= 1.2.0, confirmed against the 1.3.1 scripting dictionary
    at /Applications/Ghostty.app/Contents/Resources/Ghostty.sdef):
      - Window creation uses the DEDICATED `new window` command (sdef code
        `GhstNWin`, result type `window`) -- NOT the generic AppleScript `make`
        verb. The application's `window` element is read-only, so `make new window`
        raises `-2710 (Can't make class window ...)` at runtime; bind the command's
        result instead: `set baseWindow to (new window)`.
      - the initial surface is `focused terminal of selected tab of baseWindow`
        (sdef: window -> `selected tab` (tab) -> `focused terminal` (terminal)).
        Addressing it off the BOUND window variable rather than `front window` is
        the confirmed-working path. There is NO `current session` accessor.
      - `split <terminal> direction <right|left|down|up>` returns the new `terminal`.
      - `input text "<text>" to <terminal>` pastes text and does NOT auto-submit, so a
        separate `send key "enter" to <terminal>` is required to run the command.
      - the Return key name is the sdef-documented `"enter"` (e.g. "enter", "a", "space").
    This requires Automation (Apple Events) permission, NOT Accessibility, and does not
    depend on any Ghostty keybind. The API is new and could change in a future major.

    I-launch-1 — a session whose `build_pane_command` returns None (no usable cd-target)
    is SKIPPED: it is dropped before layout (so split counts stay correct) and a warning
    is appended to `warnings` (when a list is supplied). A group left with no launchable
    sessions emits no window.
    """
    lines = ['tell application "Ghostty"']
    for group in groups:
        # Resolve commands first; drop sessions with no usable cd-target (I-launch-1).
        # Escape+validate ONCE here so a command with control chars/newlines skips
        # only that pane (matching the cd-None skip) instead of crashing the launch;
        # the emit loop reuses the pre-escaped string.
        launchable = []  # [(uuid, escaped_cmd), ...]
        for uuid in group["sessions"]:
            # MEDIUM Fix: defensive lookup — a group referencing a uuid absent from the
            # scan results must SKIP that pane (matching the other skips in this loop)
            # rather than raise KeyError and crash the whole launch.
            session = sessions_by_uuid.get(uuid)
            if not session:
                if warnings is not None:
                    warnings.append(
                        "session %s not found in scan results; pane skipped" % uuid
                    )
                continue
            cmd = build_pane_command(session, default_config_dir, explicit_config_env)
            if cmd is None:
                if warnings is not None:
                    warnings.append(
                        "session %s has no resume cd-target (unresolved and no launch cwd); "
                        "pane skipped" % uuid
                    )
                continue
            try:
                escaped = _escape_applescript(cmd)
            except ValueError as e:
                if warnings is not None:
                    warnings.append(
                        "session %s command contains invalid characters: %s; pane skipped"
                        % (uuid, e)
                    )
                continue
            launchable.append((uuid, escaped))

        n = len(launchable)
        if n == 0:
            continue  # nothing launchable in this group -> no window

        lines.append("\tactivate")
        # Dedicated `new window` command (sdef GhstNWin); the generic `make new
        # window` verb raises -2710 because the window element is read-only.
        lines.append("\tset baseWindow to (new window)")
        # First pane: the window's initial surface, addressed off the BOUND window
        # variable (sdef: window -> selected tab -> focused terminal). There is no
        # `current session` in the real dictionary.
        lines.append("\tset pane1 to (focused terminal of selected tab of baseWindow)")
        pane_vars = ["pane1"]
        # Splits per layout heuristic.
        for i in range(1, n):
            if n == 2:
                direction = "right"
                parent = "pane1"
            elif n == 3:
                direction = "right" if i == 1 else "down"
                parent = "pane1"
            elif n == 4:
                # split right, then split each side down.
                if i == 1:
                    direction, parent = "right", "pane1"
                elif i == 2:
                    direction, parent = "down", "pane1"
                else:
                    direction, parent = "down", "pane2"
            else:
                direction = "down"
                parent = "pane1"
            pane_var = "pane%d" % (i + 1)
            lines.append("\tset %s to (split %s direction %s)" % (pane_var, parent, direction))
            pane_vars.append(pane_var)
        # Emit commands per pane (reuse the pre-escaped command from the first loop).
        for pane_var, (uuid, escaped) in zip(pane_vars, launchable):
            lines.append('\tinput text "%s" to %s' % (escaped, pane_var))
            lines.append("\tdelay 0.3")
            # `input text` pastes without a trailing newline; submit via the
            # sdef-documented Return key name "enter".
            lines.append('\tsend key "enter" to %s' % pane_var)
            lines.append("\tdelay 0.3")
    lines.append("end tell")
    return "\n".join(lines)


def apply_reorient_launch_overrides(
    plan: dict[str, Any], reorient_summary: dict[str, Any]
) -> dict[str, Any]:
    """Point reoriented sessions' launch cd-target at their POST-MOVE dir (C2; Fix 2).

    MECHANISM: `execute_launch` calls this when invoked with `--reorient-summary` (the
    summary `execute_reorient` produced THIS run). For every session actually moved this
    run, its storage dir now encodes to the reorient target dir, so resume must `cd`
    there instead of the pre-move launch cd-target. This reads the per-uuid `target_dir`
    from `reorient_summary["moved"]` and writes it onto the matching session's
    `launch_cd_target` in `plan["sessions"]`. Sessions NOT in `moved` keep the
    launch_cd_target derived from their current storage dir (Fix 1). Mutates and returns
    the plan. No filesystem access.
    """
    overrides = {
        m["uuid"]: m["target_dir"]
        for m in reorient_summary.get("moved", [])
        if m.get("target_dir")
    }
    for s in plan.get("sessions", []):
        new_target = overrides.get(s.get("uuid"))
        if new_target:
            s["launch_cd_target"] = new_target
    return plan


# ---------------------------------------------------------------------------
# Task 12: recency / lookback filter
# ---------------------------------------------------------------------------
def _parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp (handles trailing 'Z') to an aware datetime."""
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def within_lookback(
    recency_ts: str,
    now_iso: str,
    lookback_hours: float | None,
    since_iso: str | None,
) -> bool:
    """True if `recency_ts` is within the lookback window (design §5.5, §5.6).

    If `since_iso` is given, include when recency >= since. Else compute
    cutoff = now - lookback_hours and include when recency >= cutoff. Boundary
    inclusive. `since_iso` and `lookback_hours` are mutually exclusive (raises if both).
    """
    if since_iso is not None and lookback_hours is not None:
        raise ValueError("since_iso and lookback_hours are mutually exclusive")
    recency = _parse_iso(recency_ts)
    if since_iso is not None:
        return recency >= _parse_iso(since_iso)
    if lookback_hours is None:
        raise ValueError("one of since_iso or lookback_hours is required")
    cutoff = _parse_iso(now_iso) - timedelta(hours=lookback_hours)
    return recency >= cutoff


# ---------------------------------------------------------------------------
# Task 13: scan + plan subcommands (read-only) — side-effect-free I/O wrappers
# ---------------------------------------------------------------------------
def _iso_from_mtime(mtime: float) -> str | None:
    """Format a POSIX mtime (float) as a Zulu ISO-8601 string (UTC, second resolution)."""
    try:
        return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError):
        return None


def _now_iso() -> str:
    """Current time as a Zulu ISO-8601 string (UTC, second resolution)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _has_running_lock(project_dir: str, uuid: str) -> bool:
    """True if a sibling lock file marks the session as running (design §8.6).

    PRIMARY signal: presence of `<uuid>.lock` OR any `*.lock` in the project dir.
    Thin filesystem check; never raises.
    """
    specific = os.path.join(project_dir, uuid + ".lock")
    if os.path.exists(specific):
        return True
    try:
        for name in os.listdir(project_dir):
            if name.endswith(".lock"):
                return True
    except OSError:
        return False
    return False


def _recent_mtime(mtime: float, now_ts: float, threshold_sec: float) -> bool:
    """True if `mtime` is within `threshold_sec` of `now_ts` (design §8.6 recency signal)."""
    return (now_ts - mtime) <= threshold_sec


def _detect_running(
    project_dir: str, uuid: str, mtime: float, now_ts: float, threshold_sec: float
) -> bool:
    """Combine the §8.6 PRIMARY running signals: lock presence OR recent mtime.

    The flock probe (design §8.6) is OPTIONAL/best-effort and intentionally NOT
    relied upon here — these two primary signals are authoritative.
    """
    if _has_running_lock(project_dir, uuid):
        return True
    return _recent_mtime(mtime, now_ts, threshold_sec)


def scan_config_dirs(
    config_dirs: list[str],
    *,
    lookback_hours: float | None,
    since_iso: str | None,
    running_threshold_sec: float,
    now_iso: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Walk config dirs and build filtered SessionRecords (design §5, §8.6, Task 13).

    For each `<config_dir>/projects/*/<uuid>.jsonl` (UUID-pattern, EXCLUDING
    `agent-*.jsonl`), read tolerantly, build a SessionRecord, set `appears_running`
    from the §8.6 primary signals (lock presence and/or recent mtime), and keep it
    only if `recency_ts` is within the lookback window. Returns
    `(sessions, warnings)`. Pure-ish: all logic delegates to the existing builders;
    only filesystem reads happen here.
    """
    now_iso = now_iso or _now_iso()
    now_ts = _parse_iso(now_iso).timestamp()
    sessions = []
    warnings = []
    for config_dir in config_dirs:
        projects_root = os.path.join(config_dir, "projects")
        if not os.path.isdir(projects_root):
            warnings.append("config dir has no projects/ subdir: %s" % config_dir)
            continue
        # Finding 5: an unreadable projects_root (passes isdir, fails listdir) must
        # warn and skip this config dir rather than crash the whole scan.
        try:
            project_names = sorted(os.listdir(projects_root))
        except OSError as e:
            warnings.append("failed to list projects dir %s: %s" % (projects_root, e))
            continue
        for project_name in project_names:
            project_dir = os.path.join(projects_root, project_name)
            if not os.path.isdir(project_dir):
                continue
            # Finding 5: likewise, a single unreadable project_dir is skipped with a
            # warning so other readable project dirs still scan.
            try:
                fnames = sorted(os.listdir(project_dir))
            except OSError as e:
                warnings.append("failed to list project dir %s: %s" % (project_dir, e))
                continue
            for fname in fnames:
                if not fname.endswith(".jsonl"):
                    continue
                if fname.startswith("agent-"):
                    continue  # subagent transcript, not a resumable session (§5.4)
                uuid = fname[: -len(".jsonl")]
                if not _UUID_RE.match(uuid):
                    continue
                jsonl_path = os.path.join(project_dir, fname)
                sidecar = os.path.join(project_dir, uuid)
                sidecar_dir = sidecar if os.path.isdir(sidecar) else None
                try:
                    mtime = os.path.getmtime(jsonl_path)
                except OSError:
                    warnings.append("could not stat session: %s" % jsonl_path)
                    continue
                records = _read_session(jsonl_path)
                record = build_session_record(
                    uuid=uuid,
                    config_dir=config_dir,
                    jsonl_path=jsonl_path,
                    sidecar_dir=sidecar_dir,
                    encoded_cwd_current=project_name,
                    records=records,
                    file_mtime_iso=_iso_from_mtime(mtime),
                )
                record["appears_running"] = _detect_running(
                    project_dir, uuid, mtime, now_ts, running_threshold_sec
                )
                if record["recency_ts"] is None:
                    warnings.append("session %s has no recency timestamp; skipped by lookback" % uuid)
                    continue
                # HIGH Fix 2: a corrupt recency_ts makes _parse_iso raise ValueError inside
                # within_lookback. Guard so one bad session is warned+skipped rather than
                # crashing the whole scan; OTHER valid sessions still return.
                try:
                    if not within_lookback(record["recency_ts"], now_iso, lookback_hours, since_iso):
                        continue
                except ValueError as e:
                    warnings.append(
                        "session %s has invalid recency timestamp %r: %s" % (uuid, record["recency_ts"], e)
                    )
                    continue
                sessions.append(record)
    return sessions, warnings


def _scan_envelope(
    config_dirs: list[str],
    sessions: list[dict[str, Any]],
    warnings: list[str],
    *,
    lookback_hours: float | None,
    since_iso: str | None,
    now_iso: str,
) -> dict[str, Any]:
    """Build the `scan` JSON envelope (design §4.1 collection)."""
    env = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso,
        "config_dirs": list(config_dirs),
        "sessions": sessions,
        "warnings": warnings,
    }
    if since_iso is not None:
        env["since"] = since_iso
    else:
        env["lookback_hours"] = lookback_hours
    return env


def build_plan(
    sessions: list[dict[str, Any]],
    *,
    worktrees_root: str,
    repos_root: str,
    branch_of: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Derive worktrees, group, and compute reorient candidates (design §4.4, Task 13).

    Enumerates on-disk worktree dirs, builds the branch index via real git (the
    injectable `branch_of` defaults to `_git_branch`), runs `derive_worktree`
    (Phase A) over each session, then `group_sessions` (Phase B + groups). Computes
    `reorient_candidates` per §4.4 (resolved, not running, and the current encoded
    project dir differs from BOTH the repo-subdir and workspace-root target
    encodings). Returns the plan body dict (caller adds the envelope fields).
    """
    if branch_of is None:
        branch_of = _git_branch
    dirs = enumerate_worktree_dirs(worktrees_root, repos_root)
    index = build_worktree_index(dirs, branch_of, worktrees_root)

    warnings = []
    for s in sessions:
        enrichment = derive_worktree(s, index)
        s.update(enrichment)
        if enrichment.get("warning"):
            warnings.append("session %s: %s" % (s["uuid"], enrichment["warning"]))

    group_records, sessions = group_sessions(sessions)

    reorient_candidates = []
    for s in sessions:
        if s.get("resolve_confidence") == "unresolved":
            continue
        if s.get("appears_running"):
            continue
        # MEDIUM Fix 1: encoded_cwd_current may be the STRIPPED form (no leading dash)
        # for older Claude sessions, while target_encodings always carry the canonical
        # leading-dash form from encode_cwd_literal. Normalize BOTH sides (strip leading
        # dashes) before comparison so an already-at-target session is not falsely flagged.
        current = s.get("encoded_cwd_current")
        current_norm = current.lstrip("-") if current else ""
        repo_dir = s.get("resolved_worktree_dir")
        ws_root = s.get("workspace_root_dir")
        target_encodings = set()
        if repo_dir:
            target_encodings.add(encode_cwd_literal(repo_dir).lstrip("-"))
        if ws_root:
            target_encodings.add(encode_cwd_literal(ws_root).lstrip("-"))
        # Something to move only if the current dir is not already a valid target (§4.4, I2).
        if target_encodings and current_norm not in target_encodings:
            reorient_candidates.append(s["uuid"])

    return {
        "sessions": sessions,
        "groups": group_records,
        "reorient_candidates": reorient_candidates,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Task 14: reorient executor (live + dry-run, journal rollback, history backup)
# ---------------------------------------------------------------------------
def _live_running(plan: dict[str, Any]) -> bool:
    """Live TOCTOU re-check of the §8.6 primary running signals for a MovePlan.

    Re-stats the SOURCE jsonl at move time: lock presence OR recent mtime (120s).
    Returns True if the session now appears running. Conservative: any stat error
    is treated as "not running" so a transient race does not block a legitimate move
    (collision is re-checked separately).
    """
    old_jsonl = plan.get("old_jsonl")
    old_project_dir = plan.get("old_project_dir")
    uuid = plan.get("uuid")
    if not old_jsonl or not old_project_dir:
        return False
    if _has_running_lock(old_project_dir, uuid):
        return True
    try:
        mtime = os.path.getmtime(old_jsonl)
    except OSError:
        return False
    now_ts = _parse_iso(_now_iso()).timestamp()
    return _recent_mtime(mtime, now_ts, 120)


def _live_collision(plan: dict[str, Any]) -> bool:
    """Live TOCTOU re-check for destination collision (design §8.8 M5)."""
    new_jsonl = plan.get("new_jsonl")
    new_sidecar = plan.get("new_sidecar")
    if new_jsonl and os.path.exists(new_jsonl):
        return True
    if new_sidecar and os.path.exists(new_sidecar):
        return True
    return False


def _rewrite_history(history_path: str, uuid_to_new: dict[str, str]) -> int:
    """Rewrite matching `project` lines in history.jsonl (design §8.7).

    `uuid_to_new`: {sessionId: new_literal_cwd}. CONFIRMED by the spike: the
    project-reference field is `project`, holding a LITERAL absolute cwd path, and
    each entry carries a unique `sessionId` (== the session UUID).

    MEDIUM Fix 1+2: match by `sessionId`, NOT the `project` path. Two sessions can
    share the same old literal cwd but reorient to DIFFERENT targets in one run;
    path-matching would clobber both lines with a single target. Keying on the
    unique `sessionId` rewrites each line to its OWN new cwd. Lines whose
    `sessionId` is not in the map are preserved verbatim (including non-JSON lines).
    Writes atomically via a temp file + rename in the same dir. Returns the count of
    rewritten lines.
    """
    out_lines = []
    rewritten = 0
    with open(history_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                out_lines.append(line)
                continue
            try:
                rec = json.loads(stripped)
                if not isinstance(rec, dict):
                    out_lines.append(line)  # preserve non-object JSON verbatim
                    continue
            except json.JSONDecodeError:
                out_lines.append(line)  # preserve unknown shapes verbatim
                continue
            sid = rec.get("sessionId")
            if sid in uuid_to_new:
                rec["project"] = uuid_to_new[sid]
                # MEDIUM Fix 2: preserve non-ASCII chars (don't \uXXXX-escape).
                out_lines.append(json.dumps(rec, ensure_ascii=False) + "\n")
                rewritten += 1
            else:
                out_lines.append(line)
    # HIGH Fix: a RELATIVE history_path has dirname "" -> mkstemp would fall back to
    # the system temp dir, risking a cross-device os.replace failure. Resolve to an
    # absolute path FIRST so the temp file lands in the SAME dir as the target, keeping
    # os.replace atomic and same-filesystem. Guard the fd against leaks on error.
    # MEDIUM Fix: use realpath (not abspath) so a SYMLINKED history_path is updated
    # via its real target file; replacing into the symlink path would clobber the link
    # with a regular file. realpath == abspath for non-symlink paths.
    abs_history_path = os.path.realpath(history_path)
    dir_name = os.path.dirname(abs_history_path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    # MEDIUM Fix: SPLIT the write phase from the file-ops phase so the fd is closed
    # exactly once on every path. The `with os.fdopen(fd)` already closes fd on success;
    # only the write-failure branch may need to close it (when fdopen itself raised
    # before taking ownership). The second block does copymode+replace with NO fd
    # handling — a failure there must NOT re-close the already-closed fd (double-close
    # race); it only cleans up the temp file.
    opened = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            opened = True
            out.writelines(out_lines)
    except Exception:
        if not opened:
            try:
                os.close(fd)
            except OSError:
                pass
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    try:
        # MEDIUM Fix: mkstemp creates the temp file 0o600, so os.replace would clobber
        # the original file's permissions. Copy the original mode onto the temp file
        # first so the rewritten history.jsonl keeps its prior permission bits.
        try:
            shutil.copymode(abs_history_path, tmp_path)
        except OSError:
            pass
        os.replace(tmp_path, abs_history_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    return rewritten


def execute_reorient(
    plans: list[dict[str, Any]],
    *,
    dry_run: bool,
    update_history: bool,
    now_stamp: str | None = None,
    sessions_by_uuid: dict[str, dict[str, Any]] | None = None,
    json_mode: bool = False,
) -> dict[str, Any]:
    """Execute (or preview) per-item reorientation moves (design §8.5-§8.10, Task 14).

    For each non-skipped MovePlan: re-check running-status and destination collision
    against LIVE fs IMMEDIATELY before moving (TOCTOU, §8.8 M5); skip-with-reason on
    a now-running/now-colliding item without aborting the batch. Move
    `<uuid>.jsonl` then the sibling `<uuid>/` sidecar (if present) into the dest dir
    (created if needed). NEVER overwrites an existing dest. Journal-based rollback on
    EXCEPTION: the in-process journal reverses completed ops (sidecar back, then
    jsonl back) and processing STOPS. NOT crash-safe vs SIGKILL between the two moves
    (design §8.10 M1).

    C3 — when `json_mode` is True, the dry-run path SUPPRESSES all human "DRY-RUN move:"
    prints (which would otherwise corrupt stdout that SKILL.md parses as JSON) and
    instead returns a structured `dry_run_moves` array on the summary. Each entry:
    {uuid, old, new, target, sidecar, collision, running}. The non-json dry-run path
    keeps the human prints and returns an empty `dry_run_moves`.

    `--update-history` (DEFAULT OFF) runs LAST, after all moves: back up
    `<config_dir>/history.jsonl` to a TIMESTAMPED `.backup.<stamp>` then rewrite the
    `project` field of each line whose `sessionId` matches a moved session's UUID,
    setting it to that session's new literal cwd (MEDIUM Fix 1+2 — keyed by
    sessionId, not the shared old cwd). The stamp is injectable via `now_stamp` (no
    hidden datetime.now() call in tests). A history failure leaves the file moves
    standing and is reported via `history_updated=False` plus a warning.

    Returns a JSON-able summary: moved[], skipped[], collisions[], rolled_back[],
    warnings[], history_updated.
    """
    sessions_by_uuid = sessions_by_uuid or {}
    moved = []
    skipped = []
    collisions = []
    warnings = []
    rolled_back = []
    history_updated = False

    # ---- dry-run: report every planned move, mutate NOTHING (design §8.9) ----
    if dry_run:
        dry_run_moves = []
        for plan in plans:
            if plan.get("skipped"):
                skipped.append(
                    {"uuid": plan["uuid"], "skip_reason": plan.get("skip_reason")}
                )
                if plan.get("collision"):
                    collisions.append({"uuid": plan["uuid"]})
                continue
            if json_mode:
                # C3: structured entry only; NO human print (keeps stdout pure JSON).
                dry_run_moves.append(
                    {
                        "uuid": plan.get("uuid"),
                        "old": plan.get("old_project_dir"),
                        "new": plan.get("new_project_dir"),
                        "target": plan.get("target_kind"),
                        "sidecar": plan.get("sidecar_present"),
                        "collision": plan.get("collision"),
                        "running": plan.get("running"),
                    }
                )
                continue
            print(
                "DRY-RUN move: config_dir=%s uuid=%s\n  old=%s\n  new=%s\n  target=%s sidecar=%s collision=%s running=%s"
                % (
                    plan.get("config_dir"),
                    plan.get("uuid"),
                    plan.get("old_project_dir"),
                    plan.get("new_project_dir"),
                    plan.get("target_kind"),
                    plan.get("sidecar_present"),
                    plan.get("collision"),
                    plan.get("running"),
                )
            )
            if update_history:
                session = sessions_by_uuid.get(plan["uuid"], {})
                old_cwd = session.get("launch_cwd")
                if old_cwd:
                    print("  history: project %s -> (target literal cwd)" % old_cwd)
        return {
            "moved": moved,
            "skipped": skipped,
            "collisions": collisions,
            "rolled_back": rolled_back,
            "warnings": warnings,
            "history_updated": history_updated,
            "dry_run_moves": dry_run_moves,
        }

    # ---- live: per-item TOCTOU re-check, move, journal rollback on exception ----
    # MEDIUM Fix 1+2: key the history rewrite map by sessionId (== uuid), NOT the old
    # literal cwd. Two moved sessions can share an old cwd but reorient to different
    # targets; cwd-keying would clobber both history lines with one target.
    history_uuids = {}  # config_dir -> {sessionId: new_literal_cwd}
    for plan in plans:
        if plan.get("skipped"):
            skipped.append({"uuid": plan["uuid"], "skip_reason": plan.get("skip_reason")})
            if plan.get("collision"):
                collisions.append({"uuid": plan["uuid"]})
            continue

        # TOCTOU re-checks against live fs (design §8.8 M5).
        if _live_running(plan):
            skipped.append({"uuid": plan["uuid"], "skip_reason": "running"})
            warnings.append("session %s started running before move; skipped" % plan["uuid"])
            continue
        if _live_collision(plan):
            collisions.append({"uuid": plan["uuid"]})
            skipped.append({"uuid": plan["uuid"], "skip_reason": "collision"})
            warnings.append("destination for %s now collides; skipped" % plan["uuid"])
            continue

        new_project_dir = plan["new_project_dir"]
        created_dir = not os.path.isdir(new_project_dir)
        journal = []  # list of (src, dst) completed moves, for reversal
        try:
            os.makedirs(new_project_dir, exist_ok=True)
            shutil.move(plan["old_jsonl"], plan["new_jsonl"])
            journal.append((plan["old_jsonl"], plan["new_jsonl"]))
            if plan.get("sidecar_present") and plan.get("old_sidecar") and plan.get("new_sidecar"):
                shutil.move(plan["old_sidecar"], plan["new_sidecar"])
                journal.append((plan["old_sidecar"], plan["new_sidecar"]))
        except Exception as exc:  # journal-based rollback (design §8.10)
            for src, dst in reversed(journal):
                try:
                    shutil.move(dst, src)
                except Exception:
                    warnings.append(
                        "IRREVERSIBLE: could not roll back %s -> %s during failure of %s"
                        % (dst, src, plan["uuid"])
                    )
            if created_dir:
                try:
                    os.rmdir(new_project_dir)
                except OSError:
                    pass
            rolled_back.append({"uuid": plan["uuid"], "error": str(exc)})
            warnings.append(
                "move failed for %s (%s); rolled back and STOPPED batch" % (plan["uuid"], exc)
            )
            break  # stop processing further items (design §8.10)

        # Record the history rewrite entry for the LAST-phase rewrite, keyed by the
        # session's UUID (== history.jsonl `sessionId`). MEDIUM Fix 1+2.
        session = sessions_by_uuid.get(plan["uuid"], {})
        target_dir = (
            session.get("workspace_root_dir")
            if plan.get("target_kind") == "workspace_root"
            else session.get("resolved_worktree_dir")
        )
        moved.append(
            {
                "uuid": plan["uuid"],
                "config_dir": plan["config_dir"],
                "old_jsonl": plan["old_jsonl"],
                "new_jsonl": plan["new_jsonl"],
                # C2: the literal dir this session was reoriented INTO. The launch step
                # uses this as the post-move cd-target via apply_reorient_launch_overrides
                # when invoked with --reorient-summary (Fix 2).
                "target_dir": target_dir,
            }
        )
        if target_dir:
            history_uuids.setdefault(plan["config_dir"], {})[plan["uuid"]] = target_dir

    # ---- history update: LAST, only if requested and only if moves stand ----
    if update_history and moved and not rolled_back:
        stamp = now_stamp or _now_iso()
        try:
            for config_dir, uuid_to_new in history_uuids.items():
                history_path = os.path.join(config_dir, "history.jsonl")
                if not os.path.exists(history_path):
                    warnings.append("history.jsonl not found; skipped: %s" % history_path)
                    continue
                backup_path = "%s.backup.%s" % (history_path, stamp)
                shutil.copy2(history_path, backup_path)
                _rewrite_history(history_path, uuid_to_new)
                history_updated = True
        except Exception as exc:
            history_updated = False
            warnings.append("history update failed (moves intact): %s" % exc)
    elif update_history and not moved:
        warnings.append("history update skipped: no successful moves")

    return {
        "moved": moved,
        "skipped": skipped,
        "collisions": collisions,
        "rolled_back": rolled_back,
        "warnings": warnings,
        "history_updated": history_updated,
    }


# ---------------------------------------------------------------------------
# Task 15: launch executor (Ghostty native via osascript)
# ---------------------------------------------------------------------------
def _run_osascript(script: str) -> subprocess.CompletedProcess[str]:
    """Write the AppleScript to a temp file and run it via `osascript` (design §9.1).

    Returns the CompletedProcess. On the macOS Automation-permission error
    (`-1743`) the caller surfaces TCC remediation (§9.7). Thin subprocess wrapper;
    not unit-tested (tests inject a stub runner instead).
    """
    fd, path = tempfile.mkstemp(suffix=".scpt")
    # MEDIUM Fix: SPLIT the write phase from the subprocess phase so the fd is closed
    # exactly once. The `with os.fdopen(fd)` closes fd on success; only the write-failure
    # branch may need to close it (when fdopen itself raised). The subprocess block does
    # NO fd handling — a prior `finally: os.close(fd)` double-closed the fd on EVERY
    # success. The finally here only removes the temp script.
    opened = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            opened = True
            fh.write(script)
    except Exception:
        if not opened:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.remove(path)
        except OSError:
            pass
        raise

    try:
        return subprocess.run(
            ["osascript", path], capture_output=True, text=True, check=False, timeout=15.0
        )
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def execute_launch(
    plan: dict[str, Any],
    *,
    dry_run: bool,
    default_config_dir: str,
    explicit_config_env: bool = False,
    run_osascript: Callable[[str], Any] | None = None,
    reorient_summary: dict[str, Any] | None = None,
    json_mode: bool = False,
) -> dict[str, Any]:
    """Render and (unless dry-run) run the Ghostty AppleScript for a plan (Task 15).

    Builds `sessions_by_uuid` from the plan, renders via `render_applescript`
    (which builds each pane command with `build_pane_command` — ALWAYS emitting the
    CLAUDE_CONFIG_DIR prefix for non-default config dirs). `--dry-run` prints the
    script and does NOT invoke osascript (the injectable `run_osascript` runner is
    NEVER called). Per design Decision B, emits a per-session WARNING for sessions
    whose config_dir != the ambient default OR whose origin cwd is missing on disk
    (they may not auto-resume). Returns {script, warnings, ran}.

    Fix 2 (same-run wiring): when `reorient_summary` is supplied (the summary returned
    by `execute_reorient` THIS run), `apply_reorient_launch_overrides` is called BEFORE
    rendering so every session actually moved this run cd's to its POST-MOVE target dir
    instead of its pre-move launch cd-target. Sessions not in the summary's `moved` keep
    the launch_cd_target derived from their current storage dir.

    When `json_mode` is True, the dry-run path SUPPRESSES the human `print(script)`
    (which would otherwise corrupt stdout that the caller emits as a JSON object) and
    instead leaves the rendered script in the returned `script` field for the caller to
    fold into its JSON payload. Mirrors `execute_reorient`'s json_mode contract.

    The implemented backend is Ghostty's native AppleScript API (Ghostty >= 1.2.0,
    confirmed against the 1.3.1 scripting dictionary). It requires one-time Automation
    (Apple Events) permission — NOT Accessibility — and does not depend on any Ghostty
    keybind. The gui/iTerm2 backends remain DEFERRED (see launch CLI handler / design
    §13.4); the native API has been stable since 1.2.0 but is new and could change in a
    future major.
    """
    if run_osascript is None:
        run_osascript = _run_osascript
    # Fix 2: apply same-run reorient overrides to launch cd-targets before rendering.
    if reorient_summary is not None:
        apply_reorient_launch_overrides(plan, reorient_summary)
    sessions_by_uuid = {s["uuid"]: s for s in plan.get("sessions", [])}
    groups = plan.get("groups", [])

    warnings = []
    for s in plan.get("sessions", []):
        config_dir = s.get("config_dir")
        if config_dir and config_dir != default_config_dir:
            warnings.append(
                "session %s lives under non-default config dir %s; it may not auto-resume "
                "if CLAUDE_CONFIG_DIR is not honored (design Decision B)"
                % (s["uuid"], config_dir)
            )
        # C2: the resume cd-target is launch_cd_target (launch_cwd, or the reorient
        # override), NOT open_dir; warn when THAT path is missing on disk.
        cd_target = s.get("launch_cd_target")
        if cd_target and not os.path.exists(cd_target):
            warnings.append(
                "session %s origin cwd missing on disk (%s); resume will fail until restored"
                % (s["uuid"], cd_target)
            )

    script = render_applescript(
        groups,
        sessions_by_uuid,
        default_config_dir=default_config_dir,
        explicit_config_env=explicit_config_env,
        warnings=warnings,
    )

    ran = False
    if dry_run:
        # Under json_mode the caller folds `script` into its JSON payload; printing it
        # here would prepend raw AppleScript to stdout and corrupt that JSON.
        if not json_mode:
            print(script)
    else:
        # `osascript` only exists on macOS; on other platforms the runner raises
        # FileNotFoundError. It may also fail with other OS errors (permissions) or
        # a TimeoutExpired (see _run_osascript timeout). Degrade gracefully with a
        # warning instead of propagating the exception (relaunch is macOS-only).
        try:
            result = run_osascript(script)
        except (OSError, subprocess.SubprocessError) as e:
            warnings.append(
                "Failed to run osascript: %s. Relaunching sessions is only supported on macOS." % e
            )
            ran = False
        else:
            ran = True
            # Surface TCC / automation-permission failure (-1743) with remediation (§9.7).
            if result is not None and getattr(result, "returncode", 0) != 0:
                stderr = getattr(result, "stderr", "") or ""
                if "-1743" in stderr or "Not authorized" in stderr or "not allowed" in stderr.lower():
                    warnings.append(
                        "osascript was not authorized to control Ghostty (-1743). Grant access in "
                        "System Settings -> Privacy & Security -> Automation, then re-run."
                    )
                else:
                    warnings.append("osascript failed: %s" % stderr.strip())

    return {"script": script, "warnings": warnings, "ran": ran}


# ---------------------------------------------------------------------------
# CLI subcommand handlers
# ---------------------------------------------------------------------------
def _expand(path: str) -> str:
    """Expand `~` and env vars in a path argument."""
    return os.path.expanduser(os.path.expandvars(path))


def _lookback_args(args: argparse.Namespace) -> tuple[float | None, str | None]:
    """Resolve mutually-exclusive lookback inputs to (lookback_hours, since_iso).

    `--since` wins when present (lookback_hours -> None); otherwise the
    `--lookback-hours` value is used. Keeps `within_lookback` from raising on the
    argparse default coexisting with an explicit `--since` (design §5.6, §11 M3).
    """
    if args.since is not None:
        return None, args.since
    return args.lookback_hours, None


def _emit(doc: dict[str, Any], out_path: str | None) -> None:
    """Write `doc` as JSON to `out_path` if given, else to stdout."""
    # MEDIUM Fix 5: preserve non-ASCII chars in emitted JSON.
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        print(text)


def _cmd_scan(args: argparse.Namespace) -> int:
    # I-scanplan-json: always-JSON; args.json is intentionally not consulted (no-op).
    config_dirs = [_expand(c) for c in (args.config_dir or ["~/.claude"])]
    now_iso = _now_iso()
    lookback_hours, since_iso = _lookback_args(args)
    sessions, warnings = scan_config_dirs(
        config_dirs,
        lookback_hours=lookback_hours,
        since_iso=since_iso,
        running_threshold_sec=args.running_threshold_sec,
        now_iso=now_iso,
    )
    env = _scan_envelope(
        config_dirs,
        sessions,
        warnings,
        lookback_hours=lookback_hours,
        since_iso=since_iso,
        now_iso=now_iso,
    )
    _emit(env, args.out)
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    # I-scanplan-json: always-JSON; args.json is intentionally not consulted (no-op).
    config_dirs = [_expand(c) for c in (args.config_dir or ["~/.claude"])]
    now_iso = _now_iso()
    lookback_hours, since_iso = _lookback_args(args)
    if args.infile:
        with open(args.infile, "r", encoding="utf-8") as fh:
            scan_doc = json.load(fh)
        sessions = scan_doc.get("sessions", [])
        warnings = list(scan_doc.get("warnings", []))
        config_dirs = scan_doc.get("config_dirs", config_dirs)
    else:
        sessions, warnings = scan_config_dirs(
            config_dirs,
            lookback_hours=lookback_hours,
            since_iso=since_iso,
            running_threshold_sec=args.running_threshold_sec,
            now_iso=now_iso,
        )
    body = build_plan(
        sessions,
        worktrees_root=_expand(args.worktrees_root),
        repos_root=_expand(args.repos_root),
    )
    env = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso,
        "config_dirs": list(config_dirs),
        "sessions": body["sessions"],
        "groups": body["groups"],
        "reorient_candidates": body["reorient_candidates"],
        "warnings": warnings + body["warnings"],
    }
    if since_iso is not None:
        env["since"] = since_iso
    else:
        env["lookback_hours"] = lookback_hours
    _emit(env, args.out)
    return 0


def _cmd_reorient(args: argparse.Namespace) -> int:
    with open(args.decisions, "r", encoding="utf-8") as fh:
        decisions = json.load(fh)
    if args.plan:
        with open(args.plan, "r", encoding="utf-8") as fh:
            plan_doc = json.load(fh)
    else:
        config_dirs = [_expand(c) for c in (args.config_dir or ["~/.claude"])]
        lookback_hours, since_iso = _lookback_args(args)
        sessions, _w = scan_config_dirs(
            config_dirs,
            lookback_hours=lookback_hours,
            since_iso=since_iso,
            running_threshold_sec=120,
            now_iso=_now_iso(),
        )
        plan_doc = build_plan(
            sessions,
            worktrees_root=_expand(args.worktrees_root),
            repos_root=_expand(args.repos_root),
        )
    sessions_by_uuid = {s["uuid"]: s for s in plan_doc.get("sessions", [])}
    move_plans = build_reorient_plan(sessions_by_uuid, decisions, os.path.exists)
    summary = execute_reorient(
        move_plans,
        dry_run=args.dry_run,
        update_history=args.update_history,
        sessions_by_uuid=sessions_by_uuid,
        json_mode=args.json,  # C3: suppress human dry-run prints so stdout is pure JSON
    )
    # Fix 2: persist the canonical summary so the launch step can consume it via
    # --reorient-summary (same-run cd-target override without a re-scan).
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        # Match the launch command: surface skipped-move / collision / history
        # warnings to stderr in non-JSON mode instead of silently dropping them.
        for w in summary.get("warnings", []):
            sys.stderr.write("WARNING: " + w + "\n")
    return 0


def _cmd_launch(args: argparse.Namespace) -> int:
    if args.launch_mode != "native" or args.terminal != "ghostty":
        # gui / iTerm2 fallback is DEFERRED (design §9.6, §13.4). No working fallback yet.
        sys.stderr.write(
            "launch-mode=%s terminal=%s not implemented; see design §13.4 limitation. "
            "Only the Ghostty native AppleScript backend is implemented (Ghostty >= 1.2.0, "
            "Automation permission). The gui/iTerm2 backends remain deferred.\n"
            % (args.launch_mode, args.terminal)
        )
        return 2
    with open(args.plan, "r", encoding="utf-8") as fh:
        plan_doc = json.load(fh)
    default_config_dir = _expand(args.default_config_dir)
    # Fix 2: when a reorient ran THIS run, its summary points moved sessions at their
    # post-move dirs so resume cd's to the new storage location without a re-scan.
    reorient_summary = None
    if args.reorient_summary:
        with open(args.reorient_summary, "r", encoding="utf-8") as fh:
            reorient_summary = json.load(fh)
    result = execute_launch(
        plan_doc,
        dry_run=args.print_script,
        default_config_dir=default_config_dir,
        explicit_config_env=args.explicit_config_env,
        reorient_summary=reorient_summary,
        json_mode=args.json,  # suppress execute_launch's raw script print so stdout is pure JSON
    )
    if args.json:
        # JSON mode: execute_launch suppressed its human script print (json_mode), so
        # stdout is a single parseable JSON object. Under --print-script, fold the
        # rendered AppleScript into the payload instead of dumping it raw.
        out = {"warnings": result["warnings"], "ran": result["ran"]}
        if args.print_script:
            out["script"] = result["script"]
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        # Non-JSON mode: under --print-script the script was already printed by
        # execute_launch (json_mode False); surface warnings on stderr either way.
        for w in result["warnings"]:
            sys.stderr.write("WARNING: " + w + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: scan / plan / reorient / launch (design §11)."""
    parser = argparse.ArgumentParser(description="Round up scattered Claude Code worktree sessions.")
    sub = parser.add_subparsers(dest="command")

    # scan
    p_scan = sub.add_parser("scan", help="Discover sessions in config dirs within lookback.")
    p_scan.add_argument("--config-dir", action="append", help="Config dir (repeatable). Default ~/.claude.")
    p_scan.add_argument("--lookback-hours", type=float, default=72.0)
    p_scan.add_argument("--since", default=None, help="ISO-8601 cutoff (mutually exclusive with --lookback-hours).")
    p_scan.add_argument("--running-threshold-sec", type=float, default=120.0)
    # I-scanplan-json: scan ALWAYS emits JSON; --json is a documented no-op accepted
    # for SKILL.md invocation symmetry. (No human-table mode is provided.)
    p_scan.add_argument("--json", action="store_true", help="No-op; scan always emits JSON.")
    p_scan.add_argument("--out", default=None)
    p_scan.set_defaults(func=_cmd_scan)

    # plan
    p_plan = sub.add_parser("plan", help="Derive worktrees + group; emit plan envelope.")
    p_plan.add_argument("--config-dir", action="append")
    p_plan.add_argument("--in", dest="infile", default=None, help="Scan-output JSON to plan from.")
    p_plan.add_argument("--lookback-hours", type=float, default=72.0)
    p_plan.add_argument("--since", default=None)
    p_plan.add_argument("--running-threshold-sec", type=float, default=120.0)
    p_plan.add_argument("--worktrees-root", default="~/Development/worktrees")
    p_plan.add_argument("--repos-root", default="~/Development")
    # I-scanplan-json: plan ALWAYS emits JSON; --json is a documented no-op accepted
    # for SKILL.md invocation symmetry. (No human-table mode is provided.)
    p_plan.add_argument("--json", action="store_true", help="No-op; plan always emits JSON.")
    p_plan.add_argument("--out", default=None)
    p_plan.set_defaults(func=_cmd_plan)

    # reorient
    p_reorient = sub.add_parser("reorient", help="Execute (or preview) per-item moves.")
    p_reorient.add_argument("--decisions", required=True, help="Decisions JSON array.")
    p_reorient.add_argument("--plan", default=None, help="Plan JSON (provides sessions_by_uuid).")
    p_reorient.add_argument("--config-dir", action="append")
    p_reorient.add_argument("--lookback-hours", type=float, default=72.0)
    p_reorient.add_argument("--since", default=None)
    p_reorient.add_argument("--worktrees-root", default="~/Development/worktrees")
    p_reorient.add_argument("--repos-root", default="~/Development")
    p_reorient.add_argument("--dry-run", action="store_true")
    p_reorient.add_argument(
        "--update-history",
        dest="update_history",
        action="store_true",
        default=False,
        help="Rewrite history.jsonl project lines (DEFAULT OFF; design §8.7).",
    )
    p_reorient.add_argument("--no-update-history", dest="update_history", action="store_false")
    p_reorient.add_argument("--json", action="store_true")
    p_reorient.add_argument(
        "--summary-out",
        dest="summary_out",
        default=None,
        help="Write the reorient summary JSON here for `launch --reorient-summary` (Fix 2).",
    )
    p_reorient.set_defaults(func=_cmd_reorient)

    # launch
    p_launch = sub.add_parser("launch", help="Generate + run the Ghostty AppleScript.")
    p_launch.add_argument("--plan", required=True, help="Plan JSON.")
    p_launch.add_argument("--launch-mode", choices=["native", "gui"], default="native")
    p_launch.add_argument("--terminal", choices=["ghostty", "iterm2"], default="ghostty")
    p_launch.add_argument("--explicit-config-env", action="store_true")
    p_launch.add_argument("--default-config-dir", default="~/.claude")
    p_launch.add_argument("--print-script", action="store_true", help="Dump AppleScript; do NOT run osascript.")
    p_launch.add_argument(
        "--reorient-summary",
        dest="reorient_summary",
        default=None,
        help="Reorient summary JSON from this run; cd reoriented sessions to their new dir (Fix 2).",
    )
    p_launch.add_argument("--json", action="store_true")
    p_launch.set_defaults(func=_cmd_launch)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
