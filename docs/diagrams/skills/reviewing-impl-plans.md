<!-- diagram-meta: {"source": "skills/reviewing-impl-plans/SKILL.md", "source_hash": "sha256:787ae767b7192af1a899f9b9eff284d44752edcd1c413b69c28c5079b05ef83d", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: reviewing-impl-plans

Reviews implementation plans before execution, auditing interface contracts between parallel work streams, verifying behavior references against source code, and checking completeness. Dispatches subagents for each phase and assembles a prioritized remediation report.

```mermaid
flowchart TD
    Start([Start: Receive Plan]) --> P1

    P1["/review-plan-inventory"]:::command --> G1{Inventory Complete?}:::decision
    G1 -->|No| P1
    G1 -->|Yes| P2

    P2["/review-plan-contracts"]:::command --> SharpenCheck{Ambiguous Language?}:::decision
    SharpenCheck -->|Yes| Sharpen["/sharpen-audit"]:::skill
    Sharpen --> G2
    SharpenCheck -->|No| G2
    G2{All Interfaces Audited?}:::gate
    G2 -->|No| P2
    G2 -->|Yes| P3

    P3["/review-plan-behavior"]:::command --> G3{All Refs Classified?}:::gate
    G3 -->|No| P3
    G3 -->|Yes| P45

    P45["/review-plan-completeness"]:::command --> FactCheck{Claims Need Checking?}:::decision
    FactCheck -->|Yes| FC["fact-checking skill"]:::skill
    FC --> G4
    FactCheck -->|No| G4
    G4{Completeness Audit Done?}:::gate
    G4 -->|No| P45
    G4 -->|Yes| Report

    Report[Assemble Final Report]:::command --> Reflect{Self-Check Passes?}:::gate
    Reflect -->|No, gaps found| FixGaps[Revise and Re-audit]:::command
    FixGaps --> Reflect
    Reflect -->|Yes| Final([Report Delivered])

    classDef skill fill:#4CAF50,color:#fff
    classDef command fill:#2196F3,color:#fff
    classDef decision fill:#FF9800,color:#fff
    classDef gate fill:#f44336,color:#fff
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
| /review-plan-inventory | Phase 1: Context and Inventory (line 48) |
| /review-plan-contracts | Phase 2: Interface Contract Audit (line 56) |
| /sharpen-audit | Phase 2 optional deep audit (line 60) |
| /review-plan-behavior | Phase 3: Behavior Verification Audit (line 66) |
| /review-plan-completeness | Phase 4-5: Completeness Checks and Escalation (line 74) |
| fact-checking skill | Phase 4-5 escalation for claims (line 76) |
| Assemble Final Report | Report Assembly (line 82) |
| Self-Check Passes? | Reflection checklist (lines 159-186) |
