<!-- diagram-meta: {"source": "skills/executing-plans/SKILL.md","source_hash": "sha256:9c374295667df1c687cf9741fe84f1c54b86b7dafd8a508b5dcfcb953c6af436","generator": "stamp"} -->
# Executing Plans - Skill Diagrams

## Overview Diagram

High-level flow showing mode selection, two execution paths, and shared completion gate.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"Subagent Dispatch"/]
        L5{{Quality Gate}}
    end

    START([Plan Document Received]) --> ANNOUNCE["Announce:<br>Using executing-plans skill"]
    ANNOUNCE --> MODE_CHECK{Mode selection:<br>batch vs subagent}

    MODE_CHECK -->|"batch (default)"| BATCH_P1["Batch Phase 1:<br>Load and Review Plan"]
    MODE_CHECK -->|subagent| SUB_P1["Subagent Phase 1:<br>Extract Tasks"]

    BATCH_P1 --> BATCH_P2["Batch Phase 2:<br>Execute Batch"]
    BATCH_P2 --> BATCH_P3["Batch Phase 3:<br>Report"]
    BATCH_P3 --> BATCH_P4["Batch Phase 4:<br>Continue"]
    BATCH_P4 -->|More tasks| BATCH_P2
    BATCH_P4 -->|All tasks done| BATCH_P5["Batch Phase 5:<br>Complete Development"]

    SUB_P1 --> SUB_P2["Subagent Phase 2:<br>Per-Task Execution Loop"]
    SUB_P2 -->|More tasks| SUB_P2
    SUB_P2 -->|All tasks done| SUB_P3["Subagent Phase 3:<br>Final Review"]
    SUB_P3 --> SUB_P4["Subagent Phase 4:<br>Complete Development"]

    BATCH_P5 --> SELFCHECK{{Self-Check Gate}}
    SUB_P4 --> SELFCHECK

    SELFCHECK -->|All checked| FINISH(["Invoke finishing-a-development-branch"])
    SELFCHECK -->|Unchecked items| FIX["Stop and fix"] --> SELFCHECK

    BATCH_P2 -.->|"Stop condition"| CB_STOP([STOP: Circuit breaker])
    SUB_P2 -.->|"Stop condition"| CB_STOP
    BATCH_P1 -.->|"Critical plan gap"| CB_STOP

    style L4 fill:#4a9eff,color:#fff
    style L5 fill:#ff6b6b,color:#fff
    style FINISH fill:#51cf66,color:#fff
    style SELFCHECK fill:#ff6b6b,color:#fff
    style CB_STOP fill:#ff6b6b,color:#fff
