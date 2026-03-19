<!-- diagram-meta: {"source": "agents/chariot-implementer.md","source_hash": "sha256:6c7f1c4818533f4589c76af0ef8a275fb08b9006f7046520187eef832a18ae34","generated_at": "2026-03-19T00:00:00Z","generator": "generating-diagrams skill"} -->
# Diagram: chariot-implementer

Focused implementation agent that executes specifications with absolute precision. Follows a three-phase protocol (Analysis, Implementation Loop, Reflection) with quality gates enforcing traceability and scope discipline at every stage.

```mermaid
flowchart TD
    subgraph Legend
        direction LR
        LP[Process]
        LD{Decision}
        LT([Terminal])
        LG{Quality Gate}:::gate
    end

    START([Agent Invoked]) --> VALIDATE

    subgraph PHASE0["Phase 0: Input Validation"]
        VALIDATE{spec, context,<br>scope all provided?}
        VALIDATE -->|Missing| ABORT([Abort: Missing<br>required inputs]):::fail
        VALIDATE -->|All present| RECEIVE[Receive spec +<br>context + scope]
    end

    RECEIVE --> READ_SPEC

    subgraph PHASE1["Phase 1: Analysis"]
        READ_SPEC[Read specification<br>completely before<br>writing any code]
        READ_SPEC --> IDENTIFY[Identify functions,<br>classes, data<br>structures required]
        IDENTIFY --> MAP_REQS[Map each requirement<br>to planned code location]
        MAP_REQS --> VERIFY_SCOPE{Scope boundaries<br>clear?}
        VERIFY_SCOPE -->|No| CLARIFY[Clarify scope<br>with requestor]
        CLARIFY --> VERIFY_SCOPE
        VERIFY_SCOPE -->|Yes| ENTER_LOOP
    end

    ENTER_LOOP --> NEXT_REQ

    subgraph PHASE2["Phase 2: Implementation Loop"]
        NEXT_REQ{More requirements<br>to implement?}
        NEXT_REQ -->|Yes| WRITE_CODE[Write code fulfilling<br>EXACTLY that requirement]
        WRITE_CODE --> ADD_COMMENT[Add comment linking<br>to spec section]
        ADD_COMMENT --> SCOPE_CHECK{Scope creep<br>detected?}:::gate
        SCOPE_CHECK -->|Yes| REMOVE_EXTRA[Remove unauthorized code]
        REMOVE_EXTRA --> TEST
        SCOPE_CHECK -->|No| TEST[Test the specific behavior]
        TEST --> NEXT_REQ
    end

    NEXT_REQ -->|No| TRACE_CHECK

    subgraph PHASE3["Phase 3: Pre-COMMIT Reflection"]
        TRACE_CHECK{Every code block<br>traces to a<br>requirement?}:::gate
        TRACE_CHECK -->|"Fail: untraceable = unauthorized"| REMOVE_UNTRACEABLE[Remove untraceable code]
        REMOVE_UNTRACEABLE --> TRACE_CHECK

        TRACE_CHECK -->|Pass| EXTRAS_CHECK{Anything added<br>not in spec?}:::gate
        EXTRAS_CHECK -->|Yes| REMOVE_FEATURES[Remove unrequested features]
        REMOVE_FEATURES --> EXTRAS_CHECK

        EXTRAS_CHECK -->|No| ERROR_CHECK{Error handling<br>complete?}:::gate
        ERROR_CHECK -->|Fail| ADD_ERRORS[Add missing<br>error handling]
        ADD_ERRORS --> ERROR_CHECK

        ERROR_CHECK -->|Pass| FAITHFUL{Would spec author<br>recognize this as<br>faithful execution?}:::gate
        FAITHFUL -->|No| REVISE[Revise implementation]
        REVISE --> NEXT_REQ
    end

    FAITHFUL -->|Yes| COMMIT

    subgraph PHASE4["Phase 4: Output"]
        COMMIT[Generate COMMIT<br>speech act]
        COMMIT --> TRACE_MAP[Output traceability<br>matrix: spec section<br>to code location]
        TRACE_MAP --> DEFERRED[Document out-of-scope<br>items explicitly deferred]
    end

    DEFERRED --> DONE([Implementation Complete]):::success

    ENTER_LOOP:::hidden

    classDef gate fill:#ff6b6b,stroke:#c0392b,color:#fff
    classDef success fill:#51cf66,stroke:#2f9e44,color:#fff
    classDef fail fill:#ff6b6b,stroke:#c0392b,color:#fff
    classDef hidden display:none
```

## Legend

| Color | Meaning |
|-------|---------|
| Red (`#ff6b6b`) | Quality gate (scope, traceability, error handling, faithfulness) |
| Green (`#51cf66`) | Success terminal |
| Default (grey) | Process step |
| Diamond shape | Decision point or quality gate |
| Stadium shape | Terminal (start/end) |

## Forbidden Actions

The agent enforces strict boundaries. These are explicitly forbidden and caught by the reflection gates:

| Forbidden Action | Enforcing Gate |
|---|---|
| Adding "nice to have" features not in spec | Scope creep check, Extras check |
| Optimizing prematurely without requirement | Traceability check |
| Refactoring adjacent code while implementing | Scope creep check |
| Skipping error handling to save time | Error handling check |
| Implementing partial solutions | Faithful execution check |
| Deferring tests ("I'll add tests later") | Test step in implementation loop |

## Cross-Reference

| Node | Source Reference |
|------|----------------|
| Input Validation | Lines 33-38: Required inputs table |
| Read specification completely | Line 50: Analysis step 1 |
| Identify functions, classes, structures | Line 51: Analysis step 2 |
| Map requirements to code locations | Line 52: Analysis step 3 |
| Verify scope boundaries | Line 53: Analysis step 4 |
| Write code for requirement | Line 58: Implementation step 1 |
| Add comment linking to spec | Line 59: Implementation step 2 |
| Scope creep detected? | Line 60: Implementation step 3 |
| Test the specific behavior | Line 61: Implementation step 4 |
| Every block traces to requirement? | Line 66: Reflection check 1 |
| Anything added not in spec? | Line 67: Reflection check 2 |
| Error handling complete? | Line 68: Reflection check 3 |
| Faithful to spec author? | Line 69: Reflection check 4 |
| Generate COMMIT speech act | Lines 74-89: COMMIT format |
| Output traceability matrix | Lines 82-87: Traceability table |
| Document out-of-scope items | Line 88: Not Implemented section |
