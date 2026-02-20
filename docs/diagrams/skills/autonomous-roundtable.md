<!-- diagram-meta: {"source": "skills/autonomous-roundtable/SKILL.md", "source_hash": "sha256:20319cd9f4aba1192d9ff136ce0e80bdb55b1fba6ce4af3868fe9f97e820d6e3", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: autonomous-roundtable

Workflow for the autonomous-roundtable skill (Forged system). A meta-orchestrator that decomposes projects into features, processes each through DISCOVER, DESIGN, PLAN, IMPLEMENT, COMPLETE stages with roundtable consensus gating. Runs exclusively as a subagent, with handoff protocol for context overflow.

```mermaid
flowchart TD
    Start([Start]) --> SpawnSub["Spawn orchestrator subagent"]
    SpawnSub --> InitProject["forge_project_init"]
    InitProject --> DepOrder["Order features by deps"]
    DepOrder --> NextFeature{Next feature?}

    NextFeature -->|Yes| CheckDeps{Dependencies COMPLETE?}
    NextFeature -->|No| ProjectDone([Project Complete])

    CheckDeps -->|No| SkipFeature["Skip, process later"]
    CheckDeps -->|Yes| IterStart["forge_iteration_start"]
    SkipFeature --> NextFeature

    IterStart --> SelectSkill["forge_select_skill"]
    SelectSkill --> InvokeSkill["Invoke stage skill"]

    subgraph Stages["Stage Skills"]
        Discover["gathering-requirements"]
        Design["brainstorming"]
        Plan["writing-plans"]
        Implement["implementing-features"]
        Complete["Final roundtable"]
    end

    InvokeSkill --> Discover
    InvokeSkill --> Design
    InvokeSkill --> Plan
    InvokeSkill --> Implement
    InvokeSkill --> Complete

    Discover --> Roundtable
    Design --> Roundtable
    Plan --> Roundtable
    Implement --> Roundtable
    Complete --> Roundtable

    Roundtable["roundtable_convene"]
    Roundtable --> Verdict{Verdict?}

    Verdict -->|APPROVE| Advance["forge_iteration_advance"]
    Verdict -->|ITERATE| IterReturn["forge_iteration_return"]

    Advance --> LastStage{Last stage?}
    LastStage -->|No| SelectSkill
    LastStage -->|Yes| FeatureDone["Feature COMPLETE"]
    FeatureDone --> NextFeature

    IterReturn --> Reflexion["reflexion skill"]
    Reflexion --> FailCount{3+ failures?}
    FailCount -->|Yes| Escalate["ESCALATE to user"]
    FailCount -->|No| SelectSkill

    Escalate --> ContinueOthers["Continue non-blocked"]
    ContinueOthers --> NextFeature

    %% Context overflow
    InvokeSkill -.->|"<20% capacity"| Handoff["Generate HANDOFF"]
    Handoff -.-> ReturnMain["Return to main chat"]
    ReturnMain -.-> SpawnSuccessor["Spawn successor"]
    SpawnSuccessor -.-> InitProject

    style Start fill:#4CAF50,color:#fff
    style ProjectDone fill:#4CAF50,color:#fff
    style SpawnSub fill:#4CAF50,color:#fff
    style Discover fill:#4CAF50,color:#fff
    style Design fill:#4CAF50,color:#fff
    style Plan fill:#4CAF50,color:#fff
    style Implement fill:#4CAF50,color:#fff
    style Complete fill:#4CAF50,color:#fff
    style Reflexion fill:#4CAF50,color:#fff
    style InitProject fill:#2196F3,color:#fff
    style DepOrder fill:#2196F3,color:#fff
    style SkipFeature fill:#2196F3,color:#fff
    style IterStart fill:#2196F3,color:#fff
    style SelectSkill fill:#2196F3,color:#fff
    style InvokeSkill fill:#2196F3,color:#fff
    style Roundtable fill:#2196F3,color:#fff
    style Advance fill:#2196F3,color:#fff
    style IterReturn fill:#2196F3,color:#fff
    style FeatureDone fill:#2196F3,color:#fff
    style Escalate fill:#2196F3,color:#fff
    style ContinueOthers fill:#2196F3,color:#fff
    style Handoff fill:#2196F3,color:#fff
    style ReturnMain fill:#2196F3,color:#fff
    style SpawnSuccessor fill:#2196F3,color:#fff
    style NextFeature fill:#FF9800,color:#fff
    style CheckDeps fill:#FF9800,color:#fff
    style LastStage fill:#FF9800,color:#fff
    style FailCount fill:#FF9800,color:#fff
    style Verdict fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Spawn orchestrator subagent | SKILL.md: MANDATE - "Forge NEVER runs in main chat" |
| forge_project_init | SKILL.md: MCP Tools - Project initialization |
| Order features by deps | SKILL.md: Invariant 2 - "Dependency Order" |
| forge_iteration_start | SKILL.md: MCP Tools - Iteration start |
| forge_select_skill | SKILL.md: MCP Tools - Skill selection, priority rules |
| gathering-requirements | SKILL.md: Stages table - DISCOVER stage |
| brainstorming | SKILL.md: Stages table - DESIGN stage |
| writing-plans | SKILL.md: Stages table - PLAN stage |
| implementing-features | SKILL.md: Stages table - IMPLEMENT stage |
| Final roundtable | SKILL.md: Stages table - COMPLETE stage |
| roundtable_convene | SKILL.md: MCP Tools - Roundtable convene |
| Verdict (APPROVE/ITERATE) | SKILL.md: Forge Loop - roundtable outcomes |
| forge_iteration_advance | SKILL.md: Forge Loop - advance to next stage |
| forge_iteration_return | SKILL.md: ITERATE Handling - return for reflexion |
| reflexion skill | SKILL.md: Invariant 4 - "Feedback to Reflexion" |
| 3+ failures escalation | SKILL.md: ITERATE Handling - "After 3 failures: ESCALATE" |
| HANDOFF | SKILL.md: Context Overflow Protocol - handoff format |
| Spawn successor | SKILL.md: Context Overflow Protocol - main chat spawns successor |
