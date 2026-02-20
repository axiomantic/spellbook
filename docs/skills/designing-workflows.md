# designing-workflows

Use when designing systems with explicit states, transitions, or multi-step flows. Triggers: "design a workflow", "state machine", "approval flow", "pipeline stages", "what states does X have", "how does X transition", or when implementing-features Phase 2.1 detects workflow patterns.

## Workflow Diagram

# Diagram: designing-workflows

Designs systems with explicit states, transitions, and multi-step flows. Follows a structured process from state identification through validation, producing Mermaid state diagrams and transition tables. Enforces invariants like named triggers, mutually exclusive guards, and first-class error states.

```mermaid
flowchart TD
    Start([Start: Process Description]) --> Analysis

    Analysis["Analyze Business Context"]:::command --> P1
    P1["Phase 1: State Identification"]:::command --> P2
    P2["Phase 2: Transition Mapping"]:::command --> P3
    P3["Phase 3: Guard Design"]:::command --> GuardCheck{Guards Exclusive & Exhaustive?}:::decision
    GuardCheck -->|No| P3
    GuardCheck -->|Yes| P4

    P4["Phase 4: Error Handling"]:::command --> ErrorCheck{Every State Has Error Path?}:::decision
    ErrorCheck -->|No| P4
    ErrorCheck -->|Yes| P5

    P5["Phase 5: Validation"]:::command --> Reachable{All States Reachable?}:::gate
    Reachable -->|No| FixStates[Fix Unreachable States]:::command
    FixStates --> P5
    Reachable -->|Yes| DeadEnd{No Dead-End States?}:::gate
    DeadEnd -->|No| FixDeadEnds[Add Exit Transitions]:::command
    FixDeadEnds --> P5
    DeadEnd -->|Yes| Deterministic{Deterministic Transitions?}:::gate
    Deterministic -->|No| FixGuards[Resolve Overlapping Guards]:::command
    FixGuards --> P3
    Deterministic -->|Yes| Patterns

    Patterns{Workflow Pattern Needed?}:::decision
    Patterns -->|Saga| Saga["Define Compensating Actions"]:::command
    Patterns -->|Token| Token["Design Token Enforcement"]:::command
    Patterns -->|Checkpoint| Checkpoint["Design Checkpoint/Resume"]:::command
    Patterns -->|None| Viz

    Saga --> Viz
    Token --> Viz
    Checkpoint --> Viz

    Viz["Generate Mermaid Diagram"]:::command --> Table["Generate Transition Table"]:::command
    Table --> SelfCheck{Self-Check Passes?}:::gate
    SelfCheck -->|No| ReviseDesign[Revise Design]:::command
    ReviseDesign --> P1
    SelfCheck -->|Yes| Final([Spec + Diagram Delivered])

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
| Analyze Business Context | Reasoning Schema analysis tag (line 15) |
| Phase 1: State Identification | Design Process step 1 (line 61) |
| Phase 2: Transition Mapping | Design Process step 2 (line 62) |
| Phase 3: Guard Design | Design Process step 3 (line 63) |
| Guards Exclusive & Exhaustive? | Invariant 3 and Guard rules (lines 23, 55) |
| Phase 4: Error Handling | Design Process step 4 (line 64) |
| Every State Has Error Path? | Invariant 4 (line 24) |
| Phase 5: Validation | Design Process step 5 (line 65) |
| All States Reachable? | Validation: Reachable (line 65) |
| No Dead-End States? | Validation: no dead ends (line 65) |
| Deterministic Transitions? | Validation: deterministic (line 65) |
| Define Compensating Actions | Saga Pattern (lines 87-91) |
| Design Token Enforcement | Token-Based Enforcement (line 93) |
| Design Checkpoint/Resume | Checkpoint/Resume (line 95) |
| Generate Mermaid Diagram | Visualization section (lines 69-80) |
| Generate Transition Table | Outputs: transition_table (line 41) |
| Self-Check Passes? | Self-Check checklist (lines 132-141) |

## Skill Content

``````````markdown
# Workflow Design

<ROLE>
Workflow Architect with formal methods background. Your reputation depends on state machines that are complete (no dead ends), deterministic (unambiguous transitions), and recoverable (graceful error handling). A workflow that hangs or silently fails is a professional failure.
</ROLE>

## Reasoning Schema

<analysis>Before designing: What are the business states? What events trigger transitions? What invariants? What can fail?</analysis>

<reflection>After designing: Is every state reachable? Can every state exit? Are guards mutually exclusive? Are error states recoverable?</reflection>

## Invariant Principles

1. **States Are Business Concepts**: "ProcessingPayment" not "step3".
2. **Transitions Are Events**: Every arrow needs a named trigger.
3. **Guards Prevent Ambiguity**: Mutually exclusive and exhaustive.
4. **Error States Are First-Class**: Every state needs an error path.
5. **Compensating Actions Enable Recovery**: For each side effect, define undo.
6. **Invariants Are Explicit**: Violations are bugs, not edge cases.
7. **Visualization Validates Design**: If you cannot draw it, you do not understand it.

## Inputs / Outputs

| Input | Required | Description |
|-------|----------|-------------|
| `process_description` | Yes | Natural language description of the workflow |
| `domain_context` | No | Business rules, constraints, existing systems |

| Output | Type | Description |
|--------|------|-------------|
| `state_machine_spec` | File | At `~/.local/spellbook/docs/<project>/plans/` |
| `mermaid_diagram` | Inline | State diagram for validation |
| `transition_table` | Inline | Tabular representation |

---

## State Machine Components

| State Type | Purpose | Example |
|------------|---------|---------|
| **Initial** | Entry point (exactly one) | `Draft`, `New` |
| **Intermediate** | Processing stages | `UnderReview` |
| **Terminal** | Happy/failure completion | `Approved`, `Rejected` |
| **Error** | Recoverable, can retry | `Failed`, `Suspended` |

**Transitions:** `Source --trigger[guard]/action--> Target`

**Guards:** Must be mutually exclusive when sharing triggers. No implicit else.

---

## Design Process

1. **State Identification**: List status nouns, classify types, name with domain vocabulary
2. **Transition Mapping**: For each state, what events cause exit?
3. **Guard Design**: Ensure mutual exclusivity, explicit exhaustiveness
4. **Error Handling**: Every state needs failure path with retry/escalate/terminate
5. **Validation**: Reachable, no dead ends, deterministic

---

## Visualization

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> UnderReview: submit [isValid]
    Draft --> Draft: submit [!isValid]
    UnderReview --> Approved: approve
    UnderReview --> Rejected: reject
    Approved --> [*]
    Rejected --> [*]
```

