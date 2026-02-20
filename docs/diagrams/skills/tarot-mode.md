<!-- diagram-meta: {"source": "skills/tarot-mode/SKILL.md", "source_hash": "sha256:5453a12f88991d67ce1a667d0881bc0c78fba2c7dbb0b4d90c304c14d3d2b9c6", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: tarot-mode

Roundtable dialogue mode where ten tarot archetypes collaborate on tasks with embedded instruction-engineering, emotional stakes, and NegativePrompt patterns.

```mermaid
flowchart TD
    Start([Session Init]) --> ModeCheck{mode.type = tarot?}

    ModeCheck -->|No| Skip([Skip: Not Tarot])
    ModeCheck -->|Yes| Convene[Roundtable Convenes]

    Convene --> Introductions[Persona Introductions]
    Introductions --> ReceiveTask[Receive User Task]

    ReceiveTask --> IntentPhase[Magician: Resolve Intent]
    IntentPhase --> AmbiguityGate{Ambiguity Resolved?}

    AmbiguityGate -->|No| Clarify[Magician: Ask User]
    Clarify --> IntentPhase
    AmbiguityGate -->|Yes| FanOut[Magician: Scatter Tasks]

    FanOut --> PriestessExplore[Priestess: Architecture Options]
    FanOut --> HermitAudit[Hermit: Security Audit]
    FanOut --> FoolChallenge[Fool: Challenge Assumptions]

    PriestessExplore --> Dispatch1[Dispatch Parallel Agents]
    HermitAudit --> Dispatch2[Dispatch Parallel Agents]

    Dispatch1 --> Reconvene[Magician: Reconvene]
    Dispatch2 --> Reconvene
    FoolChallenge --> Reconvene

    Reconvene --> Dialogue[Personas Engage Each Other]

    Dialogue --> OptionsGate{2-3 Options with Tradeoffs?}
    OptionsGate -->|No| PriestessDeepen[Priestess: Explore More]
    PriestessDeepen --> Dialogue
    OptionsGate -->|Yes| SecurityGate{Edge Cases Checked?}

    SecurityGate -->|No| HermitDeepen[Hermit: Find Breaks]
    HermitDeepen --> Dialogue
    SecurityGate -->|Yes| AssumptionsGate{Premises Challenged?}

    AssumptionsGate -->|No| FoolDeepen[Fool: Question Obvious]
    FoolDeepen --> Dialogue
    AssumptionsGate -->|Yes| Synthesize[Magician: Synthesize]

    Synthesize --> Artifacts[Produce Clean Artifacts]

    Artifacts --> BoundaryGate{Code/Docs Clean of Persona?}
    BoundaryGate -->|No| CleanArtifacts[Remove Persona Quirks]
    CleanArtifacts --> BoundaryGate
    BoundaryGate -->|Yes| SelfCheck{Self-Check Passed?}

    SelfCheck -->|No| Revise[Revise Before Proceeding]
    Revise --> Dialogue
    SelfCheck -->|Yes| Done([Task Complete])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style Skip fill:#4CAF50,color:#fff
    style ModeCheck fill:#FF9800,color:#fff
    style AmbiguityGate fill:#FF9800,color:#fff
    style OptionsGate fill:#FF9800,color:#fff
    style SecurityGate fill:#FF9800,color:#fff
    style AssumptionsGate fill:#FF9800,color:#fff
    style BoundaryGate fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
    style Convene fill:#2196F3,color:#fff
    style Introductions fill:#2196F3,color:#fff
    style ReceiveTask fill:#2196F3,color:#fff
    style IntentPhase fill:#2196F3,color:#fff
    style Clarify fill:#2196F3,color:#fff
    style FanOut fill:#2196F3,color:#fff
    style PriestessExplore fill:#4CAF50,color:#fff
    style HermitAudit fill:#4CAF50,color:#fff
    style FoolChallenge fill:#4CAF50,color:#fff
    style Dispatch1 fill:#4CAF50,color:#fff
    style Dispatch2 fill:#4CAF50,color:#fff
    style Reconvene fill:#2196F3,color:#fff
    style Dialogue fill:#2196F3,color:#fff
    style PriestessDeepen fill:#4CAF50,color:#fff
    style HermitDeepen fill:#4CAF50,color:#fff
    style FoolDeepen fill:#4CAF50,color:#fff
    style Synthesize fill:#2196F3,color:#fff
    style Artifacts fill:#2196F3,color:#fff
    style CleanArtifacts fill:#2196F3,color:#fff
    style Revise fill:#2196F3,color:#fff
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
| Session Init | "Load when: spellbook_session_init returns mode.type = tarot" (line 20) |
| mode.type = tarot? | Inputs table: mode.type must be "tarot" (line 26) |
| Roundtable Convenes | Session Start section (lines 66-82) |
| Persona Introductions | Session Start: Magician, Priestess, Hermit, Fool introduce (lines 68-82) |
| Magician: Resolve Intent | Quality Checkpoints: Intent phase, Magician owner (line 117) |
| Magician: Scatter Tasks | Autonomous Actions fan-out pattern (lines 90-110) |
| Priestess: Architecture Options | Roundtable: Priestess function = Architecture, options (line 43) |
| Hermit: Security Audit | Roundtable: Hermit function = Security, edge cases (line 44) |
| Fool: Challenge Assumptions | Roundtable: Fool function = Assumption breaking (line 45) |
| Dispatch Parallel Agents | Autonomous Actions: "Dispatch parallel agents with stakes in prompts" (line 98) |
| 2-3 Options with Tradeoffs? | Quality Checkpoints: Options phase check (line 118) |
| Edge Cases Checked? | Quality Checkpoints: Security phase check (line 119) |
| Premises Challenged? | Quality Checkpoints: Assumptions phase check (line 120) |
| Magician: Synthesize | Outputs: Magician's summary of roundtable conclusions (line 36) |
| Code/Docs Clean of Persona? | Boundaries table: Code/commits/docs = NO persona (line 142) |
| Self-Check Passed? | Self-Check checklist (lines 157-163) |
