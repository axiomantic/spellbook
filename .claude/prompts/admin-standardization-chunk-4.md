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

The develop skill will orchestrate the full workflow including TDD (via `test-driven-development` skill), code review (via `requesting-code-review` skill), and quality gates. Each of those sub-skills must also be invoked via the Skill tool by the subagents that develop dispatches. Do NOT implement code directly without going through the skill workflow.

Tasks 10-17 are independent route file migrations.

**Key documents:**
- Implementation plan: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md`
- Design document: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-design.md`

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
