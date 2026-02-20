<!-- diagram-meta: {"source": "commands/simplify-transform.md", "source_hash": "sha256:4a0965eaa0740a62d856a2c5a298d7c2558cf59e57db04c976110fecbe2a0f9a", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: simplify-transform

Present and apply verified simplifications with multi-mode workflow and git integration. Handles automated, wizard, and report-only presentation modes.

```mermaid
flowchart TD
    Start([Verified Candidates]) --> GenReport["Generate\nSimplification Report"]
    GenReport --> ModeSwitch{"Presentation\nMode?"}
    ModeSwitch -->|Automated| ShowBatch["Show Batch Report"]
    ModeSwitch -->|Wizard| WizardLoop["Present One\nSimplification"]
    ModeSwitch -->|Report Only| ShowFull["Show Full Report"]
    ShowBatch --> AutoApproval{"User Approval?"}
    AutoApproval -->|Apply All| ApplyPhase["Step 6: Application"]
    AutoApproval -->|Review Each| WizardLoop
    AutoApproval -->|Export| SaveReport["Save Report\nand Exit"]
    WizardLoop --> WizardChoice{"Apply This\nChange?"}
    WizardChoice -->|Yes| ApplySingle["Apply Transform"]
    WizardChoice -->|No| SkipOne["Skip This One"]
    WizardChoice -->|More Context| ShowContext["Show +/- 20 Lines"]
    WizardChoice -->|Apply Remaining| ApplyPhase
    WizardChoice -->|Stop| WizardSummary["Exit with Summary"]
    ShowContext --> WizardLoop
    ApplySingle --> MoreWizard{"More Items?"}
    SkipOne --> MoreWizard
    MoreWizard -->|Yes| WizardLoop
    MoreWizard -->|No| ApplyPhase
    ShowFull --> SaveReport
    ApplyPhase --> ReadFile["Read Current File"]
    ReadFile --> ApplyChange["Apply Transformation"]
    ApplyChange --> PostVerify{"Post-Apply\nVerification?"}
    PostVerify -->|Fail| RevertChange["Revert Change"]
    PostVerify -->|Pass| NextChange{"More Changes?"}
    RevertChange --> NextChange
    NextChange -->|Yes| ReadFile
    NextChange -->|No| RunTests["Run Full Test Suite"]
    RunTests --> TestGate{"All Tests Pass?"}
    TestGate -->|No| IdentifyFail["Identify Failing\nTransform"]
    IdentifyFail --> RevertChange
    TestGate -->|Yes| CommitChoice{"Commit Strategy?"}
    CommitChoice -->|Atomic/File| AtomicCommit["Commit Per File\nWith Approval"]
    CommitChoice -->|Batch| BatchCommit["Single Batch\nCommit"]
    CommitChoice -->|No Commit| LeaveUnstaged["Leave Unstaged"]
    AtomicCommit --> FinalSummary["Display Final\nSummary"]
    BatchCommit --> FinalSummary
    LeaveUnstaged --> FinalSummary
    WizardSummary --> FinalSummary
    SaveReport --> Done([Complete])
    FinalSummary --> Done

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style GenReport fill:#2196F3,color:#fff
    style ShowBatch fill:#2196F3,color:#fff
    style WizardLoop fill:#2196F3,color:#fff
    style ShowFull fill:#2196F3,color:#fff
    style ApplyPhase fill:#2196F3,color:#fff
    style ApplySingle fill:#2196F3,color:#fff
    style SkipOne fill:#2196F3,color:#fff
    style ShowContext fill:#2196F3,color:#fff
    style WizardSummary fill:#2196F3,color:#fff
    style SaveReport fill:#2196F3,color:#fff
    style ReadFile fill:#2196F3,color:#fff
    style ApplyChange fill:#2196F3,color:#fff
    style RevertChange fill:#2196F3,color:#fff
    style RunTests fill:#2196F3,color:#fff
    style IdentifyFail fill:#2196F3,color:#fff
    style AtomicCommit fill:#2196F3,color:#fff
    style BatchCommit fill:#2196F3,color:#fff
    style LeaveUnstaged fill:#2196F3,color:#fff
    style FinalSummary fill:#2196F3,color:#fff
    style ModeSwitch fill:#FF9800,color:#fff
    style AutoApproval fill:#FF9800,color:#fff
    style WizardChoice fill:#FF9800,color:#fff
    style MoreWizard fill:#FF9800,color:#fff
    style NextChange fill:#FF9800,color:#fff
    style CommitChoice fill:#FF9800,color:#fff
    style PostVerify fill:#f44336,color:#fff
    style TestGate fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
