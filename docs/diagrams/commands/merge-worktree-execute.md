<!-- diagram-meta: {"source": "commands/merge-worktree-execute.md", "source_hash": "sha256:9e604dd546024b715eb36bf80de9354ca3a0f3608dd01dda7588b4342da45c09", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: merge-worktree-execute

Phase 2 of merging-worktrees: merges worktrees sequentially in dependency order, running the full test suite after each round, escalating conflicts to the resolution phase and test failures to the systematic-debugging skill.

```mermaid
flowchart TD
    Start([Start Phase 2]) --> Checkout[Checkout Base Branch]
    Checkout --> Pull[Pull Latest from Origin]
    Pull --> PickRound[Pick Next Round]

    PickRound --> PickWT[Pick Worktree in Round]
    PickWT --> GetBranch[Get Worktree Branch]
    GetBranch --> Merge[Git Merge Branch]

    Merge --> MergeOK{Merge Succeeded?}

    MergeOK -->|Yes| LogSuccess[Log Merge Success]
    MergeOK -->|No| Resolve[Invoke merge-worktree-resolve]

    Resolve --> MoreWT{More Worktrees in Round?}
    LogSuccess --> MoreWT

    MoreWT -->|Yes| PickWT
    MoreWT -->|No| RunTests[Run Full Test Suite]

    RunTests --> TestsPass{Tests Pass?}

    TestsPass -->|Yes| MoreRound{More Rounds?}
    TestsPass -->|No| Debug[Invoke systematic-debugging]

    Debug --> Fix[Fix Issues and Commit]
    Fix --> ReRunTests[Re-run Tests]
    ReRunTests --> RePass{Tests Pass?}

    RePass -->|Yes| MoreRound
    RePass -->|No| Debug

    MoreRound -->|Yes| PickRound
    MoreRound -->|No| Done([Phase 2 Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style Checkout fill:#2196F3,color:#fff
    style Pull fill:#2196F3,color:#fff
    style PickRound fill:#2196F3,color:#fff
    style PickWT fill:#2196F3,color:#fff
    style GetBranch fill:#2196F3,color:#fff
    style Merge fill:#2196F3,color:#fff
    style LogSuccess fill:#2196F3,color:#fff
    style Resolve fill:#4CAF50,color:#fff
    style RunTests fill:#2196F3,color:#fff
    style Debug fill:#4CAF50,color:#fff
    style Fix fill:#2196F3,color:#fff
    style ReRunTests fill:#2196F3,color:#fff
    style MergeOK fill:#FF9800,color:#fff
    style MoreWT fill:#FF9800,color:#fff
    style TestsPass fill:#f44336,color:#fff
    style MoreRound fill:#FF9800,color:#fff
    style RePass fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
