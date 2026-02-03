# /review-design-verify

## Command Content

``````````markdown
# Phase 4: Interface Verification

## Invariant Principles

1. **Read source before accepting any interface claim** - Assumed behavior from method names is the root cause of fabrication loops
2. **Every interface must be marked VERIFIED or ASSUMED** - No unmarked entries; the distinction drives the risk assessment
3. **Usage examples trump documentation** - When docs and actual usage diverge, actual usage is ground truth

<analysis>
INFERRED BEHAVIOR IS NOT VERIFIED BEHAVIOR.
`assert_model_updated(model, field=value)` might assert only those fields, require ALL changes, or behave differently.
</analysis>

<reflection>
YOU DO NOT KNOW until you READ THE SOURCE.
</reflection>

## Fabrication Anti-Pattern

| Wrong | Right |
|-------|-------|
| Assume from name | Read docstring, source |
| Code fails -> invent parameter | Find usage examples |
| Keep inventing | Write from VERIFIED behavior |

## Verification Table

| Interface | Verified/Assumed | Source Read | Notes |
|-----------|-----------------|-------------|-------|

**Every ASSUMED = critical gap.**

## Factchecker Escalation

Trigger: security claims, performance claims, concurrency claims, numeric claims, external references

Format: `**Escalate:** [claim] | Loc: [X] | Category: [Y] | Depth: SHALLOW/MEDIUM/DEEP`

---

# Phase 5: Implementation Simulation

Per component:
```
### Component: [name]
**Implement now?** YES/NO
**Questions:** [list]
**Must invent:** [what] - should specify: [why]
**Must guess:** [shape] - should specify: [why]
```
``````````
