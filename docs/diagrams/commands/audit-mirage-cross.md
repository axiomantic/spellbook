<!-- diagram-meta: {"source": "commands/audit-mirage-cross.md", "source_hash": "sha256:930a9d7002e59050a8bbe3e8b7b6fc8ae2b56e25803034cb89ffbb857df72465", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: audit-mirage-cross

Cross-test suite-level analysis after individual test audits.

```mermaid
flowchart TD
    Start([Start: Individual Audits Done]) --> ScanProd[Scan Production Code]

    ScanProd --> Untested{Untested Functions?}
    Untested -->|Found| LogUntested[Log Untested Functions]
    Untested -->|None| SideEffect

    LogUntested --> SideEffect{Side-Effect Only Coverage?}
    SideEffect -->|Found| LogSideEffect[Log Side-Effect Coverage]
    SideEffect -->|None| ErrorPaths

    LogSideEffect --> ErrorPaths[Enumerate Error Branches]
    ErrorPaths --> ErrorCheck{Error Paths Tested?}
    ErrorCheck -->|Missing| LogErrors[Log Missing Error Tests]
    ErrorCheck -->|All Covered| EdgeCases

    LogErrors --> EdgeCases[Identify Edge Cases]
    EdgeCases --> EdgeCheck{Edge Cases Tested?}
    EdgeCheck -->|Missing| LogEdges[Log Missing Edge Cases]
    EdgeCheck -->|All Covered| Isolation

    LogEdges --> Isolation[Check Test Isolation]
    Isolation --> IsoCheck{Isolation Issues?}
    IsoCheck -->|Shared State| LogShared[Log Shared State Issues]
    IsoCheck -->|External Deps| LogExternal[Log External Dependencies]
    IsoCheck -->|No Cleanup| LogCleanup[Log Cleanup Issues]
    IsoCheck -->|Clean| Report

    LogShared --> Report[Compile Cross-Analysis]
    LogExternal --> Report
    LogCleanup --> Report

    Report --> Gate{Coverage Gaps Critical?}
    Gate -->|Yes| FlagCritical[Flag Critical Gaps]
    Gate -->|No| Done([Cross-Analysis Complete])
    FlagCritical --> Done

    style Start fill:#2196F3,color:#fff
    style ScanProd fill:#2196F3,color:#fff
    style Untested fill:#FF9800,color:#fff
    style LogUntested fill:#f44336,color:#fff
    style SideEffect fill:#FF9800,color:#fff
    style LogSideEffect fill:#f44336,color:#fff
    style ErrorPaths fill:#2196F3,color:#fff
    style ErrorCheck fill:#FF9800,color:#fff
    style LogErrors fill:#f44336,color:#fff
    style EdgeCases fill:#2196F3,color:#fff
    style EdgeCheck fill:#FF9800,color:#fff
    style LogEdges fill:#f44336,color:#fff
    style Isolation fill:#2196F3,color:#fff
    style IsoCheck fill:#FF9800,color:#fff
    style LogShared fill:#f44336,color:#fff
    style LogExternal fill:#f44336,color:#fff
    style LogCleanup fill:#f44336,color:#fff
    style Report fill:#2196F3,color:#fff
    style Gate fill:#f44336,color:#fff
    style FlagCritical fill:#f44336,color:#fff
    style Done fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
