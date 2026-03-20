# Admin UI Standardization - Chunk 5/8: Core Module Migrations

## Context

This chunk migrates the non-admin core modules from raw SQL to SQLAlchemy. These are the MCP tool modules, memory system, security tools, and session handling code. This is the riskiest chunk due to sync/async complexity and FTS5 virtual tables.

Previous chunks completed: Chunks 1-3 (Foundation + Models + Alembic + Helpers)

NOTE: This chunk runs IN PARALLEL with Chunk 4 (Admin Route Migrations). Do not depend on Chunk 4's changes.

## Execution

**MANDATORY: You MUST invoke the `develop` skill using the Skill tool before doing ANY work.**

```
Skill tool call:
  skill: "develop"
  args: "Escape hatch: impl plan at ~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md, treat as ready. Tasks 18a-18e, 19, 20. Fully autonomous."
```

**Key documents:**
- Implementation plan: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md`
- Design document: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-design.md`

CRITICAL RISKS:
- **FTS5 virtual tables** (Task 18b): MemoryBrowser uses FTS5. Use raw SQL escape hatch with `text()` within async sessions. Do NOT try to map FTS5 tables to ORM models.
- **Sync vs Async**: Many core modules use synchronous code paths. The implementation plan specifies per-module strategies. Follow them exactly.
- **Task 18b depends on 18a** (config module provides settings). Other tasks are independent.

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

- Chunks 1-3 complete: Models, Alembic, and helper functions exist
- Branch: `elijahr/admin-ui-standardization`

## Exit Criteria

- `spellbook/mcp/tools/config.py` migrated (9 SQL calls)
- `spellbook/memory/store.py` migrated with FTS5 escape hatch (47 SQL calls)
- `spellbook/memory/consolidation.py` migrated (7 SQL calls)
- `spellbook/security/` tools migrated (27 SQL calls)
- `spellbook/sessions/` modules migrated (31 SQL calls)
- `spellbook/mcp/tools/fractal.py` migrated
- Forged/coordination tool modules migrated
- All existing tests pass
- All changes committed

## Next

When complete, ensure Chunk 4 and Chunk 6 are also done, then:
```
Follow the prompt in .claude/prompts/admin-standardization-chunk-7.md
```

Also, once both Chunk 4 and Chunk 5 are done:
```
Follow the prompt in .claude/prompts/admin-standardization-chunk-8.md
```
(Chunk 8 Task 32 removes the old db.py once all migrations are complete)
