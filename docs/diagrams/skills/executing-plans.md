<!-- diagram-meta: {"source": "skills/executing-plans/SKILL.md", "source_hash": "sha256:c47ff55dbb7818e78a21650abcdcc37ab44b57a8bc1355f1048e8369c10c730c", "generated_at": "2026-02-19T00:00:00Z", "generator": "generate_diagrams.py"} -->
# Diagram: executing-plans

Plan execution with two modes (batch and subagent), review loops, evidence requirements, and finishing workflow. Batch mode uses human-in-loop checkpoints; subagent mode uses automated two-stage review.

```mermaid
flowchart TD
    Start([Start: Plan document]) --> ModeSelect{"Select mode?\nbatch vs subagent"}:::decision

    %% ===== BATCH MODE =====
    ModeSelect -->|Batch| B1

    subgraph BatchMode [Batch Mode]
        B1["Load and review plan"]:::command --> B1_Concerns{"Concerns found?"}:::decision
        B1_Concerns -->|Yes| B1_Ask["AskUserQuestion:\nDiscuss / Proceed / Update"]:::command
        B1_Ask --> B1_Concerns
        B1_Concerns -->|No| B2

        B2["Execute batch\n(default 3 tasks)"]:::command --> B2_Task["Per task:\nimplement + verify"]:::command
        B2_Task --> B2_Evidence{"Evidence captured?"}:::gate
        B2_Evidence -->|No| B2_Task
        B2_Evidence -->|Yes| B3

        B3["Report batch results"]:::command --> B3_Feedback{"User feedback?"}:::decision
        B3_Feedback -->|Changes needed| B2
        B3_Feedback -->|Approved| B4_More{"More tasks?"}:::decision
        B4_More -->|Yes| B2
        B4_More -->|No| B_Complete
    end

    %% ===== SUBAGENT MODE =====
    ModeSelect -->|Subagent| S1

    subgraph SubagentMode [Subagent Mode]
        S1["Extract all tasks"]:::command --> S2

        S2["Dispatch implementer\nsubagent"]:::command --> S2_Q{"Implementer\nhas questions?"}:::decision
        S2_Q -->|Yes| S2_Answer["Answer questions"]:::command --> S2
        S2_Q -->|No| S3

        S3["Dispatch spec reviewer"]:::command --> S3_Gate{"Spec compliant?"}:::gate
        S3_Gate -->|Issues| S3_Fix["Implementer fixes"]:::command --> S3
        S3_Gate -->|Pass| S4

        S4["Dispatch quality reviewer"]:::command --> S4_Gate{"Quality approved?"}:::gate
        S4_Gate -->|Issues| S4_Fix["Implementer fixes"]:::command --> S4
        S4_Gate -->|"3+ cycles"| S4_Escalate["Escalate to user"]:::command --> S4
        S4_Gate -->|Pass| S5_More{"More tasks?"}:::decision
        S5_More -->|Yes| S2
        S5_More -->|No| S6

        S6["Dispatch final reviewer\n(entire implementation)"]:::command --> S_Complete
    end

    %% ===== SHARED COMPLETION =====
    B_Complete["Self-check:\nall evidence present?"]:::gate --> Finish
    S_Complete["Self-check:\nall evidence present?"]:::gate --> Finish

    Finish["finishing-a-development-branch\nskill"]:::skill --> Done([Done])

    %% ===== CIRCUIT BREAKERS =====
    B2_Task -.->|"3+ test failures"| CB_Stop([STOP: Circuit breaker]):::gate
    S2 -.->|"Blocker hit"| CB_Stop
    B1 -.->|"Critical gaps"| CB_Stop

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
| Mode selection (batch/subagent) | Mode Selection table (lines 44-48) |
| Load and review plan | Batch Phase 1 (lines 117-153) |
| Execute batch (3 tasks) | Batch Phase 2 (lines 155-163) |
| Report batch results | Batch Phase 3 (lines 165-169) |
| User feedback loop | Batch Phase 4 (lines 173-177) |
| Dispatch implementer subagent | Subagent Phase 2 step 1 (line 206) |
| Dispatch spec reviewer | Subagent Phase 2 step 4 (line 209) |
| Dispatch quality reviewer | Subagent Phase 2 step 5 (line 212) |
| 3+ review cycle escalation | Handling Review Issues (lines 268-271) |
| Dispatch final reviewer | Subagent Phase 3 (line 219) |
| finishing-a-development-branch | Phase 5 / Phase 4 completion (lines 189-191, 223-224) |
| Circuit breakers (3+ failures) | Autonomous Mode circuit breakers (lines 82-88) |
| Self-check evidence gate | Self-Check section (lines 283-293) |
