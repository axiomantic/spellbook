<!-- diagram-meta: {"source": "commands/pr-distill-bless.md", "source_hash": "sha256:30e7904b7c6ab190b0dbf76c351a761be0bc58f237a9f2947d9f0a8678214a6a", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: pr-distill-bless

Save a discovered pattern for future PR distillation. Validates pattern ID, checks for duplicates, and persists to project config.

```mermaid
flowchart TD
    Start([Pattern ID Input]) --> ValidateID{"Pattern ID\nValid?"}
    ValidateID -->|No| RejectID["Reject: Invalid\nFormat"]
    RejectID --> ShowRules["Show Validation\nRules"]
    ShowRules --> Done2([Aborted])
    ValidateID -->|Yes| CheckReserved{"Reserved Prefix\n_builtin-?"}
    CheckReserved -->|Yes| RejectBuiltin["Reject: Built-in\nPattern"]
    RejectBuiltin --> Done2
    CheckReserved -->|No| LoadConfig["Load Existing\nConfig"]
    LoadConfig --> ConfigExists{"Config File\nExists?"}
    ConfigExists -->|No| CreateDefaults["Create Config\nWith Defaults"]
    ConfigExists -->|Yes| CheckDuplicate{"Pattern Already\nBlessed?"}
    CreateDefaults --> AddPattern["Add to\nblessed_patterns"]
    CheckDuplicate -->|No| AddPattern
    CheckDuplicate -->|Yes| WarnOverwrite["Warn: Pattern\nExists"]
    WarnOverwrite --> ConfirmOverwrite{"Confirm\nOverwrite?"}
    ConfirmOverwrite -->|No| Done2
    ConfirmOverwrite -->|Yes| UpdatePattern["Update Existing\nPattern"]
    AddPattern --> SaveConfig["Save Updated\nConfig"]
    UpdatePattern --> SaveConfig
    SaveConfig --> VerifyPersist{"Pattern in\nConfig File?"}
    VerifyPersist -->|No| SaveConfig
    VerifyPersist -->|Yes| Done([Pattern Blessed])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style Done2 fill:#f44336,color:#fff
    style RejectID fill:#2196F3,color:#fff
    style ShowRules fill:#2196F3,color:#fff
    style RejectBuiltin fill:#2196F3,color:#fff
    style LoadConfig fill:#2196F3,color:#fff
    style CreateDefaults fill:#2196F3,color:#fff
    style AddPattern fill:#2196F3,color:#fff
    style WarnOverwrite fill:#2196F3,color:#fff
    style UpdatePattern fill:#2196F3,color:#fff
    style SaveConfig fill:#2196F3,color:#fff
    style ValidateID fill:#f44336,color:#fff
    style CheckReserved fill:#FF9800,color:#fff
    style ConfigExists fill:#FF9800,color:#fff
    style CheckDuplicate fill:#FF9800,color:#fff
    style ConfirmOverwrite fill:#FF9800,color:#fff
    style VerifyPersist fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
