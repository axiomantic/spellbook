#!/usr/bin/env bash
# branch-context.sh - Detect merge target, merge base, and show branch work
# Handles worktrees, stacked branches, uncommitted/unstaged changes.
set -euo pipefail

# --- Argument parsing ---
# Usage: branch-context.sh [subcommand] [--base <ref>]
# `--base` skips detection entirely and is reported as `explicit-override`.
SUBCOMMAND=""
BASE_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      if [[ $# -lt 2 || -z "$2" ]]; then
        echo "ERROR: --base requires a ref argument" >&2
        exit 2
      fi
      BASE_OVERRIDE="$2"
      shift 2
      ;;
    --base=*)
      BASE_OVERRIDE="${1#--base=}"
      if [[ -z "$BASE_OVERRIDE" ]]; then
        echo "ERROR: --base requires a ref argument" >&2
        exit 2
      fi
      shift
      ;;
    *)
      if [[ -z "$SUBCOMMAND" ]]; then
        SUBCOMMAND="$1"
        shift
      else
        echo "ERROR: unexpected argument: $1" >&2
        exit 2
      fi
      ;;
  esac
done
SUBCOMMAND="${SUBCOMMAND:-summary}"

# --- Detect worktree vs main repo ---
GIT_DIR=$(git rev-parse --git-dir 2>/dev/null)
TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null)
IS_WORKTREE=false
if [[ "$GIT_DIR" == *".git/worktrees/"* ]]; then
  IS_WORKTREE=true
fi

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
DETACHED_HEAD=false
if [[ -z "$CURRENT_BRANCH" ]]; then
  # Detached HEAD - defined behavior: no branch identity, so PR and upstream
  # detection are both skipped. We fall through to remote HEAD and SAY so.
  DETACHED_HEAD=true
  CURRENT_BRANCH=$(git rev-parse --short HEAD)
fi

# --- Remote preference (deterministic and documented) ---
# In a fork setup the parent repo is conventionally `upstream`; prefer it so the
# merge base is computed against the parent's default branch, not the fork's.
BASE_REMOTE=""
for candidate in upstream origin; do
  if git remote get-url "$candidate" &>/dev/null; then
    BASE_REMOTE="$candidate"
    break
  fi
done
if [[ -z "$BASE_REMOTE" ]]; then
  BASE_REMOTE=$(git remote 2>/dev/null | head -n1)
fi

# --- Detect merge target (priority order) ---
MERGE_TARGET=""
PR_URL=""
# How the merge target was resolved. One of:
#   pr-base-ref | upstream-tracking | remote-head | fallback-literal
#   pr-base-ref | upstream-tracking | remote-head | fallback-literal
#   explicit-override (when --base is supplied)
RESOLUTION_METHOD=""

# 0. Explicit override. Detection is skipped ENTIRELY and reported as such.
if [[ -n "$BASE_OVERRIDE" ]]; then
  MERGE_TARGET="$BASE_OVERRIDE"
  RESOLUTION_METHOD="explicit-override"
fi

# 1. Try PR base ref (most reliable for stacked branches)
#
# Hardening: `gh pr view <branch>` matches on head-branch NAME and can resolve to
# the wrong PR in fork and multi-remote setups (another repo, or a same-named
# branch on a different head repo). We therefore ask for the head ref back and
# REJECT any PR whose headRefName does not equal the branch we are actually on.
# Detached HEAD has no branch identity at all, so gh is skipped entirely.
if [[ -z "$MERGE_TARGET" ]] && [[ "$DETACHED_HEAD" == false ]] && command -v gh &>/dev/null; then
  PR_JSON=$(gh pr view "$CURRENT_BRANCH" --json baseRefName,url,headRefName 2>/dev/null || echo "")
  if [[ -n "$PR_JSON" ]]; then
    PR_HEAD_REF=$(echo "$PR_JSON" | jq -r '.headRefName // empty' 2>/dev/null || echo "")
    if [[ "$PR_HEAD_REF" == "$CURRENT_BRANCH" ]]; then
      MERGE_TARGET=$(echo "$PR_JSON" | jq -r '.baseRefName // empty' 2>/dev/null || echo "")
      PR_URL=$(echo "$PR_JSON" | jq -r '.url // empty' 2>/dev/null || echo "")
      [[ -n "$MERGE_TARGET" ]] && RESOLUTION_METHOD="pr-base-ref"
    fi
  fi
fi

# 2. Fallback: upstream tracking branch
if [[ -z "$MERGE_TARGET" && "$DETACHED_HEAD" == false ]]; then
  MERGE_TARGET=$(git config "branch.${CURRENT_BRANCH}.merge" 2>/dev/null | sed 's|refs/heads/||' || echo "")
  [[ -n "$MERGE_TARGET" ]] && RESOLUTION_METHOD="upstream-tracking"
fi

