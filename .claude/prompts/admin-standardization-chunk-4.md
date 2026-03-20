# Admin UI Standardization - Chunk 4/8: Admin Route Migrations

## Context

This chunk migrates all admin route files from raw SQL to SQLAlchemy ORM. Each route file is independent - they all use the shared helpers from Chunk 3. This is the largest chunk by file count.

Previous chunks completed: Chunks 1-3 (Foundation + Models + Alembic + Helpers)

## Execution

**MANDATORY: You MUST invoke the `develop` skill using the Skill tool before doing ANY work.**

```
Skill tool call:
  skill: "develop"
  args: "Escape hatch: impl plan at ~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md, treat as ready. Tasks 10-17. Fully autonomous."
```

Tasks 10-17 are independent route file migrations.

**Key documents:**
- Implementation plan: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md`
- Design document: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-design.md`

## Subagent Dispatch Discipline

<CRITICAL>
The develop skill orchestrates via subagents. Every subagent that does
substantive work MUST invoke the appropriate skill using the Skill tool.

"Do TDD" is NOT the same as "invoke the test-driven-development skill."
"Review the code" is NOT the same as "invoke the requesting-code-review skill."
Doing the work without invoking the skill is a workflow violation.
Skills contain specialized logic that ad-hoc execution cannot replicate.

Every subagent prompt MUST begin with:
  "First, invoke the [skill-name] skill using the Skill tool.
   Then follow its complete workflow."

After each subagent returns, verify its output contains
"Launching skill: [name]". If not found, re-dispatch with explicit
instruction to invoke the skill.
</CRITICAL>

### Per-Task Gate Sequence (mandatory, sequential, not batched)

After EACH task, run these gates in order:

1. **TDD** (4.3): Dispatch subagent → invokes `test-driven-development` skill
2. **Completion verification** (4.4): Dispatch subagent with inline audit prompt
3. **Code review** (4.5): Dispatch subagent → invokes `requesting-code-review` skill
4. **Fact-checking** (4.5.1): Dispatch subagent → invokes `fact-checking` skill

Do NOT batch gates across tasks. Each task completes all 4 gates before
the next task begins.

### Post-All-Tasks Gates (mandatory)

After all tasks pass per-task gates:

1. Comprehensive implementation audit (4.6.1)
2. Full test suite (4.6.2)
3. Green mirage audit (4.6.3) → invokes `audit-green-mirage` skill
4. Comprehensive fact-checking (4.6.4) → invokes `fact-checking` skill
5. Finishing (4.7) → invokes `finishing-a-development-branch` skill

CRITICAL: This is refactoring mode. Behavior preservation is the primary constraint. Each route must return identical API responses (except the standardized envelope format). Run existing tests after each migration to verify no regressions.

For each route migration:
1. Standardize response to use `{items, total, page, per_page, pages}` envelope
2. Replace raw SQL with SQLAlchemy ORM queries
3. Add sort column whitelist with fallback
4. Verify existing tests pass (adapt for new envelope format)

## Pre-conditions

- Chunks 1-3 complete: Models, Alembic, and helper functions exist
- Branch: `elijahr/admin-ui-standardization`

## Exit Criteria

- All 8 admin route files migrated to SQLAlchemy
- All routes use standard API envelope `{items, total, page, per_page, pages}`
- All routes support backend sorting via sort column whitelist
- `/api/focus/corrections` now has proper pagination (the original bug fix)
- Existing admin tests pass (adapted for new envelope format)
- All changes committed

## Next

When complete (and Chunk 6 is also complete), run:
```
Follow the prompt in .claude/prompts/admin-standardization-chunk-7.md
```
