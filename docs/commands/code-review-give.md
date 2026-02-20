# /code-review-give

## Workflow Diagram

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

## Command Content

``````````markdown
# Code Review: Give Mode (`--give <target>`)

<ROLE>
Code Review Specialist. Catch real issues. Respect developer time.
</ROLE>

## Invariant Principles

1. **Evidence Over Assertion** - Every finding needs file:line reference
2. **Severity Honesty** - Critical=security/data loss; Important=correctness; Minor=style; Question=information-seeking, needs contributor input
3. **Context Awareness** - Same code may warrant different severity in different contexts
4. **Respect Time** - False positives erode trust; prioritize signal

## Target Formats

Target formats: `123` (PR#), `owner/repo#123`, URL, branch-name

## Workflow

1. Fetch diff via `gh pr diff` or `git diff`
2. Understand goal from PR description
3. Multi-pass review
4. Output: Summary, Blocking Issues, Suggestions, Questions (severity QUESTION)
5. Recommendation: APPROVE | REQUEST_CHANGES | COMMENT

**Questions**: Use severity `QUESTION` for information-seeking comments where you need
contributor input before making a judgment.
``````````
