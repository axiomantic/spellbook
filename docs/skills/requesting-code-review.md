# requesting-code-review

Use when you want to review your own changes before submitting a PR. [DEPRECATED] Routes to code-review --self

!!! info "Origin"
    This skill originated from [obra/superpowers](https://github.com/obra/superpowers).

## Skill Content

``````````markdown
# Requesting Code Review (Deprecated)

<ROLE>
Routing agent. Immediately routes to the replacement skill.
</ROLE>

<CRITICAL>
This skill is deprecated. Routing to `code-review --self`.
</CRITICAL>

<analysis>
Deprecated skill. Routes to code-review --self for all functionality.
</analysis>

## Invariant Principles

1. **Route to Replacement** - Always route to `code-review --self`
2. **Pass Context Through** - Forward all provided context to replacement skill
3. **No Independent Execution** - This skill does not execute review logic itself

<reflection>
When this skill loads, immediately invoke the replacement. Do not attempt to execute legacy behavior.
</reflection>

## Automatic Routing

When this skill is loaded, immediately invoke:

```
/code-review --self
```

With any provided context passed through.

## Migration Guide

| Old Usage | New Equivalent |
|-----------|----------------|
| `requesting-code-review` | `code-review --self` |
| "Review my changes" | Same (auto-routes) |
| Pre-PR self-review | `code-review --self` |

## Why Deprecated?

The `code-review` skill consolidates all review functionality:
- `--self`: Pre-PR self-review (this functionality)
- `--feedback`: Process received feedback
- `--give`: Review someone else's code
- `--audit`: Comprehensive multi-pass review

See `code-review/SKILL.md` for full documentation.

<FORBIDDEN>
- Execute any review logic directly
- Ignore the replacement routing
- Maintain legacy behavior
</FORBIDDEN>
``````````
