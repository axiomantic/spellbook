#!/usr/bin/env python3
"""
branch-context.py - Detect merge target, merge base, and show branch work.
Cross-platform implementation of branch-context.sh.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def run_git(args: List[str]) -> str:
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def run_gh(args: List[str]) -> str:
    """Run a gh command and return stdout."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def main():
    # --- Detect worktree vs main repo ---
    git_dir = run_git(["rev-parse", "--git-dir"])
    toplevel = run_git(["rev-parse", "--show-toplevel"])
    is_worktree = ".git/worktrees/" in git_dir.replace("\\", "/")

    current_branch = run_git(["branch", "--show-current"])
    if not current_branch:
        # Detached HEAD - use commit hash
        current_branch = run_git(["rev-parse", "--short", "HEAD"])

    # --- Detect merge target (priority order) ---
    merge_target = ""
    pr_url = ""

    # 1. Try PR base ref
    pr_json_str = run_gh(["pr", "view", current_branch, "--json", "baseRefName,url"])
    if pr_json_str:
        try:
            pr_data = json.loads(pr_json_str)
            merge_target = pr_data.get("baseRefName", "")
            pr_url = pr_data.get("url", "")
        except json.JSONDecodeError:
            pass

    # 2. Fallback: upstream tracking branch
    if not merge_target:
        merge_target = run_git(["config", f"branch.{current_branch}.merge"]).replace("refs/heads/", "")

    # 3. Fallback: remote default branch
    if not merge_target:
        remote_info = run_git(["remote", "show", "origin"])
        for line in remote_info.splitlines():
            if "HEAD branch" in line:
                merge_target = line.split(":")[-1].strip()
                break
        if not merge_target:
            merge_target = "main"

    # --- Compute merge base ---
    merge_base = run_git(["merge-base", "HEAD", f"origin/{merge_target}"])
    if not merge_base:
        merge_base = run_git(["merge-base", "HEAD", merge_target])

    if not merge_base:
        print(f"ERROR: Could not compute merge base between HEAD and {merge_target}", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"

    if cmd == "diff":
        subprocess.run(["git", "diff", merge_base])
    elif cmd == "diff-committed":
        subprocess.run(["git", "diff", f"{merge_base}..HEAD"])
    elif cmd == "diff-uncommitted":
        subprocess.run(["git", "diff", "HEAD"])
    elif cmd == "log":
        subprocess.run(["git", "log", "--oneline", f"{merge_base}..HEAD"])
    elif cmd == "stat":
        subprocess.run(["git", "diff", "--stat", merge_base])
    elif cmd == "files":
        print(run_git(["diff", "--name-only", merge_base]))
    elif cmd == "base":
        print(merge_base)
    elif cmd == "target":
        print(merge_target)
    elif cmd == "summary":
        files_changed = run_git(["diff", "--name-only", merge_base]).splitlines()
        commits_count = run_git(["rev-list", "--count", f"{merge_base}..HEAD"])
        
        print(f"Branch:        {current_branch}")
        print(f"Merge target:  {merge_target}")
        print(f"Merge base:    {merge_base[:12]}")
        if pr_url:
            print(f"PR:            {pr_url}")
        if is_worktree:
            print(f"Worktree:      {toplevel}")
        print(f"Commits:       {commits_count}")
        print(f"Files changed: {len(files_changed)}")
        
        staged = run_git(["diff", "--cached", "--name-only"]).splitlines()
        unstaged = run_git(["diff", "--name-only"]).splitlines()
        untracked = run_git(["ls-files", "--others", "--exclude-standard"]).splitlines()
        
        if staged or unstaged or untracked:
            print(f"Uncommitted:   {len(staged)} staged, {len(unstaged)} unstaged, {len(untracked)} untracked")
        else:
            print("Working tree:  clean")
    elif cmd == "json":
        staged = run_git(["diff", "--cached", "--name-only"]).splitlines()
        unstaged = run_git(["diff", "--name-only"]).splitlines()
        untracked = run_git(["ls-files", "--others", "--exclude-standard"]).splitlines()
        files_changed = run_git(["diff", "--name-only", merge_base]).splitlines()
        commits_count = int(run_git(["rev-list", "--count", f"{merge_base}..HEAD"]) or 0)
        
        data = {
            "branch": current_branch,
            "merge_target": merge_target,
            "merge_base": merge_base,
            "pr_url": pr_url or None,
            "is_worktree": is_worktree,
            "toplevel": toplevel,
            "commits": commits_count,
            "files_changed": len(files_changed),
            "staged": len(staged),
            "unstaged": len(unstaged),
            "untracked": len(untracked)
        }
        print(json.dumps(data, indent=2))
    else:
        print(f"Usage: {sys.argv[0]} [summary|diff|diff-committed|diff-uncommitted|log|stat|files|base|target|json]")
        sys.exit(1)


if __name__ == "__main__":
    main()
