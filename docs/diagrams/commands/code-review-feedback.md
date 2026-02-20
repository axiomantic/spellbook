<!-- diagram-meta: {"source": "commands/code-review-feedback.md", "source_hash": "sha256:00b7e60cfbc8801a1c22758c090288b2f63dcf784031fcd9f80f333f5aaea1c4", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: code-review-feedback

Process received code review feedback with categorization, decision rationale, and response templates.

```mermaid
flowchart TD
    Start([Start: Feedback Received]) --> Gather[Gather All Feedback]
    Gather --> Categorize[Categorize Each Item]

    Categorize --> CatType{Bug/Style/Question/Suggestion/Nit?}
    CatType --> Decide[Decide Response]

    Decide --> Decision{Accept/Push Back/Clarify/Defer?}

    Decision -->|Accept| Accept[Make the Change]
    Decision -->|Push Back| PushBack[Disagree with Evidence]
    Decision -->|Clarify| Clarify[Ask Questions]
    Decision -->|Defer| Defer[Acknowledge + Follow-up]

    Accept --> Rationale[Document Rationale]
    PushBack --> Rationale
    Clarify --> Rationale
    Defer --> Rationale

    Rationale --> FactCheck{Claims Verified?}
    FactCheck -->|No| VerifyClaims[Verify Technical Claims]
    VerifyClaims --> FactCheck
    FactCheck -->|Yes| Execute[Execute Fixes]

    Execute --> SelfReview[/Re-run Self-Review/]
    SelfReview --> Gate{All Responses Intentional?}
    Gate -->|No| Decide
    Gate -->|Yes| Done([Complete])

    style Start fill:#2196F3,color:#fff
    style Gather fill:#2196F3,color:#fff
    style Categorize fill:#2196F3,color:#fff
    style CatType fill:#FF9800,color:#fff
    style Decide fill:#2196F3,color:#fff
    style Decision fill:#FF9800,color:#fff
    style Accept fill:#2196F3,color:#fff
    style PushBack fill:#2196F3,color:#fff
    style Clarify fill:#2196F3,color:#fff
    style Defer fill:#2196F3,color:#fff
    style Rationale fill:#2196F3,color:#fff
    style FactCheck fill:#f44336,color:#fff
    style VerifyClaims fill:#2196F3,color:#fff
    style Execute fill:#2196F3,color:#fff
    style SelfReview fill:#4CAF50,color:#fff
    style Gate fill:#f44336,color:#fff
    style Done fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
