<!-- diagram-meta: {"source": "commands/audit-green-mirage.md", "source_hash": "sha256:072111a5bcefa4bf14f8afad6fdadf97e0ac499b4945e3016341bc8beab97c60", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: audit-green-mirage

Audit test suites for Green Mirage anti-patterns: tests that pass but do not verify behavior.

```mermaid
flowchart TD
    Start([Start]) --> InvokeSkill[/audit-green-mirage skill/]
    InvokeSkill --> Discover[Discover Test Files]
    Discover --> TracePaths[Trace Assertion Paths]
    TracePaths --> Analyze{Anti-Patterns Found?}
    Analyze -->|Yes| Identify[Identify Anti-Patterns]
    Analyze -->|No| Clean[Suite Is Clean]
    Identify --> WeakAssert[Weak Assertions]
    Identify --> MockNoVerify[Mocks Without Verify]
    Identify --> CoverNoVerify[Coverage No Verification]
    Identify --> HappyOnly[Happy-Path Only]
    Identify --> DeleteSurvive[Survives Code Deletion]
    WeakAssert --> Generate[Generate Findings]
    MockNoVerify --> Generate
    CoverNoVerify --> Generate
    HappyOnly --> Generate
    DeleteSurvive --> Generate
    Generate --> Verify{Findings Actionable?}
    Verify -->|Yes| Report[Report with Fixes]
    Verify -->|No| Refine[Refine Findings]
    Refine --> Generate
    Report --> QualityGate{Evidence Gate}
    QualityGate -->|Paths Traced| Done([End])
    QualityGate -->|No Evidence| TracePaths
    Clean --> Done

    style Start fill:#4CAF50,color:#fff
    style Done fill:#4CAF50,color:#fff
    style InvokeSkill fill:#4CAF50,color:#fff
    style Analyze fill:#FF9800,color:#fff
    style Verify fill:#FF9800,color:#fff
    style QualityGate fill:#f44336,color:#fff
    style Discover fill:#2196F3,color:#fff
    style TracePaths fill:#2196F3,color:#fff
    style Identify fill:#2196F3,color:#fff
    style Generate fill:#2196F3,color:#fff
    style Report fill:#2196F3,color:#fff
    style WeakAssert fill:#2196F3,color:#fff
    style MockNoVerify fill:#2196F3,color:#fff
    style CoverNoVerify fill:#2196F3,color:#fff
    style HappyOnly fill:#2196F3,color:#fff
    style DeleteSurvive fill:#2196F3,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |
