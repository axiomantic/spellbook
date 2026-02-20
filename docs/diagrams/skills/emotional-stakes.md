<!-- diagram-meta: {"source": "skills/emotional-stakes/SKILL.md", "source_hash": "sha256:96f43ebb03db87372b17c3259b75c9a64b9531cc14f7108e2fb1894bb87e5d67", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: emotional-stakes

Workflow for applying emotional stakes framing to substantive tasks. Selects a professional persona based on task type, calibrates stakes to risk level, and optionally integrates a soul persona from fun-mode.

```mermaid
flowchart TD
    Start([New Task Received])
    Trigger{Substantive Task?}
    Skip([Skip Stakes])
    Analyze[Identify Task Type]
    SelectPersona[Select Professional Persona]
    SoulCheck{Soul Persona Active?}
    Escalation[Calibrate Stakes Level]
    IntegrateSoul[Integrate Soul + Professional]
    ProfessionalOnly[Professional Persona Only]
    FrameStakes[State Stakes Framing]
    SelfCheck{Self-Check Passes?}
    Fix[Reassess Framing]
    Proceed([Proceed with Task])

    Start --> Trigger
    Trigger -- "Yes: implementation, review, design" --> Analyze
    Trigger -- "No: clarification, lookup" --> Skip
    Analyze --> SelectPersona
    SelectPersona --> SoulCheck
    SoulCheck -- "Yes: fun-mode active" --> IntegrateSoul
    SoulCheck -- "No" --> ProfessionalOnly
    IntegrateSoul --> Escalation
    ProfessionalOnly --> Escalation
    Escalation --> FrameStakes
    FrameStakes --> SelfCheck
    SelfCheck -- "All checks pass" --> Proceed
    SelfCheck -- "Check failed" --> Fix
    Fix --> FrameStakes

    style Start fill:#4CAF50,color:#fff
    style Trigger fill:#FF9800,color:#fff
    style SoulCheck fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
    style Analyze fill:#2196F3,color:#fff
    style SelectPersona fill:#2196F3,color:#fff
    style Escalation fill:#2196F3,color:#fff
    style IntegrateSoul fill:#2196F3,color:#fff
    style ProfessionalOnly fill:#2196F3,color:#fff
    style FrameStakes fill:#2196F3,color:#fff
    style Fix fill:#2196F3,color:#fff
    style Skip fill:#2196F3,color:#fff
    style Proceed fill:#4CAF50,color:#fff
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
| Substantive Task? | Lines 52-53: TRIGGER/SKIP rules |
| Select Professional Persona | Lines 57-71: Persona selection table |
| Soul Persona Active? | Lines 41, 85-97: Soul persona integration |
| Calibrate Stakes Level | Lines 73-79: Stakes escalation table |
| State Stakes Framing | Line 81: FORMAT rule |
| Self-Check Passes? | Lines 115-123: Self-check checklist |
