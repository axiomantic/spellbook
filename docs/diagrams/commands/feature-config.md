<!-- diagram-meta: {"source": "commands/feature-config.md", "source_hash": "sha256:e05d7a8fe23a49f3f531d19e9bd9f45fcec527a6c2f3801907703ae219608cd0", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: feature-config

Phase 0 of implementing-features: Configuration wizard that collects preferences, detects escape hatches, clarifies motivation, classifies complexity, and routes to the appropriate next phase.

```mermaid
flowchart TD
    Start([Phase 0 Start])
    DetCont{Continuation signals?}
    ParseRecovery[Parse recovery context]
    VerifyArtifacts[Verify artifact existence]
    QuickPrefs[Quick preferences check]
    SynthResume[Synthesize resume point]
    ConfirmResume[Confirm and resume]
    PhaseJump[Phase jump mechanism]

    DetEscape[Detect escape hatches]
    EscapeFound{Escape hatch found?}
    AskDocHandling[Ask document handling]
    RouteEscape[Route by escape type]

    ClarifyWhy[Clarify motivation]
    MotivClear{Motivation clear?}
    AskMotiv[Ask WHY via wizard]

    ClarifyWhat[Clarify feature essence]
    CollectPrefs[Collect workflow prefs]
    DetRefactor{Refactoring mode?}
    SetRefactor[Set refactoring mode]

    RunHeuristics[Run mechanical heuristics]
    DeriveTier[Derive complexity tier]
    ConfirmTier[Present and confirm tier]

    TierRoute{Complexity tier?}
    ExitTrivial([Exit: TRIVIAL])
    SimplePath[Simple path: inline]
    StandardPath[/feature-research]
    ComplexPath[/feature-research]

    GateP0{Phase 0 checklist complete?}
    FixP0[Complete missing items]

    Start --> DetCont
    DetCont -->|Yes| ParseRecovery
    ParseRecovery --> VerifyArtifacts
    VerifyArtifacts --> QuickPrefs
    QuickPrefs --> SynthResume
    SynthResume --> ConfirmResume
    ConfirmResume --> PhaseJump
    PhaseJump --> GateP0

    DetCont -->|No| DetEscape
    DetEscape --> EscapeFound
    EscapeFound -->|Yes| AskDocHandling
    AskDocHandling --> RouteEscape
    RouteEscape --> ClarifyWhy
    EscapeFound -->|No| ClarifyWhy

    ClarifyWhy --> MotivClear
    MotivClear -->|No| AskMotiv
    AskMotiv --> ClarifyWhat
    MotivClear -->|Yes| ClarifyWhat

    ClarifyWhat --> CollectPrefs
    CollectPrefs --> DetRefactor
    DetRefactor -->|Yes| SetRefactor
    SetRefactor --> RunHeuristics
    DetRefactor -->|No| RunHeuristics

    RunHeuristics --> DeriveTier
    DeriveTier --> ConfirmTier
    ConfirmTier --> GateP0

    GateP0 -->|Incomplete| FixP0
    FixP0 --> GateP0
    GateP0 -->|Complete| TierRoute

    TierRoute -->|TRIVIAL| ExitTrivial
    TierRoute -->|SIMPLE| SimplePath
    TierRoute -->|STANDARD| StandardPath
    TierRoute -->|COMPLEX| ComplexPath

    style Start fill:#2196F3,color:#fff
    style ExitTrivial fill:#2196F3,color:#fff
    style SimplePath fill:#2196F3,color:#fff
    style StandardPath fill:#4CAF50,color:#fff
    style ComplexPath fill:#4CAF50,color:#fff
    style DetCont fill:#FF9800,color:#fff
    style EscapeFound fill:#FF9800,color:#fff
    style MotivClear fill:#FF9800,color:#fff
    style DetRefactor fill:#FF9800,color:#fff
    style TierRoute fill:#FF9800,color:#fff
    style GateP0 fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
