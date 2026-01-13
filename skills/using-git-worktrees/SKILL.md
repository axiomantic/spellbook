---
name: using-git-worktrees
description: "Use when starting feature work that needs isolation from current workspace or before executing implementation plans"
---

# Using Git Worktrees

<ROLE>
Build Engineer specializing in workspace isolation. Reputation depends on clean, reproducible development environments that never corrupt the main workspace.
</ROLE>

**Announce:** "Using git-worktrees skill for isolated workspace."

## Invariant Principles

1. **Directory precedence:** existing > CLAUDE.md > ask user (never assume)
2. **Safety gate:** Project-local worktrees MUST be gitignored before creation
3. **Clean baseline:** Tests must pass before implementation begins
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

## Directory Selection

```bash
# Priority 1: Check existing (prefer hidden)
ls -d .worktrees 2>/dev/null && echo "USE .worktrees"
ls -d worktrees 2>/dev/null && echo "USE worktrees"

# Priority 2: Check CLAUDE.md preference
grep -i "worktree.*director" CLAUDE.md 2>/dev/null

# Priority 3: Ask user
# Options: .worktrees/ (local) or ~/.local/spellbook/worktrees/<project>/
```

## Safety Verification

**Project-local only** (.worktrees or worktrees):

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

<reflection>
After worktree creation:
- Did `git worktree add` succeed?
- Are dependencies installed?
- Do tests pass in new worktree?
IF NO to any: Report failure, do NOT proceed with implementation.
</reflection>

**Global directory** (~/.local/spellbook/worktrees): No verification needed.

## Creation

```bash
project=$(basename "$(git rev-parse --show-toplevel)")
git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"

# Auto-detect setup
[ -f package.json ] && npm install
[ -f Cargo.toml ] && cargo build
[ -f requirements.txt ] && pip install -r requirements.txt
[ -f pyproject.toml ] && poetry install
[ -f go.mod ] && go mod download

# Verify baseline
# npm test | cargo test | pytest | go test ./...
```

**Report:** `Worktree ready at <path>. Tests passing (N tests). Ready for <feature>.`

## Autonomous Mode

When "Mode: AUTONOMOUS" or worktree preference detected:

| Situation | Decision |
|-----------|----------|
| Directory location | Use .worktrees/ or CLAUDE.md preference |
| Gitignore fix needed | Fix + commit automatically |
| Minor test failures | Log and proceed |

**Circuit breakers (still pause):**
- All tests failing (baseline broken)
- Git worktree command fails
- Cannot modify .gitignore

## Quick Reference

| Situation | Action |
|-----------|--------|
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | CLAUDE.md > ask |
| Not ignored | .gitignore + commit |
| Tests fail | Report + ask |

<FORBIDDEN>
- Creating worktrees in unignored project-local directories
- Proceeding with implementation when baseline tests fail
- Assuming worktree location without checking precedence
- Modifying files in main workspace while in worktree context
- Leaving orphaned worktrees after feature completion
</FORBIDDEN>

## Self-Check

Before reporting worktree ready:
- [ ] Directory location follows precedence (existing > CLAUDE.md > asked)
- [ ] Project-local path verified gitignored (or global path used)
- [ ] `git worktree add` completed successfully
- [ ] Dependencies installed for project type
- [ ] Baseline tests pass in new worktree

If ANY unchecked: STOP and resolve before proceeding.

## Integration

**Called by:** brainstorming (Phase 4), any skill needing isolation
**Pairs with:** finishing-a-development-branch (cleanup), executing-plans (implementation)
