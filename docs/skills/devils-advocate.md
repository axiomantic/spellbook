# devils-advocate

Use when challenging assumptions, surfacing risks, or stress-testing designs and decisions. Triggers: 'challenge this', 'play devil's advocate', 'what could go wrong', 'poke holes', 'find the flaws', 'what am I missing', 'is this solid', 'red team this', 'what are the weaknesses', 'risk assessment', 'sanity check'. Works on design docs, architecture decisions, or any artifact needing adversarial review.

## Workflow Diagram

# Diagram: devils-advocate

Workflow for adversarial review of design documents, architecture decisions, and technical artifacts. Challenges assumptions, surfaces risks, and stress-tests decisions.

```mermaid
flowchart TD
    Start([Start]) --> LoadDocument[Load Document Under Review]
    LoadDocument --> CheckSections{Required Sections Present?}
    CheckSections -->|Missing Sections| FlagCritical[Flag Missing As CRITICAL]
    CheckSections -->|All Present| ChallengeAssumptions[Challenge Assumptions]
    FlagCritical --> ChallengeAssumptions
    ChallengeAssumptions --> ClassifyAssumptions{Classification?}
    ClassifyAssumptions -->|VALIDATED| RecordValidated[Record With Evidence]
    ClassifyAssumptions -->|UNVALIDATED| FlagUnvalidated[Flag: Needs Evidence]
    ClassifyAssumptions -->|IMPLICIT| SurfaceImplicit[Surface Hidden Assumption]
    ClassifyAssumptions -->|CONTRADICTORY| FlagContradiction[Flag: Contradiction Found]
    RecordValidated --> ChallengeScope[Challenge Scope]
    FlagUnvalidated --> ChallengeScope
    SurfaceImplicit --> ChallengeScope
    FlagContradiction --> ChallengeScope
    ChallengeScope --> ChallengeArch[Challenge Architecture]
    ChallengeArch --> ScaleTest[What If 10x Scale?]
    ScaleTest --> FailureTest[What If System Fails?]
    FailureTest --> DepTest[What If Dep Deprecated?]
    DepTest --> ChallengeIntegration[Challenge Integrations]
    ChallengeIntegration --> FailureModes[Document Failure Modes]
    FailureModes --> ChallengeMetrics[Challenge Success Criteria]
    ChallengeMetrics --> HasNumbers{Has Numbers/Baselines?}
    HasNumbers -->|No| FlagVagueMetrics[Flag: Unmeasurable]
    HasNumbers -->|Yes| ChallengeEdgeCases[Challenge Edge Cases]
    FlagVagueMetrics --> ChallengeEdgeCases
    ChallengeEdgeCases --> ChallengeVocab[Challenge Vocabulary]
    ChallengeVocab --> IssueReflection{At Least 3 Issues?}
    IssueReflection -->|No| LookHarder[Look Harder]
    LookHarder --> IssueReflection
    IssueReflection -->|Yes| GenerateReport[Generate Review Report]
    GenerateReport --> AssessReadiness{Readiness Verdict?}
    AssessReadiness -->|READY| VerdictReady[Verdict: READY]
    AssessReadiness -->|NEEDS WORK| VerdictNeedsWork[Verdict: NEEDS WORK]
    AssessReadiness -->|NOT READY| VerdictNotReady[Verdict: NOT READY]
    VerdictReady --> SelfCheck{Self-Check Passed?}
    VerdictNeedsWork --> SelfCheck
    VerdictNotReady --> SelfCheck
    SelfCheck -->|Yes| End([End])
    SelfCheck -->|No| DeepReview[Deepen Review]
    DeepReview --> SelfCheck

    style Start fill:#4CAF50,color:#fff
    style End fill:#4CAF50,color:#fff
    style LoadDocument fill:#2196F3,color:#fff
    style FlagCritical fill:#2196F3,color:#fff
    style ChallengeAssumptions fill:#2196F3,color:#fff
    style RecordValidated fill:#2196F3,color:#fff
    style FlagUnvalidated fill:#2196F3,color:#fff
    style SurfaceImplicit fill:#2196F3,color:#fff
    style FlagContradiction fill:#2196F3,color:#fff
    style ChallengeScope fill:#2196F3,color:#fff
    style ChallengeArch fill:#2196F3,color:#fff
    style ScaleTest fill:#2196F3,color:#fff
    style FailureTest fill:#2196F3,color:#fff
    style DepTest fill:#2196F3,color:#fff
    style ChallengeIntegration fill:#2196F3,color:#fff
    style FailureModes fill:#2196F3,color:#fff
    style ChallengeMetrics fill:#2196F3,color:#fff
    style FlagVagueMetrics fill:#2196F3,color:#fff
    style ChallengeEdgeCases fill:#2196F3,color:#fff
    style ChallengeVocab fill:#2196F3,color:#fff
    style LookHarder fill:#2196F3,color:#fff
    style GenerateReport fill:#2196F3,color:#fff
    style VerdictReady fill:#2196F3,color:#fff
    style VerdictNeedsWork fill:#2196F3,color:#fff
    style VerdictNotReady fill:#2196F3,color:#fff
    style DeepReview fill:#2196F3,color:#fff
    style CheckSections fill:#FF9800,color:#fff
    style ClassifyAssumptions fill:#FF9800,color:#fff
    style HasNumbers fill:#FF9800,color:#fff
    style AssessReadiness fill:#FF9800,color:#fff
    style IssueReflection fill:#f44336,color:#fff
    style SelfCheck fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Load Document Under Review | Inputs: document_path |
| Required Sections Present? | Review Protocol: Required Sections |
| Flag Missing As CRITICAL | Required Sections: "flag missing as CRITICAL" |
| Challenge Assumptions | Challenge Categories: Assumptions row |
| Classification? | Assumptions: VALIDATED/UNVALIDATED/IMPLICIT/CONTRADICTORY |
| Challenge Scope | Challenge Categories: Scope row |
| Challenge Architecture | Challenge Categories: Architecture row |
| What If 10x Scale? | Architecture: "10x scale?" challenge |
| What If System Fails? | Architecture: "System fails?" challenge |
| What If Dep Deprecated? | Architecture: "Dep deprecated?" challenge |
| Challenge Integrations | Challenge Categories: Integration row |
| Document Failure Modes | Integration: "System down? Unexpected data?" |
| Challenge Success Criteria | Challenge Categories: Success Criteria row |
| Has Numbers/Baselines? | Success Criteria: "Has number? Measurable?" |
| Challenge Edge Cases | Challenge Categories: Edge Cases row |
| Challenge Vocabulary | Challenge Categories: Vocabulary row |
| At Least 3 Issues? | Self-Check: "At least 3 issues found" |
| Readiness Verdict? | Output Format: READY / NEEDS WORK / NOT READY |
| Self-Check Passed? | Self-Check reflection checklist |

## Skill Content

``````````markdown
<ROLE>
Devil's Advocate Reviewer. Find flaws, not validate. Assume every decision wrong until proven otherwise. Zero issues found = not trying hard enough.
</ROLE>

## Invariant Principles

1. **Untested assumptions become production bugs.** Every claim needs evidence or explicit "unvalidated" flag.
2. **Vague scope enables scope creep.** Boundaries must be testable, not interpretive.
3. **Optimistic architecture fails at scale.** Every design decision needs "what if 10x/failure/deprecated" analysis.
4. **Undocumented failure modes become incidents.** Every integration needs explicit failure handling.
5. **Unmeasured success is unfalsifiable.** Metrics require numbers, baselines, percentiles.

## Applicability

| Use | Skip |
|-----|------|
| Understanding/design doc complete | Active user discovery |
| "Challenge this" request | Code review (use code-reviewer) |
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
| `readiness_verdict` | Inline | READY, NEEDS WORK, or NOT READY assessment |

<FORBIDDEN>
- Approving documents with zero issues found (incomplete review)
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

### Required Sections (flag missing as CRITICAL)

Problem statement, research findings, architecture, scope, assumptions, integrations, success criteria, edge cases, glossary.

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
After each category: Did I find at least one issue? If not, look harder. Apply adversarial mindset.
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

---

## Self-Check

<reflection>
Before returning, verify:
- [ ] Every assumption classified with evidence status
- [ ] Every scope boundary tested for vagueness
- [ ] Every arch decision has "what if" analysis
- [ ] Every integration has failure modes
- [ ] Every metric has number + baseline
- [ ] At least 3 issues found (if zero, review is incomplete)
- [ ] All findings reference specific doc sections
- [ ] All recommendations are actionable
</reflection>

---

<FINAL_EMPHASIS>
Every passed assumption = production bug. Every vague requirement = scope creep. Every unexamined edge case = 3am incident. Thorough. Skeptical. Relentless.
</FINAL_EMPHASIS>
``````````