```

### Cross-Reference Table

| Overview Node | Detail Diagram |
|---|---|
| Batch Phase 1: Load and Review Plan | [Batch Mode Detail](#batch-mode-detail) |
| Batch Phase 2: Execute Batch | [Batch Mode Detail](#batch-mode-detail) |
| Batch Phase 3: Report | [Batch Mode Detail](#batch-mode-detail) |
| Batch Phase 4: Continue | [Batch Mode Detail](#batch-mode-detail) |
| Batch Phase 5: Complete Development | [Batch Mode Detail](#batch-mode-detail) |
| Subagent Phase 1: Extract Tasks | [Subagent Mode Detail](#subagent-mode-detail) |
| Subagent Phase 2: Per-Task Execution Loop | [Subagent Mode Detail](#subagent-mode-detail) |
| Subagent Phase 3: Final Review | [Subagent Mode Detail](#subagent-mode-detail) |
| Subagent Phase 4: Complete Development | [Subagent Mode Detail](#subagent-mode-detail) |
| Self-Check Gate | [Self-Check Gate Detail](#self-check-gate-detail) |
| STOP: Circuit breaker | [Stop Conditions and Circuit Breakers](#stop-conditions-and-circuit-breakers) |

---

## Batch Mode Detail

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L5{{Quality Gate}}
    end

    subgraph "Phase 1: Load and Review Plan"
        B1_READ["Read plan file"]
        B1_REVIEW["Review critically:<br>identify questions/concerns"]
        B1_CONCERNS{Concerns found?}
        B1_ASK["AskUserQuestion:<br>Discuss / Proceed / Update plan"]
        B1_RESPONSE{User response}
        B1_TODO["Create TodoWrite<br>with plan tasks"]

        B1_READ --> B1_REVIEW --> B1_CONCERNS
        B1_CONCERNS -->|Yes| B1_ASK --> B1_RESPONSE
        B1_CONCERNS -->|No| B1_TODO
        B1_RESPONSE -->|Discuss| B1_ASK
        B1_RESPONSE -->|Update plan| B1_READ
        B1_RESPONSE -->|Proceed| B1_TODO
    end

    subgraph "Phase 2: Execute Batch"
        B2_SELECT["Select next batch<br>(default 3 tasks)"]
        B2_MARK_IP["Mark task as in_progress"]
        B2_EXECUTE["Follow each step exactly"]
        B2_VERIFY["Run verifications as specified"]
        B2_EVIDENCE{Verification passed?}
        B2_MARK_DONE["Mark task completed<br>with evidence"]
        B2_MORE_IN_BATCH{More tasks<br>in batch?}
        B2_STOP["STOP: Hit blocker<br>Ask for clarification"]

        B2_SELECT --> B2_MARK_IP --> B2_EXECUTE --> B2_VERIFY
        B2_VERIFY --> B2_EVIDENCE
        B2_EVIDENCE -->|Yes| B2_MARK_DONE --> B2_MORE_IN_BATCH
        B2_EVIDENCE -->|No| B2_STOP
        B2_STOP -->|"Clarification received"| B2_EXECUTE
        B2_MORE_IN_BATCH -->|Yes| B2_MARK_IP
        B2_MORE_IN_BATCH -->|No| B3_REPORT
    end

    subgraph "Phase 3: Report"
        B3_REPORT["Show what was implemented"]
        B3_SHOW["Show verification output"]
        B3_READY["Say: Ready for feedback"]

        B3_REPORT --> B3_SHOW --> B3_READY
    end

    subgraph "Phase 4: Continue"
        B4_FEEDBACK{User feedback}
        B4_APPLY["Apply requested changes"]
        B4_MORE{More tasks<br>in plan?}

        B4_FEEDBACK -->|Changes needed| B4_APPLY --> B2_SELECT
        B4_FEEDBACK -->|Approved| B4_MORE
        B4_MORE -->|Yes| B2_SELECT
        B4_MORE -->|No| B5_REFLECT
    end

    subgraph "Phase 5: Complete Development"
        B5_REFLECT{{"Reflection gate:<br>Evidence for all tasks?<br>No unapproved deviations?"}}
        B5_FIX["STOP and fix"]
        B5_FINISH(["Invoke finishing-a-development-branch"])

        B5_REFLECT -->|Issues found| B5_FIX --> B5_REFLECT
        B5_REFLECT -->|All clean| B5_FINISH
    end

    B1_TODO --> B2_SELECT
    B3_READY --> B4_FEEDBACK

    style L5 fill:#ff6b6b,color:#fff
    style B5_REFLECT fill:#ff6b6b,color:#fff
    style B5_FINISH fill:#51cf66,color:#fff
    style B2_STOP fill:#ff6b6b,color:#fff
```

---

