---
name: finishing-a-development-branch
description: "Use when implementation is complete, all tests pass, and you need to decide how to integrate the work"
---

# Finishing a Development Branch

<ROLE>
Release Engineer. Your reputation depends on clean integrations that never break main or lose work. A merge that breaks the build is a public failure. A discard without confirmation is unforgivable.
</ROLE>

**Announce:** "Using finishing-a-development-branch skill to complete this work."

## Invariant Principles

1. **Tests Gate Everything** - Never present options until tests pass. Never merge without verifying tests on merged result.
2. **Structured Choice Over Open Questions** - Present exactly 4 options, never "what should I do?"
3. **Destruction Requires Proof** - Option 4 (Discard) demands typed "discard" confirmation. No shortcuts. No excuses.
4. **Worktree Lifecycle Matches Work State** - Cleanup only for Options 1 (merged) and 4 (discarded). Keep for Options 2 (PR pending) and 3 (user will handle).

---

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Passing test suite | Yes | Tests must pass before this skill can proceed |
| Feature branch | Yes | Current branch with completed implementation |
| Base branch | No | Branch to merge into (auto-detected if unset) |
| `post_impl` setting | No | Autonomous mode directive (auto_pr, offer_options, stop) |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Integration result | Action | Merge, PR, preserved branch, or discarded branch |
| PR URL | Inline | GitHub PR URL (Option 2 only) |
| Worktree state | State | Removed (Options 1,4) or preserved (Options 2,3) |

---

## Autonomous Mode

Check your context for autonomous mode indicators:
- "Mode: AUTONOMOUS" or "autonomous mode"
- `post_impl` preference specified (e.g., "auto_pr", "offer_options", "stop")

| `post_impl` value | Behavior |
|-------------------|----------|
| `auto_pr` | Skip Step 3 (present options), go directly to Option 2 (Push and Create PR) |
| `offer_options` | Present options normally (this is the interactive fallback) |
| `stop` | Skip Step 3, just report completion without action |
| (unset in autonomous) | Default to Option 2 - safest autonomous choice. Document: "Autonomous mode: defaulting to PR creation" |

<CRITICAL>
**Circuit breakers (always pause):**
- Tests failing - NEVER proceed
- Option 4 (Discard) selected - ALWAYS require typed confirmation, never auto-execute
</CRITICAL>

---

## The Process

### Step 1: Verify Tests

<analysis>
Before presenting options:
- Do tests pass on current branch?
- What is the base branch?
- Am I in a worktree?
</analysis>

```bash
# Run project's test suite
npm test / cargo test / pytest / go test ./...
```

**If tests fail:**
```
Tests failing (<N> failures). Must fix before completing:

[Show failures]

Cannot proceed with merge/PR until tests pass.
```

STOP. Do not proceed to Step 2.

**If tests pass:** Continue to Step 2.

### Step 2: Determine Base Branch

```bash
# Try common base branches
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

Or ask: "This branch split from main - is that correct?"

### Step 3: Present Options

Present exactly these 4 options:

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

**Don't add explanation** - keep options concise.

### Step 4: Execute Choice

#### Option 1: Merge Locally

```bash
# Switch to base branch
git checkout <base-branch>

# Pull latest
git pull

# Merge feature branch
git merge <feature-branch>

# Verify tests on merged result
<test command>

# If tests pass
git branch -d <feature-branch>
```

Then: Cleanup worktree (Step 5)

#### Option 2: Push and Create PR

```bash
# Push branch
git push -u origin <feature-branch>

# Create PR
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] <verification steps>
EOF
)"
```

Then: Cleanup worktree (Step 5)

#### Option 3: Keep As-Is

Report: "Keeping branch <name>. Worktree preserved at <path>."

**Don't cleanup worktree.**

#### Option 4: Discard

<CRITICAL>
**Confirm first with explicit typed confirmation:**
```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```

Wait for exact confirmation. Do NOT proceed on partial match.
</CRITICAL>

If confirmed:
```bash
git checkout <base-branch>
git branch -D <feature-branch>
```

Then: Cleanup worktree (Step 5)

### Step 5: Cleanup Worktree

**For Options 1, 2, 4:**

Check if in worktree:
```bash
git worktree list | grep $(git branch --show-current)
```

If yes:
```bash
git worktree remove <worktree-path>
```

**For Option 3:** Keep worktree intact.

---

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | Yes | - | - | Yes |
| 2. Create PR | - | Yes | Yes | - |
| 3. Keep as-is | - | - | Yes | - |
| 4. Discard | - | - | - | Yes (force) |

---

## Anti-Patterns

<FORBIDDEN>
- Proceeding with failing tests
- Merging without post-merge test verification
- Deleting branches without typed "discard" confirmation
- Force-pushing without explicit user request
- Presenting open-ended questions instead of structured options
- Cleaning up worktrees for Options 2 or 3
- Accepting partial confirmation for Option 4
</FORBIDDEN>

---

## Self-Check

<reflection>
Before completing:
- [ ] Tests pass on current branch
- [ ] Tests pass after merge (Option 1 only)
- [ ] User explicitly selected one of the 4 options
- [ ] Typed "discard" received (Option 4 only)
- [ ] Worktree cleaned only for Options 1 or 4

IF ANY unchecked: STOP and fix.
</reflection>

---

## Integration

**Called by:**
- **executing-plans** (Step 5) - After all batches complete
- **executing-plans --mode subagent** (Step 7) - After all tasks complete in subagent mode

**Pairs with:**
- **using-git-worktrees** - Cleans up worktree created by that skill
