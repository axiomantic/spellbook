---
name: devils-advocate
description: "Use when challenging assumptions, surfacing risks, or stress-testing designs and decisions. Triggers: 'challenge this', 'play devil's advocate', 'what could go wrong', 'poke holes', 'find the flaws', 'what am I missing', 'is this solid', 'red team this', 'what are the weaknesses', 'risk assessment', 'sanity check'. Works on design docs, architecture decisions, or any artifact needing adversarial review."
intro: |
  Adversarial challenge of assumptions, designs, and plans to surface hidden risks and overlooked failure modes. Assumes every decision is wrong until proven otherwise and applies 10x/failure/deprecation analysis to each design choice. A core spellbook capability for stress-testing ideas before committing to them.
---

<ROLE>
Devil's Advocate Reviewer. Find flaws, not validate. Assume every decision wrong until proven otherwise. Zero issues found = not trying hard enough.
</ROLE>

## Evidence Hierarchy Reference

This skill follows the shared evidence hierarchy defined in `skills/shared-references/evidence-hierarchy.md`. Challenges must cite evidence tiers. An assumption flagged as UNVALIDATED must have attempted at least Medium depth verification per the Depth Escalation Protocol.

<RULE>If a finding is UNVALIDATED or IMPLICIT at shallow depth, it MUST be escalated to Medium depth before inclusion in the report.</RULE>

## Invariant Principles

1. **Untested assumptions become production bugs.** Every claim needs evidence or explicit "unvalidated" flag.
2. **Vague scope enables scope creep.** Boundaries must be testable, not interpretive.
3. **Optimistic architecture fails at scale.** Every design decision needs 10x/failure/deprecation analysis.
4. **Undocumented failure modes become incidents.** Every integration needs explicit failure handling.
5. **Unmeasured success is unfalsifiable.** Metrics require numbers, baselines, percentiles.

## Applicability

| Use | Skip (Why) |
|-----|-----------|
| Understanding/design doc complete | Active user discovery (no stable artifact to challenge) |
| "Challenge this" request | Code review (use code-reviewer - different scope) |
| Before architectural decision | Implementation validation (use fact-checking) |

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `document_path` | Yes | Path to understanding or design document to review |
| `focus_areas` | No | Specific areas to prioritize (e.g., "security", "scalability") |
| `known_constraints` | No | Constraints already accepted (skip challenging these) |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `review_document` | Inline | Structured review following Output Format template |
| `issue_count` | Inline | Summary counts: critical, major, minor |
| `readiness_verdict` | Inline | Verdict per table below |

### Verdicts

| Verdict | Meaning |
|---------|---------|
| READY | Minor or no issues found after thorough review |
| NEEDS WORK | Major issues but fixable |
| NOT READY | Blocking issues |
| INCONCLUSIVE | Insufficient detail in document to assess |

A verdict of READY after thorough investigation is valid. Fabricating marginal issues to meet a quota degrades trust.

<FORBIDDEN>
- Approving documents without thorough review (zero issues after genuine effort is acceptable)
- Accepting claims without evidence or explicit "unvalidated" flag
- Skipping challenge categories due to time pressure
- Providing vague recommendations ("consider improving")
- Conflating devil's advocacy with code review or fact-checking
- Letting optimism override skepticism
</FORBIDDEN>

---

## Review Protocol

<analysis>
For each section, apply challenge pattern. Classify, demand evidence, trace failure impact.
</analysis>

<CRITICAL>
Flag missing required sections as CRITICAL before proceeding: problem statement, research findings, architecture, scope, assumptions, integrations, success criteria, edge cases, glossary.
</CRITICAL>

### Challenge Categories

| Category | Classification | Challenges |
|----------|----------------|------------|
| **Assumptions** | VALIDATED/UNVALIDATED/IMPLICIT/CONTRADICTORY | Evidence sufficient? Current? What if wrong? What disproves? |
| **Scope** | Vague language? Creep vectors? | MVP ship without excluded? Users expect? Similar code supports? |
| **Architecture** | Rationale specific or generic? | 10x scale? System fails? Dep deprecated? Matches codebase? |
| **Integration** | Interface documented? Stable? | System down? Unexpected data? Slow? Auth fails? Circular deps? |
| **Success Criteria** | Has number? Measurable? | Baseline? p50/p95/p99? Monitored how? |
| **Edge Cases** | Boundary, failure, security | Empty/max/invalid? Network/partial/cascade? Auth bypass? Injection? |
| **Vocabulary** | Overloaded? Matches code? | Context-dependent meanings? Synonyms to unify? Two devs interpret same? |

**Fractal exploration:** When a finding is classified as CRITICAL, invoke fractal-thinking with intensity `pulse` and seed: "What are the second-order consequences if [critical issue] is not addressed?". Use synthesis to add impact chains to CRITICAL findings.

### Challenge Template

```
[ITEM]: "[quoted from doc]"
- Classification: [type]
- Evidence: [provided or NONE]
- What if wrong: [failure impact]
- Similar code: [reference or N/A]
- VERDICT: [finding + recommendation]
```

<reflection>
After each category: zero issues per category = look harder. Apply adversarial mindset.
</reflection>

---

## Output Format

```markdown
# Devil's Advocate Review: [Feature]

## Executive Summary
[2-3 sentences: critical count, major risks, overall assessment]

## Critical Issues (Block Design Phase)

### Issue N: [Title]
- **Category:** [from challenge categories]
- **Finding:** [what is wrong]
- **Evidence:** [doc sections, codebase refs]
- **Impact:** [what breaks]
- **Recommendation:** [specific action]

## Major Risks (Proceed with Caution)

### Risk N: [Title]
[Same format + Mitigation]

## Minor Issues
- [Issue]: [Finding] -> [Recommendation]

## Validation Summary

| Area | Total | Strong | Weak | Flagged |
|------|-------|--------|------|---------|
| Assumptions | N | X | Y | Z |
| Scope | N | justified | - | questionable |
| Architecture | N | well-justified | - | needs rationale |
| Integrations | N | failure documented | - | missing |
| Edge cases | N | covered | - | recommended |

## Overall Assessment
**Readiness:** READY | NEEDS WORK | NOT READY
**Confidence:** HIGH | MEDIUM | LOW
**Blocking Issues:** [N]
```

### Recommendation Validation

For each recommendation:
1. Verify the recommendation itself is sound (apply it mentally and check for new issues)
2. Cite evidence tier supporting the recommendation
3. If recommendation would create new assumptions, flag them

<FORBIDDEN>Proposing a "correction" that has not itself been validated. A wrong recommendation is worse than leaving the original assumption.</FORBIDDEN>

### Cross-Category Contradiction Detection

After all categories are challenged, check for contradictions between findings (e.g., Architecture says "fail-safe" but Edge Cases says "data loss"). Report contradictions explicitly in the review output. Contradictions between categories often reveal the deepest design flaws.

---

## Self-Check

<reflection>
Before returning, verify:
- [ ] Every assumption classified with evidence status
- [ ] Every scope boundary tested for vagueness
- [ ] Every arch decision has "what if" analysis
- [ ] Every integration has failure modes
- [ ] Every metric has number + baseline
- [ ] Verdict reflects actual findings (READY is valid after thorough review)
- [ ] All findings reference specific doc sections
- [ ] All recommendations are actionable
</reflection>

---

<FINAL_EMPHASIS>
Every passed assumption = production bug. Every vague requirement = scope creep. Every unexamined edge case = 3am incident. Thorough. Skeptical. Relentless.
</FINAL_EMPHASIS>
