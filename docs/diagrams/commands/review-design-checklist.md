<!-- diagram-meta: {"source": "commands/review-design-checklist.md", "source_hash": "sha256:0b01c80f76a98070240ce3ad0224355aea90bddadc872b7ba13fc6e2e66fea55", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: review-design-checklist

Phases 2-3 of reviewing-design-docs: runs a completeness checklist across eight architecture categories, applies REST API design checks, then detects hand-waving language and unjustified magic numbers.

```mermaid
flowchart TD
    Start([Start Phase 2-3]) --> Checklist[Completeness Checklist]

    Checklist --> Arch[Evaluate Architecture]
    Checklist --> Data[Evaluate Data Models]
    Checklist --> API[Evaluate API/Protocol]
    Checklist --> FS[Evaluate Filesystem]
    Checklist --> Err[Evaluate Errors]
    Checklist --> Edge[Evaluate Edge Cases]
    Checklist --> Deps[Evaluate Dependencies]
    Checklist --> Mig[Evaluate Migration]

    Arch --> MarkItems[Mark SPECIFIED/VAGUE/MISSING/NA]
    Data --> MarkItems
    API --> MarkItems
    FS --> MarkItems
    Err --> MarkItems
    Edge --> MarkItems
    Deps --> MarkItems
    Mig --> MarkItems

    MarkItems --> APICheck{API Specified or Vague?}
    APICheck -->|Yes| REST[REST API Checklist]
    APICheck -->|No| HandWave[Hand-Waving Detection]

    REST --> Richardson[Richardson Maturity Check]
    Richardson --> Postel[Postel Law Compliance]
    Postel --> Hyrum[Hyrum Law Awareness]
    Hyrum --> APISpec[API Specification Checklist]
    APISpec --> ErrStd[Error Response Standard]
    ErrStd --> HandWave

    HandWave --> VagueLang[Flag Vague Language]
    VagueLang --> AssumedK[Flag Assumed Knowledge]
    AssumedK --> MagicNum[Flag Magic Numbers]
    MagicNum --> Gate{All Items Marked?}

    Gate -->|Yes| Done([Phase 2-3 Complete])
    Gate -->|No| Checklist

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style Checklist fill:#2196F3,color:#fff
    style Arch fill:#2196F3,color:#fff
    style Data fill:#2196F3,color:#fff
    style API fill:#2196F3,color:#fff
    style FS fill:#2196F3,color:#fff
    style Err fill:#2196F3,color:#fff
    style Edge fill:#2196F3,color:#fff
    style Deps fill:#2196F3,color:#fff
    style Mig fill:#2196F3,color:#fff
    style MarkItems fill:#2196F3,color:#fff
    style REST fill:#4CAF50,color:#fff
    style Richardson fill:#2196F3,color:#fff
    style Postel fill:#2196F3,color:#fff
    style Hyrum fill:#2196F3,color:#fff
    style APISpec fill:#2196F3,color:#fff
    style ErrStd fill:#2196F3,color:#fff
    style HandWave fill:#2196F3,color:#fff
    style VagueLang fill:#2196F3,color:#fff
    style AssumedK fill:#2196F3,color:#fff
    style MagicNum fill:#2196F3,color:#fff
    style APICheck fill:#FF9800,color:#fff
    style Gate fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
