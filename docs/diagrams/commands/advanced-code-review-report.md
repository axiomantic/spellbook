<!-- diagram-meta: {"source": "commands/advanced-code-review-report.md", "source_hash": "sha256:b8b507d034435bc313b70e7467dc7aa0b8337bae348ca6eb41ef6ce103eb6ae1", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: advanced-code-review-report

Phase 5 of advanced-code-review: Report generation that filters verified findings, determines verdict, renders the final Markdown report and machine-readable JSON summary with action items.

```mermaid
flowchart TD
    Start([Phase 5 Start])

    FilterFindings[Filter out REFUTED findings]
    SortSeverity[Sort by severity]

    DetermineVerdict{Verdict logic}
    ReqChanges[REQUEST_CHANGES]
    Comment[COMMENT]
    Approve[APPROVE]
    GenRationale[Generate verdict rationale]

    RenderReport[Render report template]
    RenderFindings[Render findings section]
    RenderActions[Generate action items]
    RenderPrevCtx[Render previous context]

    ActionItems[Build action checklist]
    CriticalAction[Blocking: CRITICAL/HIGH]
    MediumAction[Suggested: MEDIUM]

    WriteReport[Write review-report.md]
    WriteSummary[Write review-summary.json]

    SelfCheck{Phase 5 self-check OK?}
    Phase5Done([Review Complete])

    Start --> FilterFindings
    FilterFindings --> SortSeverity

    SortSeverity --> DetermineVerdict
    DetermineVerdict -->|CRITICAL or HIGH| ReqChanges
    DetermineVerdict -->|MEDIUM only| Comment
    DetermineVerdict -->|None blocking| Approve
    ReqChanges --> GenRationale
    Comment --> GenRationale
    Approve --> GenRationale

    GenRationale --> RenderReport
    RenderReport --> RenderFindings
    RenderFindings --> RenderActions
    RenderActions --> RenderPrevCtx

    RenderPrevCtx --> ActionItems
    ActionItems --> CriticalAction
    ActionItems --> MediumAction
    CriticalAction --> WriteReport
    MediumAction --> WriteReport

    WriteReport --> WriteSummary
    WriteSummary --> SelfCheck
    SelfCheck -->|Yes| Phase5Done

    style Start fill:#2196F3,color:#fff
    style Phase5Done fill:#2196F3,color:#fff
    style WriteReport fill:#2196F3,color:#fff
    style WriteSummary fill:#2196F3,color:#fff
    style DetermineVerdict fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
