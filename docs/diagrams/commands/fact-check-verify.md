<!-- diagram-meta: {"source": "commands/fact-check-verify.md", "source_hash": "sha256:0a77e83f6092f80fe004c88385e8e16778fc48f06b02c63bf69318b5c49d5045", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: fact-check-verify

Perform parallel verification of extracted claims using specialized agents, check AgentDB for prior findings, produce evidence-backed verdicts, and store results for future sessions.

```mermaid
flowchart TD
  Start([Start: Claims triaged]) --> CheckDB[Check AgentDB first]

  style Start fill:#4CAF50,color:#fff
  style CheckDB fill:#2196F3,color:#fff

  CheckDB --> DBHit{Prior finding exists?}

  style DBHit fill:#FF9800,color:#000

  DBHit -->|Yes, similarity > 0.92| Reuse[Reuse cached finding]
  DBHit -->|No| SpawnAgents[Spawn category agents]

  style Reuse fill:#2196F3,color:#fff
  style SpawnAgents fill:#4CAF50,color:#fff

  SpawnAgents --> SecAgent[SecurityAgent]
  SpawnAgents --> CorAgent[CorrectnessAgent]
  SpawnAgents --> PerfAgent[PerformanceAgent]
  SpawnAgents --> ConcAgent[ConcurrencyAgent]
  SpawnAgents --> DocAgent[DocumentationAgent]
  SpawnAgents --> HistAgent[HistoricalAgent]
  SpawnAgents --> ConfAgent[ConfigurationAgent]

  style SecAgent fill:#4CAF50,color:#fff
  style CorAgent fill:#4CAF50,color:#fff
  style PerfAgent fill:#4CAF50,color:#fff
  style ConcAgent fill:#4CAF50,color:#fff
  style DocAgent fill:#4CAF50,color:#fff
  style HistAgent fill:#4CAF50,color:#fff
  style ConfAgent fill:#4CAF50,color:#fff

  SecAgent --> Collect[Collect agent results]
  CorAgent --> Collect
  PerfAgent --> Collect
  ConcAgent --> Collect
  DocAgent --> Collect
  HistAgent --> Collect
  ConfAgent --> Collect

  style Collect fill:#2196F3,color:#fff

  Reuse --> AssignVerdict

  Collect --> EvidenceGate{Concrete evidence?}

  style EvidenceGate fill:#f44336,color:#fff

  EvidenceGate -->|No| GatherMore[Gather more evidence]
  EvidenceGate -->|Yes| AssignVerdict[Assign verdict]

  style GatherMore fill:#2196F3,color:#fff

  GatherMore --> EvidenceGate

  AssignVerdict --> Verified[Verified]
  AssignVerdict --> Refuted[Refuted]
  AssignVerdict --> Incomplete[Incomplete]
  AssignVerdict --> Inconclusive[Inconclusive]
  AssignVerdict --> Stale[Stale / Misleading]

  style AssignVerdict fill:#2196F3,color:#fff
  style Verified fill:#2196F3,color:#fff
  style Refuted fill:#2196F3,color:#fff
  style Incomplete fill:#2196F3,color:#fff
  style Inconclusive fill:#2196F3,color:#fff
  style Stale fill:#2196F3,color:#fff

  Verified --> StoreDB[Store in AgentDB]
  Refuted --> StoreDB
  Incomplete --> StoreDB
  Inconclusive --> StoreDB
  Stale --> StoreDB

  style StoreDB fill:#2196F3,color:#fff

  StoreDB --> AllDone{All claims verified?}

  style AllDone fill:#FF9800,color:#000

  AllDone -->|No| CheckDB
  AllDone -->|Yes| End([End: Verdicts assigned])

  style End fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
