<!-- diagram-meta: {"source": "commands/merge-work-packets.md", "source_hash": "sha256:083184aa5b4860bb3eaebfd7c15f0b6103481ca2981cd32e33a419e8cf4adeb2", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: merge-work-packets

Integrates completed work packets by verifying all tracks, invoking the merging-worktrees skill, handling conflicts, running QA gates, and reporting final integration status.

```mermaid
flowchart TD
    Start([Start Merge]) --> ContinueCheck{--continue-merge?}

    ContinueCheck -->|No| LoadManifest[Step 1: Load Manifest]
    ContinueCheck -->|Yes| VerifyIntegrity

    LoadManifest --> VerifyTracks[Step 2: Verify All Tracks]
    VerifyTracks --> TracksGate{All Tracks Complete?}

    TracksGate -->|No| ReportIncomplete[Report Incomplete Tracks]
    ReportIncomplete --> Abort([Abort Merge])

    TracksGate -->|Yes| PrepareBranches[Step 3: Prepare Branch List]
    PrepareBranches --> DisplayPlan[Display Merge Plan]
    DisplayPlan --> InvokeSmartMerge[Step 4: merging-worktrees Skill]

    InvokeSmartMerge --> MergeResult{Merge Result?}

    MergeResult -->|Success| VerifyIntegrity[Step 6: Verify Integrity]
    MergeResult -->|Conflicts| HandleConflicts[Step 5: Handle Conflicts]
    MergeResult -->|Error| ReportError[Report Error]
    ReportError --> Abort

    HandleConflicts --> UserChoice{Manual or Abort?}
    UserChoice -->|Manual| PauseForUser[Pause for Resolution]
    PauseForUser --> WaitContinue([Wait for --continue-merge])
    UserChoice -->|Abort| CleanupBranch[Clean Up Merge Branch]
    CleanupBranch --> Abort

    VerifyIntegrity --> BranchCheck{On Correct Branch?}
    BranchCheck -->|No| BranchError[Report Branch Error]
    BranchError --> Abort
    BranchCheck -->|Yes| CommitAncestry[Verify Track Commits]

    CommitAncestry --> AncestryGate{All Commits in History?}
    AncestryGate -->|No| AncestryError[Report Missing Commits]
    AncestryError --> Abort
    AncestryGate -->|Yes| RunQA[Step 7: Run QA Gates]

    RunQA --> Pytest[Gate: pytest]
    Pytest --> PytestGate{pytest Passes?}
    PytestGate -->|No| QAFail[Report Gate Failure]
    QAFail --> Abort
    PytestGate -->|Yes| AuditGM[Gate: audit-green-mirage]

    AuditGM --> AuditGate{Audit Passes?}
    AuditGate -->|No| QAFail
    AuditGate -->|Yes| FactCheck[Gate: fact-checking]

    FactCheck --> FactGate{Fact Check Passes?}
    FactGate -->|No| QAFail
    FactGate -->|Yes| CustomGates[Gate: Custom Commands]

    CustomGates --> CustomGate{All Custom Pass?}
    CustomGate -->|No| QAFail
    CustomGate -->|Yes| ReportSuccess[Step 8: Success Report]

    ReportSuccess --> Done([Merge Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style Abort fill:#2196F3,color:#fff
    style WaitContinue fill:#2196F3,color:#fff
    style ContinueCheck fill:#FF9800,color:#fff
    style TracksGate fill:#f44336,color:#fff
    style MergeResult fill:#FF9800,color:#fff
    style UserChoice fill:#FF9800,color:#fff
    style BranchCheck fill:#FF9800,color:#fff
    style AncestryGate fill:#f44336,color:#fff
    style PytestGate fill:#f44336,color:#fff
    style AuditGate fill:#f44336,color:#fff
    style FactGate fill:#f44336,color:#fff
    style CustomGate fill:#f44336,color:#fff
    style InvokeSmartMerge fill:#4CAF50,color:#fff
    style AuditGM fill:#4CAF50,color:#fff
    style FactCheck fill:#4CAF50,color:#fff
    style LoadManifest fill:#2196F3,color:#fff
    style VerifyTracks fill:#2196F3,color:#fff
    style ReportIncomplete fill:#2196F3,color:#fff
    style PrepareBranches fill:#2196F3,color:#fff
    style DisplayPlan fill:#2196F3,color:#fff
    style HandleConflicts fill:#2196F3,color:#fff
    style PauseForUser fill:#2196F3,color:#fff
    style CleanupBranch fill:#2196F3,color:#fff
    style VerifyIntegrity fill:#2196F3,color:#fff
    style CommitAncestry fill:#2196F3,color:#fff
    style AncestryError fill:#2196F3,color:#fff
    style BranchError fill:#2196F3,color:#fff
    style RunQA fill:#2196F3,color:#fff
    style Pytest fill:#2196F3,color:#fff
    style QAFail fill:#2196F3,color:#fff
    style CustomGates fill:#2196F3,color:#fff
    style ReportSuccess fill:#2196F3,color:#fff
    style ReportError fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
