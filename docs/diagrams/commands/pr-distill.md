<!-- diagram-meta: {"source": "commands/pr-distill.md", "source_hash": "sha256:4698c598d62fe2b0e6b6913a6c51943d5615a44131231cc13bf14aa560858555", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: pr-distill

Analyze a PR and generate a review distillation report. Runs heuristic pattern matching first, then AI analysis for unmatched files.

```mermaid
flowchart TD
    Start([PR Identifier]) --> ParsePR["Parse PR Number\nor URL"]
    ParsePR --> Phase1["Phase 1: Fetch,\nParse, Match"]
    Phase1 --> RunCLI["Run Heuristic\nCLI Tool"]
    RunCLI --> HeuristicResult["Heuristic Pattern\nMatching"]
    HeuristicResult --> UnmatchedCheck{"Unmatched Files\nRemain?"}
    UnmatchedCheck -->|No| Phase2["Phase 2: Score\nand Report"]
    UnmatchedCheck -->|Yes| AIPrompt["Process AI Prompt\nfor Discovery"]
    AIPrompt --> Phase2
    Phase2 --> ContinueCLI["Run --continue\nwith AI Response"]
    ContinueCLI --> ScoreChanges["Score All Changes"]
    ScoreChanges --> GenReport["Generate Markdown\nReport"]
    GenReport --> VerifyComplete{"All Files\nCategorized?"}
    VerifyComplete -->|No| FixMissing["Identify Missing\nFiles"]
    FixMissing --> ScoreChanges
    VerifyComplete -->|Yes| CheckDiffs{"REVIEW_REQUIRED\nHave Full Diffs?"}
    CheckDiffs -->|No| AddDiffs["Add Missing Diffs"]
    AddDiffs --> CheckDiffs
    CheckDiffs -->|Yes| SaveReport["Save Report to\n~/.local/spellbook/"]
    SaveReport --> PresentReport["Present Report\nto User"]
    PresentReport --> Done([Distillation Complete])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style ParsePR fill:#2196F3,color:#fff
    style Phase1 fill:#2196F3,color:#fff
    style RunCLI fill:#2196F3,color:#fff
    style HeuristicResult fill:#2196F3,color:#fff
    style AIPrompt fill:#4CAF50,color:#fff
    style Phase2 fill:#2196F3,color:#fff
    style ContinueCLI fill:#2196F3,color:#fff
    style ScoreChanges fill:#2196F3,color:#fff
    style GenReport fill:#2196F3,color:#fff
    style FixMissing fill:#2196F3,color:#fff
    style AddDiffs fill:#2196F3,color:#fff
    style SaveReport fill:#2196F3,color:#fff
    style PresentReport fill:#2196F3,color:#fff
    style UnmatchedCheck fill:#FF9800,color:#fff
    style VerifyComplete fill:#f44336,color:#fff
    style CheckDiffs fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
