<!-- diagram-meta: {"source": "commands/finish-branch-execute.md", "source_hash": "sha256:111e4887fa1179a0753135f8d77d08db026c3f3e6fb083dbdf002edece3c0a3a", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: finish-branch-execute

Execute the user's chosen integration option: local merge, PR creation, keep as-is, or discard with explicit confirmation.

```mermaid
flowchart TD
    Start([User Choice Received]) --> OptionSwitch{"Which Option?"}
    OptionSwitch -->|Option 1: Merge| CheckoutBase["Checkout Base Branch"]
    OptionSwitch -->|Option 2: PR| PushBranch["Push Branch\nto Origin"]
    OptionSwitch -->|Option 3: Keep| ReportKeep([Report: Keeping\nBranch As-Is])
    OptionSwitch -->|Option 4: Discard| ShowWarning["Show Discard\nWarning"]
    CheckoutBase --> PullLatest["Pull Latest\nBase Branch"]
    PullLatest --> MergeBranch["Merge Feature\nBranch"]
    MergeBranch --> PostMergeTest["Run Post-Merge\nTests"]
    PostMergeTest --> MergeTestGate{"Tests Pass?"}
    MergeTestGate -->|No| MergeFail([Report Failure\nKeep Branch])
    MergeTestGate -->|Yes| DeleteBranch["Delete Feature\nBranch"]
    DeleteBranch --> ToCleanup1["Invoke\nfinish-branch-cleanup"]
    PushBranch --> CreatePR["Create PR\nvia gh"]
    CreatePR --> ReportURL["Report PR URL"]
    ReportURL --> ToCleanup2["Invoke\nfinish-branch-cleanup"]
    ShowWarning --> TypeConfirm{"User Types\n'discard'?"}
    TypeConfirm -->|No / Partial| RejectDiscard([Discard Cancelled])
    TypeConfirm -->|Yes| CheckoutDiscard["Checkout Base\nBranch"]
    CheckoutDiscard --> ForceDelete["Force Delete\nFeature Branch"]
    ForceDelete --> ToCleanup3["Invoke\nfinish-branch-cleanup"]
    ToCleanup1 --> Done([Integration Complete])
    ToCleanup2 --> Done
    ToCleanup3 --> Done

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style ReportKeep fill:#4CAF50,color:#fff
    style MergeFail fill:#f44336,color:#fff
    style RejectDiscard fill:#f44336,color:#fff
    style CheckoutBase fill:#2196F3,color:#fff
    style PullLatest fill:#2196F3,color:#fff
    style MergeBranch fill:#2196F3,color:#fff
    style PostMergeTest fill:#2196F3,color:#fff
    style DeleteBranch fill:#2196F3,color:#fff
    style PushBranch fill:#2196F3,color:#fff
    style CreatePR fill:#2196F3,color:#fff
    style ReportURL fill:#2196F3,color:#fff
    style ShowWarning fill:#2196F3,color:#fff
    style CheckoutDiscard fill:#2196F3,color:#fff
    style ForceDelete fill:#2196F3,color:#fff
    style ToCleanup1 fill:#4CAF50,color:#fff
    style ToCleanup2 fill:#4CAF50,color:#fff
    style ToCleanup3 fill:#4CAF50,color:#fff
    style OptionSwitch fill:#FF9800,color:#fff
    style TypeConfirm fill:#FF9800,color:#fff
    style MergeTestGate fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
