<!-- diagram-meta: {"source": "commands/code-review-give.md", "source_hash": "sha256:a388a4436efc0f6a865a259c374fc30cea084e296ab486eccf5344edfeefea2a", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: code-review-give

Review someone else's code with multi-pass analysis and structured recommendations.

```mermaid
flowchart TD
    Start([Start: Target Provided]) --> Parse{Target Format?}
    Parse -->|PR Number| FetchPR[Fetch via gh pr diff]
    Parse -->|URL| FetchURL[Fetch via gh pr diff]
    Parse -->|Branch| FetchBranch[Fetch via git diff]

    FetchPR --> Understand[Understand PR Goal]
    FetchURL --> Understand
    FetchBranch --> Understand

    Understand --> Pass1[Pass 1: Security Review]
    Pass1 --> Pass2[Pass 2: Correctness Review]
    Pass2 --> Pass3[Pass 3: Style Review]

    Pass3 --> Classify{Findings Severity?}
    Classify -->|Critical| Blocking[Add to Blocking Issues]
    Classify -->|Important| Suggestions[Add to Suggestions]
    Classify -->|Minor| Minor[Add to Minor Items]
    Classify -->|Question| Questions[Add to Questions]

    Blocking --> Output[Generate Review Output]
    Suggestions --> Output
    Minor --> Output
    Questions --> Output

    Output --> Verdict{Recommendation?}
    Verdict -->|No Blockers| Approve[APPROVE]
    Verdict -->|Has Blockers| RequestChanges[REQUEST_CHANGES]
    Verdict -->|Needs Discussion| Comment[COMMENT]

    Approve --> Done([Complete])
    RequestChanges --> Done
    Comment --> Done

    style Start fill:#2196F3,color:#fff
    style Parse fill:#FF9800,color:#fff
    style FetchPR fill:#2196F3,color:#fff
    style FetchURL fill:#2196F3,color:#fff
    style FetchBranch fill:#2196F3,color:#fff
    style Understand fill:#2196F3,color:#fff
    style Pass1 fill:#2196F3,color:#fff
    style Pass2 fill:#2196F3,color:#fff
    style Pass3 fill:#2196F3,color:#fff
    style Classify fill:#FF9800,color:#fff
    style Blocking fill:#f44336,color:#fff
    style Suggestions fill:#2196F3,color:#fff
    style Minor fill:#2196F3,color:#fff
    style Questions fill:#2196F3,color:#fff
    style Output fill:#2196F3,color:#fff
    style Verdict fill:#FF9800,color:#fff
    style Approve fill:#4CAF50,color:#fff
    style RequestChanges fill:#f44336,color:#fff
    style Comment fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
