<!-- diagram-meta: {"source": "commands/dead-code-setup.md", "source_hash": "sha256:d0a19df4171dd31fbf3ad3314f1882dde6454c4dc8a84fae8c81bcb6cac21417", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: dead-code-setup

Git safety checks and scope selection for dead code analysis.

```mermaid
flowchart TD
    Start([Start: Dead Code Setup]) --> GitStatus[Check git status]

    GitStatus --> Uncommitted{Uncommitted Changes?}
    Uncommitted -->|Yes| AskCommit{Commit First?}
    Uncommitted -->|No| Worktree

    AskCommit -->|Yes| DoCommit[Create Commit]
    AskCommit -->|No, proceed| WarnRisk[Warn About Risks]
    AskCommit -->|Abort| Abort([Abort Analysis])

    DoCommit --> Worktree{Use Git Worktree?}
    WarnRisk --> Worktree

    Worktree -->|Yes| CreateWorktree[/using-git-worktrees/]
    Worktree -->|No| WarnDirect[Warn: Direct Modifications]

    CreateWorktree --> BranchName[Create dead-code-hunt Branch]
    BranchName --> Scope
    WarnDirect --> RequireApproval[Require Deletion Approval]
    RequireApproval --> Scope

    Scope{Select Scope?}
    Scope -->|Branch Changes| DiffBranch[git diff merge-base]
    Scope -->|Uncommitted Only| DiffUncommitted[git diff staged+unstaged]
    Scope -->|Specific Files| UserFiles[User Provides Paths]
    Scope -->|Full Repository| AllFiles[All Code Files]

    DiffBranch --> TargetFiles[Identify Target Files]
    DiffUncommitted --> TargetFiles
    UserFiles --> TargetFiles
    AllFiles --> TargetFiles

    TargetFiles --> Gate{Git Safe + Scope Set?}
    Gate -->|No| Start
    Gate -->|Yes| Done([Ready for dead-code-analyze])

    style Start fill:#2196F3,color:#fff
    style GitStatus fill:#2196F3,color:#fff
    style Uncommitted fill:#FF9800,color:#fff
    style AskCommit fill:#FF9800,color:#fff
    style DoCommit fill:#2196F3,color:#fff
    style WarnRisk fill:#f44336,color:#fff
    style Abort fill:#f44336,color:#fff
    style Worktree fill:#FF9800,color:#fff
    style CreateWorktree fill:#4CAF50,color:#fff
    style WarnDirect fill:#f44336,color:#fff
    style BranchName fill:#2196F3,color:#fff
    style RequireApproval fill:#f44336,color:#fff
    style Scope fill:#FF9800,color:#fff
    style DiffBranch fill:#2196F3,color:#fff
    style DiffUncommitted fill:#2196F3,color:#fff
    style UserFiles fill:#2196F3,color:#fff
    style AllFiles fill:#2196F3,color:#fff
    style TargetFiles fill:#2196F3,color:#fff
    style Gate fill:#f44336,color:#fff
    style Done fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
