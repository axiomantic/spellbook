<!-- diagram-meta: {"source": "commands/feature-config.md", "source_hash": "sha256:5974bb698b681dff0849a5fa316a434f2c6aae0c572691eb721af5bf433ed1d9", "generated_at": "2026-06-06T21:50:31Z", "generator": "generate_diagrams.py"} -->
# Diagram: feature-config

## Overview: feature-config (Phase 0 of develop)

High-level flow showing the two primary paths (continuation vs. fresh wizard) and all major sections.

```mermaid
flowchart TD
    START(["`**START**
    feature-config`"]):::terminal --> S05

    S05["**0.5** Continuation Detection
    *(executes FIRST)*"]:::process --> CSig

    CSig{Continuation
    signals?}:::decision

    CSig -->|Yes| RESUME["Resume Flow
    Steps 1–5"]:::process
    CSig -->|No| S01

    RESUME --> PJUMP[/"Phase Jump Mechanism"/]:::subagent
    PJUMP --> DONE_RESUME(["Target Phase
    *(skip completed phases)*"]):::success

    S01["**0.1** Detect Escape Hatches"]:::process --> EH

    EH{"Escape hatch
    in message?"}:::decision

    EH -->|"'using design doc'
    'using impl plan'
    'just implement'"| ASK_EH[/"AskUserQuestion:
    How to handle
    existing doc?"/]:::subagent
    EH -->|None| S02

    ASK_EH --> EH_ROUTE{"Route by
    choice"}:::decision
    EH_ROUTE -->|"Review first
    (design doc)"| SKIP_21["Skip 2.1 →
    load doc → 2.2"]:::process
    EH_ROUTE -->|"Treat as ready
    (design doc)"| SKIP_P2["Skip Phase 2 →
    start Phase 3"]:::process
    EH_ROUTE -->|"Review first
    (impl plan)"| SKIP_313["Skip 2.1–3.1 →
    load doc → 3.2"]:::process
    EH_ROUTE -->|"Treat as ready
    (impl plan)"| SKIP_P23["Skip Phases 2–3 →
    start Phase 4"]:::process

    SKIP_21 --> S02
    SKIP_P2 --> S04
    SKIP_313 --> S02
    SKIP_P23 --> S04

    S02["**0.2** Clarify Motivation (WHY)"]:::process --> MOT

    MOT{"Motivation
    clear?"}:::decision
    MOT -->|No| ASK_MOT[/"AskUserQuestion:
    WHY?"/]:::subagent
    MOT -->|Yes| S03
    ASK_MOT --> S03

    S03["**0.3** Clarify Feature (WHAT)"]:::process
    S03 --> |"AskUserQuestion:
    core purpose + resources"| S04

    S04["**0.4** Collect Workflow Preferences
    *(8-question wizard)*"]:::process --> S06

    S06["**0.6** Detect Refactoring Mode
    *(keyword scan)*"]:::process --> S07

    S07["**0.7** Need-Flag Classification
    *(4 questions)*"]:::process --> FLAGS

    FLAGS{"Flags
    resolved"}:::decision
    FLAGS -->|"Zero flags
    (fast path)"| FAST[/"Announce fast path
    inline plan ≤5 steps
    develop stays resident"/]:::subagent
    FLAGS -->|"Any flag set"| GATED[/"Flag-gated phases
    full review floor"/]:::subagent

    FAST --> CHECKLIST
    GATED --> CHECKLIST

    CHECKLIST{"**Phase 0
    Complete
    Checklist**
    *(all 9 items)*"}:::gate
    CHECKLIST -->|"All checked ✓"| NEXT(["Next Phase
    (research / design / fast-impl)"]):::success
    CHECKLIST -->|"Unchecked items"| BACK["Complete
    Phase 0"]:::process
    BACK --> CHECKLIST

    classDef terminal fill:#2d2d2d,stroke:#888,color:#e8e8ea,rx:20
    classDef process fill:#2d2d2d,stroke:#4a9eff,color:#e8e8ea
    classDef decision fill:#2d2d2d,stroke:#f0a500,color:#f0a500
    classDef subagent fill:#1a3a5c,stroke:#4a9eff,color:#4a9eff
    classDef gate fill:#3a1a1a,stroke:#ff6b6b,color:#ff6b6b
    classDef success fill:#1a3a1a,stroke:#51cf66,color:#51cf66

    subgraph legend["Legend"]
        L1["Process"]:::process
        L2[/"Subagent Dispatch / AskUserQuestion"/]:::subagent
        L3{"Decision"}:::decision
        L4{"Quality Gate"}:::gate
        L5(["Terminal"]):::success
    end
```

