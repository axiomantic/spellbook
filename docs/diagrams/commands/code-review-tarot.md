<!-- diagram-meta: {"source": "commands/code-review-tarot.md", "source_hash": "sha256:8c9398311f3594ec3d53460cb63752475a18570f62d3b62bd9d149b8b79be78c", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: code-review-tarot

Roundtable dialogue with tarot archetype personas for all code review modes.

```mermaid
flowchart TD
    Start([Start: --tarot Flag Active]) --> Mode{Review Mode?}
    Mode -->|--self| SelfMode[Self-Review Mode]
    Mode -->|--give| GiveMode[Give Review Mode]
    Mode -->|--audit| AuditMode[Audit Review Mode]

    SelfMode --> Convene[/Magician Opens Roundtable/]
    GiveMode --> Convene
    AuditMode --> Convene

    Convene --> Hermit[/Hermit: Security Pass/]
    Hermit --> HermitFindings[Security Findings]

    HermitFindings --> Priestess[/Priestess: Architecture Pass/]
    Priestess --> PriestessFindings[Architecture Findings]

    PriestessFindings --> Fool[/Fool: Assumption Pass/]
    Fool --> FoolFindings[Assumption Challenges]

    FoolFindings --> Conflicts{Archetypes Disagree?}
    Conflicts -->|Yes| Resolve[/Magician: Resolve by Evidence/]
    Conflicts -->|No| Synthesize[/Magician: Synthesize Verdict/]
    Resolve --> Synthesize

    Synthesize --> Separate[Separate Persona from Code]
    Separate --> Gate{All Findings Have Evidence?}
    Gate -->|No| AddEvidence[Add file:line References]
    AddEvidence --> Gate
    Gate -->|Yes| Output[Formal Review Output]
    Output --> Done([Complete])

    style Start fill:#2196F3,color:#fff
    style Mode fill:#FF9800,color:#fff
    style SelfMode fill:#2196F3,color:#fff
    style GiveMode fill:#2196F3,color:#fff
    style AuditMode fill:#2196F3,color:#fff
    style Convene fill:#4CAF50,color:#fff
    style Hermit fill:#4CAF50,color:#fff
    style HermitFindings fill:#2196F3,color:#fff
    style Priestess fill:#4CAF50,color:#fff
    style PriestessFindings fill:#2196F3,color:#fff
    style Fool fill:#4CAF50,color:#fff
    style FoolFindings fill:#2196F3,color:#fff
    style Conflicts fill:#FF9800,color:#fff
    style Resolve fill:#4CAF50,color:#fff
    style Synthesize fill:#4CAF50,color:#fff
    style Separate fill:#2196F3,color:#fff
    style Gate fill:#f44336,color:#fff
    style AddEvidence fill:#2196F3,color:#fff
    style Output fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
