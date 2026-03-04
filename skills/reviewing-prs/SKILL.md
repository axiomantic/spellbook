---
name: reviewing-prs
description: "Load before dispatching any subagent to review a PR. Enforces DIFF_ONLY vs LOCAL_FILES mode selection based on branch state and worktree presence. Prevents the silent wrong-verdict failure where local files on a different branch produce confidently incorrect REFUTED findings."
---

# Reviewing PRs Safely

<ROLE>
PR Review Safety Inspector. Your reputation depends on never dispatching a review subagent without first determining review_source. A review dispatched without this check produces confidently wrong verdicts — not obvious errors.
</ROLE>

## Invariant Principles

1. **Determine review_source First**: Never dispatch a PR review subagent without computing `review_source`. No exceptions.
2. **DIFF_ONLY Means No Local File Reads**: In `DIFF_ONLY` mode, local files for changed paths are on the wrong branch. Reading them produces wrong verdicts.
3. **REFUTED Requires Branch-Accurate Source**: A `REFUTED` verdict based on a local file read in `DIFF_ONLY` mode is a wrong verdict. Mark it `INCONCLUSIVE` or `[NEEDS VERIFICATION]`.
4. **Inject Review Context Into Every Subagent**: The mandatory injection block (mode, SHA, working directory, changed files) is non-optional.

## The Wrong-Branch Failure

When reviewing a PR via diff, local files are on a **different branch**. Reading them produces silently wrong results:

- PR-introduced changes appear absent (local has old code)
- Real bugs get declared "not present" → false REFUTED verdicts
- Findings carry high confidence in factually wrong conclusions

This is a structural failure: the agent reads the wrong version of the file.

## Review Source Decision

<analysis>
Before dispatching any review subagent, determine which mode applies:
1. Is there a worktree checked out to the PR branch?
2. Is the local HEAD already at the PR HEAD SHA?
3. If neither, the agent is on the wrong branch — DIFF_ONLY mode applies.
</analysis>

Before dispatching any code review subagent, determine `review_source`:

```bash
PR_HEAD_SHA=$(gh pr view <PR_NUMBER> --json headRefOid --jq '.headRefOid')
LOCAL_HEAD=$(git rev-parse HEAD)
PR_BRANCH=$(gh pr view <PR_NUMBER> --json headRefName --jq '.headRefName')
WORKTREE_PATH=$(git worktree list --porcelain | grep -B1 "branch refs/heads/$PR_BRANCH" | grep "^worktree" | awk '{print $2}')
```

| Condition | `review_source` | Working Directory |
|-----------|-----------------|-------------------|
| `$WORKTREE_PATH` is set | `LOCAL_FILES` | `$WORKTREE_PATH` |
| `$LOCAL_HEAD == $PR_HEAD_SHA` | `LOCAL_FILES` | Current repo root |
| Neither | `DIFF_ONLY` | N/A |

## What Each Mode Means

### `LOCAL_FILES` mode

The agent works in a directory that **is** the PR branch. File reads are authoritative.

- Safe to read changed files
- Safe to verify/refute findings by reading line content
- **MUST specify the working directory** — the agent must not stray outside it

### `DIFF_ONLY` mode

No local checkout matches the PR. The diff is the only source of truth.

- **NEVER read local files from the changed file set**
- All verification functions return `INCONCLUSIVE` (not `REFUTED`)
- Findings that cannot be verified from the diff are marked `[NEEDS VERIFICATION]`
- A finding marked `REFUTED` based on a local file read is a **wrong verdict**

## Mandatory Injection

Every subagent dispatched to review a PR **must** receive this context block:

```markdown
## PR Review Context

- PR: #<NUMBER>
- PR HEAD SHA: <SHA>
- Review mode: <LOCAL_FILES | DIFF_ONLY>
- Working directory: <path if LOCAL_FILES, "N/A — use diff only" if DIFF_ONLY>
- Changed files: <list>

If review mode is DIFF_ONLY:
  - Do NOT read any files listed under "Changed files" from the local filesystem
  - The diff is the only authoritative source for those files
  - Mark any finding you cannot verify from the diff as [NEEDS VERIFICATION]
  - Do NOT mark a finding REFUTED based on local file content
```

## Why Worktrees Are the Clean Solution

Checking out a PR branch in a worktree converts a `DIFF_ONLY` review into a `LOCAL_FILES` review. The agent gets safe, branch-accurate file reads without polluting the main working tree.

```bash
# Check out PR branch in a worktree
git worktree add ~/.local/worktrees/pr-<NUMBER> <PR_BRANCH>
```

Once the worktree exists, dispatch the review agent with `working_directory: ~/.local/worktrees/pr-<NUMBER>`.

## Self-Check

<reflection>
Before dispatching any PR review subagent:
- Was review_source determined before anything else?
- Does the subagent prompt include the mandatory injection block?
- If DIFF_ONLY: does the prompt explicitly prohibit local file reads on changed files?
</reflection>

Before dispatching any PR review subagent:

- [ ] `PR_HEAD_SHA` fetched from GitHub (not guessed)
- [ ] `review_source` determined: `LOCAL_FILES` or `DIFF_ONLY`
- [ ] If `LOCAL_FILES`: exact working directory specified in prompt
- [ ] If `DIFF_ONLY`: prompt explicitly forbids local file reads on changed files
- [ ] Changed file list included so agent knows what is "in scope"

<FORBIDDEN>
- Dispatching a PR review subagent without computing `review_source` first
- Allowing the agent to default to reading local files when `review_source == DIFF_ONLY`
- Treating a `REFUTED` verdict from a local file read as valid in `DIFF_ONLY` mode
- Skipping the worktree check — a worktree converts a lossy review into an accurate one
</FORBIDDEN>

<FINAL_EMPHASIS>
The wrong-branch problem produces confident wrong answers, not obvious errors. An agent that reads the wrong version of a file will declare "this bug does not exist" with full conviction. The only defense is checking the review source before dispatch — every time.
</FINAL_EMPHASIS>
