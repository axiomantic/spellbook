---
description: "Phase 4-5 of reviewing-impl-plans: Completeness Checks and Escalation"
---

# Phase 4: Completeness Checks

You are executing Phases 4-5 of the implementation plan review. Your job is to verify completeness of definitions of done, risk assessments, QA checkpoints, agent responsibilities, and dependency graphs, then escalate claims requiring fact-checking.

## Invariant Principles

1. **Subjective criteria are not acceptance criteria** - "Works well" or "clean code" are not testable; demand measurable, pass/fail outcomes
2. **Every phase needs a risk assessment** - Undocumented risks are unmitigated risks; absence of risk documentation is itself a finding
3. **Escalate what you cannot verify** - Technical claims that require execution or external validation must be forwarded to fact-checking, not assumed correct

## Definition of Done per Work Item

For EACH work item:
```
Work Item: [name]
Definition of Done: YES / NO / PARTIAL

If YES, verify:
[ ] Testable criteria (not subjective)
[ ] Measurable outcomes
[ ] Specific outputs enumerated
[ ] Clear pass/fail determination

If NO/PARTIAL: [what acceptance criteria must be added]
```

## Risk Assessment per Phase

For EACH phase:
```
Phase: [name]
Risks documented: YES / NO

If NO, identify:
1. [Risk] - likelihood H/M/L, impact H/M/L
Mitigation: [required]
Rollback point: [required]
```

## QA Checkpoints

| Phase | QA Checkpoint | Test Types | Pass Criteria | Failure Procedure |
|-------|---------------|------------|---------------|-------------------|
| | YES/NO | | | |

Required skill integrations:
- [ ] auditing-green-mirage after tests pass
- [ ] systematic-debugging on failures
- [ ] fact-checking for security/performance/behavior claims

## Agent Responsibility Matrix

For each agent/work stream:
```
Agent: [name]
Responsibilities: [specific deliverables]
Inputs (depends on): [deliverables from others]
Outputs (provides to): [deliverables to others]
Interfaces owned: [specifications]

Clarity: CLEAR / AMBIGUOUS
If ambiguous: [what needs clarification]
```

## Dependency Graph

```
Agent A (Setup)
    |
Agent B (Core)  ->  Agent C (API)
    |                  |
Agent D (Tests) <- - - -

All dependencies explicit: YES/NO
Circular dependencies: YES/NO (if yes: CRITICAL)
Missing declarations: [list]
```

# Phase 5: Escalation

Claims requiring `fact-checking` skill (do NOT self-verify):

| Category | Examples |
|----------|----------|
| Security | "Input sanitized", "tokens cryptographically random" |
| Performance | "O(n) complexity", "queries optimized", "cached" |
| Concurrency | "Thread-safe", "atomic operations", "no race conditions" |
| Test utility behavior | Claims about how helpers, mocks, fixtures behave |
| Library behavior | Specific claims about third-party behavior |

For each escalated claim:
```
Claim: [quote]
Location: [section/line]
Category: [Security/Performance/etc.]
Depth: SHALLOW / MEDIUM / DEEP
```

<RULE>
After review, invoke `fact-checking` skill with pre-flagged claims. Do NOT implement your own fact-checking.
</RULE>

## Deliverable

Populate the following sections of the review report:
- Claims escalated to fact-checking: F
- Definition of done gaps
- Risk assessment gaps
- QA checkpoint gaps
- Agent responsibility clarity issues
- Dependency graph issues (especially circular dependencies)
- All escalated claims with category and depth

Return your completed completeness and escalation audit as structured output for the orchestrator.
