<!-- diagram-meta: {"source": "agents/implementer.md", "source_hash": "sha256:ffc88f75b5dfea74c4485cc48ce5e65d04ff458ee7991134097c54505a7bd893", "generated_at": "2026-05-25T01:41:28Z", "generator": "generate_diagrams.py"} -->
# Diagram: implementer

```mermaid
flowchart TD
    START(["`**Dispatch Received**
    from parent agent`"]):::terminal

    VERIFY_ENV{"`Verify working dir
    & branch match
    dispatch?`"}:::gate

    ABORT(["`**Abort**
    mismatch — report
    to parent`"]):::error

    ANALYSIS["`**Analysis**
    Locate files & tests in scope
    Plan smallest change
    Identify test scope`"]:::process

    EDIT_FILES["`**Edit / Write Files**
    Apply changes within
    parent-specified scope`"]:::process

    SCOPE_CHECK{"`Changes confined
    to parent scope?`"}:::gate

    REPORT_DRIFT["`Add out-of-scope
    work to notes —
    do not execute`"]:::process

    RUN_BASH["`**Run Bash Command**
    build / test / git
    via spellbook gate`"]:::process

    GATE_DENIED{"`Bash gate
    denied?`"}:::gate

    SURFACE_DENIAL["`**Surface denial verbatim**
    to operator — ask
    how to proceed`"]:::process

    DESTRUCTIVE{"`Destructive git op
    requested?
    (push / reset --hard /
    checkout -- / stash drop)`"}:::gate

    CONFIRM_DESTRUCTIVE["`**Stop — require
    explicit confirmation**
    before proceeding`"]:::process

    TDD_GREEN{"`Tests
    green?`"}:::gate

    COMMIT["`**Commit changes**
    green state at
    cycle boundary`"]:::process

    REFLECTION["`**Reflection**
    Scope drift check
    Uncommitted green state?
    Gate denial surfaced?`"]:::process

    OUTPUT(["`**StructuredResult**
    files_changed
    commit_sha
    test_results
    notes`"]):::terminal

    START --> VERIFY_ENV
    VERIFY_ENV -->|"mismatch"| ABORT
    VERIFY_ENV -->|"match"| ANALYSIS
    ANALYSIS --> EDIT_FILES
    EDIT_FILES --> SCOPE_CHECK
    SCOPE_CHECK -->|"out of scope"| REPORT_DRIFT
    REPORT_DRIFT --> RUN_BASH
    SCOPE_CHECK -->|"in scope"| RUN_BASH
    RUN_BASH --> DESTRUCTIVE
    DESTRUCTIVE -->|"yes"| CONFIRM_DESTRUCTIVE
    CONFIRM_DESTRUCTIVE -->|"confirmed"| GATE_DENIED
    CONFIRM_DESTRUCTIVE -->|"denied"| OUTPUT
    DESTRUCTIVE -->|"no"| GATE_DENIED
    GATE_DENIED -->|"denied"| SURFACE_DENIAL
    SURFACE_DENIAL --> OUTPUT
    GATE_DENIED -->|"allowed"| TDD_GREEN
    TDD_GREEN -->|"no — fix & retry"| EDIT_FILES
    TDD_GREEN -->|"yes"| COMMIT
    COMMIT --> REFLECTION
    REFLECTION --> OUTPUT

    subgraph LEGEND["Legend"]
        L1[Process]:::process
        L2{Decision / Gate}:::gate
        L3([Terminal]):::terminal
        L4([Error / Abort]):::error
    end

    classDef process fill:#1e3a5f,stroke:#4a9eff,color:#e8e8ea
    classDef gate fill:#5a2020,stroke:#ff6b6b,color:#e8e8ea
    classDef terminal fill:#1a4a2e,stroke:#51cf66,color:#e8e8ea
    classDef error fill:#4a2000,stroke:#ff6b6b,color:#e8e8ea
```

**Implementer Agent Flow**

The agent enforces a strict pre-mutation environment check (working directory + branch) before any file or shell operation. Bash commands route through the spellbook gate — denials are surfaced verbatim to the operator rather than worked around. Destructive git operations require explicit confirmation. TDD cycles loop until tests are green, then commit before crossing phase boundaries. Out-of-scope work is logged in `notes` and never silently executed.
