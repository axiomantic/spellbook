# /request-review-execute

## Command Content

``````````markdown
# Phases 3-6: Dispatch + Triage + Execute + Gate

## Invariant Principles

1. **Findings require evidence** - Every finding must include location and evidence fields; unsubstantiated observations are discarded
2. **Triage before action** - All findings are categorized and prioritized before any fix is attempted
3. **Quality gate is non-negotiable** - The final gate decision (approve, iterate, escalate) is based on remaining unresolved findings, not subjective confidence

## Phase 3: DISPATCH

**Input:** Phase 2 context
**Output:** Review findings from agent

Agent: `agents/code-reviewer.md`

The code-reviewer agent provides:
- Approval Decision Matrix (verdict determination)
- Evidence Collection Protocol (systematic evidence gathering)
- Review Gates (ordered checklist: Security, Correctness, Plan Compliance, Quality, Polish)
- Suggestion Format (GitHub suggestion blocks)
- Collaborative communication style

1. Invoke code-reviewer agent with context
2. Pass: files, plan reference, git range, description
3. Block until agent returns findings
4. Validate findings have required fields (location, evidence)

**Exit criteria:** Valid findings received

## Phase 4: TRIAGE

**Input:** Phase 3 findings
**Output:** Categorized, prioritized findings

1. Sort findings by severity (Critical first)
2. Group by file for efficient fixing
3. Identify quick wins vs substantial fixes
4. Flag any findings needing clarification

**Exit criteria:** Findings triaged and prioritized

## Phase 5: EXECUTE

**Input:** Phase 4 triaged findings
**Output:** Fixes applied

1. Address Critical findings first (blocking)
2. Address High findings (blocking threshold)
3. Address Medium/Low as time permits
4. Document deferred items with rationale

**Exit criteria:** Blocking findings addressed

## Phase 6: GATE

**Input:** Phase 5 fix status
**Output:** Proceed/block decision

1. Apply severity gate rules (see Gate Rules in orchestrator SKILL.md)
2. Determine if re-review needed
3. Update review status
4. Report final verdict

**Exit criteria:** Clear proceed/block decision with rationale

## Re-Review Triggers

**MUST re-review when:**
- Critical finding was fixed (verify fix correctness)
- >=3 High findings fixed (check for regressions)
- Fix adds >100 lines of new code
- Fix modifies files outside original review scope

**MAY skip re-review when:**
- Only Low/Nit/Medium addressed
- Fix is mechanical (rename, formatting, typo)

## Deferral Documentation

When deferring a High finding, document:
1. Finding ID and summary
2. Reason for deferral (time constraint, follow-up planned, risk accepted)
3. Follow-up tracking (ticket number, target date)
4. Explicit acknowledgment of risk

<CRITICAL>
No Critical finding may be deferred. Critical = must fix before merge.
</CRITICAL>
``````````
