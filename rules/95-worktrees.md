---
id: worktrees
name: Worktrees
class: preference
default: "on"
description: >
  Isolation between a worktree and its main checkout, the worktree location
  convention, and the requirement that git commands run from the worktree path.
benefit: >
  Stops git commands from running against the wrong checkout and returning silently wrong results.
declining_means: >
  The agent may run git commands from the main checkout while working in a worktree,
  and follows no standing worktree location convention.
related:
  - skills/using-git-worktrees
  - skills/dispatching-parallel-agents
renamed_from: []
superseded_by: null
paths: []
---

## Worktrees

When working in a worktree: NEVER make changes to the main repo's files or git state without explicit confirmation. The inverse is also true.

### Worktree Location

Default: `~/Development/worktrees/{workspace-name}/{project}/`

Where `workspace-name` is a branch slug or feature name. When multiple repos share
a branch name, they nest under the same workspace directory. This groups all repos
for a single effort together rather than scattering worktrees across projects.

Project CLAUDE.md or AGENTS.md may override the naming convention (e.g., ticket-grouped
workspace tools use `{TICKET-ID-desc}` as the workspace name).

### Worktree Command Discipline

<CRITICAL>
When a worktree is active, ALL git commands (read-only included: `git diff`, `git log`, `git show`, `git branch`) MUST run from the worktree path. Git commands run from the main repo reflect a different branch and produce silently wrong results (e.g., empty diffs that look like "not in the branch" when the code is actually there).

Before running any git command for worktree work, verify the working directory:
```bash
cd <worktree-path> && pwd && git branch --show-current
```

This applies to the orchestrator AND to subagents. When dispatching a subagent to work in a worktree, include a verification preamble in the prompt (see dispatching-parallel-agents skill, Worktree Dispatch section).
</CRITICAL>
