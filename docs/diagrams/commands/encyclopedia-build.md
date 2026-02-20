<!-- diagram-meta: {"source": "commands/encyclopedia-build.md", "source_hash": "sha256:381a68eecb97664a9e71fa8f2e4d55d6c365ade70f8b93075e28c75026c467e9", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: encyclopedia-build

Build encyclopedia content: glossary, architecture skeleton, decision log, and entry points (Phases 2-5).

```mermaid
flowchart TD
    Start([Start]) --> P2[Phase 2: Glossary]
    P2 --> ScanTerms[Scan Project-Specific Terms]
    ScanTerms --> FilterGeneric{Generic Term?}
    FilterGeneric -->|Yes| Skip[Skip Term]
    FilterGeneric -->|No| AddGlossary[Add to Glossary Table]
    Skip --> MoreTerms{More Terms?}
    AddGlossary --> MoreTerms
    MoreTerms -->|Yes| ScanTerms
    MoreTerms -->|No| P3[Phase 3: Architecture]
    P3 --> IdentifyComponents[Identify 3-5 Components]
    IdentifyComponents --> MapFlows[Map Data Flows]
    MapFlows --> NodeCheck{Nodes <= 7?}
    NodeCheck -->|No| Simplify[Simplify Diagram]
    Simplify --> NodeCheck
    NodeCheck -->|Yes| DrawMermaid[Create Mermaid Diagram]
    DrawMermaid --> P4[Phase 4: Decision Log]
    P4 --> FindDecisions[Find Architectural Decisions]
    FindDecisions --> RecordWhy[Record WHY Not WHAT]
    RecordWhy --> Alternatives[Document Alternatives]
    Alternatives --> P5[Phase 5: Entry Points]
    P5 --> MapEntries[Map Entry Points]
    MapEntries --> DocTesting[Document Testing Commands]
    DocTesting --> Done([End])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style FilterGeneric fill:#FF9800,color:#fff
    style MoreTerms fill:#FF9800,color:#fff
    style NodeCheck fill:#f44336,color:#fff
    style P2 fill:#2196F3,color:#fff
    style P3 fill:#2196F3,color:#fff
    style P4 fill:#2196F3,color:#fff
    style P5 fill:#2196F3,color:#fff
    style ScanTerms fill:#2196F3,color:#fff
    style AddGlossary fill:#2196F3,color:#fff
    style IdentifyComponents fill:#2196F3,color:#fff
    style MapFlows fill:#2196F3,color:#fff
    style DrawMermaid fill:#2196F3,color:#fff
    style FindDecisions fill:#2196F3,color:#fff
    style RecordWhy fill:#2196F3,color:#fff
    style Alternatives fill:#2196F3,color:#fff
    style MapEntries fill:#2196F3,color:#fff
    style DocTesting fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
