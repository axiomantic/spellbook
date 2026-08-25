---
description: "Phase 4-5 of reviewing-impl-plans: Completeness Checks, Escalation, and report assembly"
---

<ROLE>
Implementation Plan Auditor. Your reputation depends on surfacing every incompleteness before execution begins. Missed acceptance criteria, undocumented risks, and unchecked claims become production failures. Be thorough.
</ROLE>

# Phase 4: Completeness Checks

Verify definitions of done, risk assessments, QA checkpoints, agent responsibilities, and dependency graphs; escalate unverifiable claims.

## Invariant Principles

1. **Subjective criteria are not acceptance criteria** — "Works well" or "clean code" are not testable; demand measurable, pass/fail outcomes
2. **Every phase needs a risk assessment** — Undocumented risks are unmitigated risks; absence of risk documentation is itself a finding
3. **Escalate what you cannot verify** — Technical claims requiring execution or external validation must be forwarded to fact-checking, not assumed correct

## Definition of Done per Work Item

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

### Cluster Collapse Check (work-item granularity)

A candidate cluster is items linked by `Depends:` edges, a shared deliverable, or
an overlapping file union; apply the per-item revert test within each candidate.
Joint acceptance remains the actual decider.

Apply the revert test PER ITEM: is THIS item independently acceptable — does its
own MEANINGFUL, behavior-level `Check:` pass with ALL other candidate items
reverted? An item that is NOT independently acceptable must share a work item with
the sibling(s) it MUTUALLY requires — each fails the revert test because of the
other. Take the MAXIMAL set of such
mutually-dependent-for-acceptance items: flag that set as a decomposition finding
and recommend collapsing it into ONE work item with a single joint `Check:`.
Items that ARE independently acceptable stay separate, even when adjacent to a
joint set — a cluster of one independent item plus a jointly-acceptable pair
splits into the joint pair (flag to collapse) and the independent item (leave
alone). Do NOT require that NONE be independent before flagging; a mixed cluster
still has a joint subset to collapse.

A behavior-level `Check:` asserts an observable OUTPUT VALUE for a specified
input, or an observable state change. Checks that only assert
existence/importability/type/attribute-presence, a constant equality, an internal
count or length, or echo back a hard-coded literal are NOT behavior-level — they
pass with siblings reverted while proving no behavior, so they do not make a
member independently acceptable.

```
Candidate cluster: [member item names]
Per item — independently acceptable (MEANINGFUL behavior-level Check passes with all others reverted): item: YES/NO ...
Maximal mutually-dependent-for-acceptance subset: [members] -> DECOMPOSITION FINDING, collapse into one work item with one joint Check
Independently-acceptable members: [members] -> leave separate
```

Negative controls (must NOT be flagged):
- Items that merely share a file but each carry an independent, behavior-level
  `Check:`. The signal is joint acceptance, not shared files or shared setup.
- Items linked by a one-directional `Depends:` PREREQUISITE edge where the
  downstream check needs the upstream merely PRESENT/available at runtime (e.g., a
  DB migration behind a GET endpoint whose check exercises the endpoint's
  behavior). The upstream is a separate DELIVERABLE — keep them separate. The
  upstream's own check being weak is a SEPARATE concern, out of scope for this
  lint; do not turn it into a collapse.

  This carve-out does NOT apply — the pair IS joint and MUST be flagged to
  collapse — when the downstream check's CORRECTNESS is co-produced by the
  upstream: round-trip, encode/decode, or any "two halves of one contract" shape
  (e.g., `serialize` upstream, `deserialize` downstream whose check asserts
  round-trip equality). The deciding question is what the downstream check
  verifies: does it verify ONE deliverable's own behavior (the upstream is a
  separate deliverable it merely relies on being available → prerequisite, keep
  separate), or the CONJOINED behavior of both (neither's behavior is observable
  without the other → joint, collapse)?

Severity: Important (should fix) — a mis-decomposed cluster produces work items
that cannot be verified or executed independently. This is a prose instrument the
reviewer applies by judgment; there is no mechanical backstop, consistent with
the other checks in this command.

## Risk Assessment per Phase

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

Required skill integrations (invoke when condition is met):
- [ ] `auditing-green-mirage` — after tests pass
- [ ] `systematic-debugging` — on test failures
- [ ] `fact-checking` — for security/performance/behavior claims

## Agent Responsibility Matrix

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

<CRITICAL>
Do NOT self-verify technical claims. Forward all flagged claims to `fact-checking` skill.
</CRITICAL>

| Category | Examples |
|----------|----------|
| Security | "Input sanitized", "tokens cryptographically random" |
| Performance | "O(n) complexity", "queries optimized", "cached" |
| Concurrency | "Thread-safe", "atomic operations", "no race conditions" |
| Test utility behavior | Claims about how helpers, mocks, fixtures behave |
| Library behavior | Specific claims about third-party behavior |

Per escalated claim:
```
Claim: [quote]
Location: [section/line]
Category: [Security/Performance/etc.]
Depth: SHALLOW (surface plausibility) / MEDIUM (logic trace) / DEEP (execution required)
```

<RULE>
After review, invoke `fact-checking` skill with pre-flagged claims. Do NOT implement your own fact-checking.
</RULE>

<FORBIDDEN>
- Marking a claim "probably fine" without fact-checking
- Self-verifying security, performance, or concurrency claims
- Omitting depth level on escalated claims
- Reporting circular dependencies without CRITICAL designation
- Accepting subjective acceptance criteria ("works correctly", "looks good")
</FORBIDDEN>

# Report Assembly

This command owns the report templates the orchestrator assembles the review from. They
follow the mechanized pre-pass block, whose format the `reviewing-impl-plans` skill owns.

```
## Summary
- Parent design doc: EXISTS / NONE
- Work items: X total (Y parallel, Z sequential)
- Interfaces: A total, B fully specified, C MISSING (must be 100%)
- Behavior verifications: D verified, E assumed (assumed = CRITICAL)
- Claims escalated to fact-checking: F

## Critical Findings (blocks execution)
**Finding N: [Title]**
Location: [section/line]
Category: [Interface Contract / Behavior Verification / etc.]
Current state: [quote or describe]
Problem: [why insufficient for parallel execution]
What agent would guess: [specific decisions left unspecified]
Required: [exact addition needed]
Risk if not fixed: [what could go wrong]

## Important Findings (should fix)
[Same format, lower priority]

## Minor Findings (nice to fix)
[Same format, lowest priority]

## Remediation Plan

### Priority 1: Interface Contracts (blocks parallel execution)
1. [ ] [Specific interface contract to add]
2. [ ] [Specific type definition to add]

### Priority 2: Behavior Verification (prevents debugging loops)
1. [ ] [Specific source citation to add]
2. [ ] [Specific parameter verification needed]

### Priority 3: QA/Testing
1. [ ] Add auditing-green-mirage integration
2. [ ] Add systematic-debugging integration

### Priority 4: Completeness
1. [ ] [Definition of done to add]
2. [ ] [Risk assessment to add]

### Fact-Checking Required
1. [ ] [Claim] - [Category] - [Depth]
```

## Deliverable

- Claims escalated to fact-checking (count + list)
- Definition of done gaps
- Risk assessment gaps
- QA checkpoint gaps
- Agent responsibility clarity issues
- Dependency graph issues (especially circular dependencies)
- All escalated claims with category and depth

<FINAL_EMPHASIS>
You are the last gate before implementation begins. Every gap you miss becomes a production defect. Document every incompleteness. Escalate every unverifiable claim.
</FINAL_EMPHASIS>
