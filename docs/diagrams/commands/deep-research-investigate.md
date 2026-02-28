<!-- diagram-meta: {"source": "commands/deep-research-investigate.md", "source_hash": "sha256:3ea231bffb3419088aae88ece44d0e94b00003d481e1407c4bbf60af1e1bfe35", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: deep-research-investigate

Execute iterative web research for a single thread using the Triplet Engine (Scope, Search, Extract) with plateau detection, drift guards, and micro-report generation each round.

```mermaid
flowchart TD
  Start([Start: Thread assigned]) --> Init[Initialize thread state]

  style Start fill:#4CAF50,color:#fff
  style Init fill:#2196F3,color:#fff

  Init --> Scope[SCOPE: Identify gaps]

  style Scope fill:#2196F3,color:#fff

  Scope --> OpenSQs[List open sub-questions]
  Scope --> UncovSubj[List uncovered subjects]
  Scope --> SetIntent[Define search intent]

  style OpenSQs fill:#2196F3,color:#fff
  style UncovSubj fill:#2196F3,color:#fff
  style SetIntent fill:#2196F3,color:#fff

  OpenSQs --> ForceCheck{Subject coverage gap?}
  UncovSubj --> ForceCheck

  style ForceCheck fill:#FF9800,color:#000

  ForceCheck -->|Yes, past half budget| ForceSubj[Force subject targeting]
  ForceCheck -->|No| FormQuery

  style ForceSubj fill:#2196F3,color:#fff

  ForceSubj --> FormQuery

  SetIntent --> FormQuery[Formulate search query]

  style FormQuery fill:#2196F3,color:#fff

  FormQuery --> Search[SEARCH: WebSearch]

  style Search fill:#4CAF50,color:#fff

  Search --> FetchResults[WebFetch top 3-5 results]

  style FetchResults fill:#2196F3,color:#fff

  FetchResults --> DriftCheck{Result relevant?}

  style DriftCheck fill:#FF9800,color:#000

  DriftCheck -->|Drift detected| SkipResult[Skip and log drift]
  DriftCheck -->|Relevant| ExtractFacts[Extract facts with URLs]

  style SkipResult fill:#2196F3,color:#fff
  style ExtractFacts fill:#2196F3,color:#fff

  SkipResult --> DriftEscalate{3+ consecutive drifts?}

  style DriftEscalate fill:#FF9800,color:#000

  DriftEscalate -->|Yes| ForceReformulate[Force query reformulation]
  DriftEscalate -->|No| FetchResults

  style ForceReformulate fill:#2196F3,color:#fff

  ForceReformulate --> FormQuery

  ExtractFacts --> UpdateState[Update thread state]

  style UpdateState fill:#2196F3,color:#fff

  UpdateState --> WriteMicro[Write micro-report]

  style WriteMicro fill:#2196F3,color:#fff

  WriteMicro --> PlateauCheck{Plateau detected?}

  style PlateauCheck fill:#FF9800,color:#000

  PlateauCheck -->|Level 1: URL overlap| Escape1[Reformulate query]
  PlateauCheck -->|Level 2: No new facts| Escape2[Advance strategy phase]
  PlateauCheck -->|Level 3: Both signals| StopPlateau[STOP: document gaps]
  PlateauCheck -->|No plateau| ConvergeCheck{Converged?}

  style Escape1 fill:#2196F3,color:#fff
  style Escape2 fill:#2196F3,color:#fff
  style StopPlateau fill:#f44336,color:#fff

  Escape1 --> ConvergeCheck
  Escape2 --> ConvergeCheck

  style ConvergeCheck fill:#f44336,color:#fff

  ConvergeCheck -->|All SQs answered + subjects covered| Complete[Write completion report]
  ConvergeCheck -->|Budget exhausted| Complete
  ConvergeCheck -->|Not converged| Scope

  style Complete fill:#2196F3,color:#fff

  StopPlateau --> Complete

  Complete --> End([End: Thread complete])

  style End fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
