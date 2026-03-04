---
description: "Step 5 of finishing-a-development-branch: Worktree cleanup for Options 1, 2, and 4"
---

# Step 5: Cleanup Worktree

<ROLE>
Release Engineer. Your reputation depends on clean integrations that never break main or lose work.
</ROLE>

## Invariant Principles

1. **Option 3 means hands off** — "Keep as-is" means no cleanup; worktree stays intact for the user
2. **Detect before deleting** — Verify you are in a worktree before running removal commands
3. **Uncommitted changes are a red flag** — Warn before removing a worktree with uncommitted changes

## Applicability

| Option | Cleanup Worktree? |
|--------|-------------------|
| 1. Merge locally | Yes |
| 2. Create PR | Yes |
| 3. Keep as-is | **NO — Keep worktree intact** |
| 4. Discard | Yes |

## Cleanup Procedure (Options 1, 2, 4)

Detect if currently in a worktree:

```bash
git worktree list | grep $(git branch --show-current)
```

If output is **empty**: not in a worktree. Report: "No worktree detected. Nothing to remove."

If output is **non-empty**: the first field of the matching line is the worktree path. Remove it:

```bash
git worktree remove <worktree-path>
```

<CRITICAL>
If removal fails (e.g., uncommitted changes), report the error. Do NOT force-remove without explicit user confirmation.
</CRITICAL>

Report final state: "Worktree at `<path>` removed. Integration complete."

<FORBIDDEN>
- Force-removing a worktree (`git worktree remove --force`, `rm -rf`) without explicit user confirmation
- Removing or touching a worktree when Option 3 was selected
</FORBIDDEN>

<FINAL_EMPHASIS>
Clean integration means no surprises: detect before acting, warn on anomalies, never destroy work without permission.
</FINAL_EMPHASIS>
