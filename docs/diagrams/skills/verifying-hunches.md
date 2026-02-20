<!-- diagram-meta: {"source": "skills/verifying-hunches/SKILL.md", "source_hash": "sha256:574578062d5e23e01ab37931868044d2ee21324a8b82db13730ad92c389df2b4", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: verifying-hunches

Prevents premature root cause claims during debugging by enforcing hypothesis registration, specificity requirements, falsification criteria, and test-before-claim discipline.

```mermaid
flowchart TD
    Start([Eureka Moment Detected]) --> Stop[STOP: That Is a Hypothesis]

    Stop --> Register[Register in Eureka Registry]
    Register --> AssignID[Assign ID: H1, H2, ...]

    AssignID --> DejaVu{Deja Vu Check: Similar to Disproven?}

    DejaVu -->|High Similarity| WhatsDifferent{What Is Different?}
    WhatsDifferent -->|Can Explain| ProceedWithDiff[Proceed: Document Difference]
    WhatsDifferent -->|Cannot Explain| Abandon[Abandon Hypothesis]

    DejaVu -->|No Match| SpecificityCheck

    ProceedWithDiff --> SpecificityCheck

    SpecificityCheck{Specificity Passed?}

    SpecificityCheck -->|Missing Location| AddLocation[Specify file:line]
    SpecificityCheck -->|Missing Mechanism| AddMechanism[Specify Exact Mechanism]
    SpecificityCheck -->|Missing Symptom Link| AddLink[Specify Causal Chain]
    SpecificityCheck -->|Missing Prediction| AddPrediction[Specify If X Then Y]
    SpecificityCheck -->|All Present| DefineFalsification

    AddLocation --> SpecificityCheck
    AddMechanism --> SpecificityCheck
    AddLink --> SpecificityCheck
    AddPrediction --> SpecificityCheck

    DefineFalsification[Define Falsification Criteria] --> StatePrediction[State Prediction]

    StatePrediction --> Instrument[Add Logging/Breakpoint]
    Instrument --> NoteExpected[Note: Expected If Correct vs Wrong]

    NoteExpected --> Execute[Execute with Instrumentation]
    Execute --> Compare{Prediction vs Actual?}

    Compare -->|Matched| MatchCount{2+ Matches?}
    Compare -->|Contradicted| MarkDisproven[Mark DISPROVEN]
    Compare -->|Inconclusive| RefineTest[Refine Test + Retry]

    RefineTest --> StatePrediction

    MatchCount -->|Yes| MarkConfirmed[Mark CONFIRMED]
    MatchCount -->|No| AnotherTest[Design Another Test]
    AnotherTest --> StatePrediction

    MarkDisproven --> ConsiderAlts[Consider Alternatives]
    ConsiderAlts --> SunkCostCheck{Sunk Cost Bias?}
    SunkCostCheck -->|Yes: Continuing Disproven| ForceAbandon[Force Abandon]
    SunkCostCheck -->|No| NewHypothesis([New Hypothesis Cycle])

    ForceAbandon --> NewHypothesis

    MarkConfirmed --> CalibrateLanguage[Calibrate Language]
    CalibrateLanguage --> PreClaimGate{Pre-Claim Checklist?}

    PreClaimGate -->|All Checked| ClaimDiscovery[Claim: Confirmed Finding]
    PreClaimGate -->|Any Unchecked| StillHypothesis[Still a Hypothesis: Fix Gaps]
    StillHypothesis --> SpecificityCheck

    ClaimDiscovery --> Done([Verified Discovery])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style NewHypothesis fill:#4CAF50,color:#fff
    style Stop fill:#2196F3,color:#fff
    style Register fill:#2196F3,color:#fff
    style AssignID fill:#2196F3,color:#fff
    style DejaVu fill:#FF9800,color:#fff
    style WhatsDifferent fill:#FF9800,color:#fff
    style SpecificityCheck fill:#f44336,color:#fff
    style Compare fill:#FF9800,color:#fff
    style MatchCount fill:#FF9800,color:#fff
    style SunkCostCheck fill:#FF9800,color:#fff
    style PreClaimGate fill:#f44336,color:#fff
    style ProceedWithDiff fill:#2196F3,color:#fff
    style Abandon fill:#2196F3,color:#fff
    style AddLocation fill:#2196F3,color:#fff
    style AddMechanism fill:#2196F3,color:#fff
    style AddLink fill:#2196F3,color:#fff
    style AddPrediction fill:#2196F3,color:#fff
    style DefineFalsification fill:#2196F3,color:#fff
    style StatePrediction fill:#2196F3,color:#fff
    style Instrument fill:#2196F3,color:#fff
    style NoteExpected fill:#2196F3,color:#fff
    style Execute fill:#2196F3,color:#fff
    style MarkDisproven fill:#2196F3,color:#fff
    style MarkConfirmed fill:#2196F3,color:#fff
    style RefineTest fill:#2196F3,color:#fff
    style AnotherTest fill:#2196F3,color:#fff
    style ConsiderAlts fill:#2196F3,color:#fff
    style ForceAbandon fill:#2196F3,color:#fff
    style CalibrateLanguage fill:#2196F3,color:#fff
    style ClaimDiscovery fill:#2196F3,color:#fff
    style StillHypothesis fill:#2196F3,color:#fff
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
| Eureka Moment Detected | "You are here because you're about to claim a discovery. STOP." (line 15) |
| Register in Eureka Registry | Eureka Registry section (lines 36-48) |
| Assign ID: H1, H2 | Eureka Registry: id field (line 40) |
| Deja Vu Check | Eureka Registry: deja vu check before new hypothesis (line 47) |
| What Is Different? | Eureka Registry: "explain what's DIFFERENT or abandon" (line 47) |
| Specificity Passed? | Specificity Requirements (lines 62-68) |
| file:line | Specificity: Exact location (line 63) |
| Exact Mechanism | Specificity: Exact mechanism (line 64) |
| Causal Chain | Specificity: Symptom link (line 65) |
| If X Then Y | Specificity: Testable prediction (line 66) |
| Define Falsification Criteria | Invariant Principle 4: Falsification before confirmation (line 30) |
| State Prediction | Test-Before-Claim step 1 (line 74) |
| Add Logging/Breakpoint | Test-Before-Claim step 2: Instrument (line 75) |
| Execute with Instrumentation | Test-Before-Claim step 3: Execute (line 76) |
| Prediction vs Actual? | Test-Before-Claim step 4: Compare (line 77) |
| 2+ Matches? | Test-Before-Claim step 5: CONFIRMED requires 2+ matches (line 78) |
| Sunk Cost Bias? | FORBIDDEN: Sunk Cost (line 107) |
| Pre-Claim Checklist? | Pre-Claim Checklist (lines 82-91) |
| Calibrate Language | Confidence Calibration table (lines 53-58) |
