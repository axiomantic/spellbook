<!-- diagram-meta: {"source": "commands/write-skill-test.md", "source_hash": "sha256:4acb9df69531cb26d7d79c5b169b614acd6edc7eb8d4927b1cb4b293551be036", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: write-skill-test

RED-GREEN-REFACTOR implementation for skill testing. Establishes baseline agent behavior without the skill (RED), writes a minimal skill addressing observed failures (GREEN), then closes loopholes by adding counters for new rationalizations (REFACTOR).

```mermaid
flowchart TD
  Start([Start]) --> RED[RED Phase]
  RED --> DesignScenarios[Design 3+ pressure\nscenarios]
  DesignScenarios --> SpawnBaseline[Spawn subagents\nWITHOUT skill]
  SpawnBaseline --> DocVerbatim[Document verbatim\nrationalizations]
  DocVerbatim --> IdentifyPatterns[Identify patterns\nacross runs]
  IdentifyPatterns --> SaveBaseline[Save baseline docs]
  SaveBaseline --> GREEN[GREEN Phase]
  GREEN --> CreateSkill[Create SKILL.md\nfrom schema]
  CreateSkill --> AddressFailures[Address specific\nbaseline failures]
  AddressFailures --> SchemaCheck{Schema\ncompliant?}
  SchemaCheck -- No --> FixSchema[Fix schema issues]
  FixSchema --> SchemaCheck
  SchemaCheck -- Yes --> RerunScenarios[Rerun scenarios\nWITH skill]
  RerunScenarios --> AgentComplies{Agent\ncomplies?}
  AgentComplies -- No --> ReviseSkill[Revise skill]
  ReviseSkill --> RerunScenarios
  AgentComplies -- Yes --> REFACTOR[REFACTOR Phase]
  REFACTOR --> ReviewResults[Review GREEN results\nfor new rationalizations]
  ReviewResults --> NewRats{New\nrationalizations?}
  NewRats -- Yes --> AddCounters[Add explicit counters]
  AddCounters --> BuildTable[Build rationalization\ntable]
  BuildTable --> CreateRedFlags[Create red flags list]
  CreateRedFlags --> ReTest[Re-test all scenarios]
  ReTest --> NewRats
  NewRats -- No --> QualityChecks{Quality checks\npass?}
  QualityChecks -- No --> FixQuality[Fix quality issues]
  FixQuality --> QualityChecks
  QualityChecks -- Yes --> Deploy[Deploy: commit + push]
  Deploy --> Done([Done])

  style Start fill:#4CAF50,color:#fff
  style Done fill:#4CAF50,color:#fff
  style RED fill:#f44336,color:#fff
  style GREEN fill:#4CAF50,color:#fff
  style REFACTOR fill:#2196F3,color:#fff
  style SchemaCheck fill:#f44336,color:#fff
  style AgentComplies fill:#f44336,color:#fff
  style NewRats fill:#FF9800,color:#fff
  style QualityChecks fill:#f44336,color:#fff
  style DesignScenarios fill:#2196F3,color:#fff
  style SpawnBaseline fill:#2196F3,color:#fff
  style DocVerbatim fill:#2196F3,color:#fff
  style IdentifyPatterns fill:#2196F3,color:#fff
  style SaveBaseline fill:#2196F3,color:#fff
  style CreateSkill fill:#2196F3,color:#fff
  style AddressFailures fill:#2196F3,color:#fff
  style FixSchema fill:#2196F3,color:#fff
  style RerunScenarios fill:#2196F3,color:#fff
  style ReviseSkill fill:#2196F3,color:#fff
  style ReviewResults fill:#2196F3,color:#fff
  style AddCounters fill:#2196F3,color:#fff
  style BuildTable fill:#2196F3,color:#fff
  style CreateRedFlags fill:#2196F3,color:#fff
  style ReTest fill:#2196F3,color:#fff
  style FixQuality fill:#2196F3,color:#fff
  style Deploy fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
