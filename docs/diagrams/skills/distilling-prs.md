<!-- diagram-meta: {"source": "skills/distilling-prs/SKILL.md", "source_hash": "sha256:43be309eed4d0075b68542b3b1a72d9a265707b1982e0a0d22ffd5ef2361881f", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: distilling-prs

Workflow for the distilling-prs skill. A two-phase execution model: Phase 1 fetches PR data, parses diffs, and runs heuristic pattern matching; Phase 2 applies AI analysis to unmatched files; Phase 3 generates a categorized report. Heuristics always run first before AI analysis.

```mermaid
flowchart TD
    Start([Start]) --> ParsePR["Parse PR identifier"]
    ParsePR --> Phase1["Phase 1: Fetch Parse Match"]

    subgraph Phase1Sub["Phase 1: Heuristic Matching"]
        Fetch["pr_fetch: Get PR data"]
        Parse["pr_diff: Parse unified diff"]
        Match["pr_match_patterns: Run heuristics"]
        Fetch --> Parse --> Match
    end

    Phase1 --> Fetch
    Match --> HasUnmatched{Unmatched files remain?}

    HasUnmatched -->|Yes| Phase2["Phase 2: AI Analysis"]
    HasUnmatched -->|No| Phase3

    subgraph Phase2Sub["Phase 2: AI Classification"]
        AnalyzeFile["Analyze unmatched file"]
        Classify{Classify change?}
        ReviewReq["Mark: review_required"]
        SafeSkip["Mark: safe_to_skip"]
        Uncertain["Mark: uncertain"]
        MoreFiles{More unmatched files?}
        AnalyzeFile --> Classify
        Classify -->|Significant logic/API| ReviewReq
        Classify -->|Formatting/trivial| SafeSkip
        Classify -->|Low confidence| Uncertain
        ReviewReq --> MoreFiles
        SafeSkip --> MoreFiles
        Uncertain --> MoreFiles
        MoreFiles -->|Yes| AnalyzeFile
    end

    Phase2 --> AnalyzeFile
    MoreFiles -->|No| Phase3

    Phase3["Phase 3: Generate Report"]
    Phase3 --> Summary["Summary by category"]
    Summary --> Diffs["Full diffs for review items"]
    Diffs --> Patterns["Pattern matches + confidence"]
    Patterns --> Discover["Discovered patterns + bless cmds"]
    Discover --> GateComplete{All files categorized?}

    GateComplete -->|No| Phase2
    GateComplete -->|Yes| Present["Present report to user"]
    Present --> Done([Done])

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style Phase1 fill:#4CAF50,color:#fff
    style Phase2 fill:#4CAF50,color:#fff
    style ParsePR fill:#2196F3,color:#fff
    style Fetch fill:#2196F3,color:#fff
    style Parse fill:#2196F3,color:#fff
    style Match fill:#2196F3,color:#fff
    style AnalyzeFile fill:#2196F3,color:#fff
    style ReviewReq fill:#2196F3,color:#fff
    style SafeSkip fill:#2196F3,color:#fff
    style Uncertain fill:#2196F3,color:#fff
    style Phase3 fill:#2196F3,color:#fff
    style Summary fill:#2196F3,color:#fff
    style Diffs fill:#2196F3,color:#fff
    style Patterns fill:#2196F3,color:#fff
    style Discover fill:#2196F3,color:#fff
    style Present fill:#2196F3,color:#fff
    style HasUnmatched fill:#FF9800,color:#fff
    style Classify fill:#FF9800,color:#fff
    style MoreFiles fill:#FF9800,color:#fff
    style GateComplete fill:#f44336,color:#fff
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
| Parse PR identifier | SKILL.md: Execution Flow step 1 - parse number or URL |
| pr_fetch | SKILL.md: MCP Tools - Fetch PR metadata and diff |
| pr_diff | SKILL.md: MCP Tools - Parse unified diff into FileDiff objects |
| pr_match_patterns | SKILL.md: MCP Tools - Match heuristic patterns against file diffs |
| Unmatched files remain? | SKILL.md: Phase 1 output - `match_result["unmatched"]` |
| AI Classification | SKILL.md: Phase 2 - review_required, safe_to_skip, uncertain |
| All files categorized? | SKILL.md: Reflection - "All files categorized (no files missing)" |
| Discovered patterns | SKILL.md: Phase 3 - "Discovered patterns with bless commands" |
| Builtin Patterns | SKILL.md: 15 builtin patterns across 3 confidence levels |
