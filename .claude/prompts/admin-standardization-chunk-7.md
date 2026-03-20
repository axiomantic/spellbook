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

Tasks 25-30 are independent page migrations.

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
