<!-- diagram-meta: {"source": "commands/execute-plan.md", "source_hash": "sha256:4d9f434d63f49ad20b208b8faceaae810e2bcd97e26283313c1919485a44ce46", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: execute-plan

Execute implementation plans with structured review checkpoints via the executing-plans skill.

```mermaid
flowchart TD
    Start([Start]) --> LoadSkill[/Load executing-plans Skill/]
    LoadSkill --> LoadPlan[Load Plan Document]
    LoadPlan --> Readable{Plan Readable?}
    Readable -->|No| Error[Report Error]
    Error --> Done([End])
    Readable -->|Yes| PreCheck{Gaps or Concerns?}
    PreCheck -->|Yes| RaiseConcerns[Raise Before Starting]
    RaiseConcerns --> ModeSelect{Execution Mode?}
    PreCheck -->|No| ModeSelect
    ModeSelect -->|Batch| BatchExec[Batch Execution]
    ModeSelect -->|Subagent| SubagentExec[Subagent Execution]
    BatchExec --> TaskLoop[Execute Next Task]
    SubagentExec --> TaskLoop
    TaskLoop --> Verify{Verification Evidence?}
    Verify -->|No| Block[Block: Gather Evidence]
    Block --> Verify
    Verify -->|Yes| ReviewGate{Review Checkpoint?}
    ReviewGate -->|Yes| Review[Review Issues]
    Review --> Resolved{Issues Resolved?}
    Resolved -->|No| Fix[Address Issues]
    Fix --> Resolved
    Resolved -->|Yes| MoreTasks
    ReviewGate -->|No| MoreTasks{More Tasks?}
    MoreTasks -->|Yes| TaskLoop
    MoreTasks -->|No| FinalCheck{All Tasks Verified?}
    FinalCheck -->|No| TaskLoop
    FinalCheck -->|Yes| Done

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style LoadSkill fill:#4CAF50,color:#fff
    style Readable fill:#FF9800,color:#fff
    style PreCheck fill:#FF9800,color:#fff
    style ModeSelect fill:#FF9800,color:#fff
    style MoreTasks fill:#FF9800,color:#fff
    style Verify fill:#f44336,color:#fff
    style ReviewGate fill:#f44336,color:#fff
    style Resolved fill:#f44336,color:#fff
    style FinalCheck fill:#f44336,color:#fff
    style LoadPlan fill:#2196F3,color:#fff
    style TaskLoop fill:#2196F3,color:#fff
    style Review fill:#2196F3,color:#fff
    style Fix fill:#2196F3,color:#fff
    style Block fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
