<!-- diagram-meta: {"source": "commands/merge-worktree-resolve.md", "source_hash": "sha256:8ed240638a694c3c718f9e1e7abe302b549b76145a6553179d2f5c81a9214cad", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: merge-worktree-resolve

Phase 3 of merging-worktrees: delegates merge conflicts to the resolving-merge-conflicts skill with interface contract context, then verifies that resolved code matches contract specifications for type signatures and function behavior before continuing.

```mermaid
flowchart TD
    Start([Start Phase 3]) --> GatherCtx[Gather Interface Contracts]
    GatherCtx --> GatherPurpose[Gather Worktree Purpose]
    GatherPurpose --> GatherSigs[Gather Expected Signatures]

    GatherSigs --> Delegate[Invoke resolving-merge-conflicts]

    Delegate --> Resolution[Conflict Resolution Complete]

    Resolution --> CheckTypes{Type Signatures Match?}

    CheckTypes -->|Yes| CheckBehavior{Behavior Matches Spec?}
    CheckTypes -->|No| FixTypes[Fix to Match Contract]

    FixTypes --> CheckBehavior

    CheckBehavior -->|Yes| CheckBoth{Both Sides Honor Ifaces?}
    CheckBehavior -->|No| FixBehavior[Revert to Contract Version]

    FixBehavior --> CheckBoth

    CheckBoth -->|Yes| MergeContinue[Git Merge Continue]
    CheckBoth -->|No| FixBoth[Fix Interface Violations]

    FixBoth --> CheckTypes

    MergeContinue --> Done([Phase 3 Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style GatherCtx fill:#2196F3,color:#fff
    style GatherPurpose fill:#2196F3,color:#fff
    style GatherSigs fill:#2196F3,color:#fff
    style Delegate fill:#4CAF50,color:#fff
    style Resolution fill:#2196F3,color:#fff
    style FixTypes fill:#2196F3,color:#fff
    style FixBehavior fill:#2196F3,color:#fff
    style FixBoth fill:#2196F3,color:#fff
    style MergeContinue fill:#2196F3,color:#fff
    style CheckTypes fill:#f44336,color:#fff
    style CheckBehavior fill:#f44336,color:#fff
    style CheckBoth fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