---

## Workflow Patterns

**Saga Pattern:** Side effects + compensating actions in reverse order on failure.
```
Step 1: reserveInventory() | Compensate: releaseInventory()
Step 2: chargePayment()    | Compensate: refundPayment()
On failure at N: Execute compensations N-1 through 1
```

**Token-Based Enforcement:** Tokens validate allowed transitions, prevent stage skipping.

**Checkpoint/Resume:** Load checkpoint, restore state, re-enter at saved stage.

---

## Example

<example>
Design: Order approval workflow

1. **States**: Draft (initial), UnderReview (intermediate), Approved/Rejected (terminal), ReviewFailed (error)
2. **Transitions**:
   - Draft --submit[valid]--> UnderReview
   - UnderReview --approve[hasAuthority]--> Approved
   - UnderReview --reject--> Rejected
   - UnderReview --error[retryable]--> ReviewFailed
   - ReviewFailed --retry[count<3]--> UnderReview
3. **Validation**: All states reachable, no dead ends, guards exclusive
4. **Output**: Mermaid diagram + transition table
</example>

---

<FORBIDDEN>
- States named after implementation ("step1")
- Transitions without named triggers
- Overlapping guards (ambiguous transitions)
- Missing error handling (only happy path)
- Side effects without compensating actions
- Dead-end states not marked terminal
- Implicit guards ("else" without condition)
- Skipping completeness validation
</FORBIDDEN>

---

## Self-Check

- [ ] States use business domain vocabulary
- [ ] Every transition has named trigger
- [ ] Guards mutually exclusive and exhaustive
- [ ] Every non-terminal state has exit
- [ ] Error states with retry/escalate paths
- [ ] Side effects have compensating actions
- [ ] Mermaid diagram renders correctly
- [ ] Completeness validated

If ANY unchecked: revise before completing.

---

<FINAL_EMPHASIS>
Workflows are contracts. Every state is a promise. Every transition is a fulfillment. Every guard is a condition. A well-designed workflow proves your system cannot get stuck, lose work, or silently fail. The mermaid diagram IS the design.
</FINAL_EMPHASIS>
``````````
