<!-- diagram-meta: {"source": "commands/feature-config.md","source_hash": "sha256:8f043ecc2122e81e9f6faf19fb59f73072d45ce4d357f0f0ae60070182246a3f","generator": "stamp"} -->
# Diagram: feature-config

Phase 0 of develop: Configuration wizard that collects preferences, detects escape hatches, clarifies motivation, classifies complexity, and routes to the appropriate next phase.

## Overview

High-level flow showing the two main tracks (continuation vs fresh start) and terminal routing by complexity tier.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"User Input"/]
        L5[Quality Gate]:::gate
    end

    START([Phase 0 Entry]) --> CONT_CHECK{0.5 Continuation<br>Signals Detected?}

    CONT_CHECK -->|Yes| RESUME_TRACK[Resume Track<br>Steps 1-5]
    CONT_CHECK -->|No| FRESH_TRACK[Fresh Start Track<br>Steps 0.1-0.7]

    RESUME_TRACK --> PHASE_JUMP[Phase Jump<br>Mechanism]
    PHASE_JUMP --> RESUME_TARGET([Resume at<br>Target Phase]):::success

    FRESH_TRACK --> ESCAPE{0.1 Escape<br>Hatch Detected?}
    ESCAPE -->|Yes| ESCAPE_HANDLE[Handle Escape Hatch<br>Skip Covered Phases]
    ESCAPE -->|No| MOTIVATION[0.2 Clarify Motivation]

    ESCAPE_HANDLE --> MOTIVATION
    MOTIVATION --> FEATURE[0.3 Clarify Feature]
    FEATURE --> WIZARD[0.4 Preferences Wizard]
    WIZARD --> REFACTOR{0.6 Refactoring<br>Keywords?}
    REFACTOR -->|Yes| SET_REFACTOR[Set refactoring_mode = true]
    REFACTOR -->|No| COMPLEXITY
    SET_REFACTOR --> COMPLEXITY

    COMPLEXITY[0.7 Complexity<br>Classification] --> GATE_CHECK[Phase 0 Completion Gate]:::gate
    GATE_CHECK --> TIER{Derived Tier?}

    TIER -->|TRIVIAL| EXIT_TRIVIAL([Exit Skill]):::success
    TIER -->|SIMPLE| EXIT_SIMPLE([Lightweight Research<br>then /feature-implement]):::success
    TIER -->|STANDARD| EXIT_STANDARD([/feature-research<br>Phase 1]):::success
    TIER -->|COMPLEX| EXIT_COMPLEX([/feature-research<br>Phase 1]):::success

    classDef gate fill:#ff6b6b,stroke:#d63031,color:#fff
    classDef success fill:#51cf66,stroke:#37b24d,color:#fff
```

## Cross-Reference Table

| Overview Node | Detail Diagram |
|---|---|
| 0.5 Continuation Signals Detected? | [Continuation Detection Detail](#continuation-detection-detail-section-05) |
| Resume Track Steps 1-5 | [Continuation Detection Detail](#continuation-detection-detail-section-05) |
| 0.1 Escape Hatch Detected? | [Escape Hatch Detail](#escape-hatch-detail-section-01) |
| 0.4 Preferences Wizard | [Preferences Wizard Detail](#preferences-wizard-detail-section-04) |
| 0.7 Complexity Classification | [Complexity Classification Detail](#complexity-classification-detail-section-07) |

---

## Continuation Detection Detail (Section 0.5)

Executes FIRST before any wizard questions. Detects prior session state, verifies artifacts on disk, re-collects volatile preferences, and jumps to the appropriate resume point.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[Quality Gate]:::gate
    end

    START([Enter 0.5]) --> SCAN{Scan for<br>Continuation Signals}

    SCAN -->|"User prompt: continue,<br>resume, pick up, compacted"| SIG_YES[Signal Found]
    SCAN -->|"system-reminder has<br>Skill Phase or Active Skill"| SIG_YES
    SCAN -->|"Artifacts exist<br>on disk"| SIG_YES
    SCAN -->|No signals| SIG_NO([Proceed to 0.1]):::success

    SIG_YES --> STEP1[Step 1: Parse<br>Recovery Context]
    STEP1 --> EXTRACT["Extract: active_skill,<br>skill_phase, todos,<br>exact_position"]

    EXTRACT --> STEP2[Step 2: Verify<br>Artifact Existence]
    STEP2 --> CHECK_ARTIFACTS["Check disk for:<br>- understanding/ dir<br>- *-design.md<br>- *-impl.md<br>- git worktree list"]

    CHECK_ARTIFACTS --> ARTIFACT_MATCH{Artifacts Match<br>Claimed Phase?}
    ARTIFACT_MATCH -->|Yes| REPORT_STATE[Report Verified State]
    ARTIFACT_MATCH -->|No| MISSING[Report Missing Artifacts]

    MISSING --> MISSING_CHOICE{User Choice}
    MISSING_CHOICE -->|Regenerate| REPORT_STATE
    MISSING_CHOICE -->|Start fresh| SIG_NO

    REPORT_STATE --> STEP3[Step 3: Quick<br>Preferences Check]
    STEP3 --> PREFS["Re-ask 4 prefs only:<br>- Execution mode<br>- Parallelization<br>- Worktree<br>- Post-implementation"]

    PREFS --> STEP4[Step 4: Synthesize<br>Resume Point]
    STEP4 --> SYNTH_SOURCE{Resume Source<br>Priority?}

    SYNTH_SOURCE -->|"1st: In-progress todo"| USE_TODO[Use todo as resume point]
    SYNTH_SOURCE -->|"2nd: skill_phase from<br>system-reminder"| USE_PHASE[Use claimed phase]
    SYNTH_SOURCE -->|"3rd: Neither available"| USE_ARTIFACTS[Infer from<br>artifact pattern table]

    USE_TODO --> STEP5[Step 5: Confirm and Resume]
    USE_PHASE --> STEP5
    USE_ARTIFACTS --> STEP5

    STEP5 --> DISPLAY[Display skipped<br>and current phases]
    DISPLAY --> JUMP([Phase Jump to<br>Target Phase]):::success

    classDef gate fill:#ff6b6b,stroke:#d63031,color:#fff
    classDef success fill:#51cf66,stroke:#37b24d,color:#fff
```

