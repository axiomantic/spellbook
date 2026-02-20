<!-- diagram-meta: {"source": "commands/advanced-code-review-context.md", "source_hash": "sha256:90257d354a931fb6891f8f90536858608cd6108164937efa81b52d06eee4d22f", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: advanced-code-review-context

Phase 2 of advanced-code-review: Context analysis that discovers previous reviews, loads item states, fetches PR history, detects re-check requests, and builds the context object for the deep review phase.

```mermaid
flowchart TD
    Start([Phase 2 Start])

    DiscoverPrev[Discover previous review]
    PrevExists{Previous review found?}
    CheckFresh{Review fresh enough?}
    CheckStructure{Structure valid?}
    NoPrev[No previous review]

    LoadItems[Load previous items]
    ClassifyItems[Classify item states]
    Declined[DECLINED: never re-raise]
    Fixed[FIXED: skip]
    Partial[PARTIAL: note pending]
    Alternative[ALTERNATIVE: evaluate]
    Pending[PENDING: include if present]

    OnlineCheck{Online mode?}
    FetchPR[Fetch PR description]
    FetchComments[Fetch PR comments]
    SkipOnline[Skip PR history]

    DetectRecheck[Detect re-check requests]
    ParsePatterns[Parse PTAL patterns]
    ExtractTargets[Extract re-check targets]

    BuildContext[Build context object]
    MergeDeclined[Add declined items]
    MergePartial[Add partial items]
    MergeAlternative[Add alternative items]
    MergeRecheck[Add re-check requests]

    WriteAnalysis[Write context-analysis.md]
    WriteItems[Write previous-items.json]

    SelfCheck{Phase 2 self-check OK?}
    Phase2Done([Phase 2 Complete])

    Start --> DiscoverPrev
    DiscoverPrev --> PrevExists
    PrevExists -->|No| NoPrev
    PrevExists -->|Yes| CheckFresh
    CheckFresh -->|Stale| NoPrev
    CheckFresh -->|Fresh| CheckStructure
    CheckStructure -->|Invalid| NoPrev
    CheckStructure -->|Valid| LoadItems

    NoPrev --> OnlineCheck

    LoadItems --> ClassifyItems
    ClassifyItems --> Declined
    ClassifyItems --> Fixed
    ClassifyItems --> Partial
    ClassifyItems --> Alternative
    ClassifyItems --> Pending
    Declined --> OnlineCheck
    Fixed --> OnlineCheck
    Partial --> OnlineCheck
    Alternative --> OnlineCheck
    Pending --> OnlineCheck

    OnlineCheck -->|Yes| FetchPR
    OnlineCheck -->|No| SkipOnline
    FetchPR --> FetchComments
    FetchComments --> DetectRecheck
    SkipOnline --> BuildContext

    DetectRecheck --> ParsePatterns
    ParsePatterns --> ExtractTargets
    ExtractTargets --> BuildContext

    BuildContext --> MergeDeclined
    MergeDeclined --> MergePartial
    MergePartial --> MergeAlternative
    MergeAlternative --> MergeRecheck
    MergeRecheck --> WriteAnalysis

    WriteAnalysis --> WriteItems
    WriteItems --> SelfCheck
    SelfCheck -->|Yes| Phase2Done

    style Start fill:#2196F3,color:#fff
    style Phase2Done fill:#2196F3,color:#fff
    style WriteAnalysis fill:#2196F3,color:#fff
    style WriteItems fill:#2196F3,color:#fff
    style PrevExists fill:#FF9800,color:#fff
    style CheckFresh fill:#FF9800,color:#fff
    style CheckStructure fill:#FF9800,color:#fff
    style OnlineCheck fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
