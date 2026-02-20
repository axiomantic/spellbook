<!-- diagram-meta: {"source": "commands/handoff.md", "source_hash": "sha256:45eb6e030e42aa92ebe3d1ecbdd59f31b583fd6d90af0454c464d775eac29829", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: handoff

Session state transfer command that produces a structured handoff document enabling a successor instance to resume mid-stride with zero context loss. Supports manual, auto, and checkpoint invocation modes.

```mermaid
flowchart TD
    Start([Start Handoff]) --> DetectMode{Invocation Mode?}

    DetectMode -->|manual| AnalysisWalk[Conversation Walkthrough]
    DetectMode -->|auto| FastExtract[Fast State Extraction]
    DetectMode -->|checkpoint| SnapshotState[Snapshot Current State]

    AnalysisWalk --> SearchPlans[Search Planning Docs]
    FastExtract --> SearchPlans
    SnapshotState --> SearchPlans

    SearchPlans --> GenSection0[Generate Section 0: Boot Actions]
    GenSection0 --> GenSkillRestore[Write Skill Restore Commands]
    GenSkillRestore --> GenDocReads[Write Document Read Calls]
    GenDocReads --> GenTodoRestore[Write TodoWrite Calls]
    GenTodoRestore --> GenConstraints[Write Behavioral Constraints]

    GenConstraints --> GenSection1[Generate Section 1: Context]
    GenSection1 --> OrgStructure[Org Structure + Subagents]
    OrgStructure --> GoalStack[Goal Stack + Decisions]
    GoalStack --> ArtifactState[Artifact State Verification]
    ArtifactState --> ConversationCtx[Conversation Context]
    ConversationCtx --> MachineYAML[Section 1.20: YAML State]

    MachineYAML --> PersistCheck{Mode auto or checkpoint?}
    PersistCheck -->|Yes| MCPSave[workflow_state_save MCP]
    PersistCheck -->|No| SkipPersist[Skip Persistence]

    MCPSave --> GenSection2[Generate Section 2: Continuation]
    SkipPersist --> GenSection2

    GenSection2 --> QualityGate{Quality Check Passes?}
    QualityGate -->|No| FixGaps[Add Missing Detail]
    FixGaps --> QualityGate
    QualityGate -->|Yes| Reflection[Reflection Verification]

    Reflection --> Done([Handoff Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style DetectMode fill:#FF9800,color:#fff
    style PersistCheck fill:#FF9800,color:#fff
    style QualityGate fill:#f44336,color:#fff
    style MCPSave fill:#4CAF50,color:#fff
    style AnalysisWalk fill:#2196F3,color:#fff
    style FastExtract fill:#2196F3,color:#fff
    style SnapshotState fill:#2196F3,color:#fff
    style SearchPlans fill:#2196F3,color:#fff
    style GenSection0 fill:#2196F3,color:#fff
    style GenSkillRestore fill:#2196F3,color:#fff
    style GenDocReads fill:#2196F3,color:#fff
    style GenTodoRestore fill:#2196F3,color:#fff
    style GenConstraints fill:#2196F3,color:#fff
    style GenSection1 fill:#2196F3,color:#fff
    style OrgStructure fill:#2196F3,color:#fff
    style GoalStack fill:#2196F3,color:#fff
    style ArtifactState fill:#2196F3,color:#fff
    style ConversationCtx fill:#2196F3,color:#fff
    style MachineYAML fill:#2196F3,color:#fff
    style SkipPersist fill:#2196F3,color:#fff
    style GenSection2 fill:#2196F3,color:#fff
    style Reflection fill:#2196F3,color:#fff
    style FixGaps fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
