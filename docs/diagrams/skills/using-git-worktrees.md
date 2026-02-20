<!-- diagram-meta: {"source": "skills/using-git-worktrees/SKILL.md", "source_hash": "sha256:c7a571a5be25f296f9154a74da5c0fc2f0ace6b7342820fb6bff4766a5baa823", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: using-git-worktrees

Workspace isolation via git worktrees with safety verification, dependency setup, and clean test baseline enforcement.

```mermaid
flowchart TD
    Start([Start: Worktree Request]) --> CheckExisting{Existing Directory?}

    CheckExisting -->|.worktrees exists| UseWorktrees[Use .worktrees/]
    CheckExisting -->|worktrees exists| UseWorktreesAlt[Use worktrees/]
    CheckExisting -->|Both exist| UseWorktrees
    CheckExisting -->|Neither| CheckClaude{CLAUDE.md Preference?}

    CheckClaude -->|Yes| UsePref[Use Specified Path]
    CheckClaude -->|No| AskUser[Ask User for Location]

    AskUser --> LocationChoice{Project-Local or Global?}
    LocationChoice -->|Project-Local| UseWorktrees
    LocationChoice -->|Global| UseGlobal[Use ~/.local/spellbook/worktrees/]

    UseWorktrees --> SafetyCheck
    UseWorktreesAlt --> SafetyCheck
    UsePref --> PathType{Project-Local Path?}

    PathType -->|Yes| SafetyCheck
    PathType -->|No| CreateWorktree

    SafetyCheck{git check-ignore Passes?}
    SafetyCheck -->|Yes| CreateWorktree
    SafetyCheck -->|No| FixIgnore[Add to .gitignore]
    FixIgnore --> CommitIgnore[Commit .gitignore Change]
    CommitIgnore --> SafetyCheck

    UseGlobal --> CreateWorktree

    CreateWorktree[git worktree add] --> WorktreeExists{Worktree Already Exists?}
    WorktreeExists -->|Yes| ReportError[Report Error: Ask New Name]
    WorktreeExists -->|No| DetectProject[Detect Project Type]

    DetectProject --> SetupDeps{Setup Dependencies}
    SetupDeps -->|package.json| NpmInstall[npm install]
    SetupDeps -->|Cargo.toml| CargoBuild[cargo build]
    SetupDeps -->|requirements.txt| PipInstall[pip install]
    SetupDeps -->|pyproject.toml| UvSync[poetry install / uv sync]
    SetupDeps -->|go.mod| GoMod[go mod download]
    SetupDeps -->|None found| SkipDeps[Skip Dependency Install]

    NpmInstall --> SetupGate{Setup Succeeded?}
    CargoBuild --> SetupGate
    PipInstall --> SetupGate
    UvSync --> SetupGate
    GoMod --> SetupGate
    SkipDeps --> RunTests

    SetupGate -->|Yes| RunTests[Run Baseline Tests]
    SetupGate -->|No| ReportSetupFail[Report Failure: Ask User]

    RunTests --> TestGate{Tests Pass?}
    TestGate -->|Yes| ReportReady[Report Worktree Ready]
    TestGate -->|No| ReportTestFail[Report Failures: Ask User]

    ReportReady --> SelfCheck{Self-Check Passed?}
    SelfCheck -->|Yes| Done([Worktree Ready])
    SelfCheck -->|No| Resolve[STOP: Resolve Issues]

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style CheckExisting fill:#FF9800,color:#fff
    style CheckClaude fill:#FF9800,color:#fff
    style LocationChoice fill:#FF9800,color:#fff
    style PathType fill:#FF9800,color:#fff
    style SafetyCheck fill:#f44336,color:#fff
    style WorktreeExists fill:#FF9800,color:#fff
    style SetupDeps fill:#FF9800,color:#fff
    style SetupGate fill:#f44336,color:#fff
    style TestGate fill:#f44336,color:#fff
    style SelfCheck fill:#f44336,color:#fff
    style UseWorktrees fill:#2196F3,color:#fff
    style UseWorktreesAlt fill:#2196F3,color:#fff
    style UsePref fill:#2196F3,color:#fff
    style AskUser fill:#2196F3,color:#fff
    style UseGlobal fill:#2196F3,color:#fff
    style FixIgnore fill:#2196F3,color:#fff
    style CommitIgnore fill:#2196F3,color:#fff
    style CreateWorktree fill:#2196F3,color:#fff
    style ReportError fill:#2196F3,color:#fff
    style DetectProject fill:#2196F3,color:#fff
    style NpmInstall fill:#2196F3,color:#fff
    style CargoBuild fill:#2196F3,color:#fff
    style PipInstall fill:#2196F3,color:#fff
    style UvSync fill:#2196F3,color:#fff
    style GoMod fill:#2196F3,color:#fff
    style SkipDeps fill:#2196F3,color:#fff
    style RunTests fill:#2196F3,color:#fff
    style ReportReady fill:#2196F3,color:#fff
    style ReportSetupFail fill:#2196F3,color:#fff
    style ReportTestFail fill:#2196F3,color:#fff
    style Resolve fill:#f44336,color:#fff
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
| Start: Worktree Request | Inputs: feature_name required (line 25) |
| Existing Directory? | Directory Selection Process step 1 (lines 43-51) |
| CLAUDE.md Preference? | Directory Selection Process step 2 (lines 53-59) |
| Ask User for Location | Directory Selection Process step 3 (lines 61-72) |
| git check-ignore Passes? | Safety Verification: verify directory is ignored (lines 76-95) |
| Add to .gitignore | Safety Verification: fix if not ignored (lines 97-100) |
| git worktree add | Creation Steps step 2 (lines 114-133) |
| Detect Project Type | Creation Steps step 3: auto-detect setup (lines 135-152) |
| Setup Dependencies | Creation Steps step 3: language-specific install (lines 140-152) |
| Run Baseline Tests | Creation Steps step 4: verify clean baseline (lines 156-178) |
| Tests Pass? | Reflection block: do tests pass in new worktree? (lines 168-174) |
| Report Worktree Ready | Creation Steps step 5: report location (lines 180-186) |
| Self-Check Passed? | Self-Check checklist (lines 296-304) |