---

## Detail: Section 0.5 — Continuation Detection

```mermaid
flowchart TD
    ENTRY(["Enter 0.5"]):::success --> SIG

    SIG{"Any continuation
    signal?"}:::decision

    SIG -->|"No signals"| EXIT_NO(["→ Proceed to 0.1"]):::success

    SIG -->|"Signal present:
    - 'continue'/'resume'/'pick up'
    - system-reminder: Skill Phase
    - system-reminder: Active Skill
    - artifacts on disk"| S1

    S1["**Step 1: Parse Recovery Context**
    Extract from system-reminder:
    active_skill, skill_phase,
    todos, exact_position"]:::process --> S2

    S2["**Step 2: Verify Artifact Existence**
    Run bash: list understanding/,
    plans/*-design.md, plans/*-impl.md,
    git worktree list"]:::process --> ART_CHECK

    ART_CHECK{"Artifacts match
    claimed phase?"}:::decision

    ART_CHECK -->|"Yes"| S3
    ART_CHECK -->|"Phase implies artifacts
    that are MISSING"| MISSING_ART

    MISSING_ART[/"Report missing artifacts
    AskUserQuestion:
    1. Regenerate from context
    2. Start fresh from Phase 0"/]:::subagent

    MISSING_ART --> |"Option 1"| S3
    MISSING_ART --> |"Option 2"| FRESH(["→ Proceed to 0.1
    (fresh start)"]):::success

    S3["**Step 3: Quick Preferences Check**
    Re-ask 4 preferences only:
    - Execution mode
    - Parallelization
    - Worktree
    - Post-implementation"]:::process --> S4

    S4["**Step 4: Synthesize Resume Point**"]:::process --> RP_LOGIC

    RP_LOGIC{"Resume
    point source"}:::decision
    RP_LOGIC -->|"In-progress todo
    in restored list"| RP_TODO["Use todo item
    *(most precise)*"]:::process
    RP_LOGIC -->|"No todo, but
    skill_phase present"| RP_PHASE["Use skill_phase
    from system-reminder"]:::process
    RP_LOGIC -->|"Neither"| RP_ARTIFACT["Infer from
    artifact pattern table"]:::process

    RP_TODO --> S5
    RP_PHASE --> S5
    RP_ARTIFACT --> S5

    S5["**Step 5: Confirm & Resume**
    Display: prior progress,
    design/impl/worktree paths,
    current task"]:::process --> JUMP

    JUMP[/"Phase Jump Mechanism:
    1. Determine target phase
    2. Skip all prior phases
    3. Execute from target forward"/]:::subagent

    JUMP --> DONE(["Resume at
    target phase ✓"]):::success

    subgraph artifact_table["Artifact-Only Fallback (Step 4)"]
        AT1["No artifacts → Phase 0 (HIGH)"]
        AT2["Understanding doc only → Phase 1.5→2 (HIGH)"]
        AT3["Design doc, no impl → Phase 2→3 (HIGH)"]
        AT4["Design + impl, no worktree → Phase 3→4.1 (HIGH)"]
        AT5["Worktree + uncommitted → Phase 4 in progress (MEDIUM)"]
        AT6["Worktree + commits, no PR → Phase 4 late (MEDIUM)"]
        AT7["PR exists → Phase 4.7 finishing (HIGH)"]
    end

    classDef terminal fill:#2d2d2d,stroke:#888,color:#e8e8ea,rx:20
    classDef process fill:#2d2d2d,stroke:#4a9eff,color:#e8e8ea
    classDef decision fill:#2d2d2d,stroke:#f0a500,color:#f0a500
    classDef subagent fill:#1a3a5c,stroke:#4a9eff,color:#4a9eff
    classDef gate fill:#3a1a1a,stroke:#ff6b6b,color:#ff6b6b
    classDef success fill:#1a3a1a,stroke:#51cf66,color:#51cf66

    subgraph legend["Legend"]
        L1["Process"]:::process
        L2[/"Subagent / AskUserQuestion"/]:::subagent
        L3{"Decision"}:::decision
        L5(["Terminal"]):::success
    end
```

