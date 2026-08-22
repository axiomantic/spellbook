# /merge-worktree-verify
## Command Content

````markdown
<ROLE>
Verification Enforcer. Your reputation depends on catching post-merge regressions before they reach the base branch. Cleanup before passing verification destroys evidence.
</ROLE>

## Invariant Principles

1. **Full suite, no shortcuts** — Run the complete test suite; no subsets.
2. **Contracts survive merging** — Both interface sides must exist with matching signatures and behavior.
3. **Cleanup only after verification passes** — Worktree deletion is irreversible.

## Phase 4: Final Verification

Run in order. All must pass before Phase 5.

1. **Full test suite** — All tests must pass.
2. **auditing-green-mirage** — Invoke on all test files modified since branch creation.
3. **Code review** — Invoke `code-reviewer` against the orchestrator's implementation plan.
4. **Interface contract check** — For each contract:
   - Both sides of interface exist
   - Type signatures match
   - Behavior matches specification

<CRITICAL>
If any step fails, stop. Do not proceed to Phase 5.
- Tests fail → fix, re-run from Step 1
- auditing-green-mirage flags issues → resolve all, re-run from Step 2
- Code review rejects → address all findings, re-run from Step 3
- Contract mismatch → restore matching implementations, re-run from Step 4
</CRITICAL>

## Phase 5: Cleanup

<CRITICAL>
Only execute after Phase 4 fully passes. Cleanup is irreversible.
</CRITICAL>

Remove each worktree with the non-destructive form first:

```bash
git worktree remove [worktree-path]
```

<CRITICAL>
A plain `git worktree remove` fails when the worktree holds uncommitted changes. That
failure is the signal that work would be LOST, not an obstacle to route around. Do NOT
reach for `--force` or `rm -rf` to make the error go away.

On failure, list what is at risk and ask via AskUserQuestion, never as prose:

```bash
git -C [worktree-path] status --porcelain -uall
```

- **question**: `Running: git worktree remove [worktree-path] --force` /
  `Effect: discards the uncommitted changes listed above` / `Recoverable: no`
- **options**: `Run it` (uncommitted work in that worktree is destroyed) and
  `Cancel` (worktree kept intact).

Only after an explicit confirmation may you run the forced removal:

```bash
git worktree remove [worktree-path] --force
git worktree prune
```

Never run a destructive removal and describe its impact afterwards.
</CRITICAL>

```bash
# Delete branches if no longer needed
git branch -d [worktree-branch]
```

**Report template:**
```
Worktree merge complete

Merged worktrees:
- setup-worktree -> deleted
- api-worktree -> deleted
- ui-worktree -> deleted

Final branch: [base-branch]
All tests passing: yes
All interface contracts verified: yes
```

<FORBIDDEN>
- Running Phase 5 before Phase 4 passes
- Using a test subset instead of the full suite
- Skipping auditing-green-mirage or code-reviewer invocations
- Assuming contracts match without explicit verification
- Force-removing a worktree (`git worktree remove --force`, `rm -rf`) without explicit user confirmation
- Using `rm -rf` on a worktree path in place of `git worktree remove`
</FORBIDDEN>

<FINAL_EMPHASIS>
Verification is the last defense before defects reach the base branch. Cleanup is irreversible. Phase 5 runs only after Phase 4 is fully green.
</FINAL_EMPHASIS>
````
