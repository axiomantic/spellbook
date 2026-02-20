<!-- diagram-meta: {"source": "skills/deep-research/SKILL.md", "source_hash": "sha256:15093b3794f8fce9fce4f00af1012ea21b881f5d6a478878e8bcfdcde915013e", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: deep-research

Multi-threaded research workflow with parallel investigation, fact-checking, and verified synthesis. Phases: Interview, Plan, Investigate (parallel), Verify, Synthesize.

```mermaid
flowchart TD
    Start([Start]) --> P0

    subgraph Phase0 [Phase 0: Interview]
        P0["/deep-research-interview"]:::command --> P0_Gate{"Subjects registered?\nCriteria defined?"}:::decision
    end

    P0_Gate -->|No| P0_Fail([STOP: No scope]):::gate
    P0_Gate -->|Yes| P1

    subgraph Phase1 [Phase 1: Plan]
        P1["/deep-research-plan"]:::command --> P1_Gate{"Threads independent?\nAll subjects assigned?"}:::decision
    end

    P1_Gate -->|No| P1_Fix["Fix thread definitions"]:::command --> P1
    P1_Gate -->|Yes| P2

    subgraph Phase2 [Phase 2: Investigate]
        P2["Dispatch parallel subagents"]:::command --> P2_Thread1["/deep-research-investigate\n(Thread 1)"]:::command
        P2 --> P2_Thread2["/deep-research-investigate\n(Thread 2)"]:::command
        P2 --> P2_ThreadN["/deep-research-investigate\n(Thread N)"]:::command
        P2_Thread1 --> P2_Plateau{"URL overlap >= 60%?\nStale rounds?"}:::decision
        P2_Thread2 --> P2_Plateau
        P2_ThreadN --> P2_Plateau
    end

    P2_Plateau -->|"L1: Reformulate"| P2
    P2_Plateau -->|"L2: Change sources"| P2
    P2_Plateau -->|"L3: 3 stale"| P2_StopPartial["Report partial findings"]:::gate
    P2_Plateau -->|No plateau| P2_Gate{"All threads complete?\nAll subjects covered?"}:::decision

    P2_Gate -->|No| P2
    P2_Gate -->|Yes| P3

    subgraph Phase3 [Phase 3: Verify]
        P3["fact-checking skill"]:::skill --> P3_Dehalluc["dehallucination skill"]:::skill
        P3_Dehalluc --> P3_Gate{"Claims verified?\nNo REFUTED as fact?"}:::decision
    end

    P3_Gate -->|">50% REFUTED"| P1
    P3_Gate -->|Issues| P3_Fix["Fix claim verdicts"]:::command --> P3_Dehalluc
    P3_Gate -->|Pass| P4

    subgraph Phase4 [Phase 4: Synthesize]
        P4["Assemble report"]:::command --> P4_Complete{"Completeness check\nvs success criteria"}:::decision
    end

    P4_Complete -->|">30% gaps"| P2
    P4_Complete -->|Pass| P4_Bib["Build bibliography"]:::command --> P4_Gate{"All subjects in report?\nBibliography complete?"}:::gate

    P4_Gate --> Done([Done: Research report])

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
| /deep-research-interview | Phase 0 (line 63) |
| /deep-research-plan | Phase 1 (line 69) |
| /deep-research-investigate | Phase 2 parallel subagents (lines 77-83) |
| Plateau breaker (L1/L2/L3) | Plateau Breaker registry (line 47) |
| fact-checking skill | Phase 3 verification (line 89) |
| dehallucination skill | Phase 3 verification (line 89) |
| Completeness check | Phase 4 completeness check (line 104) |
| >50% REFUTED circuit breaker | Circuit Breakers table (line 113) |
| >30% gaps loop | Circuit Breakers table (line 115) |
| Subject registry enforcement | Registries section (line 41) |
