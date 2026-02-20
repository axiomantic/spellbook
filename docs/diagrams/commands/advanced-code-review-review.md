<!-- diagram-meta: {"source": "commands/advanced-code-review-review.md", "source_hash": "sha256:18de2671236d63c2a7e5d45f8a26d45193ab3b97f31f5377e4b2436c31e2cc44", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: advanced-code-review-review

Phase 3 of advanced-code-review: Deep multi-pass code review that analyzes each file through security, correctness, quality, and polish passes, integrates previous item context, and generates structured findings.

```mermaid
flowchart TD
    Start([Phase 3 Start])

    GetOrder[Get priority-ordered files]
    NextFile{More files to review?}

    FileStart[Start file review]
    Pass1[Pass 1: Security]
    Pass1Findings[Security findings]
    Pass2[Pass 2: Correctness]
    Pass2Findings[Logic findings]
    Pass3[Pass 3: Quality]
    Pass3Findings[Quality findings]
    Pass4[Pass 4: Polish]
    Pass4Findings[Polish findings]

    CheckPrev{Previous item match?}
    DeclinedSkip[Skip: declined item]
    AltSkip[Skip: accepted alternative]
    PartialNote[Annotate: partial pending]
    RaiseFinding[Raise as new finding]

    SeverityTree{Severity classification}
    Critical[CRITICAL: security/data loss]
    High[HIGH: broken functionality]
    Medium[MEDIUM: quality concern]
    Low[LOW: minor improvement]
    Nit[NIT: purely stylistic]
    Question[QUESTION: needs input]
    Praise[PRAISE: noteworthy positive]

    CollectNoteworthy[Collect praise items]
    BuildFinding[Build finding with schema]

    WriteFindingsJSON[Write findings.json]
    WriteFindingsMD[Write findings.md]

    SelfCheck{Phase 3 self-check OK?}
    SelfCheckFail([STOP: Incomplete findings])
    Phase3Done([Phase 3 Complete])

    Start --> GetOrder
    GetOrder --> NextFile
    NextFile -->|Yes| FileStart
    NextFile -->|No| WriteFindingsJSON

    FileStart --> Pass1
    Pass1 --> Pass1Findings
    Pass1Findings --> Pass2
    Pass2 --> Pass2Findings
    Pass2Findings --> Pass3
    Pass3 --> Pass3Findings
    Pass3Findings --> Pass4
    Pass4 --> Pass4Findings

    Pass4Findings --> CheckPrev
    CheckPrev -->|Declined| DeclinedSkip
    CheckPrev -->|Alternative| AltSkip
    CheckPrev -->|Partial| PartialNote
    CheckPrev -->|New| RaiseFinding
    DeclinedSkip --> NextFile
    AltSkip --> NextFile
    PartialNote --> SeverityTree
    RaiseFinding --> SeverityTree

    SeverityTree --> Critical
    SeverityTree --> High
    SeverityTree --> Medium
    SeverityTree --> Low
    SeverityTree --> Nit
    SeverityTree --> Question
    SeverityTree --> Praise

    Critical --> BuildFinding
    High --> BuildFinding
    Medium --> BuildFinding
    Low --> BuildFinding
    Nit --> BuildFinding
    Question --> BuildFinding
    Praise --> CollectNoteworthy
    CollectNoteworthy --> BuildFinding
    BuildFinding --> NextFile

    WriteFindingsJSON --> WriteFindingsMD
    WriteFindingsMD --> SelfCheck
    SelfCheck -->|No| SelfCheckFail
    SelfCheck -->|Yes| Phase3Done

    style Start fill:#2196F3,color:#fff
    style Phase3Done fill:#2196F3,color:#fff
    style SelfCheckFail fill:#2196F3,color:#fff
    style WriteFindingsJSON fill:#2196F3,color:#fff
    style WriteFindingsMD fill:#2196F3,color:#fff
    style NextFile fill:#FF9800,color:#fff
    style CheckPrev fill:#FF9800,color:#fff
    style SeverityTree fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
