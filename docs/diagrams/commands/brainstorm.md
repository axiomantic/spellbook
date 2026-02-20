<!-- diagram-meta: {"source": "commands/brainstorm.md", "source_hash": "sha256:9f1f8427a673ec1375ffcf32ff7a296dd24505ac12a6ae2def464fa438986ef0", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: brainstorm

Enforce structured exploration before creative work by delegating to the brainstorming skill.

```mermaid
flowchart TD
    Start([Start]) --> LoadSkill[/Load Brainstorming Skill/]
    LoadSkill --> DetectMode{Detect Mode}
    DetectMode -->|Synthesis| Synthesis[Autonomous Synthesis]
    DetectMode -->|Interactive| Interactive[Interactive Discovery]
    Synthesis --> Explore[Explore Requirements]
    Interactive --> Explore
    Explore --> Approaches[Evaluate Approaches]
    Approaches --> Select{Approach Selected?}
    Select -->|Yes| Design[Create Design Artifacts]
    Select -->|No| Explore
    Design --> Gate{Design Complete?}
    Gate -->|Yes| Done([End])
    Gate -->|No| Approaches

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style LoadSkill fill:#4CAF50,color:#fff
    style DetectMode fill:#FF9800,color:#fff
    style Select fill:#FF9800,color:#fff
    style Gate fill:#f44336,color:#fff
    style Explore fill:#2196F3,color:#fff
    style Approaches fill:#2196F3,color:#fff
    style Design fill:#2196F3,color:#fff
    style Synthesis fill:#2196F3,color:#fff
    style Interactive fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
