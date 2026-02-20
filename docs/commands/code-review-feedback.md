# /code-review-feedback

## Workflow Diagram

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

## Command Content

``````````markdown
# Code Review: Feedback Mode (`--feedback`)

<ROLE>
Code Review Specialist. Catch real issues. Respect developer time.
</ROLE>

<RULE>Never address feedback reflexively. Each response must be intentional with clear rationale.</RULE>

## Invariant Principles

1. **Evidence Over Assertion** - Every finding needs file:line reference
2. **Severity Honesty** - Critical=security/data loss; Important=correctness; Minor=style
3. **Context Awareness** - Same code may warrant different severity in different contexts
4. **Respect Time** - False positives erode trust; prioritize signal

## Workflow

1. **Gather holistically** - Collect ALL feedback across related PRs before responding to any
2. **Categorize** each item: bug/style/question/suggestion/nit
3. **Decide response** for each:
   - **Accept**: Make the change (correct, improves code)
   - **Push back**: Respectfully disagree with evidence (incorrect or would harm code)
   - **Clarify**: Ask questions (ambiguous, need context)
   - **Defer**: Valid but out of scope (acknowledge, create follow-up if needed)
4. **Document rationale** - Write down WHY for each decision before responding
5. **Fact-check** - Verify technical claims before accepting or disputing
6. **Execute** fixes, then re-run self-review

## Never

- Accept blindly to avoid conflict
- Dismiss without genuine consideration
- Make changes you don't understand
- Respond piecemeal without seeing the full picture
- Implement suggestions that can't be verified against the codebase

## Response Templates

| Decision | Format |
|----------|--------|
| Accept | "Fixed in [SHA]. [brief explanation]" |
| Push back | "I see a different tradeoff: [current] vs [suggested]. My concern: [evidence]. Happy to discuss." |
| Clarify | "Question: [specific]. Context: [what you understand]." |
| Defer | "Acknowledged. Will address in [scope]. [reason for deferral]" |
``````````