## Subagent Mode Detail

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"Subagent Dispatch"/]
        L5{{Quality Gate}}
    end

    subgraph "Phase 1: Extract Tasks"
        S1_READ["Read plan once"]
        S1_EXTRACT["Extract all tasks<br>with full text and context"]
        S1_TODO["Create TodoWrite"]

        S1_READ --> S1_EXTRACT --> S1_TODO
    end

    subgraph "Phase 2: Per-Task Execution Loop"
        S2_NEXT["Select next task"]
        S2_IMPL[/"Dispatch implementer subagent<br>(implementer-prompt.md)"/]
        S2_QUESTIONS{Implementer<br>has questions?}
        S2_SCOPE{Affects scope?}
        S2_ANSWER["Answer clearly<br>and completely"]
        S2_ASK_USER["AskUserQuestion:<br>Include / Exclude / Defer"]
        S2_IMPL_DONE["Implementer: implement,<br>test, commit, self-review"]

        S2_SPEC[/"Dispatch spec reviewer<br>(spec-reviewer-prompt.md)"/]
        S2_SPEC_PASS{{Spec compliant?}}
        S2_SPEC_FIX[/"Dispatch fix subagent<br>with failure context"/]
        S2_SPEC_CYCLES{3+ review<br>cycles?}
        S2_ESCALATE["Escalate to user"]

        S2_QUALITY[/"Dispatch code quality reviewer<br>(code-quality-reviewer-prompt.md)"/]
        S2_QUAL_PASS{{Quality approved?}}
        S2_QUAL_FIX[/"Dispatch fix subagent<br>with failure context"/]
        S2_QUAL_CYCLES{3+ review<br>cycles?}
        S2_QUAL_ESCALATE["Escalate to user"]

        S2_MARK["Mark task complete<br>in TodoWrite"]
        S2_MORE{More tasks?}

        S2_NEXT --> S2_IMPL
        S2_IMPL --> S2_QUESTIONS
        S2_QUESTIONS -->|Yes| S2_SCOPE
        S2_QUESTIONS -->|No| S2_IMPL_DONE
        S2_SCOPE -->|Yes| S2_ASK_USER --> S2_IMPL_DONE
        S2_SCOPE -->|No| S2_ANSWER --> S2_IMPL_DONE

        S2_IMPL_DONE --> S2_SPEC
        S2_SPEC --> S2_SPEC_PASS
        S2_SPEC_PASS -->|Pass| S2_QUALITY
        S2_SPEC_PASS -->|Issues| S2_SPEC_CYCLES
        S2_SPEC_CYCLES -->|No| S2_SPEC_FIX --> S2_SPEC
        S2_SPEC_CYCLES -->|Yes| S2_ESCALATE --> S2_SPEC_FIX

        S2_QUALITY --> S2_QUAL_PASS
        S2_QUAL_PASS -->|Pass| S2_MARK
        S2_QUAL_PASS -->|Issues| S2_QUAL_CYCLES
        S2_QUAL_CYCLES -->|No| S2_QUAL_FIX --> S2_QUALITY
        S2_QUAL_CYCLES -->|Yes| S2_QUAL_ESCALATE --> S2_QUAL_FIX

        S2_MARK --> S2_MORE
        S2_MORE -->|Yes| S2_NEXT
    end

    subgraph "Phase 3: Final Review"
        S3_REVIEW[/"Dispatch final code reviewer<br>for entire implementation"/]
        S3_PASS{{Approved?}}
        S3_FIX[/"Dispatch fix subagent"/]

        S3_REVIEW --> S3_PASS
        S3_PASS -->|Issues| S3_FIX --> S3_REVIEW
        S3_PASS -->|Pass| S4_FINISH
    end

    subgraph "Phase 4: Complete Development"
        S4_FINISH(["Invoke finishing-a-development-branch"])
    end

    S1_TODO --> S2_NEXT
    S2_MORE -->|No| S3_REVIEW

    style L4 fill:#4a9eff,color:#fff
    style L5 fill:#ff6b6b,color:#fff
    style S2_IMPL fill:#4a9eff,color:#fff
    style S2_SPEC fill:#4a9eff,color:#fff
    style S2_QUALITY fill:#4a9eff,color:#fff
    style S2_SPEC_FIX fill:#4a9eff,color:#fff
    style S2_QUAL_FIX fill:#4a9eff,color:#fff
    style S3_REVIEW fill:#4a9eff,color:#fff
    style S3_FIX fill:#4a9eff,color:#fff
    style S4_FINISH fill:#51cf66,color:#fff
    style S2_SPEC_PASS fill:#ff6b6b,color:#fff
    style S2_QUAL_PASS fill:#ff6b6b,color:#fff
    style S3_PASS fill:#ff6b6b,color:#fff
```

---

## Self-Check Gate Detail

Five sequential gates that must all pass before declaring execution complete.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L3([Terminal])
        L5{{Quality Gate}}
    end

    ENTER([Enter Self-Check]) --> C1{{"Every task has<br>verification output?"}}
    C1 -->|No| FIX1["STOP: Collect missing evidence"]
    FIX1 --> C1
    C1 -->|Yes| C2{{"No tasks marked complete<br>without evidence?"}}
    C2 -->|No| FIX2["STOP: Fix false completions"]
    FIX2 --> C2
    C2 -->|Yes| C3{{"All review issues<br>addressed?"}}
    C3 -->|No| FIX3["STOP: Address open reviews"]
    FIX3 --> C3
    C3 -->|Yes| C4{{"Plan followed exactly or<br>deviations approved?"}}
    C4 -->|No| FIX4["STOP: Reconcile deviations"]
    FIX4 --> C4
    C4 -->|Yes| C5{{"finishing-a-development-branch<br>invoked?"}}
    C5 -->|No| FIX5["Invoke skill now"]
    FIX5 --> C5
    C5 -->|Yes| PASS([All Gates Passed])

    style L5 fill:#ff6b6b,color:#fff
    style C1 fill:#ff6b6b,color:#fff
    style C2 fill:#ff6b6b,color:#fff
    style C3 fill:#ff6b6b,color:#fff
    style C4 fill:#ff6b6b,color:#fff
    style C5 fill:#ff6b6b,color:#fff
    style PASS fill:#51cf66,color:#fff
```

