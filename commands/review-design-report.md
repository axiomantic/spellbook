---
description: "Phases 6-7 of reviewing-design-docs: Findings Report + Remediation Plan"
---

# Phase 6: Findings Report

## Invariant Principles

1. **Findings require exact remediation** - "Needs more detail" is not actionable; specify precisely what must be added and where
2. **Scores must be reproducible** - Another reviewer following the same checklist should arrive at the same category counts
3. **Remediation plans are ordered by dependency** - Fix structural gaps before detail gaps; interfaces before implementations

## Score

```
## Score
| Category | Specified | Vague | Missing | N/A |
|----------|-----------|-------|---------|-----|

Hand-Waving: N | Assumed: M | Magic Numbers: P | Escalated: Q
```

## Findings Format

```
**#N: [Title]**
Loc: [X]
Current: [quote]
Problem: [why insufficient]
Would guess: [decisions]
Required: [exact fix]
```

---

# Phase 7: Remediation Plan

```
### P1: Critical (Blocks Implementation)
1. [ ] [addition + acceptance criteria]

### P2: Important
1. [ ] [clarification]

### P3: Minor
1. [ ] [improvement]

### Factcheck Verification
1. [ ] [claim] - [category] - [depth]

### Additions
- [ ] Diagram: [type] showing [what]
- [ ] Table: [topic] specifying [what]
- [ ] Section: [name] covering [what]
```
