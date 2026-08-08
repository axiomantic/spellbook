# Diff and Branch Semantics

!!! warning "Mandatory module"
    This module installs on every platform and cannot be declined.

How the merge target and merge base are detected, and how the diff endpoint is chosen for the task at hand.

**Related artifacts:**

- `skills/branch-context`
- `skills/finishing-a-development-branch`
- `skills/code-review`
- `skills/advanced-code-review`

## Rule Content

``````````markdown
<CRITICAL>
### Branch Context: "The Work on This Branch"

"The work on this branch", "what this branch does", "the changes on this branch", and similar
phrases name a diff with two independent axes. Decide both, and say which you used.

#### Axis 1 — BASE. Invariant.

The base is ALWAYS the merge base against the **detected** merge target. It is never a literal
you assumed.

```
git fetch origin <target>          # ALWAYS first. Nothing computes a base against a stale ref.

detection order, first success wins:
  1. gh pr view --json baseRefName --jq .baseRefName
  2. the upstream tracking branch
  3. remote HEAD (origin/HEAD)
  4. a last-ditch literal — and SAY that it was a last-ditch literal

merge base:
  git merge-base <resolved-target> HEAD
```

Rules that make this reliable:

- **Fetch first.** A merge base computed against a stale remote ref is wrong in a way that looks
  right.
- **Report which base was used and how it was resolved.** A diff whose base is unstated is not
  reviewable.
- **No hardcoded base literal appears in any instruction.** Do not assume `main`. Do not assume
  `master`. A repository whose default branch is `master` must resolve to `master`, and a fork
  must resolve against the parent's default branch.
- **Detached HEAD is a defined case.** Either fail explicitly, or take an explicitly supplied
  base. Never silently produce a diff against a plausible-looking wrong ref.

#### Axis 2 — ENDPOINT. Task-dependent.

| Task | Endpoint |
|------|----------|
| Reviewing what will merge (the PR diff) | Committed only: `git diff <merge-base>...HEAD`, three-dot / merge-base semantics |
| Describing what the branch does (changelog, PR body, status report) | Include the working tree: `git diff <merge-base>` |
| Pre-commit self-review | Include the working tree |

Three-dot semantics EXCLUDE commits merged in FROM the target, so a merge of the target branch
does not pollute the review with changes the branch did not author. Two-dot `target..HEAD` and a
bare `git diff <target>` both include those merged-in commits and are the wrong shape for review.

**The bare term "branch diff" is retired.** It named both axes at once and meant neither
precisely. State the base and the endpoint.

Load `branch-context` skill for `branch-context.sh` usage, stacked branch handling, worktree context, and branch-relative documentation policy.
Load `finishing-a-development-branch` skill for the branch-relative documentation policy applied at the end of a branch.
</CRITICAL>
``````````
