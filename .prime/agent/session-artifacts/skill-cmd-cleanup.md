# Skill & Command Cleanup Summary

## Deletions (3 items)

| Item | Type | Reason |
|------|------|--------|
| `skills/canvas/` | Skill directory | All canvas tools deleted (`canvas_open`, `canvas_write`, `canvas_close`, `canvas_list`) |
| `skills/canvas-decision/` | Skill directory | All canvas-decision tools deleted (`canvas_decision_open`, `canvas_decision_await`, `canvas_decision_cancel`) |
| `commands/canvas.md` | Command file | Canvas tools deleted |

## Cleaned Up References (12 files)

### Skills

| File | Tools Removed | Changes |
|------|---------------|---------|
| `skills/advanced-code-review/SKILL.md` | `pr_fetch`, `pr_diff`, `pr_files`, `pr_match_patterns` | Removed MCP Tools table; merged heading with Git Commands section. Migration note replaced with gh CLI. |
| `skills/code-review/SKILL.md` | `pr_fetch`, `pr_diff`, `pr_files`, `pr_match_patterns` | Replaced MCP Tool Integration table with gh CLI + git guidance. |
| `skills/distilling-prs/SKILL.md` | `pr_fetch`, `pr_diff`, `pr_files`, `pr_match_patterns`, `pr_bless_pattern` | Major rewrite: replaced MCP Tools table with gh/git; rewrote Phase 1, Examples, Builtin Patterns, and reflection sections to use native commands. |
| `skills/develop/SKILL.md` | `forge_project_init`, `workflow_state_save`, `workflow_state_update` | Removed forge_project_init mentions; replaced workflow_state_update with generic "state write" notation while preserving the merge-only pattern. |
| `skills/reflexion/SKILL.md` | `forge_iteration_return` | Rewrote Integration section to describe trigger conceptually without the deleted MCP tool. |
| `skills/using-skills/SKILL.md` | `spellbook_session_init`, `spellbook_config_set` | Simplified Session Init section; replaced checklist item. |

### Commands

| File | Tools Removed | Changes |
|------|---------------|---------|
| `commands/a2a.md` | `stint_check` | Replaced stint candidate with "no longer available" note. |
| `commands/advanced-code-review-context.md` | `pr_fetch` | Replaced Python code block with `gh pr view` and `gh pr diff` shell examples. |
| `commands/advanced-code-review-plan.md` | `pr_files` | Replaced with `gh pr view --json files` comment. |
| `commands/feature-config.md` | `workflow_state_save`, `workflow_state_update` | Replaced with "persistent state deep-merge" description. |
| `commands/feature-implement-execute.md` | `forge_roundtable_convene`, `forge_record_gate_completion`, `forge_iteration_advance` | Removed code block for roundtable convene; rewrote token enforcement section without deleted tools. |
| `commands/handoff.md` | `workflow_state_save`, `workflow_state_load`, `workflow_state_update` | Replaced all references with `persistWorkflowState`/`loadWorkflowState`/`updateWorkflowState`; updated MCP Tools Required table to generic State Persistence operations. |

## Not Touched

- No test files modified
- No docs files modified
- Only the 12 specified files + 3 deletions
