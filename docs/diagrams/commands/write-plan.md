<!-- diagram-meta: {"source": "commands/write-plan.md", "source_hash": "sha256:236da353413a691a48256711f04ada835ff1ea78d33416d9a059f8c948177ef8", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: write-plan

Transform requirements into an executable implementation plan with atomic, verifiable tasks. Invokes the writing-plans skill, stores output in the project artifacts directory.

```mermaid
flowchart TD
  Start([Start]) --> Analysis[Pre-plan analysis]
  Analysis --> HardReqs[Identify hard requirements\nvs nice-to-haves]
  HardReqs --> ExistingCode[Review existing code\nand patterns]
  ExistingCode --> Unknowns[Identify unknown\nunknowns]
  Unknowns --> CritPath[Determine critical path]
  CritPath --> InvokeSkill[/Invoke writing-plans skill/]
  InvokeSkill --> FollowWorkflow[Follow skill workflow]
  FollowWorkflow --> SelfCheck{Self-check\npasses?}
  SelfCheck -- No --> Revise[Revise plan]
  Revise --> SelfCheck
  SelfCheck -- Yes --> StorePlan[Store in artifacts dir]
  StorePlan --> Done([Done])

  subgraph SelfChecks [Self-Check Criteria]
    SC1[Each task fits\none session]
    SC2[Every task has\ndone criteria]
    SC3[Dependencies explicit\nand ordered]
    SC4[Unknowns identified\nas spike tasks]
  end

  SelfCheck -.-> SelfChecks

  style Start fill:#4CAF50,color:#fff
  style Done fill:#4CAF50,color:#fff
  style InvokeSkill fill:#4CAF50,color:#fff
  style SelfCheck fill:#f44336,color:#fff
  style Analysis fill:#2196F3,color:#fff
  style HardReqs fill:#2196F3,color:#fff
  style ExistingCode fill:#2196F3,color:#fff
  style Unknowns fill:#2196F3,color:#fff
  style CritPath fill:#2196F3,color:#fff
  style FollowWorkflow fill:#2196F3,color:#fff
  style Revise fill:#2196F3,color:#fff
  style StorePlan fill:#2196F3,color:#fff
  style SC1 fill:#fff,color:#333
  style SC2 fill:#fff,color:#333
  style SC3 fill:#fff,color:#333
  style SC4 fill:#fff,color:#333
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
