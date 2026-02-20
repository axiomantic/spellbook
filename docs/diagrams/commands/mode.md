<!-- diagram-meta: {"source": "commands/mode.md", "source_hash": "sha256:a4cd6b75b6e037d40cd99912bc0ac529a44a686130bb2b8ad71f064dc41d06c7", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: mode

Manages spellbook session modes (fun, tarot, off). Handles status queries, mode switching with permanence preference, and skill loading for creative dialogue modes.

```mermaid
flowchart TD
    Start([Invoke /mode]) --> ParseArg{Argument Provided?}

    ParseArg -->|No argument| StatusQuery[Get Current Mode]
    StatusQuery --> MCPGet[spellbook_session_mode_get]
    MCPGet --> ReportStatus[Report Mode + Source]
    ReportStatus --> Done([Done])

    ParseArg -->|fun / tarot / off| AskPermanence{Save Permanently?}

    AskPermanence -->|Permanent| SetPerm[Set permanent=true]
    AskPermanence -->|Session only| SetSession[Set permanent=false]

    SetPerm --> MCPSet[spellbook_session_mode_set]
    SetSession --> MCPSet

    MCPSet --> ModeType{Which Mode?}

    ModeType -->|fun| InitFun[spellbook_session_init]
    InitFun --> LoadFun[Load fun-mode Skill]
    LoadFun --> AnnounceFun[Announce Persona]
    AnnounceFun --> Done

    ModeType -->|tarot| LoadTarot[Load tarot-mode Skill]
    LoadTarot --> AnnounceTarot[Announce Roundtable]
    AnnounceTarot --> Done

    ModeType -->|off / none| WasPrev{Previous Mode?}
    WasPrev -->|fun| DropPersona[Drop Persona Gracefully]
    WasPrev -->|tarot| DisperseTable[Roundtable Disperses]
    WasPrev -->|none| ConfirmOff[Confirm Mode Disabled]
    DropPersona --> ConfirmOff
    DisperseTable --> ConfirmOff
    ConfirmOff --> Done

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style ParseArg fill:#FF9800,color:#fff
    style AskPermanence fill:#FF9800,color:#fff
    style ModeType fill:#FF9800,color:#fff
    style WasPrev fill:#FF9800,color:#fff
    style LoadFun fill:#4CAF50,color:#fff
    style LoadTarot fill:#4CAF50,color:#fff
    style MCPGet fill:#2196F3,color:#fff
    style MCPSet fill:#2196F3,color:#fff
    style StatusQuery fill:#2196F3,color:#fff
    style ReportStatus fill:#2196F3,color:#fff
    style SetPerm fill:#2196F3,color:#fff
    style SetSession fill:#2196F3,color:#fff
    style InitFun fill:#2196F3,color:#fff
    style AnnounceFun fill:#2196F3,color:#fff
    style AnnounceTarot fill:#2196F3,color:#fff
    style DropPersona fill:#2196F3,color:#fff
    style DisperseTable fill:#2196F3,color:#fff
    style ConfirmOff fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
