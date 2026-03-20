# Admin UI Standardization - Chunk 8/8: Finalization

## Context

This is the final chunk. It updates sidebar navigation and routing for the FocusPage split, removes the old `spellbook/admin/db.py` (now fully replaced by SQLAlchemy), and runs the complete test suite to verify everything works end-to-end.

Previous chunks completed: Chunks 1-7 (all implementation complete)

## Execution

**MANDATORY: You MUST invoke the `develop` skill using the Skill tool before doing ANY work.**

```
Skill tool call:
  skill: "develop"
  args: "Escape hatch: impl plan at ~/.local/spellbook/docs/Users-elijahrutschman-Development-spellbook/plans/2026-03-20-admin-ui-standardization-impl.md, treat as ready. Tasks 31, 32, 33. Fully autonomous."
```

Tasks 31-33 are sequential.

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

Task 31: Sidebar + Routing Updates
- Update Sidebar.tsx to replace "Focus" nav item with "Stacks" and "Corrections"
- Update App.tsx routes: add /stacks, /corrections routes, add /focus redirect to /stacks
- Remove old FocusPage import

Task 32: Cleanup
- Remove `spellbook/admin/db.py` (replaced by `spellbook/db/` package)
- Remove any remaining raw SQL imports
- Verify no code references the old db.py module

Task 33: Full Test Suite Verification
- Run full backend test suite: `uv run pytest tests/ -x`
- Run frontend tests: `cd spellbook/admin/frontend && npm test`
- Build frontend: `cd spellbook/admin/frontend && npm run build`
- Copy build output to `spellbook/admin/static/`
- Verify all tests pass, no regressions

## Pre-conditions

- ALL Chunks 1-7 complete
- All route files use SQLAlchemy (no raw SQL remains in admin routes)
- All pages use shared components
- Branch: `elijahr/admin-ui-standardization`

## Exit Criteria

- Sidebar shows "Stacks" and "Corrections" instead of "Focus"
- /focus redirects to /stacks
- Old db.py removed, no remaining raw SQL in admin code
- Full test suite passes (backend + frontend)
- Frontend builds successfully
- Static assets updated
- All changes committed
- Branch ready for PR

## Finishing

After all tasks complete and tests pass, you MUST invoke the `finishing-a-development-branch` skill using the Skill tool to create the PR automatically.

The PR should summarize:
- Phase A: SQLAlchemy migration (4 databases, ~328 SQL calls replaced, Alembic migrations)
- Phase B: Admin UI standardization (DataTable, shared components, 6 list pages, FocusPage split)
- Bug fix: Correction log now has proper pagination and working filters
- Breaking change: Admin API envelope standardized to {items, total, page, per_page, pages}
