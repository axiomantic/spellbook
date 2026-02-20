<!-- diagram-meta: {"source": "commands/execute-work-packet.md", "source_hash": "sha256:5998cc1bb0df7dff5150fd2b4eff9e7289f9a3d250154c6925a191b1f6235c01", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: execute-work-packet

Execute a single work packet: parse, check dependencies, run TDD tasks with review and fact-check gates, then mark complete.

```mermaid
flowchart TD
    Start([Start]) --> P1[Phase 1: Parse Packet]
    P1 --> LoadManifest[Load Manifest]
    LoadManifest --> P2[Phase 2: Dependency Gate]
    P2 --> CheckDeps{All Deps Complete?}
    CheckDeps -->|No| WaitOrAbort{Wait or Abort?}
    WaitOrAbort -->|Wait| Poll[Poll 30s for 30min]
    Poll --> Timeout{Timeout?}
    Timeout -->|Yes| Abort([Abort])
    Timeout -->|No| CheckDeps
    WaitOrAbort -->|Abort| Abort
    CheckDeps -->|Yes| P3{Resume Mode?}
    P3 -->|Yes| LoadCheckpoint[Load Checkpoint]
    P3 -->|No| P4[Phase 4: Verify Worktree]
    LoadCheckpoint --> P4
    P4 --> BranchCheck{Branch Matches?}
    BranchCheck -->|No| HardFail([Hard Fail])
    BranchCheck -->|Yes| P5[Phase 5: TDD Task Loop]
    P5 --> DisplayTask[Display Task Info]
    DisplayTask --> TDD[/TDD Skill: Red-Green-Refactor/]
    TDD --> TDDPass{TDD Pass?}
    TDDPass -->|No| TDDFail([Stop: TDD Failed])
    TDDPass -->|Yes| CodeReview[/Code Review Skill/]
    CodeReview --> ReviewPass{Review Pass?}
    ReviewPass -->|No| FixReview[Address Feedback]
    FixReview --> TDD
    ReviewPass -->|Yes| FactCheck[/Fact-Check Skill/]
    FactCheck --> FactPass{Criteria Met?}
    FactPass -->|No| TDD
    FactPass -->|Yes| Checkpoint[Create Checkpoint]
    Checkpoint --> MoreTasks{More Tasks?}
    MoreTasks -->|Yes| DisplayTask
    MoreTasks -->|No| P6[Phase 6: Completion Marker]
    P6 --> Report[Phase 7: Report]
    Report --> Done([End])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style Abort fill:#4CAF50,color:#fff
    style HardFail fill:#4CAF50,color:#fff
    style TDDFail fill:#4CAF50,color:#fff
    style TDD fill:#4CAF50,color:#fff
    style CodeReview fill:#4CAF50,color:#fff
    style FactCheck fill:#4CAF50,color:#fff
    style CheckDeps fill:#FF9800,color:#fff
    style WaitOrAbort fill:#FF9800,color:#fff
    style Timeout fill:#FF9800,color:#fff
    style P3 fill:#FF9800,color:#fff
    style MoreTasks fill:#FF9800,color:#fff
    style TDDPass fill:#f44336,color:#fff
    style ReviewPass fill:#f44336,color:#fff
    style FactPass fill:#f44336,color:#fff
    style BranchCheck fill:#f44336,color:#fff
    style P1 fill:#2196F3,color:#fff
    style P2 fill:#2196F3,color:#fff
    style P4 fill:#2196F3,color:#fff
    style P5 fill:#2196F3,color:#fff
    style P6 fill:#2196F3,color:#fff
    style DisplayTask fill:#2196F3,color:#fff
    style Checkpoint fill:#2196F3,color:#fff
    style Report fill:#2196F3,color:#fff
    style LoadManifest fill:#2196F3,color:#fff
    style Poll fill:#2196F3,color:#fff
    style LoadCheckpoint fill:#2196F3,color:#fff
    style FixReview fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
