<!-- diagram-meta: {"source": "commands/feature-design.md", "source_hash": "sha256:12a9d7d21516261af772ff183088cb9729f7e58479181ce440f6ce4123199617", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: feature-design

Phase 2 of implementing-features: Create design document via brainstorming skill in synthesis mode, review via reviewing-design-docs, handle approval gate by execution mode, and fix findings.

```mermaid
flowchart TD
    Start([Phase 2 Start])
    PrereqCheck{Prerequisites met?}
    PrereqFail([STOP: Return to Phase 1.5])

    EscapeCheck{Escape hatch type?}
    SkipAll([Skip to Phase 3])

    CreateDesign[Dispatch brainstorming subagent]
    SynthMode[Synthesis mode: no questions]
    SaveDesign[Save design document]

    ReviewDesign[Dispatch reviewing-design-docs]
    ReviewFindings[Collect findings]

    ApprovalGate{Execution mode?}
    AutoFix[Auto-fix all findings]
    InteractiveWait[Present findings, wait]
    MostlyAutoCheck{Critical blockers?}
    PresentCritical[Present critical blockers]
    AutoFixNonCrit[Auto-fix non-critical]

    HasFindings{Findings exist?}
    DispatchFix[Dispatch executing-plans fix]
    FixComplete[Fix complete]

    VerifyDesign{Design doc exists?}
    Phase2Done([Phase 2 Complete])

    Start --> PrereqCheck
    PrereqCheck -->|No| PrereqFail
    PrereqCheck -->|Yes| EscapeCheck

    EscapeCheck -->|"Treat as ready"| SkipAll
    EscapeCheck -->|"Review first"| ReviewDesign
    EscapeCheck -->|None| CreateDesign

    CreateDesign --> SynthMode
    SynthMode --> SaveDesign
    SaveDesign --> ReviewDesign

    ReviewDesign --> ReviewFindings
    ReviewFindings --> ApprovalGate

    ApprovalGate -->|Autonomous| HasFindings
    ApprovalGate -->|Interactive| InteractiveWait
    ApprovalGate -->|Mostly autonomous| MostlyAutoCheck

    InteractiveWait --> HasFindings
    MostlyAutoCheck -->|Yes| PresentCritical
    PresentCritical --> HasFindings
    MostlyAutoCheck -->|No| HasFindings

    HasFindings -->|Yes| DispatchFix
    HasFindings -->|No| VerifyDesign
    DispatchFix --> FixComplete
    FixComplete --> VerifyDesign

    VerifyDesign -->|No| CreateDesign
    VerifyDesign -->|Yes| Phase2Done

    style Start fill:#2196F3,color:#fff
    style Phase2Done fill:#2196F3,color:#fff
    style PrereqFail fill:#2196F3,color:#fff
    style SkipAll fill:#2196F3,color:#fff
    style CreateDesign fill:#4CAF50,color:#fff
    style ReviewDesign fill:#4CAF50,color:#fff
    style DispatchFix fill:#4CAF50,color:#fff
    style PrereqCheck fill:#FF9800,color:#fff
    style EscapeCheck fill:#FF9800,color:#fff
    style ApprovalGate fill:#FF9800,color:#fff
    style MostlyAutoCheck fill:#FF9800,color:#fff
    style HasFindings fill:#FF9800,color:#fff
    style VerifyDesign fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
