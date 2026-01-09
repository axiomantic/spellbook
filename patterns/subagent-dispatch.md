# Subagent Dispatch Pattern

## Purpose
Standard decision framework for when to use subagents vs main context. Reference this instead of repeating heuristics.

## Quick Decision Tree

```
Task requires reading 3+ files for single answer? → Subagent
Task has uncertain scope / exploration needed?   → Subagent (Explore)
Task is parallel-independent from other tasks?   → Multiple subagents
Task needs iterative user feedback?              → Main context
Task builds on established conversation context? → Main context
Task is safety-critical git operation?           → Main context
```

## Subagent Types

| Type | Use When |
|------|----------|
| `Explore` | Codebase exploration, finding files, understanding structure |
| `general-purpose` | Multi-step tasks, research, implementation |
| `Plan` | Architecture decisions, implementation planning |
| `Bash` | Command execution, git operations |

## Cost-Benefit Analysis

Use subagent when: `subagent_cost < main_context_cost`

Where:
- `subagent_cost` = instructions + work + output summary
- `main_context_cost` = all intermediate steps kept in conversation

## Prompt Requirements

Good subagent prompts include:
1. Clear task description
2. Expected output format
3. Scope boundaries (what NOT to do)
4. Context needed from conversation

## Output Handling

- Subagent returns summary, not raw data
- Orchestrator synthesizes for user
- Large outputs go to files, return path only

## Usage in Skills

```markdown
## Research Phase
Use subagent dispatch pattern (patterns/subagent-dispatch.md).
Launch Explore agent for codebase analysis.
```
