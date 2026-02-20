<!-- diagram-meta: {"source": "commands/finish-branch-cleanup.md", "source_hash": "sha256:557a08b1c3bc542f64b1d7864f6567e804dc5a6cdee78a35111c375ab3f8bc5e", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: finish-branch-cleanup

Worktree cleanup after branch integration. Applies to merge, PR, and discard options. Keeps worktree intact for keep-as-is option.

```mermaid
flowchart TD
    Start([Integration Complete]) --> CheckOption{"Which Integration\nOption?"}
    CheckOption -->|Option 1: Merge| Cleanup["Proceed to Cleanup"]
    CheckOption -->|Option 2: PR| Cleanup
    CheckOption -->|Option 3: Keep| NoCleanup([Keep Worktree Intact])
    CheckOption -->|Option 4: Discard| Cleanup
    Cleanup --> DetectWorktree["Detect if in\nWorktree"]
    DetectWorktree --> IsWorktree{"Currently in\nWorktree?"}
    IsWorktree -->|No| AlreadyClean([No Cleanup Needed])
    IsWorktree -->|Yes| RemoveWorktree["Remove Worktree"]
    RemoveWorktree --> RemoveResult{"Removal\nSucceeded?"}
    RemoveResult -->|Yes| Done([Worktree Removed\nIntegration Complete])
    RemoveResult -->|No| CheckChanges{"Uncommitted\nChanges?"}
    CheckChanges -->|Yes| WarnUser["Warn: Uncommitted\nChanges Detected"]
    CheckChanges -->|No| ReportError["Report Removal\nError"]
    WarnUser --> AskConfirm{"Force Remove?"}
    AskConfirm -->|Yes| ForceRemove["Force Remove\nWorktree"]
    AskConfirm -->|No| KeepForNow([Keep Worktree\nFor User])
    ForceRemove --> Done
    ReportError --> KeepForNow

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style NoCleanup fill:#4CAF50,color:#fff
    style AlreadyClean fill:#4CAF50,color:#fff
    style KeepForNow fill:#4CAF50,color:#fff
    style Cleanup fill:#2196F3,color:#fff
    style DetectWorktree fill:#2196F3,color:#fff
    style RemoveWorktree fill:#2196F3,color:#fff
    style WarnUser fill:#2196F3,color:#fff
    style ForceRemove fill:#2196F3,color:#fff
    style ReportError fill:#2196F3,color:#fff
    style CheckOption fill:#FF9800,color:#fff
    style IsWorktree fill:#FF9800,color:#fff
    style CheckChanges fill:#FF9800,color:#fff
    style AskConfirm fill:#FF9800,color:#fff
    style RemoveResult fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