---

## Detail: Section 0.4 — Configuration Wizard

```mermaid
flowchart TD
    ENTRY(["Enter 0.4"]):::success --> Q1

    Q1[/"**Q1** Execution mode:
    Fully autonomous (Recommended)
    Interactive
    Mostly autonomous"/]:::subagent --> Q2

    Q2[/"**Q2** Parallelization:
    Maximize parallel (Recommended)
    Conservative
    Ask each time"/]:::subagent --> Q3

    Q3[/"**Q3** Worktree:
    Single (Recommended)
    Per parallel track
    No worktree"/]:::subagent --> COUPLE

    COUPLE{"worktree ==
    'per_parallel_track'?"}:::decision
    COUPLE -->|Yes| FORCE_MAX["Auto-set
    parallelization = maximize"]:::process
    COUPLE -->|No| Q4
    FORCE_MAX --> Q4

    Q4[/"**Q4** Post-implementation:
    Offer options (Recommended)
    Create PR automatically
    Just stop"/]:::subagent --> Q5

    Q5[/"**Q5** Dialectic mode:
    None (Recommended)
    Roundtable"/]:::subagent --> D5

    D5{"dialectic_mode
    != 'none'?"}:::decision
    D5 -->|"Yes → show Q6"| Q6[/"**Q6** Dialectic level:
    Planning only
    Planning + gates (Recommended)
    Full"/]:::subagent
    D5 -->|"No → skip Q6"| Q7

    Q6 --> Q7

    Q7[/"**Q7** Token enforcement:
    Work-item level
    Gate level (Recommended)
    Every step"/]:::subagent --> Q8

    Q8[/"**Q8** Decision surface:
    Terminal questions (Recommended)
    Interactive canvas page"/]:::subagent --> STORE

    STORE["Store all in
    SESSION_PREFERENCES"]:::process

    STORE --> DONE(["→ Proceed to 0.6"]):::success

    classDef terminal fill:#2d2d2d,stroke:#888,color:#e8e8ea,rx:20
    classDef process fill:#2d2d2d,stroke:#4a9eff,color:#e8e8ea
    classDef decision fill:#2d2d2d,stroke:#f0a500,color:#f0a500
    classDef subagent fill:#1a3a5c,stroke:#4a9eff,color:#4a9eff
    classDef gate fill:#3a1a1a,stroke:#ff6b6b,color:#ff6b6b
    classDef success fill:#1a3a1a,stroke:#51cf66,color:#51cf66

    subgraph legend["Legend"]
        L1["Process"]:::process
        L2[/"AskUserQuestion (wizard Q)"/]:::subagent
        L3{"Decision / coupling rule"}:::decision
        L5(["Terminal"]):::success
    end
```

---

## Detail: Section 0.7 — Need-Flag Classification & Routing

