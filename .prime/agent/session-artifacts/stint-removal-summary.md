# Stint Removal Summary

## Date
Generated during session at /Users/eek/Development/spellbook

## Overview
Removed all stint-related code (Zeigarnik focus tracking stack) from spellbook source files. Tests and docs were NOT modified — those are separate work.

## Files Deleted (3)
1. **scripts/reset_bloated_stints.py** — One-time cleanup script for resetting bloated stint stacks
2. **spellbook/coordination/stint.py** — Core stint stack logic (push, pop, check, replace, correction classification)
3. **spellbook/stint_tools.py** — Backward compatibility shim re-exporting from `spellbook.coordination.stint`

## Files Modified (9)

### 1. hooks/spellbook_hook.py
- Removed `_stint_depth_check()` function (~80 lines) — checked stint stack depth and emitted behavioral mode + tree warnings
- Removed the `_stint_depth_check` call from `_handle_post_tool_use` (L1306-1309)
- Removed stint_stack save logic from `_handle_pre_compact` — no longer loads/merges stint_stack into workflow state before compaction
- Removed stint_stack restore logic from `_handle_session_start` — no longer calls `stint_replace` or appends focus stack info to recovery directive
- Updated comment about `_INTERACTIVE_EXCLUDED_TOOLS` (removed "stint depth checks")
- Updated `_handle_pre_compact` docstring

### 2. installer/components/hooks.py
- Removed "stint auto-push" from hook comment (L52)

### 3. spellbook/coordination/__init__.py
- Changed docstring from "curator and stint tracking" to "curator tracking"

### 4. spellbook/core/db.py
- Removed `_migrate_stint_stack_schema()` function (~55 lines) — schema migration for stint_stack table
- Removed `stint_stack` and `stint_correction_events` table creation (~45 lines)
- Removed associated indexes
- Removed call to `_migrate_stint_stack_schema(cursor)`

### 5. spellbook/db/spellbook_models.py
- Removed `StintStack` ORM model class (~22 lines)
- Removed `StintCorrectionEvent` ORM model class (~22 lines)

### 6. spellbook/mcp/tools/coordination.py
- Removed all 4 stint MCP tool functions: `stint_push`, `stint_pop`, `stint_check`, `stint_replace` (~200 lines)
- Kept `mcp_curator_track_prune` and `_require_session_id` helper
- Updated `__all__` to only contain `mcp_curator_track_prune`
- Updated module docstring and error message

### 7. spellbook/mcp/tools/misc.py
- Removed "stint_stack" mention from CRIT-2 comment about atomic read-merge-write

### 8. spellbook/sessions/injection.py
- Updated module docstring — removed reference to live caller in `spellbook.coordination.stint._validate_stint_entry`

### 9. spellbook/sessions/resume.py
- Removed `"stint_stack"` from `RECOVERABLE_FIELDS` set (used for workflow state save/restore across compactions)

## Remaining Artifacts (not removed — out of scope)
- Test files (e.g., `tests/test_stint*.py`) — separate task
- Docs files — separate task
- Database tables in existing installations — the tables will remain but are no longer created for new installs; existing data is inert
- `spellbook/admin/events.py` — `Subsystem.FOCUS` may still exist but is unused without stint events
- `__pycache__` files — will be stale but harmless; recompiled on next import

## Verification
All 9 modified files verified clean — no "stint" references remain. All 3 deleted files confirmed removed.
