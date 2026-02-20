<!-- diagram-meta: {"source": "commands/simplify-verify.md", "source_hash": "sha256:5910c137bad483d041c7146e47cc7921b976c529ea663242581e96d86df93e3a", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: simplify-verify

Multi-gate verification pipeline for simplification candidates. Each candidate passes through parse, type, test, and complexity gates.

```mermaid
flowchart TD
    Start([Analyzed Candidates]) --> NextCandidate["Load Next\nCandidate"]
    NextCandidate --> Gate1["Gate 1:\nParse Check"]
    Gate1 --> ParseResult{"Syntax Valid?"}
    ParseResult -->|No| AbortParse["Abort: Syntax Error"]
    ParseResult -->|Yes| Gate2["Gate 2:\nType Check"]
    Gate2 --> TypeResult{"Types Valid?"}
    TypeResult -->|No| AbortType["Abort: Type Error"]
    TypeResult -->|Yes| Gate3["Gate 3:\nTest Run"]
    Gate3 --> TestCoverage{"Tests Found?"}
    TestCoverage -->|No| AllowUncovered{"--allow-uncovered\nFlag Set?"}
    AllowUncovered -->|No| AbortCoverage["Abort: No Coverage"]
    AllowUncovered -->|Yes| HighRisk["Proceed with\nHigh Risk Flag"]
    TestCoverage -->|Yes| RunTests["Run Covering Tests"]
    RunTests --> TestResult{"Tests Pass?"}
    TestResult -->|No| AbortTest["Abort: Tests Failed"]
    TestResult -->|Yes| Gate4["Gate 4:\nComplexity Delta"]
    HighRisk --> Gate4
    Gate4 --> CalcDelta["Calculate\nBefore/After Scores"]
    CalcDelta --> DeltaResult{"Complexity\nReduced?"}
    DeltaResult -->|No| AbortDelta["Abort: No Improvement"]
    DeltaResult -->|Yes| RecordMetrics["Record Metrics\nBefore/After/Delta"]
    AbortParse --> RecordFail["Record Failure\nReason"]
    AbortType --> RecordFail
    AbortCoverage --> RecordFail
    AbortTest --> RecordFail
    AbortDelta --> RecordFail
    RecordFail --> MoreCandidates{"More\nCandidates?"}
    RecordMetrics --> MoreCandidates
    MoreCandidates -->|Yes| NextCandidate
    MoreCandidates -->|No| Output([Verified Candidates\n+ SESSION_STATE])

    style Start fill:#4CAF50,color:#fff
    style Output fill:#4CAF50,color:#fff
    style NextCandidate fill:#2196F3,color:#fff
    style RunTests fill:#2196F3,color:#fff
    style CalcDelta fill:#2196F3,color:#fff
    style RecordMetrics fill:#2196F3,color:#fff
    style RecordFail fill:#2196F3,color:#fff
    style HighRisk fill:#2196F3,color:#fff
    style AbortParse fill:#2196F3,color:#fff
    style AbortType fill:#2196F3,color:#fff
    style AbortCoverage fill:#2196F3,color:#fff
    style AbortTest fill:#2196F3,color:#fff
    style AbortDelta fill:#2196F3,color:#fff
    style Gate1 fill:#f44336,color:#fff
    style Gate2 fill:#f44336,color:#fff
    style Gate3 fill:#f44336,color:#fff
    style Gate4 fill:#f44336,color:#fff
    style ParseResult fill:#FF9800,color:#fff
    style TypeResult fill:#FF9800,color:#fff
    style TestCoverage fill:#FF9800,color:#fff
    style AllowUncovered fill:#FF9800,color:#fff
    style TestResult fill:#FF9800,color:#fff
    style DeltaResult fill:#FF9800,color:#fff
    style MoreCandidates fill:#FF9800,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
