# Admin UI Standardization - Chunk 6/8: Frontend Shared Components

## Context

This chunk builds all the reusable frontend components: DataTable (using @tanstack/react-table), enhanced Pagination, SearchBar, FilterBar, and the useListPage hook. These components will be used by all page migrations in Chunk 7.

Previous chunks completed: Chunk 1 (for branch setup only)

IMPORTANT: This chunk is INDEPENDENT of Phase A (SQLAlchemy migration). It can run in parallel with Chunks 2-5. The only prerequisite is that the branch exists.

## Execution

**MANDATORY: You MUST invoke the `develop` skill using the Skill tool before doing ANY work.**

```
Skill tool call:
  skill: "develop"
  args: "Escape hatch: impl plan at ~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md, treat as ready. Tasks 21-24. Fully autonomous."
```

Tasks 21-23 are independent (DataTable, Pagination, SearchBar+FilterBar). Task 24 (useListPage hook) depends on all three.

Working directory for frontend: `/Users/elijahrutschman/Development/spellbook/spellbook/admin/frontend/`

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

- Branch `elijahr/admin-ui-standardization` exists
- Frontend dependencies installed (`cd spellbook/admin/frontend && npm install`)

## Exit Criteria

- `components/shared/DataTable.tsx` using @tanstack/react-table with server-side sort/pagination
- `components/shared/Pagination.tsx` enhanced with page size selector, jump-to-page, page numbers
- `components/shared/SearchBar.tsx` with debounced input
- `components/shared/FilterBar.tsx` with chip/select/date-range filter types
- `hooks/useListPage.ts` combining pagination + filtering + sorting state with React Query
- All components have TypeScript interfaces exported
- Frontend tests pass
- All changes committed

## Next

When complete AND Chunk 4 (Admin Routes) is complete, run:
```
Follow the prompt in .claude/prompts/admin-standardization-chunk-7.md
```
