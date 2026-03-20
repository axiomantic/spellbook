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

The develop skill will orchestrate the full workflow including TDD (via `test-driven-development` skill), code review (via `requesting-code-review` skill), and quality gates. Each of those sub-skills must also be invoked via the Skill tool by the subagents that develop dispatches. Do NOT implement code directly without going through the skill workflow.

Tasks 21-23 are independent (DataTable, Pagination, SearchBar+FilterBar). Task 24 (useListPage hook) depends on all three.

Working directory for frontend: `/Users/elijahrutschman/Development/spellbook/spellbook/admin/frontend/`

**Key documents:**
- Implementation plan: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md`
- Design document: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-design.md`

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
