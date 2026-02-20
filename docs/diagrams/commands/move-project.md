<!-- diagram-meta: {"source": "commands/move-project.md", "source_hash": "sha256:90808f4af1397bbe698819e34fcb2e72b9bebbd07fa378c1f07b7e2e80b497fa", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: move-project

Safely relocates a project directory and updates all Claude Code session references (history.jsonl, projects directory) with mandatory safety checks, backups, and user confirmation.

```mermaid
flowchart TD
    Start([Invoke /move-project]) --> SafetyCheck[Step 1: Verify CWD]
    SafetyCheck --> CWDSafe{CWD Outside Src+Dest?}

    CWDSafe -->|No| CWDError[Error: Navigate Away]
    CWDError --> Abort([Abort])

    CWDSafe -->|Yes| ValidateArgs[Step 2: Validate Arguments]
    ValidateArgs --> ArgsValid{Paths Absolute?}
    ArgsValid -->|No| PromptPaths[Ask for Valid Paths]
    PromptPaths --> ValidateArgs
    ArgsValid -->|Yes| VerifySource[Step 3: Source Exists?]

    VerifySource --> SourceExists{Directory Found?}
    SourceExists -->|No| SourceError[Error: Not Found]
    SourceError --> Abort

    SourceExists -->|Yes| VerifyDest[Step 4: Dest Not Exists?]
    VerifyDest --> DestFree{Dest Available?}
    DestFree -->|No| DestError[Error: Already Exists]
    DestError --> Abort

    DestFree -->|Yes| FindRefs[Step 5: Find Claude Refs]
    FindRefs --> ShowPreview[Show Change Preview]
    ShowPreview --> Confirm{User Confirms?}

    Confirm -->|Show detail| DetailedPreview[Show Detailed Preview]
    DetailedPreview --> Confirm
    Confirm -->|No| Abort
    Confirm -->|Yes| BackupHistory[Step 7a: Backup history.jsonl]

    BackupHistory --> UpdateHistory[Update history.jsonl Refs]
    UpdateHistory --> RenameProjects[Step 7b: Rename Projects Dir]
    RenameProjects --> MoveFilesystem[Step 7c: Move Directory]

    MoveFilesystem --> Verify[Step 8: Verify All Changes]
    Verify --> AllOK{All Verified?}

    AllOK -->|No| Rollback[Error Recovery + Rollback]
    Rollback --> Abort
    AllOK -->|Yes| Report[Success Report]

    Report --> SelfCheckGate{Self-Check Passes?}
    SelfCheckGate -->|No| FixMissing[Complete Missing Steps]
    FixMissing --> SelfCheckGate
    SelfCheckGate -->|Yes| Done([Move Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style Abort fill:#2196F3,color:#fff
    style CWDSafe fill:#FF9800,color:#fff
    style ArgsValid fill:#FF9800,color:#fff
    style SourceExists fill:#FF9800,color:#fff
    style DestFree fill:#FF9800,color:#fff
    style Confirm fill:#FF9800,color:#fff
    style AllOK fill:#f44336,color:#fff
    style SelfCheckGate fill:#f44336,color:#fff
    style SafetyCheck fill:#2196F3,color:#fff
    style CWDError fill:#2196F3,color:#fff
    style ValidateArgs fill:#2196F3,color:#fff
    style PromptPaths fill:#2196F3,color:#fff
    style VerifySource fill:#2196F3,color:#fff
    style SourceError fill:#2196F3,color:#fff
    style VerifyDest fill:#2196F3,color:#fff
    style DestError fill:#2196F3,color:#fff
    style FindRefs fill:#2196F3,color:#fff
    style ShowPreview fill:#2196F3,color:#fff
    style DetailedPreview fill:#2196F3,color:#fff
    style BackupHistory fill:#2196F3,color:#fff
    style UpdateHistory fill:#2196F3,color:#fff
    style RenameProjects fill:#2196F3,color:#fff
    style MoveFilesystem fill:#2196F3,color:#fff
    style Verify fill:#2196F3,color:#fff
    style Rollback fill:#2196F3,color:#fff
    style Report fill:#2196F3,color:#fff
    style FixMissing fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
