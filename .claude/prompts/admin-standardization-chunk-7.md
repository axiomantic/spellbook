# Admin UI Standardization - Chunk 7/8: Page Migrations

## Context

This chunk migrates all 6 list pages to use the new shared components (DataTable, SearchBar, FilterBar, useListPage). It also splits FocusPage into two separate pages (StacksPage + CorrectionsPage) and standardizes detail pages.

Previous chunks completed: Chunks 1-6 (all backend + frontend infrastructure)

## Execution

**MANDATORY: You MUST invoke the `develop` skill using the Skill tool before doing ANY work.**

```
Skill tool call:
  skill: "develop"
  args: "Escape hatch: impl plan at ~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md, treat as ready. Tasks 25-30. Fully autonomous."
```

The develop skill will orchestrate the full workflow including TDD (via `test-driven-development` skill), code review (via `requesting-code-review` skill), and quality gates. Each of those sub-skills must also be invoked via the Skill tool by the subagents that develop dispatches. Do NOT implement code directly without going through the skill workflow.

Tasks 25-30 are independent page migrations.

**Key documents:**
- Implementation plan: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md`
- Design document: `~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-design.md`

CRITICAL: This is refactoring mode. Each page must preserve its existing functionality while adopting the new shared components. The backend APIs now return the standard `{items, total, page, per_page, pages}` envelope from Chunk 4.

Page migration order (all independent, can be done in any order):
- Task 25: SecurityLog -> uses DataTable + useListPage
- Task 26: Sessions -> uses DataTable + useListPage
- Task 27: GraphTable (fractal list) -> uses DataTable + useListPage
- Task 28: MemoryBrowser -> uses DataTable + useListPage (with FTS search)
- Task 29: CorrectionsPage (NEW, split from FocusPage) -> uses DataTable + useListPage
- Task 30: StacksPage (NEW, split from FocusPage) -> uses DataTable + useListPage

For the FocusPage split (Tasks 29-30):
- Create two NEW page components
- Old FocusPage.tsx will be replaced by a redirect in Chunk 8
- Update useFocus.ts hooks to support the new pagination/sorting params

## Pre-conditions

- Chunks 1-4 complete: Backend routes return standard API envelope
- Chunk 6 complete: Frontend shared components and useListPage hook exist
- Branch: `elijahr/admin-ui-standardization`

## Exit Criteria

- All 6 list pages use DataTable component with useListPage hook
- SearchBar and FilterBar used consistently across all pages
- Backend sorting works on all list pages (clicking column headers sorts server-side)
- Pagination works on all list pages (including corrections - the original bug fix!)
- FocusPage split into StacksPage and CorrectionsPage
- Detail pages (SessionDetail, memory detail pane) have consistent layout
- All frontend tests pass
- All changes committed

## Next

When complete, run the final chunk:
```
Follow the prompt in .claude/prompts/admin-standardization-chunk-8.md
```
