<!-- diagram-meta: {"source": "commands/simplify.md", "source_hash": "sha256:3b7d785e613407dc796dbeff0a7d1280bcd8cfe23b0a212587f7e91489055eb5", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: simplify

Orchestrates systematic code simplification targeting cognitive complexity reduction. Delegates to three sequential sub-commands (simplify-analyze, simplify-verify, simplify-transform) with multi-gate verification and user approval gates.

```mermaid
flowchart TD
    Start([Invoke /simplify]) --> DetermineScope[Determine Target Scope]
    DetermineScope --> ScopeType{Scope Source?}

    ScopeType -->|default| FindBaseBranch[Find Base Branch]
    ScopeType -->|--staged| StagedChanges[Staged Changes Only]
    ScopeType -->|--repo| ConfirmRepo{User Confirms Repo?}
    ScopeType -->|file/dir| ExplicitTarget[Use Explicit Path]

    ConfirmRepo -->|No| Abort([Abort])
    ConfirmRepo -->|Yes| ExplicitTarget

    FindBaseBranch --> AskMode{Mode?}
    StagedChanges --> AskMode
    ExplicitTarget --> AskMode

    AskMode -->|--dry-run| DryRun[Report Only Mode]
    AskMode -->|--auto| AutoMode[Automated Mode]
    AskMode -->|--wizard| WizardMode[Wizard Mode]
    AskMode -->|default| PromptUser[Ask User for Mode]
    PromptUser --> AutoMode
    PromptUser --> WizardMode
    PromptUser --> DryRun

    DryRun --> Analyze[/simplify-analyze]
    AutoMode --> Analyze
    WizardMode --> Analyze

    Analyze --> DiscoverFunctions[Discover Functions]
    DiscoverFunctions --> CalcComplexity[Calculate Cognitive Complexity]
    CalcComplexity --> FilterMin{Above Min Threshold?}
    FilterMin -->|No| SkipFunction[Skip Function]
    FilterMin -->|Yes| CoverageCheck{Has Test Coverage?}

    CoverageCheck -->|No + no flag| SkipUncovered[Skip Uncovered]
    CoverageCheck -->|No + --allow-uncovered| MarkHighRisk[Mark High Risk]
    CoverageCheck -->|Yes| AddCandidate[Add to Candidates]
    MarkHighRisk --> AddCandidate

    SkipFunction --> FilterMin
    SkipUncovered --> FilterMin
    AddCandidate --> FilterMin

    AddCandidate --> DryRunCheck{Dry Run?}
    DryRunCheck -->|Yes| GenerateReport[Generate Report]
    GenerateReport --> Done([Done])

    DryRunCheck -->|No| Verify[/simplify-verify]
    Verify --> ParseGate{Parse Gate?}
    ParseGate -->|Fail| RejectChange[Reject Transformation]
    ParseGate -->|Pass| TypeGate{Type Check Gate?}
    TypeGate -->|Fail| RejectChange
    TypeGate -->|Pass| TestGate{Test Gate?}
    TestGate -->|Fail| RejectChange
    TestGate -->|Pass| DeltaGate{Complexity Reduced?}
    DeltaGate -->|No| RejectChange
    DeltaGate -->|Yes| Transform[/simplify-transform]

    RejectChange --> NextCandidate[Next Candidate]
    NextCandidate --> Verify

    Transform --> ModeRoute{Mode?}
    ModeRoute -->|auto| BatchApproval{User Approves Batch?}
    ModeRoute -->|wizard| StepApproval{User Approves Change?}

    BatchApproval -->|No| Done
    BatchApproval -->|Yes| ApplyAll[Apply All Changes]
    StepApproval -->|No| SkipOne[Skip This Change]
    StepApproval -->|Yes| ApplyOne[Apply Change]
    SkipOne --> StepApproval
    ApplyOne --> ReVerify[Re-Verify After Apply]
    ReVerify --> StepApproval

    ApplyAll --> FinalVerify[Final Verification]
    FinalVerify --> FinalReport[Show Summary]
    FinalReport --> Done

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style Abort fill:#2196F3,color:#fff
    style ScopeType fill:#FF9800,color:#fff
    style ConfirmRepo fill:#FF9800,color:#fff
    style AskMode fill:#FF9800,color:#fff
    style FilterMin fill:#FF9800,color:#fff
    style CoverageCheck fill:#FF9800,color:#fff
    style DryRunCheck fill:#FF9800,color:#fff
    style ModeRoute fill:#FF9800,color:#fff
    style BatchApproval fill:#FF9800,color:#fff
    style StepApproval fill:#FF9800,color:#fff
    style ParseGate fill:#f44336,color:#fff
    style TypeGate fill:#f44336,color:#fff
    style TestGate fill:#f44336,color:#fff
    style DeltaGate fill:#f44336,color:#fff
    style Analyze fill:#4CAF50,color:#fff
    style Verify fill:#4CAF50,color:#fff
    style Transform fill:#4CAF50,color:#fff
    style DetermineScope fill:#2196F3,color:#fff
    style FindBaseBranch fill:#2196F3,color:#fff
    style StagedChanges fill:#2196F3,color:#fff
    style ExplicitTarget fill:#2196F3,color:#fff
    style PromptUser fill:#2196F3,color:#fff
    style DryRun fill:#2196F3,color:#fff
    style AutoMode fill:#2196F3,color:#fff
    style WizardMode fill:#2196F3,color:#fff
    style DiscoverFunctions fill:#2196F3,color:#fff
    style CalcComplexity fill:#2196F3,color:#fff
    style SkipFunction fill:#2196F3,color:#fff
    style SkipUncovered fill:#2196F3,color:#fff
    style MarkHighRisk fill:#2196F3,color:#fff
    style AddCandidate fill:#2196F3,color:#fff
    style GenerateReport fill:#2196F3,color:#fff
    style RejectChange fill:#2196F3,color:#fff
    style NextCandidate fill:#2196F3,color:#fff
    style ApplyAll fill:#2196F3,color:#fff
    style SkipOne fill:#2196F3,color:#fff
    style ApplyOne fill:#2196F3,color:#fff
    style ReVerify fill:#2196F3,color:#fff
    style FinalVerify fill:#2196F3,color:#fff
    style FinalReport fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
