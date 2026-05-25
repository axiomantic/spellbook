<!-- diagram-meta: {"source": "agents/test-runner.md", "source_hash": "sha256:ffc88f75b5dfea74c4485cc48ce5e65d04ff458ee7991134097c54505a7bd893", "generated_at": "2026-05-25T01:43:34Z", "generator": "generate_diagrams.py"} -->
# Diagram: test-runner

```mermaid
flowchart TD
    START(["Parent dispatches test-runner"]):::terminal

    subgraph ANALYSIS["Phase 1 — Analysis"]
        A1["Determine tightest test selector\n(path / test ID / marker)"]
        A2{"Scope specified?"}
        A3["Identify correct runner\n(pytest / npm test / cargo test / go test)"]
        A4["Confirm command before running"]
        A5["Plan output parsing\n(pass/fail/skip/error counts + excerpts)"]
    end

    subgraph EXEC["Phase 2 — Execution"]
        E1["Run test command via Bash\n(scoped selector)"]
        E2{{"Bash gate check"}}:::gate
        E3["Gate denied"]
        E4["Test run completes"]
    end

    subgraph PARSE["Phase 3 — Parse & Reflect"]
        P1["Parse output:\npassed / failed / skipped / errors"]
        P2["Extract failing_tests:\ntest_id + failure_excerpt"]
        P3{"Flaky signals?\n(intermittent / ordering /\ntimeout)"}
        P4["Disclose in notes\n(never retry to green)"]
        P5["Reflection:\nsmallest selector? no edits? no git side effects?"]
    end

    subgraph GUARD["Guardrails — never"]
        G1[/"Edit or Write source files"/]:::gate
        G2[/"git add / commit / push /\ncheckout / reset / stash"/]:::gate
        G3[/"Run full suite when\ntighter scope specified"/]:::gate
        G4[/"Retry to green to hide\nflaky failures"/]:::gate
        G5[/"Reshape denied command\nto evade bash gate"/]:::gate
    end

    subgraph OUTPUT["Phase 4 — Output"]
        O1["Assemble TestRunnerResult JSON:\ntest_results · command · exit_code\nfailing_tests · notes"]
        O2{{"Source fix needed?"}}:::gate
        O3["Report in notes →\ndefer to implementer"]
        O4(["Return structured result\nto parent"]):::success
    end

    START --> A1
    A1 --> A2
    A2 -->|"Yes — use it"| A3
    A2 -->|"No — reject wide run,\nreport in notes"| A3
    A3 --> A4 --> A5

    A5 --> E1
    E1 --> E2
    E2 -->|"Allowed"| E4
    E2 -->|"Denied"| E3
    E3 -->|"Surface verbatim to operator,\nask how to proceed"| O1

    E4 --> P1 --> P2
    P2 --> P3
    P3 -->|"Yes"| P4 --> P5
    P3 -->|"No"| P5

    P5 --> O1
    O1 --> O2
    O2 -->|"Yes"| O3 --> O4
    O2 -->|"No"| O4

    subgraph LEGEND["Legend"]
        direction LR
        L1["Process step"]
        L2{{"Quality gate / decision"}}:::gate
        L3(["Terminal"]):::success
        L4[/"Forbidden action"/]:::gate
    end

    classDef gate fill:#ff6b6b,color:#fff,stroke:#c0392b
    classDef success fill:#51cf66,color:#000,stroke:#2f9e44
    classDef terminal fill:#868e96,color:#fff,stroke:#495057
```

**Description:** The `test-runner` agent follows a four-phase flow — Analysis → Execution → Parse & Reflect → Output — with a permanent guardrails layer that applies throughout. The bash gate is the only external decision point; a denial surfaces verbatim to the operator rather than being papered over. Source fixes are never attempted in-agent; they are deferred to `implementer` via the `notes` field.