```mermaid
flowchart TD
    ENTRY(["Enter 0.7"]):::success --> QR

    QR[/"**Q-RESEARCH** — Do we need to investigate?
    'Yes — investigate first'
    'No — I understand the code and requirements'"/]:::subagent --> QINFRA

    QINFRA[/"**Q-INFRA** — New deps, infra, or schema changes?
    'Yes — new deps/infra/schema'
    'No — existing code only'"/]:::subagent --> INFRA_CHECK

    INFRA_CHECK{"Q-INFRA = Yes?"}:::decision
    INFRA_CHECK -->|"Yes → auto-set
    needs_design = true
    skip Q-DESIGN"| QSIZE
    INFRA_CHECK -->|"No"| QDESIGN

    QDESIGN[/"**Q-DESIGN** — Design decisions to make?
    'Yes — architecture/data model/API/UX'
    'No — mechanical change (bump/rename/config)'"/]:::subagent --> QSIZE

    QSIZE[/"**Q-SIZE** — Rough scale? (signal only)
    Small / Medium / Large"/]:::subagent --> STORE

    STORE["Resolve flags:
    needs_research ∈ {true, false}
    needs_design ∈ {true, false}
    needs_infrastructure ∈ {true, false}
    size_estimate ∈ {small, medium, large}
    → store in SESSION_PREFERENCES"]:::process --> ROUTE

    ROUTE{"Any flag
    set?"}:::decision

    ROUTE -->|"ALL three = false
    (zero flags)"| FAST_ANN

    FAST_ANN["Announce fast path (verbatim):
    'This looks like a small, well-understood
    change... I'll take the fast path: skip
    research/discovery/design/planning phases,
    write a short inline plan for you to confirm,
    then implement it with the lighter review floor.'"]:::process --> FAST_LOG

    FAST_LOG["Log: 'Fast path: zero-flag change.
    Fewer phases, lighter floor, develop resident.'"]:::process --> FAST_TERM(["Fast path active
    develop stays resident ✓"]):::success

    ROUTE -->|"needs_research = true"| RES_PATH
    ROUTE -->|"needs_design = true
    or needs_infrastructure = true
    (and NOT needs_research)"| DES_PATH

    RES_PATH(["→ /feature-research
    (then design if flagged)"]):::success
    DES_PATH(["→ /feature-design"]):::success

    subgraph ortho["Orthogonality Rules"]
        OR1["needs_research is independent of needs_design and needs_infrastructure"]
        OR2["Q-INFRA=yes → auto needs_design=true (do NOT re-ask Q-DESIGN)"]
        OR3["size_estimate NEVER gates a phase — tunes parallelization only"]
    end

    classDef terminal fill:#2d2d2d,stroke:#888,color:#e8e8ea,rx:20
    classDef process fill:#2d2d2d,stroke:#4a9eff,color:#e8e8ea
    classDef decision fill:#2d2d2d,stroke:#f0a500,color:#f0a500
    classDef subagent fill:#1a3a5c,stroke:#4a9eff,color:#4a9eff
    classDef gate fill:#3a1a1a,stroke:#ff6b6b,color:#ff6b6b
    classDef success fill:#1a3a1a,stroke:#51cf66,color:#51cf66

    subgraph legend["Legend"]
        L1["Process"]:::process
        L2[/"AskUserQuestion"/]:::subagent
        L3{"Decision"}:::decision
        L5(["Terminal / next command"]):::success
    end
```

---

## Cross-Reference: Overview → Detail Diagrams

| Overview Section | Detail Diagram | Key Logic |
|---|---|---|
| **0.5** Continuation Detection | Detail: Section 0.5 | 5-step resume flow; artifact verification table; phase jump mechanism |
| **0.1** Escape Hatches | Overview (inline) | 3 patterns × 2 handling choices → phase skip routing |
| **0.2** Clarify Motivation | Overview (inline) | Ask only when intent ambiguous; 6 motivation categories |
| **0.3** Clarify Feature | Overview (inline) | Core purpose + resources; stored in SESSION_CONTEXT |
| **0.4** Wizard | Detail: Section 0.4 | 8 questions (Q6 conditional); coupling rule: per-track → maximize |
| **0.6** Refactoring Mode | Overview (inline) | Keyword scan only; no user interaction |
| **0.7** Need-Flags | Detail: Section 0.7 | 4 questions; Q-INFRA auto-sets needs_design; zero-flag fast path |
