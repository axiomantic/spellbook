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

Task 7 (Alembic) must complete before Tasks 8-9 can start. Tasks 8 and 9 are independent.

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
