<!-- diagram-meta: {"source": "commands/dead-code-report.md", "source_hash": "sha256:4c9a4a0311565c6bde7d7c8a6c97634875b3fb089fce95c8a9973717dd8f7726", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: dead-code-report

Generate a comprehensive dead code report with categorized findings, evidence, risk assessment, and an ordered implementation plan for safe deletion. Runs after `/dead-code-analyze`.

```mermaid
flowchart TD
  Start([Start: Analysis Complete]) --> Gate1{All items verified?}

  Gate1 -->|No| Block[Return to analyze]
  Gate1 -->|Yes| Collect[Collect verified findings]

  style Gate1 fill:#FF9800,color:#000
  style Block fill:#f44336,color:#fff

  Collect --> CatHigh[Categorize: Zero callers]
  Collect --> CatTrans[Categorize: Transitive dead]
  Collect --> CatWrite[Categorize: Write-only dead]
  Collect --> CatAlive[Categorize: Alive code]

  style CatHigh fill:#2196F3,color:#fff
  style CatTrans fill:#2196F3,color:#fff
  style CatWrite fill:#2196F3,color:#fff
  style CatAlive fill:#2196F3,color:#fff

  CatHigh --> Evidence[Attach evidence per finding]
  CatTrans --> Evidence
  CatWrite --> Evidence
  CatAlive --> Evidence

  style Evidence fill:#2196F3,color:#fff

  Evidence --> EvidenceGate{Evidence for every finding?}

  style EvidenceGate fill:#f44336,color:#fff

  EvidenceGate -->|No| BackEvidence[Fill missing evidence]
  EvidenceGate -->|Yes| Risk[Assess risk per item]

  BackEvidence --> Evidence

  style Risk fill:#2196F3,color:#fff

  Risk --> Order[Order deletion plan]

  style Order fill:#2196F3,color:#fff

  Order --> DependCheck{Dependency order safe?}

  style DependCheck fill:#FF9800,color:#000

  DependCheck -->|No| Reorder[Reorder by dependencies]
  DependCheck -->|Yes| GenReport[Generate markdown report]

  Reorder --> DependCheck

  style GenReport fill:#2196F3,color:#fff

  GenReport --> VerifyCmds[Generate verify commands]

  style VerifyCmds fill:#2196F3,color:#fff

  VerifyCmds --> SaveReport[Save to reports dir]

  style SaveReport fill:#2196F3,color:#fff

  SaveReport --> Summary[Output summary stats]

  style Summary fill:#2196F3,color:#fff

  Summary --> Next[Suggest next steps]

  style Next fill:#2196F3,color:#fff

  Next --> End([End: Report saved])

  style Start fill:#4CAF50,color:#fff
  style End fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
