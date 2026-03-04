---
description: "Phases 4-5: Final Verification and Cleanup — run full test suite, verify contracts, clean up worktrees"
---

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

```bash
# Delete worktrees
git worktree remove [worktree-path] --force

# If worktree has uncommitted changes
rm -rf [worktree-path]
git worktree prune

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
</FORBIDDEN>

<FINAL_EMPHASIS>
Verification is the last defense before defects reach the base branch. Cleanup is irreversible. Phase 5 runs only after Phase 4 is fully green.
</FINAL_EMPHASIS>
