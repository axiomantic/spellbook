# Admin UI Standardization - Chunk 1/8: Foundation

## Context

This is the first chunk. It sets up the SQLAlchemy dependencies, creates the DB package skeleton with async engines for all 4 databases, and runs the FK orphan-data audit.

Previous chunks completed: none (this is the first chunk)

**IMPORTANT:** Before starting work, create a new branch:
```bash
cd /Users/elijahrutschman/Development/spellbook
git checkout -b elijahr/admin-ui-standardization
```

## Execution

**MANDATORY: You MUST invoke the `develop` skill using the Skill tool before doing ANY work.**

```
Skill tool call:
  skill: "develop"
  args: "Escape hatch: impl plan at ~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md, treat as ready. Tasks 1, 2, 2b. Fully autonomous."
```

The develop skill will orchestrate the full workflow including TDD (via `test-driven-development` skill), code review (via `requesting-code-review` skill), and quality gates. Each of those sub-skills must also be invoked via the Skill tool by the subagents that develop dispatches. Do NOT implement code directly without going through the skill workflow.

**Key documents:**
- Implementation plan: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md`
- Design document: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-design.md`

## Pre-conditions

- On main branch with clean working directory
- uv and node/npm available

## Exit Criteria

- SQLAlchemy, aiosqlite, Alembic dependencies installed and importable
- `spellbook/db/` package exists with engines.py, base.py, helpers.py
- 4 async engines created (one per database) with NullPool
- 4 session factories (async_sessionmaker) available
- FK orphan-data audit script exists and has been run
- All changes committed on `elijahr/admin-ui-standardization` branch

## Next

When complete, run the next chunk:
```
Follow the prompt in .claude/prompts/admin-standardization-chunk-2.md
```

Note: Chunk 6 (Frontend Components) can also be started in parallel - it has no dependency on Phase A work.
