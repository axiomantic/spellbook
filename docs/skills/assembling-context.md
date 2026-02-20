# assembling-context

Use when preparing context for subagents or managing token budgets. Triggers: "prepare context for", "assemble context", "what context does X need", "token budget", "context package", or automatically invoked by implementing-features Phase 3.5 (work packets) and Phase 4.2 (parallel subagents).

## Workflow Diagram

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

## Skill Content

``````````markdown
# Context Assembly

<ROLE>
Context Curator. Deliver precisely the right information at the right time. Too little causes failures. Too much burns tokens and buries signal. Every token must earn its place.
</ROLE>

## Invariant Principles

1. **Tier 1 Never Truncates**: Essential context survives any budget pressure
2. **Budget Before Assembly**: Calculate budget FIRST, then select
3. **Purpose Drives Selection**: Design ≠ implementation ≠ review context
4. **Recency Over Completeness**: Recent feedback > historical context
5. **Summarize, Don't Truncate**: Intelligent summarization preserves signal
6. **Integration Points are Tier 1**: Interface contracts are essential

## Inputs / Outputs

| Input | Required | Description |
|-------|----------|-------------|
| `purpose` | Yes | `design`, `implementation`, `review`, `handoff`, `subagent` |
| `token_budget` | Yes | Maximum tokens available |
| `source_context` | Yes | Raw context to select from |

| Output | Type | Description |
|--------|------|-------------|
| `context_package` | Structured | Tiered context ready for injection |
| `truncation_report` | Inline | What was excluded and why |

---

## Context Tiers

<CRITICAL>Over budget: remove Tier 3 first, then Tier 2. Never remove Tier 1.</CRITICAL>

| Tier | Budget | Content | Examples |
|------|--------|---------|----------|
| **1: Essential** | 40-60% | Active instructions, user decisions, current artifact, interface contracts, blocking issues | Task spec, APIs, unresolved feedback |
| **2: Supporting** | 20-35% | Recent learnings, patterns, prior feedback, success criteria | Last 2-3 iterations, codebase patterns |
| **3: Reference** | 10-20% | Historical context, rejected alternatives, verbose docs | Early iterations, full docs (summarize instead) |

---

## Purpose-Specific Packages

| Purpose | Tier 1 Focus | Budget Split | Use With |
|---------|--------------|--------------|----------|
| **Design** | Requirements, decisions, constraints, integration points | 50/30/20 | brainstorming, writing-plans |
| **Implementation** | Task spec, acceptance criteria, interfaces, test expectations | 60/25/15 | test-driven-development, executing-plans |
| **Review** | Code diff, requirements traced, test results | 55/30/15 | code-review, fact-checking |
| **Handoff** | Current position, pending work, active decisions, blocking issues | 70/20/10 | session boundaries, compaction |
| **Subagent** | Task, constraints, expected output format | 65/25/10 | dispatching-parallel-agents |

---

## Token Budget

**Estimation:** `tokens ≈ chars / 4` (conservative)

**Available budget:** `context_window - system_prompt - response_reserve - tool_overhead`
Example: `200000 - 8000 - 4000 - 2000 = 186000`

**Smart Truncation:** Never blind `head`/`tail`. Preserve structure: keep intro (30%) + conclusion (20%), mark omitted middle.

---

## Cross-Session Context

| Action | Items |
|--------|-------|
| **Persist** | User decisions, validated assumptions, glossary, blocking issues |
| **Regenerate** | File contents, test results, code patterns (may have changed) |
| **Discard** | Exploration paths, rejected alternatives, verbose logs |

**Handoff format:** Position → Pending work → Active decisions → Key learnings → Verification commands

---

## Reasoning Schema

<analysis>
Before assembling: PURPOSE? TOKEN BUDGET? TIER 1 for this purpose? RECIPIENT?
</analysis>

<reflection>
After assembling: Tier 1 fits? Essential excluded? Room for Tier 2? Truncation report accurate?
</reflection>

---

<FORBIDDEN>
- Assembling without calculating budget first
- Blind truncation (`head`, `tail -n`, arbitrary limits)
- Truncating Tier 1 to fit budget
- Same package for different purposes
- Omitting integration points
- Including exploration paths in handoff
- Persisting raw command output across sessions
</FORBIDDEN>

## Self-Check

- [ ] Calculated token budget explicitly
- [ ] Identified Tier 1 for this purpose
- [ ] Tier 1 fits within budget
- [ ] Smart truncation applied (not blind)
- [ ] Integration points included
- [ ] Truncation report created

<FINAL_EMPHASIS>
Context assembly is invisible infrastructure. Calculate budget. Prioritize by tier. Truncate intelligently. Every token earns its place.
</FINAL_EMPHASIS>
``````````
