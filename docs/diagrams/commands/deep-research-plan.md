<!-- diagram-meta: {"source": "commands/deep-research-plan.md", "source_hash": "sha256:15759e4cb96797d42744fe35ae69f0a5216f4916447db1fd257f1834017e66e3", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: deep-research-plan

Decompose a Research Brief into independent parallel threads with source strategies, round budgets, convergence criteria, and risk assessment. Planning only, no searching.

```mermaid
flowchart TD
  Start([Start: Research Brief]) --> PreReq{Brief prerequisites met?}

  style Start fill:#4CAF50,color:#fff
  style PreReq fill:#f44336,color:#fff

  PreReq -->|No| BackToInterview[Return to Phase 0]
  PreReq -->|Yes| ReadBrief[Read Research Brief]

  style BackToInterview fill:#4CAF50,color:#fff
  style ReadBrief fill:#2196F3,color:#fff

  ReadBrief --> Decompose[Decompose into threads]

  style Decompose fill:#2196F3,color:#fff

  Decompose --> AssignSQ[Assign sub-questions]
  Decompose --> AssignSubj[Assign subjects]

  style AssignSQ fill:#2196F3,color:#fff
  style AssignSubj fill:#2196F3,color:#fff

  AssignSQ --> IndepCheck{Threads independent?}
  AssignSubj --> IndepCheck

  style IndepCheck fill:#f44336,color:#fff

  IndepCheck -->|No source collision| ChkInputDep{No input dependency?}
  IndepCheck -->|Collision| MergeThreads[Merge dependent threads]

  style ChkInputDep fill:#f44336,color:#fff
  style MergeThreads fill:#2196F3,color:#fff

  MergeThreads --> IndepCheck

  ChkInputDep -->|Dependency found| MergeThreads
  ChkInputDep -->|Independent| AssignSrcStrategy[Assign source strategies]

  style AssignSrcStrategy fill:#2196F3,color:#fff

  AssignSrcStrategy --> PhSurvey[SURVEY phase]
  AssignSrcStrategy --> PhExtract[EXTRACT phase]
  AssignSrcStrategy --> PhDiversify[DIVERSIFY phase]
  AssignSrcStrategy --> PhVerify[VERIFY phase]

  style PhSurvey fill:#2196F3,color:#fff
  style PhExtract fill:#2196F3,color:#fff
  style PhDiversify fill:#2196F3,color:#fff
  style PhVerify fill:#2196F3,color:#fff

  PhSurvey --> CalcBudget[Calculate round budgets]
  PhExtract --> CalcBudget
  PhDiversify --> CalcBudget
  PhVerify --> CalcBudget

  style CalcBudget fill:#2196F3,color:#fff

  CalcBudget --> BudgetCheck{Total <= 30 rounds?}

  style BudgetCheck fill:#FF9800,color:#000

  BudgetCheck -->|No| ReduceRounds[Reduce DIVERSIFY first]
  BudgetCheck -->|Yes| DefConverge[Define convergence criteria]

  style ReduceRounds fill:#2196F3,color:#fff

  ReduceRounds --> BudgetCheck

  style DefConverge fill:#2196F3,color:#fff

  DefConverge --> PerThread[Per-thread criteria]
  DefConverge --> CrossThread[Cross-thread criteria]

  style PerThread fill:#2196F3,color:#fff
  style CrossThread fill:#2196F3,color:#fff

  PerThread --> RiskAssess[Risk assessment]
  CrossThread --> RiskAssess

  style RiskAssess fill:#2196F3,color:#fff

  RiskAssess --> WritePlan[Write Research Plan]

  style WritePlan fill:#2196F3,color:#fff

  WritePlan --> PlanGate{Quality gate}

  style PlanGate fill:#f44336,color:#fff

  PlanGate -->|All SQs assigned?| CovGate{All subjects covered?}
  PlanGate -->|Fail| FixPlan[Fix plan gaps]

  style FixPlan fill:#2196F3,color:#fff

  FixPlan --> PlanGate

  style CovGate fill:#f44336,color:#fff

  CovGate -->|No| FixPlan
  CovGate -->|Yes| SavePlan[Save plan artifact]

  style SavePlan fill:#2196F3,color:#fff

  SavePlan --> UserReview{User approves plan?}

  style UserReview fill:#FF9800,color:#000

  UserReview -->|No| FixPlan
  UserReview -->|Yes| End([End: Phase 1 complete])

  style End fill:#4CAF50,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
