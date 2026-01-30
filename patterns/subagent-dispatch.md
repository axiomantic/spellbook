# Subagent Dispatch Pattern

## Invariant Principles

1. **Context is cost.** Every token in main context persists; subagent context is discarded after synthesis.
2. **Subagents isolate complexity.** Exploration, research, parallel work belong in disposable contexts.
3. **Main context preserves continuity.** User feedback loops, accumulated evidence, safety decisions require persistent state.
4. **Output must be actionable.** Subagents return summaries, not data dumps.

## Decision Schema

```
<analysis>
- Does task need 3+ file reads for one answer? → subagent
- Is scope uncertain / exploratory? → subagent (Explore)
- Are tasks parallel-independent? → multiple subagents
- Needs user feedback iteration? → main context
- Builds on established context? → main context
- Safety-critical git operation? → main context
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

When running in OpenCode with custom agents (yolo, yolo-focused), subagents must inherit the parent's agent type to preserve permissions.

**Detection:** Check your system prompt for agent indicators:

- "operating in YOLO mode" → use `subagent_type: "yolo"`
- "YOLO mode with a focus on precision" → use `subagent_type: "yolo-focused"`
- No YOLO indicators → use `subagent_type: "general"` (default)

**Critical:** When dispatching subagents, use the same agent type you're running under. This ensures:

- `yolo` parent → `yolo` subagents (full autonomous permissions)
- `general` parent → `general` subagents (standard permissions)

**Exception:** For pure exploration tasks (finding files, searching code) where you explicitly want read-only behavior, you may use `explore` even when parent is YOLO.

## Prompt Requirements

Every subagent prompt:

1. Clear task + expected output format
2. Scope boundaries (what NOT to do)
3. Relevant conversation context
4. NegativePrompt: explicit prohibitions prevent drift

## Output Contract

- Return summary, not raw data
- Large outputs → file path only
- Orchestrator synthesizes for user

## Usage Reference

```markdown
Use subagent dispatch pattern (patterns/subagent-dispatch.md).
Launch [Type] agent for [task].
```