### Artifact-to-Phase Inference Table

Used by Step 4 when no todo or skill_phase is available.

| Artifact Pattern | Inferred Phase | Confidence |
|---|---|---|
| No artifacts | Phase 0 (fresh start) | HIGH |
| Understanding doc only | Phase 1.5 complete, resume Phase 2 | HIGH |
| Design doc, no impl plan | Phase 2 complete, resume Phase 3 | HIGH |
| Design + impl plan, no worktree | Phase 3 complete, resume Phase 4.1 | HIGH |
| Worktree with uncommitted changes | Phase 4 in progress | MEDIUM |
| Worktree with commits, no PR | Phase 4 late stages | MEDIUM |
| PR exists for feature branch | Phase 4.7 (finishing) | HIGH |

---

## Escape Hatch Detail (Section 0.1)

Parses user's initial message for patterns that skip phases by providing pre-existing documents.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"User Input"/]
    end

    START([Enter 0.1]) --> PARSE[Parse User Message<br>for Escape Patterns]

    PARSE --> PATTERN{Pattern Detected?}

    PATTERN -->|"'using design doc path'"| DESIGN_ESC[Design Doc Escape]
    PATTERN -->|"'using impl plan path'"| IMPL_ESC[Impl Plan Escape]
    PATTERN -->|"'just implement, no docs'"| NODOCS_ESC[No-Docs Escape]
    PATTERN -->|No pattern| NO_ESCAPE([No Escape Hatch<br>Proceed to 0.2]):::success

    DESIGN_ESC --> ASK_HANDLE{/"How to handle<br>existing doc?"/}
    IMPL_ESC --> ASK_HANDLE

    ASK_HANDLE -->|Review first| REVIEW_CHOICE{Doc Type?}
    ASK_HANDLE -->|Treat as ready| READY_CHOICE{Doc Type?}

    REVIEW_CHOICE -->|Design doc| SKIP_21([Skip to Phase 2.2<br>Review Design]):::success
    REVIEW_CHOICE -->|Impl plan| SKIP_32([Skip to Phase 3.2<br>Review Plan]):::success

    READY_CHOICE -->|Design doc| SKIP_P2([Skip Phase 2<br>Start Phase 3]):::success
    READY_CHOICE -->|Impl plan| SKIP_P23([Skip Phases 2-3<br>Start Phase 4]):::success

    NODOCS_ESC --> SKIP_INLINE([Skip Phases 2-3<br>Minimal Inline Plan<br>Start Phase 4]):::success

    classDef success fill:#51cf66,stroke:#37b24d,color:#fff
