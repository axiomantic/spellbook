<!-- diagram-meta: {"source": "agents/pr-merger.md", "source_hash": "sha256:ffc88f75b5dfea74c4485cc48ce5e65d04ff458ee7991134097c54505a7bd893", "generated_at": "2026-05-25T01:43:08Z", "generator": "generate_diagrams.py"} -->
# Diagram: pr-merger

## pr-merger Agent — Workflow Diagram

```mermaid
flowchart TD
    START(["`**pr-merger agent invoked**
    Bash · Read only`"]):::terminal

    subgraph ANALYSIS["Analysis Phase"]
        A1["Identify PR number &\nrequested action\n(merge vs ready-mark)"]:::process
        A2["Identify merge method\n(squash / merge / rebase)"]:::process
        A3["gh pr view\n→ check mergeability &\nbranch info"]:::process
        A4["gh pr checks\n→ check CI status"]:::process
    end

    subgraph REFLECTION["Reflection Gates"]
        R1{"All required CI\nchecks green?"}:::gate
        R2{"Admin bypass\nrequested?"}:::gate
        R3{"Explicit operator\nauthorization for\nthis PR number?"}:::gate
        R4{"Unrequested side\neffects present?\n(branch delete, close)"}:::gate
    end

    subgraph CONFIRM["Operator Confirmation Gate"]
        C1["Print exact gh pr command\n+ PR number\n+ merge method\n+ head/base branches"]:::process
        C2{"Operator\nconfirms?"}:::gate
    end

    subgraph EXECUTE["Execution"]
        E1["gh pr merge\n(squash|merge|rebase)"]:::subagent
        E2["gh pr ready\n(draft → ready-for-review)"]:::subagent
    end

    subgraph BASHGATE["Spellbook Bash Gate (PreToolUse)"]
        BG1{"Gate\napproves?"}:::gate
        BG2["Surface denial verbatim\nto operator"]:::process
        BG3{"Operator\nadvises?"}:::gate
    end

    subgraph OUTPUT["Output"]
        O1["`Return PrMergerResult JSON
        action: merged
        merged: true`"]:::success
        O2["`Return PrMergerResult JSON
        action: marked_ready
        merged: false`"]:::success
        O3["`Return PrMergerResult JSON
        action: none
        merged: false
        notes: decline/abort reason`"]:::fail
    end

    START --> A1
    A1 --> A2
    A2 --> A3
    A3 --> A4
    A4 --> R1

    R1 -->|"No — failing or pending"| DECLINE_CI["Decline merge\nSurface failures to operator"]:::process
    DECLINE_CI --> O3

    R1 -->|"Yes"| R2
    R2 -->|"Yes (--admin)"| R3
    R3 -->|"No explicit auth\nfor this PR number"| DECLINE_ADMIN["Decline --admin bypass"]:::process
    DECLINE_ADMIN --> O3
    R3 -->|"Yes, authorized"| R4

    R2 -->|"No"| R4
    R4 -->|"Yes — unrequested\nbranch delete / close"| STRIP_SIDE["Remove unrequested\nside-effect flags\n(default: retain branch)"]:::process
    STRIP_SIDE --> C1
    R4 -->|"No"| C1

    C1 --> C2
    C2 -->|"No / abort"| O3
    C2 -->|"Yes — merge"| BG1
    C2 -->|"Yes — ready-mark"| BG1

    BG1 -->|"Denied"| BG2
    BG2 --> BG3
    BG3 -->|"Cannot proceed"| O3
    BG3 -->|"Alternative approved"| BG1

    BG1 -->|"Approved — merge"| E1
    BG1 -->|"Approved — ready"| E2

    E1 --> O1
    E2 --> O2

    subgraph LEGEND["Legend"]
        L1["Process step"]:::process
        L2{"Decision / gate"}:::gate
        L3["Subagent / gh CLI call"]:::subagent
        L4([Terminal]):::terminal
        L5["Success result"]:::success
        L6["Decline / abort result"]:::fail
    end

    classDef process fill:#2d2d2d,stroke:#888,color:#e8e8ea
    classDef gate fill:#ff6b6b,stroke:#cc4444,color:#fff
    classDef subagent fill:#4a9eff,stroke:#2277cc,color:#fff
    classDef terminal fill:#333,stroke:#aaa,color:#e8e8ea,rx:20
    classDef success fill:#51cf66,stroke:#2a9c3f,color:#fff
    classDef fail fill:#ff6b6b,stroke:#cc4444,color:#fff
```

**pr-merger** is a narrow state-mutation agent. It reads PR state, enforces four sequential guardrails (CI green → no unauthorized admin bypass → no unrequested side effects → operator confirmation), passes the composed command through the spellbook bash gate, and executes exactly one of two mutating verbs: `gh pr merge` or `gh pr ready`. Every path that cannot proceed terminates in a `PrMergerResult` with `action: none` and a `notes` field explaining the abort reason.