# 3. Fallback: remote default branch (master or main - never assumed)
if [[ -z "$MERGE_TARGET" && -n "$BASE_REMOTE" ]]; then
  MERGE_TARGET=$(git symbolic-ref --quiet --short "refs/remotes/${BASE_REMOTE}/HEAD" 2>/dev/null | sed "s|^${BASE_REMOTE}/||" || echo "")
  if [[ -z "$MERGE_TARGET" ]]; then
    MERGE_TARGET=$(git remote show "$BASE_REMOTE" 2>/dev/null | grep 'HEAD branch' | awk '{print $NF}' || echo "")
  fi
  [[ -n "$MERGE_TARGET" ]] && RESOLUTION_METHOD="remote-head"
fi

# 4. Last-ditch literal. This is a GUESS and is reported as one.
if [[ -z "$MERGE_TARGET" ]]; then
  for candidate in main master; do
    if git rev-parse --verify --quiet "refs/heads/${candidate}" &>/dev/null \
      || git rev-parse --verify --quiet "refs/remotes/${BASE_REMOTE}/${candidate}" &>/dev/null; then
      MERGE_TARGET="$candidate"
      break
    fi
  done
  [[ -z "$MERGE_TARGET" ]] && MERGE_TARGET="main"
  RESOLUTION_METHOD="fallback-literal"
fi

# --- Fetch before computing the merge base ---
# Nothing computes a base against a stale ref. Non-fatal: a network failure
# degrades to the local ref, and the degradation is REPORTED, never silent.
FETCH_STATUS="skipped"
if [[ "${SPELLBOOK_BRANCH_CONTEXT_NO_FETCH:-0}" == "1" ]]; then
  FETCH_STATUS="skipped (SPELLBOOK_BRANCH_CONTEXT_NO_FETCH=1)"
elif [[ -n "$BASE_OVERRIDE" ]]; then
  # An override may name a local-only ref or a sha; fetching it is not meaningful.
  FETCH_STATUS="skipped (--base override)"
elif [[ -n "$BASE_REMOTE" ]]; then
  if git fetch --quiet "$BASE_REMOTE" "$MERGE_TARGET" 2>/dev/null; then
    FETCH_STATUS="ok"
  else
    FETCH_STATUS="FAILED (offline or no such ref) - merge base may be STALE"
  fi
else
  FETCH_STATUS="skipped (no remote configured)"
fi

# --- Compute merge base ---
# Try <remote>/<target> first (more up-to-date), fall back to local ref
if [[ -n "$BASE_OVERRIDE" ]]; then
  BASE_REF="$BASE_OVERRIDE"
else
  BASE_REF="${BASE_REMOTE:+${BASE_REMOTE}/}${MERGE_TARGET}"
fi
MERGE_BASE=$(git merge-base HEAD "$BASE_REF" 2>/dev/null || echo "")
if [[ -z "$MERGE_BASE" ]]; then
  BASE_REF="$MERGE_TARGET"
  MERGE_BASE=$(git merge-base HEAD "$BASE_REF" 2>/dev/null || echo "")
fi

if [[ -z "$MERGE_BASE" ]]; then
  echo "ERROR: Could not compute merge base between HEAD and $MERGE_TARGET" >&2
  echo "       (remote=${BASE_REMOTE:-none}, resolution=${RESOLUTION_METHOD}, fetch=${FETCH_STATUS})" >&2
  exit 1
fi

# --- Resolution banner ---
# Printed to stderr for every non-summary subcommand so a consumer that only
# captures stdout (a diff, a file list) still SEES which base was used and how
# it was resolved. Silent fallback is the failure this script exists to prevent.
resolution_banner() {
  echo "base-ref:       $BASE_REF" >&2
  echo "merge-target:   $MERGE_TARGET" >&2
  echo "resolved-via:   $RESOLUTION_METHOD" >&2
  echo "remote:         ${BASE_REMOTE:-none}" >&2
  echo "fetch:          $FETCH_STATUS" >&2
  echo "merge-base:     $MERGE_BASE" >&2
  $DETACHED_HEAD && echo "WARNING:        detached HEAD - no branch identity; PR/upstream detection skipped" >&2
  [[ "$RESOLUTION_METHOD" == "fallback-literal" ]] && \
    echo "WARNING:        merge target was GUESSED (last-ditch literal), not detected" >&2
  return 0
}

