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

Tasks 3-6 are independent and can be worked on in any order.

**Key documents:**
- Implementation plan: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md`
- Design document: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-design.md`

CRITICAL: The implementation plan contains "Verified Schema Reference" sections for each task with the ACTUAL column definitions from the source code. Use those exactly. Do NOT fabricate or guess column definitions.

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
