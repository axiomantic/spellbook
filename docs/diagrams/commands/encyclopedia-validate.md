<!-- diagram-meta: {"source": "commands/encyclopedia-validate.md", "source_hash": "sha256:c8e8b208b33b58fd87bd2a75f88fd02a2ee6377cdc85b5f37ebb732605335139", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: encyclopedia-validate

Assemble and validate encyclopedia content, then write to the output path (Phase 6).

```mermaid
flowchart TD
    Start([Start]) --> Assemble[Assemble All Sections]
    Assemble --> LineCheck{Lines < 1000?}
    LineCheck -->|No| Trim[Trim to Overview Level]
    Trim --> LineCheck
    LineCheck -->|Yes| ImplCheck{Implementation Details?}
    ImplCheck -->|Yes| RemoveImpl[Remove Impl Details]
    RemoveImpl --> ImplCheck
    ImplCheck -->|No| DupCheck{Duplicates README?}
    DupCheck -->|Yes| Deduplicate[Remove Duplicated Content]
    Deduplicate --> DupCheck
    DupCheck -->|No| GlossaryCheck{Terms Project-Specific?}
    GlossaryCheck -->|No| RemoveGeneric[Remove Generic Terms]
    RemoveGeneric --> GlossaryCheck
    GlossaryCheck -->|Yes| DiagramCheck{Diagram <= 7 Nodes?}
    DiagramCheck -->|No| SimplifyDiag[Simplify Architecture]
    SimplifyDiag --> DiagramCheck
    DiagramCheck -->|Yes| DecisionCheck{Decisions Explain WHY?}
    DecisionCheck -->|No| FixDecisions[Add Rationale]
    FixDecisions --> DecisionCheck
    DecisionCheck -->|Yes| AllPass{All Checks Pass?}
    AllPass -->|Yes| EncodePath[Compute Project-Encoded Path]
    AllPass -->|No| Assemble
    EncodePath --> WriteFile[Write Encyclopedia]
    WriteFile --> Done([End])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style LineCheck fill:#f44336,color:#fff
    style ImplCheck fill:#f44336,color:#fff
    style DupCheck fill:#f44336,color:#fff
    style GlossaryCheck fill:#f44336,color:#fff
    style DiagramCheck fill:#f44336,color:#fff
    style DecisionCheck fill:#f44336,color:#fff
    style AllPass fill:#f44336,color:#fff
    style Assemble fill:#2196F3,color:#fff
    style EncodePath fill:#2196F3,color:#fff
    style WriteFile fill:#2196F3,color:#fff
    style Trim fill:#2196F3,color:#fff
    style RemoveImpl fill:#2196F3,color:#fff
    style Deduplicate fill:#2196F3,color:#fff
    style RemoveGeneric fill:#2196F3,color:#fff
    style SimplifyDiag fill:#2196F3,color:#fff
    style FixDecisions fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
