---
name: using-git-worktrees
description: "Use when starting feature work that needs isolation from current workspace, or setting up parallel development tracks. Triggers: 'worktree', 'separate branch', 'isolate this work', 'don't mess up current work', 'work on two things at once', 'parallel workstreams', 'new branch for this', 'keep my current work safe'."
intro: |
  Creates isolated git worktrees for parallel feature development without branch switching. Sets up clean, reproducible development environments with proper gitignore rules and dependency installation so that work on one feature never corrupts another. A core spellbook capability for managing concurrent development tracks.
---

# Using Git Worktrees

<ROLE>
Build Engineer specializing in workspace isolation. Your reputation depends on clean, reproducible development environments that never corrupt the main workspace. Improper worktree setup causes repository corruption and lost work. This is very important.
</ROLE>

**Announce:** "Using git-worktrees skill for isolated workspace."

## Invariant Principles

1. **Directory precedence:** CLAUDE.md/AGENTS.md override > existing ~/Development/worktrees/ > default (never assume)
2. **Safety gate:** Project-local worktrees MUST be gitignored before creation
3. **Clean baseline:** Tests must pass before implementation begins (interactive default; autonomous mode applies graduated policy -- see Autonomous Mode)
4. **Auto-detect over hardcode:** Infer setup from manifest files

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `feature_name` | Yes | Name for the worktree branch (e.g., "add-dark-mode") |
| `base_branch` | No | Branch to base worktree on (defaults to current HEAD) |
| `worktree_preference` | No | Explicit path preference from CLAUDE.md or user |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `worktree_path` | Path | Absolute path to created worktree directory |
| `branch_name` | String | Name of the created branch |
| `baseline_status` | Report | Test results confirming clean starting state |

---

## Workspace Structure

Worktrees are organized by **workspace** (branch or feature name), not by project:

```
~/Development/worktrees/
  {workspace-name}/
    {repo-a}/          <- git worktree
    {repo-b}/          <- git worktree
```

When multiple repos share a branch name or belong to the same feature, they
nest under the same workspace directory. This makes it easy to find all repos
related to a single effort.

**Examples:**
```
~/Development/worktrees/mcp-events/fastmcp/         # shared branch across repos
~/Development/worktrees/mcp-events/python-sdk/
~/Development/worktrees/mcp-events/typescript-sdk/
~/Development/worktrees/fix-auth-flow/myproject/     # single-repo feature
```

Project CLAUDE.md or AGENTS.md may specify a different naming convention for the
workspace name (e.g., `ODY-2863-card-reader-eligibility` for ticket-grouped tools).
The nesting structure remains the same: `{workspace}/{repo}/`.

## Directory Selection Process

Follow this priority order:

### 1. Check CLAUDE.md / AGENTS.md for Project Override

Some projects override the default worktree location (e.g., ticket-grouped
workspace tools). Check for explicit worktree path instructions.

**If override found:** Use it without asking.

### 2. Check Existing Global Directory

```bash
ls -d ~/Development/worktrees/ 2>/dev/null
```

**If found:** Use `~/Development/worktrees/{workspace-name}/{project}`.

### 3. Default to Global Location

```bash
mkdir -p ~/Development/worktrees/
```

Default: `~/Development/worktrees/{branch-slug}/{project}`. No gitignore needed (outside project).

## Safety Verification

The default location (`~/Development/worktrees/`) is outside the project, so no gitignore
verification is needed. If a project override directs worktrees to a
project-local path, the following gate applies:

<CRITICAL>
Worktree contents committed to the repository causes permanent pollution. This gate is non-negotiable: verify gitignore status before creating any project-local worktree.
</CRITICAL>

### For Project-Local Directories (only when override specifies one)

**MUST verify directory is ignored before creating worktree:**

```bash
git check-ignore -q "$WORKTREE_DIR" 2>/dev/null
```

<analysis>
Before creating worktree:
- Does target directory already exist?
- Is directory preference established (override > default)?
- Is project-local path gitignored?
If NOT ignored: add to .gitignore + commit immediately. Worktree contents must never be tracked.
</analysis>

**If NOT ignored:**
1. Add appropriate line to .gitignore
2. Commit the change
3. Proceed with worktree creation

### For Global Directory (~/Development/worktrees/ -- the default)

No .gitignore verification needed -- outside project entirely.

## Creation Steps

### 1. Detect Project Name

```bash
project=$(basename "$(git rev-parse --show-toplevel)")
```

### 2. Create Worktree

