---
name: finishing-a-development-branch
description: "Use when implementation is complete, all tests pass, and you need to decide how to integrate the work"
---

# Finishing a Development Branch

**Announce:** "I'm using the finishing-a-development-branch skill to complete this work."

<ROLE>
Release Engineer. Reputation depends on clean integrations that never break main or lose work.
</ROLE>

## Invariant Principles

1. **Tests Gate Everything** - Never present options until tests pass. Never merge without verifying tests on merged result.
2. **Structured Choice Over Open Questions** - Present exactly 4 options, never "what should I do?"
3. **Destruction Requires Proof** - Option 4 (Discard) demands typed "discard" confirmation. No shortcuts.
4. **Worktree Lifecycle Matches Work State** - Cleanup only for Options 1 (merged) and 4 (discarded). Keep for Options 2 (PR pending) and 3 (user will handle).

## Reasoning Schema

Before each step:
```
<analysis>
Current state: [tests pass/fail, branch name, base branch, worktree status]
Next action: [what and why]
Blockers: [what would prevent proceeding]
</analysis>
```

After completing:
```
<reflection>
Executed: [action taken]
Evidence: [command output proving success]
Next: [remaining steps or completion]
</reflection>
```

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

## Autonomous Mode

| `post_impl` value | Behavior |
|-------------------|----------|
| `auto_pr` | Skip options, execute Option 2 directly |
| `offer_options` | Present options normally |
| `stop` | Report completion, no action |
| (unset) | Default to Option 2, document: "Autonomous mode: defaulting to PR creation" |

**Circuit breakers (always pause):** Tests failing, Option 4 selected.

## Process

### 1. Verify Tests

```bash
npm test / cargo test / pytest / go test ./...
```

**Pass:** Continue. **Fail:** Stop. Show failures. Cannot proceed.

### 2. Determine Base Branch

```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master
```

Or confirm: "Branch split from main - correct?"

### 3. Present Options

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

### 4. Execute Choice

| Option | Commands | Worktree |
|--------|----------|----------|
| **1. Merge** | `checkout base` → `pull` → `merge feature` → verify tests → `branch -d` | Remove |
| **2. PR** | `push -u origin` → `gh pr create` | Keep |
| **3. Keep** | Report: "Keeping branch. Worktree preserved at path." | Keep |
| **4. Discard** | Confirm with typed "discard" → `checkout base` → `branch -D` | Remove |

**PR body template:**
```
## Summary
<2-3 bullets>

## Test Plan
- [ ] <verification steps>
```

**Discard confirmation:**
```
This will permanently delete:
- Branch <name>
- All commits: <list>
- Worktree at <path>

Type 'discard' to confirm.
```

### 5. Cleanup Worktree (Options 1, 4 only)

```bash
git worktree list | grep $(git branch --show-current)
# If match:
git worktree remove <path>
```

## Anti-Patterns

<FORBIDDEN>
- Proceeding with failing tests
- Merging without post-merge test verification
- Deleting branches without typed confirmation
- Force-pushing without explicit user request
- Presenting open-ended questions instead of structured options
- Cleaning up worktrees for Options 2 or 3
</FORBIDDEN>

## Self-Check

Before completing:
- [ ] Tests pass on current branch
- [ ] Tests pass after merge (Option 1 only)
- [ ] User explicitly selected one of the 4 options
- [ ] Typed confirmation received (Option 4 only)
- [ ] Worktree cleaned only for Options 1 or 4

If ANY unchecked: STOP and fix.

## Integration

- **Called by:** executing-plans (Step 5, Step 7 subagent mode)
- **Pairs with:** using-git-worktrees (cleanup)
