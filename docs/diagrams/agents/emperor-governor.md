<!-- diagram-meta: {"source": "agents/emperor-governor.md", "source_hash": "sha256:de41ed5a63ac99d5528062e8df983257e4e4d9b21e8ee1615a4cacf4cc7cd9b5", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: emperor-governor

Resource governance agent that tracks scope creep, token usage, and project drift. Reports pure measurements without opinions or recommendations.

```mermaid
flowchart TD
    Start([Start: Governance\nCheck Requested])
    Invoke[/Honor-Bound Invocation/]

    EstBaseline["Establish Baseline:\nOriginal Scope"]
    MapCurrent["Map Current State:\nWhat Exists Now"]
    CalcDelta["Calculate Delta:\nAdded Beyond Original"]
    IdentifyDrift["Identify Drift Factors:\nWhere Scope Expanded"]

    MeasureCreep["Measure Scope\nCreep Factor"]
    MeasureFocus["Measure Focus\nDrift Topics"]
    MeasureResource["Measure Resource\nUsage vs Estimate"]

    CutCandidates["Identify Cut\nCandidates"]

    OpinionGate{"Pure Measurement?\nNo Opinion Leaked?"}
    RemoveOpinion["Remove Opinions\nand Recommendations"]

    DefensibleGate{"Numbers\nDefensible?"}
    ReCount["Re-count and\nVerify Metrics"]

    GenResourceReport["Generate Resource\nReport (JSON)"]
    GenDriftAssessment["Generate Drift\nAssessment"]

    Done([End: Report Delivered])

    Start --> Invoke
    Invoke --> EstBaseline
    EstBaseline --> MapCurrent
    MapCurrent --> CalcDelta
    CalcDelta --> IdentifyDrift

    IdentifyDrift --> MeasureCreep
    MeasureCreep --> MeasureFocus
    MeasureFocus --> MeasureResource
    MeasureResource --> CutCandidates

    CutCandidates --> OpinionGate
    OpinionGate -->|Opinion Found| RemoveOpinion
    RemoveOpinion --> OpinionGate
    OpinionGate -->|Pure Data| DefensibleGate

    DefensibleGate -->|Not Defensible| ReCount
    ReCount --> DefensibleGate
    DefensibleGate -->|Defensible| GenResourceReport

    GenResourceReport --> GenDriftAssessment
    GenDriftAssessment --> Done

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style Invoke fill:#4CAF50,color:#fff
    style EstBaseline fill:#2196F3,color:#fff
    style MapCurrent fill:#2196F3,color:#fff
    style CalcDelta fill:#2196F3,color:#fff
    style IdentifyDrift fill:#2196F3,color:#fff
    style MeasureCreep fill:#2196F3,color:#fff
    style MeasureFocus fill:#2196F3,color:#fff
    style MeasureResource fill:#2196F3,color:#fff
    style CutCandidates fill:#2196F3,color:#fff
    style RemoveOpinion fill:#2196F3,color:#fff
    style ReCount fill:#2196F3,color:#fff
    style GenResourceReport fill:#2196F3,color:#fff
    style GenDriftAssessment fill:#2196F3,color:#fff
    style OpinionGate fill:#f44336,color:#fff
    style DefensibleGate fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation / start-end |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Honor-Bound Invocation | Lines 14-15: Honor pledge before measurement |
| Establish Baseline | Lines 53: Analysis step 1 - original scope |
| Map Current State | Lines 54: Analysis step 2 - what exists now |
| Calculate Delta | Lines 55: Analysis step 3 - added beyond original |
| Identify Drift Factors | Lines 56: Analysis step 4 - where scope expanded |
| Measure Scope Creep Factor | Lines 61: current_items / original_items |
| Measure Focus Drift Topics | Lines 62: Tangential topics count |
| Measure Resource Usage | Lines 63: Tokens/time spent vs estimated |
| Identify Cut Candidates | Lines 90-96: Items not in original scope |
| Pure Measurement? | Lines 74-75: Reflection - is this pure measurement? |
| Numbers Defensible? | Lines 76: Would another observer reach same counts? |
| Generate Resource Report | Lines 81-103: JSON resource report format |
| Generate Drift Assessment | Lines 107-131: Drift assessment markdown format |