```bash
# Default path (override may change this)
path="$HOME/Development/worktrees/$BRANCH_NAME/$project"
mkdir -p "$(dirname "$path")"

# Check if branch/worktree already exists
git worktree list | grep -q "$BRANCH_NAME" && echo "ERROR: Worktree exists"

# Create worktree with new branch
git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

### 3. Run Project Setup

Auto-detect and run appropriate setup:

```bash
if [ -f package.json ]; then npm install; fi
if [ -f Cargo.toml ]; then cargo build; fi
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install || uv sync; fi
if [ -f go.mod ]; then go mod download; fi
```

**If setup fails:** Report specific failure. Ask whether to proceed or troubleshoot.

### 4. Verify Clean Baseline

Run tests to ensure worktree starts clean:

```bash
# Use project-appropriate command: npm test / cargo test / pytest / go test ./...
```

<reflection>
After worktree creation:
- Did `git worktree add` succeed?
- Are dependencies installed?
- Do tests pass in new worktree?
IF NO to any: Report failure, do NOT proceed with implementation.
</reflection>

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

### 5. Report Location

```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```

## Autonomous Mode Behavior

Check context for autonomous mode indicators:
- "Mode: AUTONOMOUS" or "autonomous mode"
- `worktree` preference specified (e.g., "single", "per_parallel_track", "none")

When autonomous mode is active:

### Skip These Interactions
- "Where should I create worktrees?" -- use `~/Development/worktrees/{branch}/{project}` or CLAUDE.md override
- "Tests fail during baseline -- ask whether to proceed" -- proceed if minor, pause if critical

### Make These Decisions Autonomously
- Directory location: Use `~/Development/worktrees/{branch}/{project}` as default if no CLAUDE.md override
- Gitignore fix: Always fix automatically (add to .gitignore + commit)
- Minor test failures: Log and proceed; major failures pause

### Circuit Breakers (Always Pause For)
- All tests failing (baseline completely broken)
- Git worktree command fails (structural git issue)
- .gitignore cannot be modified (permissions or other issue)

## Quick Reference

| Situation | Action |
|-----------|--------|
| CLAUDE.md/AGENTS.md override | Use specified path |
| No override | Use `~/Development/worktrees/{branch-slug}/{project}` |
| Override points to project-local path | Verify gitignored first |
| Directory not ignored | Add to .gitignore + commit |
| Tests fail during baseline | Report failures + ask |
| Worktree already exists | Report error, ask for new name |
| Setup command fails | Report failure, ask how to proceed |
| No package.json/Cargo.toml | Skip dependency install |

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Skip ignore verification | Worktree contents get tracked, pollute git status | Always `git check-ignore` before creating project-local worktree |
| Assume directory location | Creates inconsistency, violates project conventions | Follow priority: override > default |
| Proceed with failing tests | Can't distinguish new bugs from pre-existing issues | Report failures, get explicit permission to proceed |
| Hardcode setup commands | Breaks on projects using different tools | Auto-detect from manifest files |
| Put worktrees under project name | Multi-repo features get scattered | Group by workspace (branch/feature), nest repos inside |

## Example Workflow

```
[Check CLAUDE.md -- no override]
[Default to ~/Development/worktrees/feature-auth/myproject]
[Create worktree: git worktree add ~/Development/worktrees/feature-auth/myproject -b feature/auth]
[Run npm install]
[Run npm test -- 47 passing]

Worktree ready at ~/Development/worktrees/feature-auth/myproject
Tests passing (47 tests, 0 failures)
Ready to implement auth feature
```

<FORBIDDEN>
- Creating worktrees in unignored project-local directories
- Proceeding with implementation when baseline tests fail
- Assuming worktree location without checking precedence
- Modifying files in main workspace while in worktree context
- Leaving orphaned worktrees after feature completion
- Skipping safety verification for speed
</FORBIDDEN>

<CRITICAL>
## Self-Check

Before reporting worktree ready -- if ANY unchecked, STOP and resolve:

- [ ] Directory location follows precedence (override > default)
- [ ] Project-local path verified gitignored (or global path used)
- [ ] `git worktree add` completed successfully
- [ ] Dependencies installed for project type
- [ ] Baseline tests pass in new worktree
</CRITICAL>

## Integration

**Called by:**
- **design-exploration** (Phase 4) -- REQUIRED when design is approved and implementation follows
- Any skill needing isolated workspace

**Pairs with:**
- **finishing-a-development-branch** -- REQUIRED for cleanup after work complete
- **executing-plans** -- Work happens in this worktree (supports both batch and subagent modes)

<FINAL_EMPHASIS>
Worktree isolation protects the main workspace from experimental damage. Skipping safety verification causes repository pollution requiring manual cleanup. Proceeding without baseline tests makes it impossible to distinguish new bugs from pre-existing failures. Take the time to do it right.
</FINAL_EMPHASIS>
