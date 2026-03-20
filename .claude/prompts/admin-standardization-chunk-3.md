# Admin UI Standardization - Chunk 3/8: Alembic + Backend Helpers

## Context

This chunk sets up Alembic multi-database migration infrastructure and creates shared backend helper functions for pagination, sorting, and filtering. These helpers will be used by all route migrations in subsequent chunks.

Previous chunks completed: Chunks 1-2 (Foundation + Model definitions)

## Execution

**MANDATORY: You MUST invoke the `develop` skill using the Skill tool before doing ANY work.**

```
Skill tool call:
  skill: "develop"
  args: "Escape hatch: impl plan at ~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md, treat as ready. Tasks 7, 8, 9. Fully autonomous."
```

The develop skill will orchestrate the full workflow including TDD (via `test-driven-development` skill), code review (via `requesting-code-review` skill), and quality gates. Each of those sub-skills must also be invoked via the Skill tool by the subagents that develop dispatches. Do NOT implement code directly without going through the skill workflow.

Task 7 (Alembic) must complete before Tasks 8-9 can start. Tasks 8 and 9 are independent.

**Key documents:**
- Implementation plan: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md`
- Design document: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-design.md`

## Pre-conditions

- Chunks 1-2 complete: All model definitions exist in `spellbook/db/models/`
- Branch: `elijahr/admin-ui-standardization`

## Exit Criteria

- Alembic multi-database configuration with separate version directories per DB
- `alembic.ini` and `alembic/` directory structure created
- Baseline migrations generated and applied
- `spellbook/db/helpers.py` has pagination, sorting, filtering utility functions
- `spellbook/admin/routes/schemas.py` updated with standard API envelope types
- Frontend `api/types.ts` updated with `ListResponse<T>` type
- Tests for Alembic upgrade/downgrade and helper functions
- All changes committed

## Next

When complete, Chunks 4 and 5 can run in parallel:
```
Follow the prompt in .claude/prompts/admin-standardization-chunk-4.md
```
AND (in a parallel session):
```
Follow the prompt in .claude/prompts/admin-standardization-chunk-5.md
```
