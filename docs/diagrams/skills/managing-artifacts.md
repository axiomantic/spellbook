<!-- diagram-meta: {"source": "skills/managing-artifacts/SKILL.md", "source_hash": "sha256:fe7763b76b0d3e63a39e44123e2457e5ebccec2f8e120c3181e94f1908742d3a", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: managing-artifacts

Artifact routing workflow that determines the correct storage location for generated files. Computes project-encoded paths, detects multi-contributor repos, and enforces the rule that generated artifacts never litter project directories.

```mermaid
flowchart TD
    Start([Artifact to Write])
    DetermineType[Determine Artifact Type]
    FindGitRoot{Git Repo Exists?}
    NoRepo[Use Fallback Path]
    ComputeEncoded[Compute Project-Encoded Path]
    MultiContrib{Multi-Contributor?}
    CheckUpstream[Check: upstream remote?]
    CheckAuthors[Check: multiple authors?]
    CheckContrib[Check: CONTRIBUTING.md?]
    CheckFork[Check: is fork?]
    IsCLAUDE{Is CLAUDE.md?}
    FallbackCLAUDE[Write to ~/.local/spellbook]
    SelectDir{Artifact Type?}
    Plans[plans/ Directory]
    Audits[audits/ Directory]
    Reports[reports/ Directory]
    Encyclopedia[docs/ Root]
    Distilled[distilled/ Directory]
    Logs[logs/ Directory]
    WriteFile[Write to Spellbook Path]
    VerifyGate{Written Outside Project?}
    FixPath[Correct Path]
    InformUser[Inform User of Location]
    Complete([Artifact Stored])

    Start --> DetermineType
    DetermineType --> FindGitRoot
    FindGitRoot -- "No" --> NoRepo
    FindGitRoot -- "Yes" --> ComputeEncoded
    NoRepo --> WriteFile
    ComputeEncoded --> MultiContrib
    MultiContrib -- "Check signals" --> CheckUpstream
    CheckUpstream --> CheckAuthors
    CheckAuthors --> CheckContrib
    CheckContrib --> CheckFork
    CheckFork --> IsCLAUDE
    IsCLAUDE -- "Yes + multi-contrib" --> FallbackCLAUDE
    IsCLAUDE -- "No / single-contrib" --> SelectDir
    FallbackCLAUDE --> WriteFile
    SelectDir -- "Design/impl plan" --> Plans
    SelectDir -- "Audit/review" --> Audits
    SelectDir -- "Analysis/summary" --> Reports
    SelectDir -- "Encyclopedia" --> Encyclopedia
    SelectDir -- "Session distill" --> Distilled
    SelectDir -- "Operation log" --> Logs
    Plans --> WriteFile
    Audits --> WriteFile
    Reports --> WriteFile
    Encyclopedia --> WriteFile
    Distilled --> WriteFile
    Logs --> WriteFile
    WriteFile --> VerifyGate
    VerifyGate -- "Yes" --> InformUser
    VerifyGate -- "No: in project dir" --> FixPath
    FixPath --> WriteFile
    InformUser --> Complete

    style Start fill:#4CAF50,color:#fff
    style FindGitRoot fill:#FF9800,color:#fff
    style MultiContrib fill:#FF9800,color:#fff
    style IsCLAUDE fill:#FF9800,color:#fff
    style SelectDir fill:#FF9800,color:#fff
    style VerifyGate fill:#f44336,color:#fff
    style DetermineType fill:#2196F3,color:#fff
    style NoRepo fill:#2196F3,color:#fff
    style ComputeEncoded fill:#2196F3,color:#fff
    style CheckUpstream fill:#2196F3,color:#fff
    style CheckAuthors fill:#2196F3,color:#fff
    style CheckContrib fill:#2196F3,color:#fff
    style CheckFork fill:#2196F3,color:#fff
    style FallbackCLAUDE fill:#2196F3,color:#fff
    style Plans fill:#2196F3,color:#fff
    style Audits fill:#2196F3,color:#fff
    style Reports fill:#2196F3,color:#fff
    style Encyclopedia fill:#2196F3,color:#fff
    style Distilled fill:#2196F3,color:#fff
    style Logs fill:#2196F3,color:#fff
    style WriteFile fill:#2196F3,color:#fff
    style FixPath fill:#2196F3,color:#fff
    style InformUser fill:#2196F3,color:#fff
    style Complete fill:#4CAF50,color:#fff
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
| Determine Artifact Type | Lines 23-27: Analysis - determine artifact type |
| Git Repo Exists? | Lines 62-74: _outer_git_root function, NO_GIT_REPO fallback |
| Compute Project-Encoded Path | Lines 60-74: Project encoded path generation |
| Multi-Contributor? | Lines 100-105: Detection signals (upstream, authors, CONTRIBUTING, fork) |
| Is CLAUDE.md? | Lines 89-109: Open source project handling |
| Artifact Type? | Lines 111-121: Quick reference table for artifact locations |
| Written Outside Project? | Lines 78-85, 123-129: NEVER write to project dirs, FORBIDDEN list |
