---
name: receiving-code-review
description: "Use when you have received code review feedback and need to process it. [DEPRECATED] Routes to code-review --feedback"
deprecated: true
replacement: code-review --feedback
---

# Receiving Code Review (Deprecated)

<ROLE>
Routing agent. Immediately routes to the replacement skill.
</ROLE>

<CRITICAL>
This skill is deprecated. Routing to `code-review --feedback`.
</CRITICAL>

<analysis>
Deprecated skill. Routes to code-review --feedback for all functionality.
</analysis>

## Invariant Principles

1. **Route to Replacement** - Always route to `code-review --feedback`
2. **Pass Context Through** - Forward all provided context to replacement skill
3. **No Independent Execution** - This skill does not execute feedback processing logic itself

<reflection>
When this skill loads, immediately invoke the replacement. Do not attempt to execute legacy behavior.
</reflection>

## Automatic Routing

When this skill is loaded, immediately invoke:

```
/code-review --feedback
```

With any provided context passed through.

## Migration Guide

| Old Usage | New Equivalent |
|-----------|----------------|
| `receiving-code-review` | `code-review --feedback` |
| "Address review comments" | Same (auto-routes) |
| "Fix PR feedback" | `code-review --feedback --pr <num>` |

## Why Deprecated?

The `code-review` skill consolidates all review functionality:
- `--self`: Pre-PR self-review
- `--feedback`: Process received feedback (this functionality)
- `--give`: Review someone else's code
- `--audit`: Comprehensive multi-pass review

See `code-review/SKILL.md` for full documentation.

<FORBIDDEN>
- Execute any feedback processing logic directly
- Ignore the replacement routing
- Maintain legacy behavior
</FORBIDDEN>
