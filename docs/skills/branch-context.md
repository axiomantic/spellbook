# branch-context

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Triggers: 'branch diff', 'what changed on this branch', 'merge base', 'stacked branches', 'branch-context.sh', 'what does this branch do', 'PR description', 'changelog', 'branch comparison', 'diff since', 'what work is on this branch'. Also relevant during PR creation and finishing-a-development-branch workflows.
## Skill Content

``````````markdown
<analysis>
Reference for inspecting branch diffs, detecting stacked branches, and writing branch-relative documentation using branch-context.sh.
</analysis>

<reflection>
Did I run branch-context.sh from the correct directory (worktree path, not main repo) and verify the merge target is correct?
</reflection>

# Branch Context

**Type:** Reference + Technique

Practical guide for inspecting branch context, handling stacked branches, and
producing branch-relative documentation. Core definitions (merge target, merge
base, branch diff) live in AGENTS.spellbook.md; this skill covers usage details.

## Invariant Principles

1. **Directory Determines Truth** - Branch-context commands must run from the correct working directory; running from the wrong repo produces silently wrong results.
2. **Merge Base Is the Reference Point** - All branch diffs, PR descriptions, and changelogs describe changes relative to the merge base, never absolute state.
3. **Stacked Branches Show Only Their Layer** - In a stack, each branch's diff includes only what it added on top of its parent branch.

---

## Script Usage

Use `$SPELLBOOK_DIR/scripts/branch-context.sh` to detect branch context
automatically:

```
branch-context.sh              # summary: target, base, stats, uncommitted state
branch-context.sh diff         # full diff (merge base to working tree)
branch-context.sh diff-committed   # committed only (merge base to HEAD)
branch-context.sh diff-uncommitted # uncommitted only (staged + unstaged vs HEAD)
branch-context.sh log          # commit log since merge base
branch-context.sh files        # changed file list
branch-context.sh json         # machine-readable JSON
```

`$SPELLBOOK_DIR` is substituted at load time from spellbook configuration.

---

## Stacked Branches

This matters for stacked branches: if `master -> branch-A -> branch-B`, the
work on branch-B is only what branch-B added on top of branch-A. The script
auto-detects stacking via PR base refs.

When reviewing stacked branches:

1. Run `branch-context.sh` to confirm the detected merge target.
2. Verify the merge target is the parent branch (e.g., `branch-A`), not `main`
   or `master`.
3. The diff will show only branch-B's additions, not the full stack.

---

## Worktree Notes

In worktrees, run this script FROM the worktree directory. It detects worktree
context automatically.

Before running any branch-context command in a worktree, verify you are in the
correct directory:

```bash
cd <worktree-path> && pwd && git branch --show-current
```

Running `branch-context.sh` from the main repo while intending to inspect a
worktree branch will produce silently wrong results (empty diffs, wrong merge
base).

---

## Branch-Relative Documentation

Changelogs, PR titles, PR descriptions, commit messages, and code comments
describe the merge-base delta only. No historical narratives in code comments.
Full policy in `finishing-a-development-branch` skill.

**Rules:**

- Describe what the branch introduces relative to its merge base.
- Do not narrate the development history ("first we tried X, then switched to Y").
- Do not reference work from parent branches in stacked PRs.
- PR descriptions should summarize the diff, not the journey.
``````````
