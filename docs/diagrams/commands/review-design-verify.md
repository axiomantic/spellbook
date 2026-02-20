<!-- diagram-meta: {"source": "commands/review-design-verify.md", "source_hash": "sha256:5bd7f5286fc8a291f0c419d644297a0e09fd63c6fd2d5b912239b26ad9a751d0", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: review-design-verify

Phases 4-5 of reviewing-design-docs: verifies all interface claims against actual source code, escalates unverifiable claims to fact-checking, then simulates implementation per component to surface specification gaps.

```mermaid
flowchart TD
    Start([Start Phase 4-5]) --> Ifaces[List All Interfaces]

    Ifaces --> ReadSrc[Read Source Code]
    ReadSrc --> MarkV{Verified or Assumed?}

    MarkV -->|Verified| LogV[Log as VERIFIED]
    MarkV -->|Assumed| LogA[Log as ASSUMED - Critical]

    LogV --> MoreIf{More Interfaces?}
    LogA --> MoreIf

    MoreIf -->|Yes| ReadSrc
    MoreIf -->|No| Escalate{Escalation Triggers?}

    Escalate -->|Yes| FactCheck[Escalate to Fact-Checking]
    Escalate -->|No| SimStart[Start Implementation Sim]

    FactCheck --> SimStart

    SimStart --> PickComp[Pick Component]
    PickComp --> CanImpl{Implement Now?}

    CanImpl -->|Yes| LogReady[Log Ready]
    CanImpl -->|No| LogQuestions[Log Questions/Gaps]

    LogReady --> MustInvent[Identify Must-Invent]
    LogQuestions --> MustInvent

    MustInvent --> MustGuess[Identify Must-Guess]
    MustGuess --> MoreComp{More Components?}

    MoreComp -->|Yes| PickComp
    MoreComp -->|No| AllMarked{All Interfaces Marked?}

    AllMarked -->|Yes| Done([Phase 4-5 Complete])
    AllMarked -->|No| Ifaces

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style Ifaces fill:#2196F3,color:#fff
    style ReadSrc fill:#2196F3,color:#fff
    style LogV fill:#2196F3,color:#fff
    style LogA fill:#f44336,color:#fff
    style FactCheck fill:#4CAF50,color:#fff
    style SimStart fill:#2196F3,color:#fff
    style PickComp fill:#2196F3,color:#fff
    style LogReady fill:#2196F3,color:#fff
    style LogQuestions fill:#2196F3,color:#fff
    style MustInvent fill:#2196F3,color:#fff
    style MustGuess fill:#2196F3,color:#fff
    style MarkV fill:#FF9800,color:#fff
    style MoreIf fill:#FF9800,color:#fff
    style Escalate fill:#FF9800,color:#fff
    style CanImpl fill:#FF9800,color:#fff
    style MoreComp fill:#FF9800,color:#fff
    style AllMarked fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
