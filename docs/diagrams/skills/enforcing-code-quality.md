<!-- diagram-meta: {"source": "skills/enforcing-code-quality/SKILL.md", "source_hash": "sha256:e95fba3bbadc1106928ea73e9c3f88f033cd78ed94978cbe5520d940ae620eeb", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: enforcing-code-quality

Continuous quality enforcement workflow applied during code writing. Reads existing patterns first, applies prohibitions during implementation, flags pre-existing issues, and validates against a quality checklist before completion.

```mermaid
flowchart TD
    Start([Code Change Initiated])
    ReadPatterns[Read Existing Patterns]
    AnalyzePre[Analyze Pre-existing Issues]
    IssuesFound{Issues Found?}
    FlagIssues[Flag Issues to User]
    UserDecision{Fix Now?}
    FixIssues[Fix Pre-existing Issues]
    TrackIssues[Track Separately]
    WriteCode[Write Implementation]
    ProhibCheck{Prohibitions Violated?}
    FixViolation[Remove Violation]
    ErrorHandling[Verify Error Handling]
    TestAssertions[Verify Test Assertions]
    QualityGate{Quality Checklist?}
    FixQuality[Address Failures]
    Complete([Code Complete])

    Start --> ReadPatterns
    ReadPatterns --> AnalyzePre
    AnalyzePre --> IssuesFound
    IssuesFound -- "Yes" --> FlagIssues
    IssuesFound -- "No" --> WriteCode
    FlagIssues --> UserDecision
    UserDecision -- "Yes" --> FixIssues
    UserDecision -- "No" --> TrackIssues
    FixIssues --> WriteCode
    TrackIssues --> WriteCode
    WriteCode --> ProhibCheck
    ProhibCheck -- "Yes: any, try-catch, etc." --> FixViolation
    ProhibCheck -- "No violations" --> ErrorHandling
    FixViolation --> WriteCode
    ErrorHandling --> TestAssertions
    TestAssertions --> QualityGate
    QualityGate -- "All pass" --> Complete
    QualityGate -- "Failures" --> FixQuality
    FixQuality --> WriteCode

    style Start fill:#4CAF50,color:#fff
    style IssuesFound fill:#FF9800,color:#fff
    style UserDecision fill:#FF9800,color:#fff
    style ProhibCheck fill:#FF9800,color:#fff
    style QualityGate fill:#f44336,color:#fff
    style ReadPatterns fill:#2196F3,color:#fff
    style AnalyzePre fill:#2196F3,color:#fff
    style FlagIssues fill:#2196F3,color:#fff
    style FixIssues fill:#2196F3,color:#fff
    style TrackIssues fill:#2196F3,color:#fff
    style WriteCode fill:#2196F3,color:#fff
    style FixViolation fill:#2196F3,color:#fff
    style ErrorHandling fill:#2196F3,color:#fff
    style TestAssertions fill:#2196F3,color:#fff
    style FixQuality fill:#2196F3,color:#fff
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
| Read Existing Patterns | Lines 76, 100: "Read existing patterns FIRST" |
| Analyze Pre-existing Issues | Lines 83-95: Pre-existing issues protocol |
| Prohibitions Violated? | Lines 60-70: FORBIDDEN list |
| Verify Error Handling | Lines 78-79: Error branch and assertion requirements |
| Verify Test Assertions | Line 78: "Full assertions in tests" |
| Quality Checklist? | Lines 99-106: Quality checklist |
