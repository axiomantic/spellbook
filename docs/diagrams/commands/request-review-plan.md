<!-- diagram-meta: {"source": "commands/request-review-plan.md", "source_hash": "sha256:b961ea96e889f7dfee8174183f7dc7fac41d2230ea141c4d98266e773f7fdebf", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: request-review-plan

Planning and context assembly phases for code review requests. Determines git range, builds file list, and assembles reviewer context bundle.

```mermaid
flowchart TD
    Start([Start]) --> P1["Phase 1: Planning"]
    P1 --> GitRange["Determine Git Range\nBASE_SHA..HEAD_SHA"]
    GitRange --> FileList["List Files to Review"]
    FileList --> ExcludeGen{"Generated/Vendor\nFiles?"}
    ExcludeGen -->|Yes| FilterOut["Exclude from List"]
    ExcludeGen -->|No| KeepFile["Include in List"]
    FilterOut --> FindPlan["Find Plan/Spec Doc"]
    KeepFile --> FindPlan
    FindPlan --> EstComplexity["Estimate Complexity"]
    EstComplexity --> Gate1{"Range Defined?\nFile List Confirmed?"}
    Gate1 -->|No| P1
    Gate1 -->|Yes| P2["Phase 2: Context"]
    P2 --> ExtractPlan["Extract Plan Excerpts"]
    ExtractPlan --> GatherDeps["Gather Code Context"]
    GatherDeps --> PriorFindings{"Prior Review\nFindings?"}
    PriorFindings -->|Yes| NotePrior["Note Prior Findings"]
    PriorFindings -->|No| PrepContext["Prepare Context Bundle"]
    NotePrior --> PrepContext
    PrepContext --> Gate2{"Context Bundle\nReady?"}
    Gate2 -->|No| P2
    Gate2 -->|Yes| Done([Context Bundle Complete])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style P1 fill:#2196F3,color:#fff
    style P2 fill:#2196F3,color:#fff
    style GitRange fill:#2196F3,color:#fff
    style FileList fill:#2196F3,color:#fff
    style FilterOut fill:#2196F3,color:#fff
    style KeepFile fill:#2196F3,color:#fff
    style FindPlan fill:#2196F3,color:#fff
    style EstComplexity fill:#2196F3,color:#fff
    style ExtractPlan fill:#2196F3,color:#fff
    style GatherDeps fill:#2196F3,color:#fff
    style NotePrior fill:#2196F3,color:#fff
    style PrepContext fill:#2196F3,color:#fff
    style ExcludeGen fill:#FF9800,color:#fff
    style PriorFindings fill:#FF9800,color:#fff
    style Gate1 fill:#f44336,color:#fff
    style Gate2 fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
