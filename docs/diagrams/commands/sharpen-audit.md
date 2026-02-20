<!-- diagram-meta: {"source": "commands/sharpen-audit.md", "source_hash": "sha256:ac9b53942754ea1d54cad14a3cc82d8039b3d0fe7b93c4069adde8a34d5d924d", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: sharpen-audit

Audits LLM prompts and instructions for ambiguity through a 6-phase protocol: inventory, line-by-line scan, categorize findings, generate executor predictions, draft clarification questions, and compile a structured report with severity ratings and verdict.

```mermaid
flowchart TD
    Start([Invoke /sharpen-audit]) --> Analysis[Pre-Audit Analysis]
    Analysis --> Phase1[Phase 1: Inventory]
    Phase1 --> IdentifyType[Identify Prompt Type]
    IdentifyType --> NoteContext[Note Executor Context]

    NoteContext --> Phase2[Phase 2: Line-by-Line Scan]
    Phase2 --> ScanLoop{All Statements Checked?}
    ScanLoop -->|No| CheckStatement[Check for Ambiguity]
    CheckStatement --> MultiMeaning{Multiple Meanings?}
    MultiMeaning -->|Yes| FlagFinding[Flag as Finding]
    MultiMeaning -->|No| NextStatement[Next Statement]
    FlagFinding --> NextStatement
    NextStatement --> ScanLoop

    ScanLoop -->|Yes| Phase3[Phase 3: Categorize Findings]
    Phase3 --> AssignSeverity{Assign Severity}
    AssignSeverity -->|Core undefined| Critical[CRITICAL]
    AssignSeverity -->|Main path unclear| High[HIGH]
    AssignSeverity -->|Edge case unclear| Medium[MEDIUM]
    AssignSeverity -->|Convention resolves| Low[LOW]

    Critical --> Phase4[Phase 4: Executor Predictions]
    High --> Phase4
    Medium --> Phase4
    Low --> Phase4

    Phase4 --> PredictGuess[Predict LLM Behavior Per Finding]
    PredictGuess --> Phase5[Phase 5: Clarification Questions]
    Phase5 --> DraftQuestions[Draft Specific Questions]

    DraftQuestions --> Phase6[Phase 6: Compile Report]
    Phase6 --> WriteSummary[Write Severity Distribution]
    WriteSummary --> WriteFindings[Write All Findings]
    WriteFindings --> WriteClarifications[Write Clarification Requests]
    WriteClarifications --> WriteRemediation[Write Remediation Checklist]

    WriteRemediation --> Verdict{Determine Verdict}
    Verdict -->|No CRITICAL/HIGH| Pass[PASS]
    Verdict -->|Has HIGH only| NeedsWork[NEEDS_WORK]
    Verdict -->|Has CRITICAL| CriticalIssues[CRITICAL_ISSUES]

    Pass --> Reflection[Post-Audit Reflection]
    NeedsWork --> Reflection
    CriticalIssues --> Reflection
    Reflection --> Done([Audit Complete])

    style Start fill:#2196F3,color:#fff
    style Done fill:#2196F3,color:#fff
    style ScanLoop fill:#FF9800,color:#fff
    style MultiMeaning fill:#FF9800,color:#fff
    style AssignSeverity fill:#FF9800,color:#fff
    style Verdict fill:#f44336,color:#fff
    style Analysis fill:#2196F3,color:#fff
    style Phase1 fill:#2196F3,color:#fff
    style IdentifyType fill:#2196F3,color:#fff
    style NoteContext fill:#2196F3,color:#fff
    style Phase2 fill:#2196F3,color:#fff
    style CheckStatement fill:#2196F3,color:#fff
    style FlagFinding fill:#2196F3,color:#fff
    style NextStatement fill:#2196F3,color:#fff
    style Phase3 fill:#2196F3,color:#fff
    style Critical fill:#2196F3,color:#fff
    style High fill:#2196F3,color:#fff
    style Medium fill:#2196F3,color:#fff
    style Low fill:#2196F3,color:#fff
    style Phase4 fill:#2196F3,color:#fff
    style PredictGuess fill:#2196F3,color:#fff
    style Phase5 fill:#2196F3,color:#fff
    style DraftQuestions fill:#2196F3,color:#fff
    style Phase6 fill:#2196F3,color:#fff
    style WriteSummary fill:#2196F3,color:#fff
    style WriteFindings fill:#2196F3,color:#fff
    style WriteClarifications fill:#2196F3,color:#fff
    style WriteRemediation fill:#2196F3,color:#fff
    style Pass fill:#2196F3,color:#fff
    style NeedsWork fill:#2196F3,color:#fff
    style CriticalIssues fill:#2196F3,color:#fff
    style Reflection fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
