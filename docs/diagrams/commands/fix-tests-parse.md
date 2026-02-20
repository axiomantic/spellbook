<!-- diagram-meta: {"source": "commands/fix-tests-parse.md", "source_hash": "sha256:0f039b2b7d0d28db226c75822a72cb0f784f8f44c53bd60a58cf7d2bcacdebeb", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: fix-tests-parse

Parse audit reports or test failure output into structured work items, honor dependency ordering from remediation plans, and select a commit strategy before execution begins.

```mermaid
flowchart TD
  Start([Start: Audit report input]) --> DetectFormat{YAML block present?}

  style Start fill:#4CAF50,color:#fff
  style DetectFormat fill:#FF9800,color:#000

  DetectFormat -->|Yes| ParseYAML[Parse YAML findings]
  DetectFormat -->|No| FallbackParse[Fallback: split by headers]

  style ParseYAML fill:#2196F3,color:#fff
  style FallbackParse fill:#2196F3,color:#fff

  ParseYAML --> ExtractFields[Extract id, priority, file, pattern]

  style ExtractFields fill:#2196F3,color:#fff

  FallbackParse --> SplitHeaders[Split by Finding headers]

  style SplitHeaders fill:#2196F3,color:#fff

  SplitHeaders --> ExtractFallback[Extract file, line, pattern]

  style ExtractFallback fill:#2196F3,color:#fff

  ExtractFields --> ParseRemPlan{Remediation plan exists?}

  style ParseRemPlan fill:#FF9800,color:#000

  ParseRemPlan -->|Yes| ReadPhases[Read phase ordering]
  ParseRemPlan -->|No| SortPriority[Sort by priority only]

  style ReadPhases fill:#2196F3,color:#fff
  style SortPriority fill:#2196F3,color:#fff

  ExtractFallback --> SortPriority

  ReadPhases --> HonorDeps[Honor depends_on fields]

  style HonorDeps fill:#2196F3,color:#fff

  HonorDeps --> BuildItems[Build work items list]
  SortPriority --> BuildItems

  style BuildItems fill:#2196F3,color:#fff

  BuildItems --> ParseGate{All items parsed?}

  style ParseGate fill:#f44336,color:#fff

  ParseGate -->|No| FixParse[Re-parse failed items]
  ParseGate -->|Yes| OrderItems[Order: critical > important > minor]

  style FixParse fill:#2196F3,color:#fff
  style OrderItems fill:#2196F3,color:#fff

  FixParse --> ParseGate

  OrderItems --> AskCommit{Commit strategy?}

  style AskCommit fill:#FF9800,color:#000

  AskCommit -->|A| PerFix[Per-fix commits]
  AskCommit -->|B| BatchFile[Batch by file]
  AskCommit -->|C| SingleCommit[Single commit]

  style PerFix fill:#2196F3,color:#fff
  style BatchFile fill:#2196F3,color:#fff
  style SingleCommit fill:#2196F3,color:#fff

  PerFix --> End([End: Work items ready])
  BatchFile --> End
  SingleCommit --> End

  style End fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
