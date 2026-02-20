<!-- diagram-meta: {"source": "skills/assembling-context/SKILL.md", "source_hash": "sha256:405a2a98569f608ce23970b2ab0f2737121baa734ae7ccf62b9825cd3db8679a", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: assembling-context

Workflow for curating and assembling tiered context packages for subagents, handoffs, and other consumers. Budget-first approach with intelligent truncation.

```mermaid
flowchart TD
    Start([Start]) --> IdentifyPurpose[Identify Purpose]
    IdentifyPurpose --> PurposeType{Purpose Type?}
    PurposeType -->|Design| DesignSplit[Budget: 50/30/20]
    PurposeType -->|Implementation| ImplSplit[Budget: 60/25/15]
    PurposeType -->|Review| ReviewSplit[Budget: 55/30/15]
    PurposeType -->|Handoff| HandoffSplit[Budget: 70/20/10]
    PurposeType -->|Subagent| SubagentSplit[Budget: 65/25/10]
    DesignSplit --> CalcBudget[Calculate Token Budget]
    ImplSplit --> CalcBudget
    ReviewSplit --> CalcBudget
    HandoffSplit --> CalcBudget
    SubagentSplit --> CalcBudget
    CalcBudget --> SelectTier1[Select Tier 1: Essential]
    SelectTier1 --> Tier1Fits{Tier 1 Fits Budget?}
    Tier1Fits -->|No| BudgetError[STOP: Budget Too Small]
    Tier1Fits -->|Yes| SelectTier2[Select Tier 2: Supporting]
    SelectTier2 --> RoomForTier2{Room For Tier 2?}
    RoomForTier2 -->|Yes| SelectTier3[Select Tier 3: Reference]
    RoomForTier2 -->|No| SmartTruncate2[Smart Truncate Tier 2]
    SmartTruncate2 --> AssemblePackage[Assemble Context Package]
    SelectTier3 --> RoomForTier3{Room For Tier 3?}
    RoomForTier3 -->|Yes| AssemblePackage
    RoomForTier3 -->|No| SmartTruncate3[Smart Truncate Tier 3]
    SmartTruncate3 --> AssemblePackage
    AssemblePackage --> CreateReport[Create Truncation Report]
    CreateReport --> CrossSessionCheck{Cross-Session?}
    CrossSessionCheck -->|Yes| PersistDecisions[Persist Decisions Only]
    CrossSessionCheck -->|No| SelfCheck{Self-Check Passed?}
    PersistDecisions --> SelfCheck
    SelfCheck -->|Yes| End([End])
    SelfCheck -->|No| FixAssembly[Fix Assembly Issues]
    FixAssembly --> SelfCheck

    style Start fill:#4CAF50,color:#fff
    style End fill:#4CAF50,color:#fff
    style IdentifyPurpose fill:#2196F3,color:#fff
    style DesignSplit fill:#2196F3,color:#fff
    style ImplSplit fill:#2196F3,color:#fff
    style ReviewSplit fill:#2196F3,color:#fff
    style HandoffSplit fill:#2196F3,color:#fff
    style SubagentSplit fill:#2196F3,color:#fff
    style CalcBudget fill:#2196F3,color:#fff
    style SelectTier1 fill:#2196F3,color:#fff
    style SelectTier2 fill:#2196F3,color:#fff
    style SelectTier3 fill:#2196F3,color:#fff
    style SmartTruncate2 fill:#2196F3,color:#fff
    style SmartTruncate3 fill:#2196F3,color:#fff
    style AssemblePackage fill:#2196F3,color:#fff
    style CreateReport fill:#2196F3,color:#fff
    style PersistDecisions fill:#2196F3,color:#fff
    style FixAssembly fill:#2196F3,color:#fff
    style BudgetError fill:#f44336,color:#fff
    style PurposeType fill:#FF9800,color:#fff
    style Tier1Fits fill:#FF9800,color:#fff
    style RoomForTier2 fill:#FF9800,color:#fff
    style RoomForTier3 fill:#FF9800,color:#fff
    style CrossSessionCheck fill:#FF9800,color:#fff
    style SelfCheck fill:#f44336,color:#fff
```

## Legend

| Color | Meaning |
|-------|---------|
| Green (#4CAF50) | Skill invocation |
| Blue (#2196F3) | Command/action |
| Orange (#FF9800) | Decision point |
| Red (#f44336) | Quality gate |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Identify Purpose | Inputs: purpose (design, implementation, review, handoff, subagent) |
| Purpose Type? | Purpose-Specific Packages table |
| Budget splits | Purpose-Specific Packages: Budget Split column |
| Calculate Token Budget | Token Budget section: tokens = chars / 4 |
| Select Tier 1: Essential | Context Tiers: Tier 1, 40-60% budget |
| Tier 1 Fits Budget? | CRITICAL: Never remove Tier 1 |
| Select Tier 2: Supporting | Context Tiers: Tier 2, 20-35% budget |
| Select Tier 3: Reference | Context Tiers: Tier 3, 10-20% budget |
| Smart Truncate | Token Budget: Smart Truncation |
| Assemble Context Package | Outputs: context_package |
| Create Truncation Report | Outputs: truncation_report |
| Cross-Session? | Cross-Session Context section |
| Persist Decisions Only | Cross-Session Context: Persist vs Regenerate vs Discard |
| Self-Check Passed? | Self-Check checklist |
