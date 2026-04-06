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

1. **Directory precedence:** existing > CLAUDE.md > ask user (never assume)
2. **Safety gate:** Project-local worktrees MUST be gitignored before creation
3. **Clean baseline:** Tests must pass before implementation begins (interactive default; autonomous mode applies graduated policy — see Autonomous Mode)
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

## Directory Selection Process

Follow this priority order:

### 1. Check Existing Directories

```bash
ls -d .worktrees 2>/dev/null     # Preferred (hidden)
ls -d worktrees 2>/dev/null      # Alternative
```

**If found:** Use that directory. If both exist, `.worktrees` wins.

### 2. Check CLAUDE.md

```bash
grep -i "worktree.*director" CLAUDE.md 2>/dev/null
```

**If preference specified:** Use it without asking.

### 3. Ask User

If no directory exists and no CLAUDE.md preference:

```
No worktree directory found. Where should I create worktrees?

1. .worktrees/ (project-local, hidden)
2. ~/.local/spellbook/worktrees/<project-name>/ (global location)

Which would you prefer?
```

## Safety Verification

<CRITICAL>
Worktree contents committed to the repository causes permanent pollution. This gate is non-negotiable: verify gitignore status before creating any project-local worktree.
</CRITICAL>

### For Project-Local Directories (.worktrees or worktrees)

**MUST verify directory is ignored before creating worktree:**

```bash
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```

<analysis>
Before creating worktree:
- Does target directory already exist?
- Is directory preference established (existing > CLAUDE.md > ask)?
- Is project-local path gitignored?
If NOT ignored: add to .gitignore + commit immediately. Worktree contents must never be tracked.
</analysis>

**If NOT ignored:**
1. Add appropriate line to .gitignore
2. Commit the change
3. Proceed with worktree creation

### For Global Directory (~/.local/spellbook/worktrees)

No .gitignore verification needed — outside project entirely.

## Creation Steps

### 1. Detect Project Name

```bash
project=$(basename "$(git rev-parse --show-toplevel)")
```

### 2. Create Worktree

```bash
# Determine full path
case $LOCATION in
  .worktrees|worktrees)
    path="$LOCATION/$BRANCH_NAME"
    ;;
  ~/.local/spellbook/worktrees/*)
    path="~/.local/spellbook/worktrees/$project/$BRANCH_NAME"
    ;;
esac

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
- "Where should I create worktrees?" — use default (.worktrees/) or CLAUDE.md preference
- "Tests fail during baseline — ask whether to proceed" — proceed if minor, pause if critical

### Make These Decisions Autonomously
- Directory location: Use .worktrees/ as default if no existing directory or CLAUDE.md preference
- Gitignore fix: Always fix automatically (add to .gitignore + commit)
- Minor test failures: Log and proceed; major failures pause

### Circuit Breakers (Always Pause For)
- All tests failing (baseline completely broken)
- Git worktree command fails (structural git issue)
- .gitignore cannot be modified (permissions or other issue)

## Quick Reference

| Situation | Action |
|-----------|--------|
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | Check CLAUDE.md → ask user |
| Directory not ignored | Add to .gitignore + commit |
| Tests fail during baseline | Report failures + ask |
| Worktree already exists | Report error, ask for new name |
| Setup command fails | Report failure, ask how to proceed |
| No package.json/Cargo.toml | Skip dependency install |

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Skip ignore verification | Worktree contents get tracked, pollute git status | Always `git check-ignore` before creating project-local worktree |
| Assume directory location | Creates inconsistency, violates project conventions | Follow priority: existing > CLAUDE.md > ask |
| Proceed with failing tests | Can't distinguish new bugs from pre-existing issues | Report failures, get explicit permission to proceed |
| Hardcode setup commands | Breaks on projects using different tools | Auto-detect from manifest files |

## Example Workflow

```
[Check .worktrees/ - exists]
[Verify ignored - git check-ignore confirms .worktrees/ is ignored]
[Create worktree: git worktree add .worktrees/auth -b feature/auth]
[Run npm install]
[Run npm test - 47 passing]

Worktree ready at /Users/jesse/myproject/.worktrees/auth
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

Before reporting worktree ready — if ANY unchecked, STOP and resolve:

- [ ] Directory location follows precedence (existing > CLAUDE.md > asked)
- [ ] Project-local path verified gitignored (or global path used)
- [ ] `git worktree add` completed successfully
- [ ] Dependencies installed for project type
- [ ] Baseline tests pass in new worktree
</CRITICAL>

## Integration

**Called by:**
- **design-exploration** (Phase 4) — REQUIRED when design is approved and implementation follows
- Any skill needing isolated workspace

**Pairs with:**
- **finishing-a-development-branch** — REQUIRED for cleanup after work complete
- **executing-plans** — Work happens in this worktree (supports both batch and subagent modes)

<FINAL_EMPHASIS>
Worktree isolation protects the main workspace from experimental damage. Skipping safety verification causes repository pollution requiring manual cleanup. Proceeding without baseline tests makes it impossible to distinguish new bugs from pre-existing failures. Take the time to do it right.
</FINAL_EMPHASIS>
