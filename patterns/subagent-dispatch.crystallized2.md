# Subagent Dispatch Pattern

<ROLE>
Orchestrator. Your reputation depends on keeping main context lean and subagent output actionable. Bloated orchestration context and raw-data returns are failures.
</ROLE>

## Invariant Principles

1. **Context is cost.** Every token in main context persists; subagent context is discarded after synthesis.
2. **Subagents isolate complexity.** Exploration, research, parallel work belong in disposable contexts.
3. **Main context preserves continuity.** User feedback loops, accumulated evidence, safety decisions require persistent state.

## Decision Schema

```
<analysis>
- Does task need 3+ file reads for one answer? → subagent
- Is scope uncertain / exploratory? → subagent (Explore)
- Are tasks parallel-independent? → multiple subagents
- Needs user feedback iteration? → main context
- Builds on established context? → main context
- Safety-critical git operation? → main context
  (safety-critical = commit, push, checkout, restore, stash, merge, rebase, reset)
</analysis>

<reflection>
subagent_cost = instructions + work + output_summary
main_cost = all intermediate steps retained
Use subagent when: subagent_cost < main_cost
</reflection>
```

## Subagent Types

| Type    | Trigger                                                     |
| ------- | ----------------------------------------------------------- |
| Explore | Finding files, understanding structure, codebase navigation |
| General | Multi-step research, implementation tasks                   |
| Plan    | Architecture decisions, implementation planning             |
| Bash    | Command execution, git operations                           |

### OpenCode Agent Inheritance

When running in OpenCode, subagents must inherit the parent agent type.

| System prompt contains | Use subagent_type |
|---|---|
| "operating in YOLO mode" | `yolo` |
| "YOLO mode with a focus on precision" | `yolo-focused` |
| Neither | `general` (default) |

<CRITICAL>
Exception: For pure read-only exploration (finding files, searching code), use `explore` even when parent is YOLO.
</CRITICAL>

## Prompt Requirements

Every subagent prompt:

1. Clear task + expected output format
2. Scope boundaries (what NOT to do)
3. Relevant conversation context
4. NegativePrompt: explicit prohibitions prevent drift

**Example (well-formed):**
```
Launch Explore agent.
Task: Find all Django model files in src/ that define a `status` field.
Return: List of file paths and field definitions only. Do NOT read test files.
Context: We are auditing status field usage before a migration.
```

## Output Contract

- Return summary, not raw data
- Output >50 lines → write to file, return path only
- Orchestrator synthesizes for user

**Error handling:** If subagent returns insufficient or malformed output, re-dispatch with tighter scope. Do NOT expand main context with the raw output to compensate.

<FORBIDDEN>
- Returning raw file contents or command output to main context
- Dispatching a subagent without scope boundaries (what NOT to do)
- Using main context for tasks that meet subagent dispatch criteria
- Expanding main context with subagent raw output when synthesis fails
- Skipping subagent dispatch because "it seems simple"
</FORBIDDEN>

## Usage Reference

```markdown
Use subagent dispatch pattern (patterns/subagent-dispatch.md).
Launch [Type] agent for [task].
```

<FINAL_EMPHASIS>
Every token in main context has a cost that compounds. Dispatch aggressively. Return summaries only. A bloated orchestrator is a failed orchestrator.
</FINAL_EMPHASIS>
