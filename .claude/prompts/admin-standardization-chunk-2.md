# Admin UI Standardization - Chunk 2/8: Model Definitions

## Context

This chunk defines SQLAlchemy ORM models for all tables across all 4 databases. Each database gets its own models module. The implementation plan contains verified schema references extracted from the actual source code.

Previous chunks completed: Chunk 1 (Foundation - DB package skeleton exists)

## Execution

**MANDATORY: You MUST invoke the `develop` skill using the Skill tool before doing ANY work.**

```
Skill tool call:
  skill: "develop"
  args: "Escape hatch: impl plan at ~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md, treat as ready. Tasks 3, 4, 5, 6. Fully autonomous."
```

The develop skill will orchestrate the full workflow including TDD (via `test-driven-development` skill), code review (via `requesting-code-review` skill), and quality gates. Each of those sub-skills must also be invoked via the Skill tool by the subagents that develop dispatches. Do NOT implement code directly without going through the skill workflow.

Tasks 3-6 are independent and can be worked on in any order.

**Key documents:**
- Implementation plan: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md`
- Design document: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-design.md`

CRITICAL: The implementation plan contains "Verified Schema Reference" sections for each task with the ACTUAL column definitions from the source code. Use those exactly. Do NOT fabricate or guess column definitions.

## Pre-conditions

- Chunk 1 complete: `spellbook/db/` package exists with base.py defining 4 DeclarativeBase classes
- Branch: `elijahr/admin-ui-standardization`

## Exit Criteria

- `spellbook/db/models/spellbook.py` with all spellbook.db table models (verified against real schemas)
- `spellbook/db/models/fractal.py` with all fractal.db table models
- `spellbook/db/models/forged.py` with all forged.db table models
- `spellbook/db/models/coordination.py` with all coordination.db table models
- Each model has a `to_dict()` method
- Tests verify model instantiation and column presence against actual DB schemas
- All changes committed

## Next

When complete, run the next chunk:
```
Follow the prompt in .claude/prompts/admin-standardization-chunk-3.md
```
