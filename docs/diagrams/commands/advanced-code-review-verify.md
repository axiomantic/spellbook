<!-- diagram-meta: {"source": "commands/advanced-code-review-verify.md", "source_hash": "sha256:f1d0fb4d4c0ba54f1564bba26b2ead12e0f3da4ff326c06128c450e5fdcd872b", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: advanced-code-review-verify

Phase 4 of advanced-code-review: Verification that fact-checks every finding against the actual codebase, removes false positives, flags inconclusive items, detects duplicates, and calculates signal-to-noise ratio.

```mermaid
flowchart TD
    Start([Phase 4 Start])

    DetectDups[Detect duplicate findings]
    DupsFound{Duplicates found?}
    MergeDups[Merge duplicate findings]

    NextFinding{More findings?}
    ExtractClaims[Extract verifiable claims]

    ClaimType{Claim type?}
    VerifyLine[Verify line content]
    VerifyFunc[Verify function behavior]
    VerifyCall[Verify call pattern]
    VerifyPattern[Verify pattern violation]

    AggResult{Aggregate result?}
    MarkVerified[Mark: VERIFIED]
    MarkRefuted[Mark: REFUTED]
    MarkInconclusive[Mark: INCONCLUSIVE]

    ValidateLines[Validate line numbers]
    LinesValid{Lines valid?}
    AdjustLines[Flag invalid lines]

    AllVerified{All findings processed?}

    RemoveRefuted[Remove REFUTED findings]
    LogRefuted[Log to verification audit]
    FlagInconclusive[Flag INCONCLUSIVE items]

    CalcSNR[Calculate signal-to-noise]
    SNRResult[Signal/Noise ratio computed]

    WriteAudit[Write verification-audit.md]
    UpdateJSON[Update findings.json]

    SelfCheck{Phase 4 self-check OK?}
    SelfCheckFail([STOP: Unverified findings])
    Phase4Done([Phase 4 Complete])

    Start --> DetectDups
    DetectDups --> DupsFound
    DupsFound -->|Yes| MergeDups
    MergeDups --> NextFinding
    DupsFound -->|No| NextFinding

    NextFinding -->|Yes| ExtractClaims
    ExtractClaims --> ClaimType

    ClaimType -->|line_content| VerifyLine
    ClaimType -->|function_behavior| VerifyFunc
    ClaimType -->|call_pattern| VerifyCall
    ClaimType -->|pattern_violation| VerifyPattern

    VerifyLine --> AggResult
    VerifyFunc --> AggResult
    VerifyCall --> AggResult
    VerifyPattern --> AggResult

    AggResult -->|Verified| MarkVerified
    AggResult -->|Refuted| MarkRefuted
    AggResult -->|Inconclusive| MarkInconclusive

    MarkVerified --> ValidateLines
    MarkRefuted --> ValidateLines
    MarkInconclusive --> ValidateLines

    ValidateLines --> LinesValid
    LinesValid -->|No| AdjustLines
    AdjustLines --> AllVerified
    LinesValid -->|Yes| AllVerified

    AllVerified -->|No| NextFinding
    AllVerified -->|Yes| RemoveRefuted

    NextFinding -->|No| RemoveRefuted

    RemoveRefuted --> LogRefuted
    LogRefuted --> FlagInconclusive
    FlagInconclusive --> CalcSNR
    CalcSNR --> SNRResult

    SNRResult --> WriteAudit
    WriteAudit --> UpdateJSON
    UpdateJSON --> SelfCheck

    SelfCheck -->|No| SelfCheckFail
    SelfCheck -->|Yes| Phase4Done

    style Start fill:#2196F3,color:#fff
    style Phase4Done fill:#2196F3,color:#fff
    style SelfCheckFail fill:#2196F3,color:#fff
    style WriteAudit fill:#2196F3,color:#fff
    style UpdateJSON fill:#2196F3,color:#fff
    style DupsFound fill:#FF9800,color:#fff
    style NextFinding fill:#FF9800,color:#fff
    style ClaimType fill:#FF9800,color:#fff
    style AggResult fill:#FF9800,color:#fff
    style LinesValid fill:#FF9800,color:#fff
    style AllVerified fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