# --- Subcommands ---
case "$SUBCOMMAND" in
  diff)
    # Full diff: merge base to working tree (includes committed + staged + unstaged)
    resolution_banner
    git diff "$MERGE_BASE"
    ;;
  diff-committed)
    # Only committed changes (merge base to HEAD) - three-dot equivalent
    resolution_banner
    git diff "$MERGE_BASE"..HEAD
    ;;
  diff-uncommitted)
    # Only uncommitted changes (staged + unstaged relative to HEAD)
    git diff HEAD
    ;;
  log)
    resolution_banner
    git log --oneline "$MERGE_BASE"..HEAD
    ;;
  stat)
    # Full stat: merge base to working tree
    resolution_banner
    git diff --stat "$MERGE_BASE"
    ;;
  stat-committed)
    # Diffstat for committed changes only (merge base to HEAD)
    resolution_banner
    git diff --stat "$MERGE_BASE"..HEAD
    ;;
  files)
    # All changed files: merge base to working tree
    resolution_banner
    git diff --name-only "$MERGE_BASE"
    ;;
  files-committed)
    # Changed files in committed changes only (merge base to HEAD).
    # This is the endpoint that pairs with `diff-committed`. Building a
    # coverage manifest from `files` while reading `diff-committed` lets a
    # review certify N-of-N files against an empty diff.
    resolution_banner
    git diff --name-only "$MERGE_BASE"..HEAD
    ;;
  base)
    resolution_banner
    echo "$MERGE_BASE"
    ;;
  target)
    resolution_banner
    echo "$MERGE_TARGET"
    ;;
  resolution)
    # Just the base-resolution provenance, on stdout
    echo "base_ref=$BASE_REF"
    echo "merge_target=$MERGE_TARGET"
    echo "resolved_via=$RESOLUTION_METHOD"
    echo "remote=${BASE_REMOTE:-none}"
    echo "fetch=$FETCH_STATUS"
    echo "merge_base=$MERGE_BASE"
    echo "detached_head=$DETACHED_HEAD"
    ;;
  summary)
    echo "Branch:        $CURRENT_BRANCH"
    echo "Merge target:  $MERGE_TARGET"
    echo "Resolved via:  $RESOLUTION_METHOD"
    echo "Base ref:      $BASE_REF"
    echo "Remote:        ${BASE_REMOTE:-none}"
    echo "Fetch:         $FETCH_STATUS"
    echo "Merge base:    $(echo "$MERGE_BASE" | cut -c1-12)"
    [[ -n "$PR_URL" ]] && echo "PR:            $PR_URL"
    $DETACHED_HEAD && echo "WARNING:       detached HEAD - PR/upstream detection skipped"
    [[ "$RESOLUTION_METHOD" == "fallback-literal" ]] && \
      echo "WARNING:       merge target GUESSED (last-ditch literal), not detected"
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
      --arg base_ref "$BASE_REF" \
      --arg resolved_via "$RESOLUTION_METHOD" \
      --arg remote "${BASE_REMOTE:-}" \
      --arg fetch "$FETCH_STATUS" \
      --argjson detached "$DETACHED_HEAD" \
      --arg pr "$PR_URL" \
      --argjson worktree "$IS_WORKTREE" \
      --arg toplevel "$TOPLEVEL" \
      --argjson commits "$(git rev-list --count "$MERGE_BASE"..HEAD)" \
      --argjson files "$(git diff --name-only "$MERGE_BASE" | wc -l | tr -d ' ')" \
      --argjson files_committed "$(git diff --name-only "$MERGE_BASE"..HEAD | wc -l | tr -d ' ')" \
      --argjson staged "$STAGED" \
      --argjson unstaged "$UNSTAGED" \
      --argjson untracked "$UNTRACKED" \
      '{
        branch: $branch,
        merge_target: $target,
        merge_base: $base,
        base_ref: $base_ref,
        resolved_via: $resolved_via,
        remote: (if $remote == "" then null else $remote end),
        fetch: $fetch,
        detached_head: $detached,
        pr_url: (if $pr == "" then null else $pr end),
        is_worktree: $worktree,
        toplevel: $toplevel,
        commits: $commits,
        files_changed: $files,
        files_changed_committed: $files_committed,
        staged: $staged,
        unstaged: $unstaged,
        untracked: $untracked
      }'
    ;;
  *)
    echo "Usage: branch-context.sh [subcommand] [--base <ref>]"
    echo ""
    echo "Subcommands:"
    echo "  summary          Branch info, merge target, resolution, and change stats (default)"
    echo "  diff             Full diff: merge base to working tree (committed + uncommitted)"
    echo "  diff-committed   Committed changes only (merge base to HEAD)"
    echo "  diff-uncommitted Uncommitted changes only (staged + unstaged vs HEAD)"
    echo "  log              Commit log since merge base"
    echo "  stat             Diffstat: merge base to working tree"
    echo "  stat-committed   Diffstat: merge base to HEAD (committed only)"
    echo "  files            Changed file list: merge base to working tree"
    echo "  files-committed  Changed file list: merge base to HEAD (committed only)"
    echo "  base             Print merge base commit hash"
    echo "  target           Print merge target branch name"
    echo "  resolution       Print how the merge target/base were resolved"
    echo "  json             Machine-readable JSON output"
    echo ""
    echo "Options:"
    echo "  --base <ref>     Skip detection; use <ref> as the merge target"
    echo "                   (reported as resolved_via=explicit-override)"
    echo ""
    echo "Endpoint selection (choose by TASK, not by habit):"
    echo "  reviewing what will merge          -> files-committed + diff-committed"
    echo "  describing the branch (PR body,"
    echo "  changelog) or pre-commit self-review -> files + diff"
    echo ""
    echo "Env:"
    echo "  SPELLBOOK_BRANCH_CONTEXT_NO_FETCH=1  Skip the pre-merge-base fetch (offline)"
    exit 1
    ;;
esac
