<!-- diagram-meta: {"source": "commands/review-plan-inventory.md", "source_hash": "sha256:3994c536dccf1634ad3f1bd027888a88248711390e6af3facb081f54b6e3f7a2", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: review-plan-inventory

Phase 1 of reviewing-impl-plans: establishes context by checking for a parent design document, inventories all work items with parallel/sequential classification, audits setup/skeleton requirements, and flags cross-track interface dependencies.

```mermaid
flowchart TD
    Start([Start Phase 1]) --> CheckDesign{Parent Design Doc?}

    CheckDesign -->|Yes| LogDesign[Log Design Doc Location]
    CheckDesign -->|No| JustifyNo[Require Justification]

    LogDesign --> MoreDetail{Plan Has More Detail?}
    JustifyNo --> RiskUp[Increase Risk Level]

    MoreDetail -->|Yes| Inventory[Inventory Work Items]
    MoreDetail -->|No| FlagGap[Flag Detail Gap]
    RiskUp --> Inventory
    FlagGap --> Inventory

    Inventory --> Classify[Classify Each Item]

    Classify --> IsParallel{Parallel or Sequential?}

    IsParallel -->|Parallel| LogPar[Log Parallel Item]
    IsParallel -->|Sequential| LogSeq[Log Sequential Item]

    LogPar --> RecordDeps[Record Dependencies]
    LogSeq --> RecordBlocks[Record Blocks/Blocked-By]

    RecordDeps --> MoreItems{More Work Items?}
    RecordBlocks --> MoreItems

    MoreItems -->|Yes| Classify
    MoreItems -->|No| Setup[Audit Setup/Skeleton]

    Setup --> GitRepo[Check Git Structure]
    GitRepo --> Config[Check Config Files]
    Config --> Types[Check Shared Types]
    Types --> Stubs[Check Interface Stubs]
    Stubs --> BuildTest[Check Build/Test Infra]

    BuildTest --> CrossTrack[Identify Cross-Track Interfaces]
    CrossTrack --> GateAll{All Items Classified?}

    GateAll -->|Yes| Deliver[Deliver Inventory Report]
    GateAll -->|No| Classify

    Deliver --> Done([Phase 1 Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style CheckDesign fill:#FF9800,color:#fff
    style LogDesign fill:#2196F3,color:#fff
    style JustifyNo fill:#2196F3,color:#fff
    style MoreDetail fill:#FF9800,color:#fff
    style RiskUp fill:#f44336,color:#fff
    style Inventory fill:#2196F3,color:#fff
    style Classify fill:#2196F3,color:#fff
    style IsParallel fill:#FF9800,color:#fff
    style LogPar fill:#2196F3,color:#fff
    style LogSeq fill:#2196F3,color:#fff
    style RecordDeps fill:#2196F3,color:#fff
    style RecordBlocks fill:#2196F3,color:#fff
    style MoreItems fill:#FF9800,color:#fff
    style Setup fill:#2196F3,color:#fff
    style GitRepo fill:#2196F3,color:#fff
    style Config fill:#2196F3,color:#fff
    style Types fill:#2196F3,color:#fff
    style Stubs fill:#2196F3,color:#fff
    style BuildTest fill:#2196F3,color:#fff
    style CrossTrack fill:#f44336,color:#fff
    style FlagGap fill:#2196F3,color:#fff
    style GateAll fill:#f44336,color:#fff
    style Deliver fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
