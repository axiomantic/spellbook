#!/usr/bin/env python3
"""
branch-context.py - Detect merge target, merge base, and show branch work.
Cross-platform implementation of branch-context.sh.
"""

import json
import os
import subprocess
import sys
from typing import List


def run_git(args: List[str]) -> str:
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(["git"] + args, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def emit_lines(text: str) -> None:
    """Print a newline-separated list, emitting nothing at all when empty.

    `print("")` writes a bare newline; the shell implementation writes zero
    bytes. A consumer that splits on newlines would see one phantom entry.
    """
    if text:
        print(text)


def git_ok(args: list[str]) -> bool:
    """Run a git command and report whether it succeeded."""
    try:
        subprocess.run(["git"] + args, capture_output=True, text=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def run_gh(args: List[str]) -> str:
    """Run a gh command and return stdout."""
    try:
        result = subprocess.run(["gh"] + args, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def parse_args(argv: List[str]) -> tuple[str, str]:
    """Parse ``[subcommand] [--base <ref>]`` into ``(subcommand, base_override)``.

    Mirrors the shell implementation's hand-rolled parser exactly, including the
    exit code (2) for a malformed invocation.
    """
    subcommand = ""
    base_override = ""
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--base":
            if i + 1 >= len(argv) or not argv[i + 1]:
                print("ERROR: --base requires a ref argument", file=sys.stderr)
                sys.exit(2)
            base_override = argv[i + 1]
            i += 2
        elif arg.startswith("--base="):
            base_override = arg[len("--base=") :]
            if not base_override:
                print("ERROR: --base requires a ref argument", file=sys.stderr)
                sys.exit(2)
            i += 1
        else:
            if subcommand:
                print(f"ERROR: unexpected argument: {arg}", file=sys.stderr)
                sys.exit(2)
            subcommand = arg
            i += 1
    return subcommand or "summary", base_override


def main():
    cmd, base_override = parse_args(sys.argv[1:])

    # --- Detect worktree vs main repo ---
    git_dir = run_git(["rev-parse", "--git-dir"])
    toplevel = run_git(["rev-parse", "--show-toplevel"])
    is_worktree = ".git/worktrees/" in git_dir.replace("\\", "/")

    current_branch = run_git(["branch", "--show-current"])
    detached_head = False
    if not current_branch:
        # Detached HEAD - defined behavior: no branch identity, so PR and upstream
        # detection are both skipped. We fall through to remote HEAD and SAY so.
        detached_head = True
        current_branch = run_git(["rev-parse", "--short", "HEAD"])

    # --- Remote preference (deterministic and documented) ---
    # In a fork setup the parent repo is conventionally `upstream`; prefer it so the
    # merge base is computed against the parent's default branch, not the fork's.
    base_remote = ""
    for candidate in ("upstream", "origin"):
        if git_ok(["remote", "get-url", candidate]):
            base_remote = candidate
            break
    if not base_remote:
        remotes = run_git(["remote"]).splitlines()
        base_remote = remotes[0].strip() if remotes else ""

    # --- Detect merge target (priority order) ---
    merge_target = ""
    pr_url = ""
    # How the merge target was resolved. One of:
    #   pr-base-ref | upstream-tracking | remote-head | fallback-literal
    #   explicit-override (when --base is supplied)
    resolution_method = ""

    # 0. Explicit override. Detection is skipped ENTIRELY and reported as such.
    if base_override:
        merge_target = base_override
        resolution_method = "explicit-override"

    # 1. Try PR base ref.
    #
    # Hardening: `gh pr view <branch>` matches on head-branch NAME and can resolve to
    # the wrong PR in fork and multi-remote setups (another repo, or a same-named
    # branch on a different head repo). We therefore ask for the head ref back and
    # REJECT any PR whose headRefName does not equal the branch we are actually on.
    # Detached HEAD has no branch identity at all, so gh is skipped entirely.
    if not merge_target and not detached_head:
        pr_json_str = run_gh(
            ["pr", "view", current_branch, "--json", "baseRefName,url,headRefName"]
        )
        if pr_json_str:
            try:
                pr_data = json.loads(pr_json_str)
                if pr_data.get("headRefName", "") == current_branch:
                    merge_target = pr_data.get("baseRefName", "")
                    pr_url = pr_data.get("url", "")
                    if merge_target:
                        resolution_method = "pr-base-ref"
            except json.JSONDecodeError:
                pass

    # 2. Fallback: upstream tracking branch
    if not merge_target and not detached_head:
        merge_target = run_git(["config", f"branch.{current_branch}.merge"]).replace(
            "refs/heads/", ""
        )
        if merge_target:
            resolution_method = "upstream-tracking"

    # 3. Fallback: remote default branch (master or main - never assumed)
    if not merge_target and base_remote:
        symref = run_git(["symbolic-ref", "--quiet", "--short", f"refs/remotes/{base_remote}/HEAD"])
        # The shell strips a leading `<remote>/` with sed and passes an
        # unprefixed value through unchanged. Requiring the prefix here would
        # diverge on an unusual symref, so mirror the sed exactly.
        prefix = f"{base_remote}/"
        merge_target = symref[len(prefix) :] if symref.startswith(prefix) else symref
        if not merge_target:
            remote_info = run_git(["remote", "show", base_remote])
            for line in remote_info.splitlines():
                if "HEAD branch" in line:
                    merge_target = line.split(":")[-1].strip()
                    break
        if merge_target:
            resolution_method = "remote-head"

    # 4. Last-ditch literal. This is a GUESS and is reported as one.
    if not merge_target:
        for candidate in ("main", "master"):
            if git_ok(["rev-parse", "--verify", "--quiet", f"refs/heads/{candidate}"]) or git_ok(
                [
                    "rev-parse",
                    "--verify",
                    "--quiet",
                    f"refs/remotes/{base_remote}/{candidate}",
                ]
            ):
                merge_target = candidate
                break
        if not merge_target:
            merge_target = "main"
        resolution_method = "fallback-literal"

    # --- Fetch before computing the merge base ---
    # Nothing computes a base against a stale ref. Non-fatal: a network failure
    # degrades to the local ref, and the degradation is REPORTED, never silent.
    if os.environ.get("SPELLBOOK_BRANCH_CONTEXT_NO_FETCH") == "1":
        fetch_status = "skipped (SPELLBOOK_BRANCH_CONTEXT_NO_FETCH=1)"
    elif base_override:
        # An override may name a local-only ref or a sha; fetching it is not meaningful.
        fetch_status = "skipped (--base override)"
    elif base_remote:
        if git_ok(["fetch", "--quiet", base_remote, merge_target]):
            fetch_status = "ok"
        else:
            fetch_status = "FAILED (offline or no such ref) - merge base may be STALE"
    else:
        fetch_status = "skipped (no remote configured)"

    # --- Compute merge base ---
    # Try <remote>/<target> first (more up-to-date), fall back to local ref
    if base_override:
        base_ref = base_override
    else:
        base_ref = f"{base_remote}/{merge_target}" if base_remote else merge_target
    merge_base = run_git(["merge-base", "HEAD", base_ref])
    if not merge_base:
        base_ref = merge_target
        merge_base = run_git(["merge-base", "HEAD", base_ref])

    if not merge_base:
        print(
            f"ERROR: Could not compute merge base between HEAD and {merge_target}",
            file=sys.stderr,
        )
        print(
            f"       (remote={base_remote or 'none'}, resolution={resolution_method}, "
            f"fetch={fetch_status})",
            file=sys.stderr,
        )
        sys.exit(1)

    def resolution_banner() -> None:
        """Print base-resolution provenance to stderr.

        Emitted for every non-summary subcommand so a consumer that only captures
        stdout (a diff, a file list) still SEES which base was used and how it was
        resolved. Silent fallback is the failure this script exists to prevent.
        """
        print(f"base-ref:       {base_ref}", file=sys.stderr)
        print(f"merge-target:   {merge_target}", file=sys.stderr)
        print(f"resolved-via:   {resolution_method}", file=sys.stderr)
        print(f"remote:         {base_remote or 'none'}", file=sys.stderr)
        print(f"fetch:          {fetch_status}", file=sys.stderr)
        print(f"merge-base:     {merge_base}", file=sys.stderr)
        if detached_head:
            print(
                "WARNING:        detached HEAD - no branch identity; PR/upstream detection skipped",
                file=sys.stderr,
            )
        if resolution_method == "fallback-literal":
            print(
                "WARNING:        merge target was GUESSED (last-ditch literal), not detected",
                file=sys.stderr,
            )

    if cmd == "diff":
        resolution_banner()
        subprocess.run(["git", "diff", merge_base])
    elif cmd == "diff-committed":
        resolution_banner()
        subprocess.run(["git", "diff", f"{merge_base}..HEAD"])
    elif cmd == "diff-uncommitted":
        subprocess.run(["git", "diff", "HEAD"])
    elif cmd == "log":
        resolution_banner()
        subprocess.run(["git", "log", "--oneline", f"{merge_base}..HEAD"])
    elif cmd == "stat":
        resolution_banner()
        subprocess.run(["git", "diff", "--stat", merge_base])
    elif cmd == "stat-committed":
        resolution_banner()
        subprocess.run(["git", "diff", "--stat", f"{merge_base}..HEAD"])
    elif cmd == "files":
        resolution_banner()
        # An empty list must emit ZERO bytes, matching the shell. `print("")`
        # emits a bare newline, and a consumer doing `.split("\n")` then sees
        # one phantom filename -- a coverage manifest of one nonexistent file.
        emit_lines(run_git(["diff", "--name-only", merge_base]))
    elif cmd == "files-committed":
        # Pairs with `diff-committed`. Building a coverage manifest from `files`
        # while reading `diff-committed` lets a review certify N-of-N files
        # against an empty diff.
        resolution_banner()
        emit_lines(run_git(["diff", "--name-only", f"{merge_base}..HEAD"]))
    elif cmd == "base":
        resolution_banner()
        print(merge_base)
    elif cmd == "target":
        resolution_banner()
        print(merge_target)
    elif cmd == "resolution":
        print(f"base_ref={base_ref}")
        print(f"merge_target={merge_target}")
        print(f"resolved_via={resolution_method}")
        print(f"remote={base_remote or 'none'}")
        print(f"fetch={fetch_status}")
        print(f"merge_base={merge_base}")
        print(f"detached_head={str(detached_head).lower()}")
    elif cmd == "summary":
        files_changed = run_git(["diff", "--name-only", merge_base]).splitlines()
        commits_count = run_git(["rev-list", "--count", f"{merge_base}..HEAD"])

        print(f"Branch:        {current_branch}")
        print(f"Merge target:  {merge_target}")
        print(f"Resolved via:  {resolution_method}")
        print(f"Base ref:      {base_ref}")
        print(f"Remote:        {base_remote or 'none'}")
        print(f"Fetch:         {fetch_status}")
        print(f"Merge base:    {merge_base[:12]}")
        if pr_url:
            print(f"PR:            {pr_url}")
        if detached_head:
            print("WARNING:       detached HEAD - PR/upstream detection skipped")
        if resolution_method == "fallback-literal":
            print("WARNING:       merge target GUESSED (last-ditch literal), not detected")
        if is_worktree:
            print(f"Worktree:      {toplevel}")
        print(f"Commits:       {commits_count}")
        print(f"Files changed: {len(files_changed)}")

        staged = run_git(["diff", "--cached", "--name-only"]).splitlines()
        unstaged = run_git(["diff", "--name-only"]).splitlines()
        untracked = run_git(["ls-files", "--others", "--exclude-standard"]).splitlines()

        if staged or unstaged or untracked:
            print(
                f"Uncommitted:   {len(staged)} staged, {len(unstaged)} unstaged, {len(untracked)} untracked"
            )
        else:
            print("Working tree:  clean")
    elif cmd == "json":
        staged = run_git(["diff", "--cached", "--name-only"]).splitlines()
        unstaged = run_git(["diff", "--name-only"]).splitlines()
        untracked = run_git(["ls-files", "--others", "--exclude-standard"]).splitlines()
        files_changed = run_git(["diff", "--name-only", merge_base]).splitlines()
        files_changed_committed = run_git(
            ["diff", "--name-only", f"{merge_base}..HEAD"]
        ).splitlines()
        commits_count = int(run_git(["rev-list", "--count", f"{merge_base}..HEAD"]) or 0)

        data = {
            "branch": current_branch,
            "merge_target": merge_target,
            "merge_base": merge_base,
            "base_ref": base_ref,
            "resolved_via": resolution_method,
            "remote": base_remote or None,
            "fetch": fetch_status,
            "detached_head": detached_head,
            "pr_url": pr_url or None,
            "is_worktree": is_worktree,
            "toplevel": toplevel,
            "commits": commits_count,
            "files_changed": len(files_changed),
            "files_changed_committed": len(files_changed_committed),
            "staged": len(staged),
            "unstaged": len(unstaged),
            "untracked": len(untracked),
        }
        print(json.dumps(data, indent=2))
    else:
        print(
            f"Usage: {sys.argv[0]} [summary|diff|diff-committed|diff-uncommitted|log|"
            "stat|stat-committed|files|files-committed|base|target|resolution|json]"
            " [--base <ref>]"
        )
        print()
        print("Options:")
        print("  --base <ref>  Skip detection; use <ref> as the merge target")
        print("                (reported as resolved_via=explicit-override)")
        print()
        print("Endpoint selection (choose by TASK, not by habit):")
        print("  reviewing what will merge                    -> files-committed + diff-committed")
        print("  describing the branch (PR body, changelog)   -> files + diff")
        print("  pre-commit self-review                       -> files + diff")
        print()
        print("Env:")
        print("  SPELLBOOK_BRANCH_CONTEXT_NO_FETCH=1  Skip the pre-merge-base fetch (offline)")
        sys.exit(1)


if __name__ == "__main__":
    main()