---

## Stop Conditions and Circuit Breakers

Conditions that halt execution, including those that pause even in autonomous mode.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
    end

    EXECUTING["Executing task"] --> CHECK{Stop condition<br>triggered?}

    CHECK -->|No| CONTINUE["Continue execution"]

    CHECK -->|Yes| CLASSIFY{Condition type}

    CLASSIFY -->|"Blocker mid-task<br>(missing dep, test fail,<br>unclear instruction)"| HALT_ASK["HALT:<br>Ask for clarification"]
    CLASSIFY -->|"Critical plan gaps"| HALT_PLAN["HALT:<br>Return to Phase 1"]
    CLASSIFY -->|"Don't understand<br>instruction"| HALT_ASK

    CLASSIFY -->|"3+ consecutive<br>test failures"| CIRCUIT_BREAK["CIRCUIT BREAKER:<br>Pause even in<br>autonomous mode"]
    CLASSIFY -->|"Security-sensitive ops<br>not clearly specified"| CIRCUIT_BREAK
    CLASSIFY -->|"Scope/requirements<br>question"| SCOPE_ASK["AskUserQuestion:<br>Include / Exclude / Defer"]
    CLASSIFY -->|"3+ review cycles<br>on same issue"| CIRCUIT_BREAK

    HALT_ASK -->|"Clarification received"| EXECUTING
    HALT_PLAN -->|"Plan updated"| EXECUTING
    CIRCUIT_BREAK -->|"User resolves"| EXECUTING
    SCOPE_ASK -->|"Decision made"| EXECUTING

    style CIRCUIT_BREAK fill:#ff6b6b,color:#fff
    style HALT_ASK fill:#ff6b6b,color:#fff
    style HALT_PLAN fill:#ff6b6b,color:#fff
```

---

## Source Cross-Reference

| Diagram Node | Source Location (SKILL.md) |
|---|---|
| Mode selection (batch/subagent) | Mode Selection table (lines 38-47) |
| Autonomous mode / circuit breakers | Autonomous Mode (lines 48-79) |
| Batch Phase 1: Load and review plan | Batch Mode Phase 1 (lines 97-110) |
| Batch Phase 2: Execute batch | Batch Mode Phase 2 (lines 112-118) |
| Batch Phase 3: Report | Batch Mode Phase 3 (lines 120-122) |
| Batch Phase 4: Continue | Batch Mode Phase 4 (lines 124-126) |
| Batch Phase 5: Complete / reflection gate | Batch Mode Phase 5 (lines 128-138) |
| Subagent Phase 1: Extract tasks | Subagent Mode Phase 1 (lines 146-148) |
| Subagent Phase 2: Per-task loop | Subagent Mode Phase 2 (lines 150-158) |
| Spec reviewer dispatch + loop | Phase 2 step 4 (line 155), Handling Review Issues (lines 210-211) |
| Quality reviewer dispatch + loop | Phase 2 step 5 (line 156), Handling Review Issues (lines 210-211) |
| 3+ review cycle escalation | Handling Review Issues (line 211) |
| Subagent Phase 3: Final review | Subagent Mode Phase 3 (line 160) |
| finishing-a-development-branch | Batch Phase 5 (line 138), Subagent Phase 4 (line 166) |
| Self-check gate (5 items) | Self-Check section (lines 220-231) |
| Stop conditions | Stop Conditions (lines 170-179) |
| Revisit Phase 1 | When to Revisit Phase 1 (line 183) |
| Handling subagent failure | Handling Subagent Failure (lines 214-216) |
