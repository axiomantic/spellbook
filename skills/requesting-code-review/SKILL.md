---
name: requesting-code-review
description: "Use when you want to review your own changes before submitting a PR. [DEPRECATED] Routes to code-review --self"
deprecated: true
replacement: code-review --self
---

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

## Self-Check

Before completing review cycle:
- [ ] All Critical issues fixed and verified
- [ ] All Important issues fixed or explicitly deferred with rationale
- [ ] Re-review triggered if Critical fixes were substantial
- [ ] Feedback addressed with code/tests, not just acknowledgment

If ANY unchecked: STOP and fix.

## Handoff to Receiving Skill

When external feedback arrives after an internal review:

### Context Preservation
- Pass `review-manifest.json` path to receiving skill
- Include internal findings for cross-reference
- Note which internal findings overlap with external

### Invocation Pattern
```
When processing external PR feedback:
1. Load review-manifest.json from prior internal review (if exists)
2. Invoke receiving-code-review skill with:
   - External feedback source
   - Internal review artifacts path
   - Trust level for source
```

### Provenance Tracking
Mark each finding with source:
- `source: internal` - From code-reviewer agent
- `source: external` - From PR reviewer
- `source: merged` - External finding confirmed by internal

Template: `requesting-code-review/code-reviewer.md`
