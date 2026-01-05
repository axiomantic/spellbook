# /finish-branch

Guide completion of development work by presenting structured options for merge, PR, or cleanup.

## Overview

The finish-branch command provides a structured workflow for completing development branches. It verifies tests, presents exactly 4 options, and handles cleanup appropriately.

## When to Use

- Implementation is complete
- All tests are passing
- Ready to integrate work (merge, PR, or defer)

## Invocation

```
/finish-branch
```

## The Process

### Step 1: Verify Tests

Before presenting options, tests must pass. If tests fail, the command blocks.

### Step 2: Present 4 Options

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work
```

### Step 3: Execute Choice

| Option | Action | Worktree |
|--------|--------|----------|
| 1. Merge locally | Checkout base, pull, merge, delete branch | Removed |
| 2. Create PR | Push, `gh pr create` | Kept for reviews |
| 3. Keep as-is | Report status | Kept |
| 4. Discard | Require "discard" confirmation, delete branch | Removed |

## Autonomous Mode

When in autonomous mode with `post_impl` preference:

| Preference | Behavior |
|------------|----------|
| `auto_pr` | Skip to Option 2 (Push and Create PR) |
| `offer_options` | Present options as normal |
| `stop` | Report completion without action |

## Circuit Breakers

Always pause for:
- Failing tests (blocks completely)
- Option 4 (Discard) - requires typed "discard" confirmation

## Integration

Called by:
- `subagent-driven-development` (Step 7)
- `executing-plans` (Step 5)

Pairs with:
- `using-git-worktrees` - Cleans up worktree created by that skill

## Related

- [debug skill](../skills/debug.md) - May invoke after debugging
- [using-git-worktrees](../skills/using-git-worktrees.md) - Worktree creation
- [executing-plans](../skills/executing-plans.md) - Plan execution workflow
