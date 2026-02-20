<!-- diagram-meta: {"source": "commands/advanced-code-review-plan.md", "source_hash": "sha256:bae4e46252e6d88dc0a7606d0986b319a5d1a40c940ec8b27b7c8305a92edfac", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: advanced-code-review-plan

Phase 1 of advanced-code-review: Strategic planning that resolves the review target, acquires the diff, categorizes files by risk, estimates complexity, and produces a prioritized review manifest and plan.

```mermaid
flowchart TD
    Start([Phase 1 Start])

    ResolveTarget[Resolve target to refs]
    TargetValid{Target valid?}
    TargetError[List similar branches, exit]

    GetDiff[Acquire diff from merge base]
    DiffEmpty{Diff empty?}
    NoDiff([No changes: exit clean])

    CatFiles[Categorize files by risk]
    HighRisk[HIGH: auth, security, payment]
    MedRisk[MEDIUM: api, config, database]
    LowRisk[LOW: tests, docs, styles]

    EstComplexity[Estimate review complexity]
    CalcMinutes[Calculate estimated minutes]
    ClassifyEffort{Effort level?}
    SmallEffort[Small: under 15 min]
    MedEffort[Medium: 15-45 min]
    LargeEffort[Large: 45+ min]

    ComputeWeight[Compute risk-weighted scope]
    PriorityOrder[Create priority ordering]

    WriteManifest[Write review-manifest.json]
    WritePlan[Write review-plan.md]

    SelfCheck{Phase 1 self-check OK?}
    SelfCheckFail([STOP: Report issue])
    Phase1Done([Phase 1 Complete])

    Start --> ResolveTarget
    ResolveTarget --> TargetValid
    TargetValid -->|No| TargetError
    TargetValid -->|Yes| GetDiff

    GetDiff --> DiffEmpty
    DiffEmpty -->|Yes| NoDiff
    DiffEmpty -->|No| CatFiles

    CatFiles --> HighRisk
    CatFiles --> MedRisk
    CatFiles --> LowRisk
    HighRisk --> EstComplexity
    MedRisk --> EstComplexity
    LowRisk --> EstComplexity

    EstComplexity --> CalcMinutes
    CalcMinutes --> ClassifyEffort
    ClassifyEffort -->|Small| SmallEffort
    ClassifyEffort -->|Medium| MedEffort
    ClassifyEffort -->|Large| LargeEffort
    SmallEffort --> ComputeWeight
    MedEffort --> ComputeWeight
    LargeEffort --> ComputeWeight

    ComputeWeight --> PriorityOrder
    PriorityOrder --> WriteManifest
    WriteManifest --> WritePlan

    WritePlan --> SelfCheck
    SelfCheck -->|No| SelfCheckFail
    SelfCheck -->|Yes| Phase1Done

    style Start fill:#2196F3,color:#fff
    style Phase1Done fill:#2196F3,color:#fff
    style NoDiff fill:#2196F3,color:#fff
    style TargetError fill:#2196F3,color:#fff
    style SelfCheckFail fill:#2196F3,color:#fff
    style WriteManifest fill:#2196F3,color:#fff
    style WritePlan fill:#2196F3,color:#fff
    style TargetValid fill:#FF9800,color:#fff
    style DiffEmpty fill:#FF9800,color:#fff
    style ClassifyEffort fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
