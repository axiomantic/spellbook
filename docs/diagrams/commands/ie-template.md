<!-- diagram-meta: {"source": "commands/ie-template.md", "source_hash": "sha256:219436b93c9716d48196f2011cdbad606487c440dc0903777b0e96dcf7391654", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: ie-template

Template and example for engineered instructions. Provides a standard structure (ROLE, CRITICAL_INSTRUCTION, BEFORE_RESPONDING, RULES, EXAMPLE, FORBIDDEN, SELF_CHECK, FINAL_EMPHASIS) with a complete security code review example.

```mermaid
flowchart TD
    Start([Invoke /ie-template]) --> RoleSection[Define ROLE + Persona]
    RoleSection --> CriticalInstr[Write CRITICAL_INSTRUCTION]
    CriticalInstr --> BeforeRespond[Write BEFORE_RESPONDING]
    BeforeRespond --> CoreRules[Define Core Rules]
    CoreRules --> FewShotEx[Add Few-Shot Example]
    FewShotEx --> ExampleCheck{Example Complete?}

    ExampleCheck -->|No| ExpandExample[Add Missing Detail]
    ExpandExample --> ExampleCheck
    ExampleCheck -->|Yes| Forbidden[Define FORBIDDEN List]

    Forbidden --> SelfCheck[Write SELF_CHECK Checklist]
    SelfCheck --> FinalEmphasis[Write FINAL_EMPHASIS]
    FinalEmphasis --> CrystallizeAsk{Crystallize Prompt?}

    CrystallizeAsk -->|Yes| Crystallize[/crystallize]
    CrystallizeAsk -->|No| Done([Template Complete])
    Crystallize --> Done

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style ExampleCheck fill:#FF9800,color:#fff
    style CrystallizeAsk fill:#FF9800,color:#fff
    style Crystallize fill:#4CAF50,color:#fff
    style RoleSection fill:#2196F3,color:#fff
    style CriticalInstr fill:#2196F3,color:#fff
    style BeforeRespond fill:#2196F3,color:#fff
    style CoreRules fill:#2196F3,color:#fff
    style FewShotEx fill:#2196F3,color:#fff
    style ExpandExample fill:#2196F3,color:#fff
    style Forbidden fill:#2196F3,color:#fff
    style SelfCheck fill:#2196F3,color:#fff
    style FinalEmphasis fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
