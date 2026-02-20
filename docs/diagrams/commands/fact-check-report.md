<!-- diagram-meta: {"source": "commands/fact-check-report.md", "source_hash": "sha256:f40e25dabf911ac18f0c0ec2c05cd564c186200e7d92f2241b74227b6ea6081c", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: fact-check-report

Generate a fact-checking report with traceable bibliography, actionable findings, optional clarity-mode glossary injection, and learning trajectory persistence for future sessions.

```mermaid
flowchart TD
  Start([Start: Verdicts complete]) --> BuildReport[Build report sections]

  style Start fill:#4CAF50,color:#fff
  style BuildReport fill:#2196F3,color:#fff

  BuildReport --> Header[Generate header/summary]
  BuildReport --> Findings[Group findings by category]
  BuildReport --> Biblio[Format bibliography]
  BuildReport --> ImplPlan[Create implementation plan]

  style Header fill:#2196F3,color:#fff
  style Findings fill:#2196F3,color:#fff
  style Biblio fill:#2196F3,color:#fff
  style ImplPlan fill:#2196F3,color:#fff

  Header --> BiblioGate{Every finding has citation?}
  Findings --> BiblioGate
  Biblio --> BiblioGate

  style BiblioGate fill:#f44336,color:#fff

  BiblioGate -->|No| FixCite[Add missing citations]
  BiblioGate -->|Yes| CheckClarity{Clarity mode enabled?}

  style FixCite fill:#2196F3,color:#fff
  style CheckClarity fill:#FF9800,color:#000

  FixCite --> BiblioGate

  CheckClarity -->|Yes| FilterConf{Confidence > 0.7?}
  CheckClarity -->|No| SaveReport[Save report to artifacts]

  style FilterConf fill:#FF9800,color:#000

  FilterConf -->|Yes| GenGloss[Generate glossary entries]
  FilterConf -->|No| SaveReport

  style GenGloss fill:#2196F3,color:#fff

  GenGloss --> GenFacts[Generate key facts]

  style GenFacts fill:#2196F3,color:#fff

  GenFacts --> FindTargets[Find config target files]

  style FindTargets fill:#2196F3,color:#fff

  FindTargets --> UpdateConfigs[Update CLAUDE.md / AGENTS.md]

  style UpdateConfigs fill:#2196F3,color:#fff

  UpdateConfigs --> SaveReport

  style SaveReport fill:#2196F3,color:#fff

  ImplPlan --> SaveReport

  SaveReport --> Learning[Store in ReasoningBank]

  style Learning fill:#4CAF50,color:#fff

  Learning --> StoreTrajectory[Store verification trajectories]

  style StoreTrajectory fill:#2196F3,color:#fff

  StoreTrajectory --> Applications[Depth prediction / Strategy selection]

  style Applications fill:#2196F3,color:#fff

  Applications --> End([End: Report saved])

  style End fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
