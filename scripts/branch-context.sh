#!/usr/bin/env bash
# branch-context.sh - Detect merge target, merge base, and show branch work
# Handles worktrees, stacked branches, uncommitted/unstaged changes.
set -euo pipefail

# --- Detect worktree vs main repo ---
GIT_DIR=$(git rev-parse --git-dir 2>/dev/null)
TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null)
IS_WORKTREE=false
if [[ "$GIT_DIR" == *".git/worktrees/"* ]]; then
  IS_WORKTREE=true
fi

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [[ -z "$CURRENT_BRANCH" ]]; then
  # Detached HEAD - use commit hash
  CURRENT_BRANCH=$(git rev-parse --short HEAD)
fi

# --- Detect merge target (priority order) ---
MERGE_TARGET=""
PR_URL=""

# 1. Try PR base ref (most reliable for stacked branches)
if command -v gh &>/dev/null; then
  PR_JSON=$(gh pr view "$CURRENT_BRANCH" --json baseRefName,url 2>/dev/null || echo "")
  if [[ -n "$PR_JSON" ]]; then
    MERGE_TARGET=$(echo "$PR_JSON" | jq -r '.baseRefName // empty' 2>/dev/null || echo "")
    PR_URL=$(echo "$PR_JSON" | jq -r '.url // empty' 2>/dev/null || echo "")
  fi
fi

# 2. Fallback: upstream tracking branch
if [[ -z "$MERGE_TARGET" ]]; then
  MERGE_TARGET=$(git config "branch.${CURRENT_BRANCH}.merge" 2>/dev/null | sed 's|refs/heads/||' || echo "")
fi

# 3. Fallback: remote default branch (usually master or main)
if [[ -z "$MERGE_TARGET" ]]; then
  MERGE_TARGET=$(git remote show origin 2>/dev/null | grep 'HEAD branch' | awk '{print $NF}' || echo "master")
fi

# --- Compute merge base ---
# Try origin/<target> first (more up-to-date), fall back to local ref
MERGE_BASE=$(git merge-base HEAD "origin/${MERGE_TARGET}" 2>/dev/null \
  || git merge-base HEAD "$MERGE_TARGET" 2>/dev/null \
  || echo "")

if [[ -z "$MERGE_BASE" ]]; then
  echo "ERROR: Could not compute merge base between HEAD and $MERGE_TARGET" >&2
  exit 1
fi

# --- Subcommands ---
case "${1:-summary}" in
  diff)
    # Full diff: merge base to working tree (includes committed + staged + unstaged)
    git diff "$MERGE_BASE"
    ;;
  diff-committed)
    # Only committed changes (merge base to HEAD)
    git diff "$MERGE_BASE"..HEAD
    ;;
  diff-uncommitted)
    # Only uncommitted changes (staged + unstaged relative to HEAD)
    git diff HEAD
    ;;
  log)
    git log --oneline "$MERGE_BASE"..HEAD
    ;;
  stat)
    # Full stat: merge base to working tree
    git diff --stat "$MERGE_BASE"
    ;;
  files)
    # All changed files: merge base to working tree
    git diff --name-only "$MERGE_BASE"
    ;;
  base)
    echo "$MERGE_BASE"
    ;;
  target)
    echo "$MERGE_TARGET"
    ;;
  summary)
    echo "Branch:        $CURRENT_BRANCH"
    echo "Merge target:  $MERGE_TARGET"
    echo "Merge base:    $(echo "$MERGE_BASE" | cut -c1-12)"
    [[ -n "$PR_URL" ]] && echo "PR:            $PR_URL"
    $IS_WORKTREE && echo "Worktree:      $TOPLEVEL"
    echo "Commits:       $(git rev-list --count "$MERGE_BASE"..HEAD)"
    echo "Files changed: $(git diff --name-only "$MERGE_BASE" | wc -l | tr -d ' ')"
    # Show uncommitted state
    STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
    UNSTAGED=$(git diff --name-only | wc -l | tr -d ' ')
    UNTRACKED=$(git ls-files --others --exclude-standard | wc -l | tr -d ' ')
    if [[ "$STAGED" -gt 0 || "$UNSTAGED" -gt 0 || "$UNTRACKED" -gt 0 ]]; then
      echo "Uncommitted:   ${STAGED} staged, ${UNSTAGED} unstaged, ${UNTRACKED} untracked"
    else
      echo "Working tree:  clean"
    fi
    ;;
  json)
    # Machine-readable output
    STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
    UNSTAGED=$(git diff --name-only | wc -l | tr -d ' ')
    UNTRACKED=$(git ls-files --others --exclude-standard | wc -l | tr -d ' ')
    jq -n \
      --arg branch "$CURRENT_BRANCH" \
      --arg target "$MERGE_TARGET" \
      --arg base "$MERGE_BASE" \
      --arg pr "$PR_URL" \
      --argjson worktree "$IS_WORKTREE" \
      --arg toplevel "$TOPLEVEL" \
      --argjson commits "$(git rev-list --count "$MERGE_BASE"..HEAD)" \
      --argjson files "$(git diff --name-only "$MERGE_BASE" | wc -l | tr -d ' ')" \
      --argjson staged "$STAGED" \
      --argjson unstaged "$UNSTAGED" \
      --argjson untracked "$UNTRACKED" \
      '{
        branch: $branch,
        merge_target: $target,
        merge_base: $base,
        pr_url: (if $pr == "" then null else $pr end),
        is_worktree: $worktree,
        toplevel: $toplevel,
        commits: $commits,
        files_changed: $files,
        staged: $staged,
        unstaged: $unstaged,
        untracked: $untracked
      }'
    ;;
  *)
    echo "Usage: branch-context.sh [summary|diff|diff-committed|diff-uncommitted|log|stat|files|base|target|json]"
    echo ""
    echo "  summary          Branch info, merge target, and change stats (default)"
    echo "  diff             Full diff: merge base to working tree (committed + uncommitted)"
    echo "  diff-committed   Committed changes only (merge base to HEAD)"
    echo "  diff-uncommitted Uncommitted changes only (staged + unstaged vs HEAD)"
    echo "  log              Commit log since merge base"
    echo "  stat             Diffstat: merge base to working tree"
    echo "  files            Changed file list: merge base to working tree"
    echo "  base             Print merge base commit hash"
    echo "  target           Print merge target branch name"
    echo "  json             Machine-readable JSON output"
    exit 1
    ;;
esac