```

---

## Preferences Wizard Detail (Section 0.4)

Collects all workflow preferences in a single wizard interaction. Questions 6-7 are conditional.

```mermaid
flowchart TD
    subgraph Legend
        L1[/"User Input"/]
        L2{Decision}
        L3([Terminal])
    end

    START([Enter 0.4]) --> Q1[/"Q1: Execution Mode<br>Autonomous / Interactive /<br>Mostly Autonomous"/]

    Q1 --> Q2[/"Q2: Parallelization<br>Maximize / Conservative /<br>Ask Each Time"/]

    Q2 --> Q3[/"Q3: Worktree Strategy<br>Single / Per Track / None"/]

    Q3 --> Q4[/"Q4: Post-Implementation<br>Offer Options / Auto PR /<br>Just Stop"/]

    Q4 --> Q5[/"Q5: Dialectic Mode<br>None / Roundtable"/]

    Q5 --> DIALECTIC{Dialectic Mode<br>!= None?}

    DIALECTIC -->|Yes| Q6[/"Q6: Dialectic Level<br>Planning Only /<br>Planning + Gates / Full"/]
    DIALECTIC -->|No| Q7

    Q6 --> Q7[/"Q7: Token Enforcement<br>Work-Item / Gate /<br>Every Step"/]

    Q7 --> COUPLING{Worktree ==<br>per_parallel_track?}
    COUPLING -->|Yes| FORCE_PARALLEL["Force parallelization<br>= maximize"]
    COUPLING -->|No| STORE

    FORCE_PARALLEL --> STORE[Store all in<br>SESSION_PREFERENCES]
    STORE --> DONE([Preferences Complete]):::success

    classDef success fill:#51cf66,stroke:#37b24d,color:#fff
```

---

## Complexity Classification Detail (Section 0.7)

Derives complexity tier from mechanical heuristics. The executor cannot override the matrix; only the user can confirm or change the tier.

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{Decision}
        L3([Terminal])
        L4[/"User Input"/]
        L5[Quality Gate]:::gate
    end

    START([Enter 0.7]) --> HEURISTICS[Step 1: Run<br>Mechanical Heuristics]

    HEURISTICS --> H1["H1: File Count<br>grep -rl pattern | wc -l"]
    HEURISTICS --> H2["H2: Behavioral Change?<br>New endpoints, UI, API?"]
    HEURISTICS --> H3["H3: Test Impact<br>grep -rl module tests/ | wc -l"]
    HEURISTICS --> H4["H4: Structural Change?<br>New files, schemas, migrations?"]
    HEURISTICS --> H5["H5: Integration Points<br>grep -rl import module | wc -l"]

    H1 --> MATRIX[Step 2: Derive Tier<br>from Matrix]
    H2 --> MATRIX
    H3 --> MATRIX
    H4 --> MATRIX
    H5 --> MATRIX

    MATRIX --> TRIVIAL_CHECK{All Trivial<br>Conditions Met?}:::gate

    TRIVIAL_CHECK -->|"Only literal values AND<br>no structure change AND<br>zero behavior impact AND<br>zero test changes"| TIER_TRIVIAL[Tier: TRIVIAL]
    TRIVIAL_CHECK -->|Any condition unmet| TIER_HIGHER{Classify by<br>Heuristic Ranges}

    TIER_HIGHER -->|"1-5 files, minor behavior,<br>less than 3 tests, 0-2 integrations"| TIER_SIMPLE[Tier: SIMPLE]
    TIER_HIGHER -->|"3-15 files, behavior change,<br>3+ tests, new interfaces"| TIER_STANDARD[Tier: STANDARD]
    TIER_HIGHER -->|"10+ files, significant change,<br>new suites, 5+ integrations"| TIER_COMPLEX[Tier: COMPLEX]

    TIER_TRIVIAL --> PRESENT[Step 3: Present<br>Heuristic Results Table]
    TIER_SIMPLE --> PRESENT
    TIER_STANDARD --> PRESENT
    TIER_COMPLEX --> PRESENT

    PRESENT --> CONFIRM{/"User: Confirm<br>or Override?"/}

    CONFIRM -->|Confirm| STORE[Store in<br>SESSION_PREFERENCES]
    CONFIRM -->|Override with reason| STORE

    STORE --> ROUTE{Step 4: Route<br>by Tier}

    ROUTE -->|TRIVIAL| EXIT(["Exit Skill<br>(direct change)"]):::success
    ROUTE -->|SIMPLE| SIMPLE([Lightweight Research<br>then /feature-implement]):::success
    ROUTE -->|STANDARD| RESEARCH([/feature-research<br>Phase 1]):::success
    ROUTE -->|COMPLEX| RESEARCH

    classDef gate fill:#ff6b6b,stroke:#d63031,color:#fff
    classDef success fill:#51cf66,stroke:#37b24d,color:#fff
```

### Tier Classification Matrix

| Tier | File Count | Behavioral Change | Test Impact | Structural Change | Integration Points |
|---|---|---|---|---|---|
| TRIVIAL | 1-2 | None | 0 test files | None (values only) | 0 |
| SIMPLE | 1-5 | Minor or none | < 3 test files | None or minimal | 0-2 |
| STANDARD | 3-15 | Yes | 3+ test files | Some new files/interfaces | 2-5 |
| COMPLEX | 10+ | Significant | New test suites needed | New modules/schemas | 5+ |

Tie-breaking rule: classify UP when heuristics span tiers.
