<!-- diagram-meta: {"source": "commands/verify.md", "source_hash": "sha256:a6c09aa5fdeda80188cd2913db060488a84d7734d02dec8fc8365ea87c075404", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: verify

Run verification commands and confirm output before making success claims. Enforces evidence-before-assertions discipline: identify the proving command, run it fresh, read full output, then and only then state the claim with cited evidence.

```mermaid
flowchart TD
  Start([Start]) --> Identify[Identify claim\nto verify]
  Identify --> SelectCmd[Select proving command]
  SelectCmd --> RunCmd[Run command fresh]
  RunCmd --> ReadOutput[Read full output\ncheck exit code]
  ReadOutput --> Verified{Output confirms\nclaim?}
  Verified -- Yes --> CitedClaim[State claim with\ncited evidence]
  CitedClaim --> Done([Done])
  Verified -- No --> ActualStatus[State actual status\nwith evidence]
  ActualStatus --> Done

  RedFlags[/Red flag check/]
  RedFlags --> ShouldProb{"should/probably\ndetected?"}
  ShouldProb -- Yes --> STOP[STOP: Run command]
  STOP --> RunCmd
  ShouldProb -- No --> SatisfactionCheck{"Premature\nsatisfaction?"}
  SatisfactionCheck -- Yes --> STOP
  SatisfactionCheck -- No --> AgentTrust{"Trusting agent\nreport?"}
  AgentTrust -- Yes --> STOP
  AgentTrust -- No --> OK[Proceed]

  style Start fill:#4CAF50,color:#fff
  style Done fill:#4CAF50,color:#fff
  style Verified fill:#f44336,color:#fff
  style ShouldProb fill:#FF9800,color:#fff
  style SatisfactionCheck fill:#FF9800,color:#fff
  style AgentTrust fill:#FF9800,color:#fff
  style Identify fill:#2196F3,color:#fff
  style SelectCmd fill:#2196F3,color:#fff
  style RunCmd fill:#2196F3,color:#fff
  style ReadOutput fill:#2196F3,color:#fff
  style CitedClaim fill:#2196F3,color:#fff
  style ActualStatus fill:#2196F3,color:#fff
  style STOP fill:#f44336,color:#fff
  style OK fill:#2196F3,color:#fff
  style RedFlags fill:#FF9800,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
