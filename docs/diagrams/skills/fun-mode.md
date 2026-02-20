<!-- diagram-meta: {"source": "skills/fun-mode/SKILL.md", "source_hash": "sha256:b25b78495cddb566054f7675bc48efcc3f1b03c6fc7473b833c8e8d389daa6e6", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: fun-mode

Persona synthesis workflow for creative session engagement. Receives persona/context/undertow from session init, synthesizes a coherent character, enforces dialogue-only boundaries, and handles opt-out flow.

```mermaid
flowchart TD
    Start([Session Start / /fun])
    Source{Input Source?}
    SessionInit[Read spellbook_session_init]
    CustomInstr[Parse /fun Instructions]
    HasElements{Persona + Context + Undertow?}
    Synthesize[Synthesize Character]
    LoadStakes[Load emotional-stakes]
    Announce[Character Introduction]
    Economy[Apply Economy Principle]
    BoundaryCheck{Artifact Context?}
    Professional[Professional Output Only]
    PersonaDialogue[Persona-colored Dialogue]
    OptOut{User Requests Stop?}
    AskPerm{Permanent or Session?}
    PermanentOff[Set Config fun_mode=false]
    SessionOff[Drop Persona for Session]
    SelfCheck{Self-Check Passes?}
    Revise[Revise Synthesis]
    Continue([Continue Session])

    Start --> Source
    Source -- "Session init" --> SessionInit
    Source -- "/fun [instructions]" --> CustomInstr
    SessionInit --> HasElements
    CustomInstr --> HasElements
    HasElements -- "Yes" --> Synthesize
    HasElements -- "No: missing element" --> Start
    Synthesize --> LoadStakes
    LoadStakes --> Announce
    Announce --> Economy
    Economy --> BoundaryCheck
    BoundaryCheck -- "Code/commits/docs/files" --> Professional
    BoundaryCheck -- "User dialogue" --> PersonaDialogue
    Professional --> OptOut
    PersonaDialogue --> OptOut
    OptOut -- "Yes" --> AskPerm
    OptOut -- "No" --> SelfCheck
    AskPerm -- "Permanent" --> PermanentOff
    AskPerm -- "Session only" --> SessionOff
    PermanentOff --> Continue
    SessionOff --> Continue
    SelfCheck -- "Pass" --> Continue
    SelfCheck -- "Fail" --> Revise
    Revise --> Synthesize

    style Start fill:#4CAF50,color:#fff
    style Source fill:#FF9800,color:#fff
    style HasElements fill:#FF9800,color:#fff
    style BoundaryCheck fill:#FF9800,color:#fff
    style OptOut fill:#FF9800,color:#fff
    style AskPerm fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
    style LoadStakes fill:#4CAF50,color:#fff
    style SessionInit fill:#2196F3,color:#fff
    style CustomInstr fill:#2196F3,color:#fff
    style Synthesize fill:#2196F3,color:#fff
    style Announce fill:#2196F3,color:#fff
    style Economy fill:#2196F3,color:#fff
    style Professional fill:#2196F3,color:#fff
    style PersonaDialogue fill:#2196F3,color:#fff
    style PermanentOff fill:#2196F3,color:#fff
    style SessionOff fill:#2196F3,color:#fff
    style Revise fill:#2196F3,color:#fff
    style Continue fill:#4CAF50,color:#fff
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
| Read spellbook_session_init | Lines 25-27, 41-42: Input from session init |
| Synthesize Character | Lines 49-58: Announcement schema, three-element synthesis |
| Load emotional-stakes | Line 12: "Also load: emotional-stakes skill" |
| Apply Economy Principle | Lines 64-70: Economy after opening |
| Artifact Context? | Lines 73-81: Boundaries table (dialogue-only) |
| Permanent or Session? | Lines 101-108: Opt-out flow |
| Self-Check Passes? | Lines 125-131: Self-check checklist |
