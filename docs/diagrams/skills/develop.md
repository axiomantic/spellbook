<!-- diagram-meta: {"source": "skills/develop/SKILL.md", "source_hash": "sha256:1964c2a15065e6c830a702a7418243990aabb68abd327b103be7f4f0b9ca970b", "generated_at": "2026-05-25T01:32:42Z", "generator": "generate_diagrams.py"} -->
# Diagram: develop

## Overview: `develop` Skill — Phase Routing

High-level phase routing, escape hatch handling, and need-flag dispatch.

```mermaid
flowchart TD
    classDef subagent fill:#4a9eff,color:#fff,stroke:#2d7dd2
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc5555
    classDef terminal fill:#51cf66,color:#fff,stroke:#3da854

    INVOKE(["/develop invoked"]) --> P0["Phase 0\nConfiguration Wizard"]
    P0 --> EH{"Escape hatch?"}

    EH -->|"design doc · treat-as-ready"| SKIP_P2["Skip Phase 2"]
    EH -->|"design doc · review-first"| AT_22["Phase 2 at step 2.2"]
    EH -->|"impl plan · treat-as-ready"| SKIP_P23["Skip Phase 2 + Phase 3"]
    EH -->|"impl plan · review-first"| AT_32["Phase 3 at step 3.2"]
    EH -->|"no hatch"| FLAGS{"Need-flags set?"}

    FLAGS -->|"all zero"| DIRECT["Direct / Lightweight Path"]
    FLAGS -->|"needs_research"| P1["Phase 1: Research"]
    FLAGS -->|"needs_design only"| P2["Phase 2: Design"]
    FLAGS -->|"needs_infrastructure only"| P3["Phase 3: Impl Planning"]

    P1 --> P15["Phase 1.5: Informed Discovery"]
    P15 --> DA["1.6 · devil's-advocate subagent\nif needs_design OR needs_research"]
    DA --> ND{"needs_design?"}
    ND -->|"yes"| P2
    ND -->|"no"| NI{"needs_infrastructure?"}
    NI -->|"yes"| P3
    NI -->|"no"| P4["Phase 4: Implementation"]

    P2 --> P3
    P3 --> P4
    SKIP_P2 --> P3
    AT_22 --> P2
    SKIP_P23 --> P4
    AT_32 --> P3

    P4 --> DONE(["Branch Complete"])
    DIRECT --> DONE

    class DA subagent
    class DONE terminal

    subgraph LEGEND["Legend"]
        LS["Subagent Dispatch"]:::subagent
        LG["Quality Gate"]:::gate
        LT(["Terminal"]):::terminal
    end
```

---

## Phase 0: Configuration Wizard

Steps 0.1–0.7: escape hatch detection, motivation/scope clarification, preferences storage, continuation detection, refactoring mode, and need-flag wizard.

```mermaid
flowchart TD
    classDef subagent fill:#4a9eff,color:#fff,stroke:#2d7dd2
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc5555
    classDef terminal fill:#51cf66,color:#fff,stroke:#3da854

    S(["Phase 0 Start"]) --> P01["0.1 · Escape Hatch Detection\nLook for existing design doc or impl plan"]
    P01 --> EH{"Hatch found?"}
    EH -->|"yes"| EH_R(["Route per escape hatch\n→ see Overview diagram"])
    EH -->|"no"| P02["0.2 · Motivation Clarification\nAsk WHY the feature is needed"]
    P02 --> P03["0.3 · Core Feature Clarification\nAsk WHAT the feature does"]
    P03 --> P04["0.4 · Workflow Preferences\nStore SESSION_PREFERENCES\nautonomous mode · verbosity\nworktree prefs · review floor"]
    P04 --> P05["0.5 · Continuation Detection\nLoad workflow_state — check for prior session"]
    P05 --> CONT{"Prior session\ndetected?"}
    CONT -->|"yes"| RESUME(["Resume from last checkpoint"])
    CONT -->|"no"| P06["0.6 · Detect Refactoring Mode\nIs this a pure refactor?"]
    P06 --> P07["0.7 · Need-Flag Wizard"]

    P07 --> QR{"Q-RESEARCH\nExternal knowledge needed?"}
    QR -->|"yes · needs_research=true"| QD{"Q-DESIGN\nArchitecture decisions needed?"}
    QR -->|"no"| QD
    QD -->|"yes · needs_design=true"| QI{"Q-INFRA\nNew infrastructure needed?"}
    QD -->|"no"| QI
    QI -->|"yes · needs_infrastructure=true\nalso sets needs_design=true"| QSZ{"Q-SIZE\nScope estimate"}
    QI -->|"no"| QSZ
    QSZ --> DONE(["Phase 0 Complete\nRoute to first active phase"])

    class EH_R,RESUME,DONE terminal

    subgraph LEGEND["Legend"]
        LS["Subagent Dispatch"]:::subagent
        LG["Quality Gate"]:::gate
        LT(["Terminal"]):::terminal
    end
```

---

## Phases 1 + 1.5: Research and Informed Discovery

Phase 1 (steps 1.1–1.4) and Phase 1.5 (steps 1.5.0–1.6). Both phases require `needs_research`. Contains two never-bypassable quality gates and two subagent-backed verification steps.

```mermaid
flowchart TD
    classDef subagent fill:#4a9eff,color:#fff,stroke:#2d7dd2
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc5555
    classDef terminal fill:#51cf66,color:#fff,stroke:#3da854

    S(["Phase 1 Start\n(needs_research = true)"]) --> P11["1.1 · Research Strategy Planning\nSelect scope, sources, and questions"]
    P11 --> P12["1.2 · Execute Research\nexplore subagent"]
    P12 --> G14["GATE 1.4 · Research Quality Score = 100%\n12 quality functions evaluated"]
    G14 --> RQ{"Pass?"}
    RQ -->|"no"| P12
    RQ -->|"yes"| P15["Phase 1.5 · Informed Discovery\nMemory-primed context load"]

    P15 --> P150["1.5.0 · Disambiguation Session\nResolve ambiguous terms from research"]
    P150 --> P151["1.5.1 · Generate 7-Category Discovery Questions\nfunctional · non-functional · integration\nsecurity · performance · ops · UX"]
    P151 --> P152["1.5.2 · Conduct Discovery Wizard\nInteractive Q&A with user"]
    P152 --> P153["1.5.3 · Build Glossary\nCanonical terms and definitions"]
    P153 --> P154["1.5.4 · Synthesize design_context\nComposite from research + discovery"]
    P154 --> G155["GATE 1.5.5 · Completeness Score = 100%\n12 validation functions evaluated"]
    G155 --> CQ{"Pass?"}
    CQ -->|"no · insufficiently complete"| P152
    CQ -->|"yes"| P156["1.5.6 · Create Understanding Document\nFormal artifact capturing design_context"]
    P156 --> P157["1.5.7 · Dehallucination Gate\ndehallucination subagent"]
    P157 --> DH{"Clean?"}
    DH -->|"no · hallucinations found"| P154
    DH -->|"yes"| P16["1.6 · Devil's Advocate\ndevils-advocate subagent"]
    P16 --> DONE(["Phases 1 + 1.5 Complete\n→ Phase 2, 3, or 4"])

    class P12,P157,P16 subagent
    class G14,G155 gate
    class DONE terminal

    subgraph LEGEND["Legend"]
        LS["Subagent Dispatch"]:::subagent
        LG["Quality Gate"]:::gate
        LT(["Terminal"]):::terminal
    end
```

---

## Phases 2 + 3: Design and Implementation Planning

Phase 2 (needs_design) and Phase 3 (needs_design OR needs_infrastructure). Both include subagent-authored artifacts, review subagents, user-approval gates, and fix loops.

```mermaid
flowchart TD
    classDef subagent fill:#4a9eff,color:#fff,stroke:#2d7dd2
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc5555
    classDef terminal fill:#51cf66,color:#fff,stroke:#3da854

    P2S(["Phase 2 Start\n(needs_design = true)"]) --> P21["2.1 · Design Creation\ndesign-exploration subagent (SYNTHESIS MODE)"]
    P21 --> P22["2.2 · Design Review\nreviewing-design-docs subagent"]
    P22 --> G23["GATE 2.3 · User Design Approval"]
    G23 --> UA{"Approved?"}
    UA -->|"no"| P24["2.4 · Fix Design\nexecuting-plans subagent"]
    P24 --> P22
    UA -->|"yes"| P25["2.5 · Assumption Verification\nfact-checking subagent"]
    P25 --> P2E(["Phase 2 Complete"])

    P3S(["Phase 3 Start\n(needs_design OR needs_infrastructure)"]) --> P31["3.1 · Plan Creation\nwriting-plans subagent"]
    P31 --> P32["3.2 · Plan Review\nreviewing-impl-plans subagent"]
    P32 --> G33["GATE 3.3 · User Plan Approval\nper mode: autonomous vs interactive"]
    G33 --> PA{"Approved?"}
    PA -->|"no"| P34["3.4 · Fix Plan\nexecuting-plans subagent"]
    P34 --> P32
    PA -->|"yes"| P345["3.4.5 · Execution Mode Analysis\ndirect vs delegated"]
    P345 --> P3E(["Phase 3 Complete\n→ Phase 4"])

    P2E --> P3S

    class P21,P22,P24,P25 subagent
    class P31,P32,P34 subagent
    class G23,G33 gate
    class P2E,P3E terminal

    subgraph LEGEND["Legend"]
        LS["Subagent Dispatch"]:::subagent
        LG["Quality Gate"]:::gate
        LT(["Terminal"]):::terminal
    end
```

---

## Phase 4: Implementation

Steps 4.0–4.7: environment gate, worktree setup, task batching, per-task loop (TDD → audit → review → fact-check), smart merge, and end-of-phase gates.

```mermaid
flowchart TD
    classDef subagent fill:#4a9eff,color:#fff,stroke:#2d7dd2
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc5555
    classDef terminal fill:#51cf66,color:#fff,stroke:#3da854

    P4S(["Phase 4 Start"]) --> P40["4.0 · Pre-impl Environment Gate\nVerify environment ready"]
    P40 --> P41["4.1 · Setup Worktree(s)"]
    P41 --> BATCH{"Task count?"}
    BATCH -->|"< 8"| M1["direct or delegated\none dispatch per gate per task"]
    BATCH -->|"8–12"| M2["delegated\nbatched per-domain dispatches"]
    BATCH -->|"> 12 or ≥2 tracks"| M3["delegated (aggressive)\nbatched; ledger checkpoint +\nFollow-up Tasks if context exhausted"]
    M1 --> LOOP["Next task"]
    M2 --> LOOP
    M3 --> LOOP

    LOOP --> T43["4.3 · test-driven-development subagent"]
    T43 --> T44["4.4 · Completion Audit\ninline audit prompt"]
    T44 --> T45["4.5 · Code Review\nrequesting-code-review subagent"]
    T45 --> T451["4.5.1 · Per-Task Fact-Check\nfact-checking subagent"]
    T451 --> MORE{"More tasks?"}
    MORE -->|"yes"| LOOP
    MORE -->|"no"| MERGE["4.2.5 · Smart Merge\nif per_parallel_track mode"]

    MERGE --> G461["4.6.1 · Comprehensive Audit\ninline audit prompt"]
    G461 --> G462["4.6.2 · Run Test Suite"]
    G462 --> TQ{"Tests pass?"}
    TQ -->|"no"| TFIX["Fix failures"]
    TFIX --> G462
    TQ -->|"yes"| G463["4.6.3 · Green Mirage Check\nauditing-green-mirage subagent"]
    G463 --> GQ{"Clean?"}
    GQ -->|"no"| GFIX["Address findings"]
    GFIX --> G462
    GQ -->|"yes"| G464["4.6.4 · Comprehensive Fact-Check\nfact-checking subagent\nif needs_research OR needs_design"]
    G464 --> G465["4.6.5 · Pre-PR Fact-Check\nfact-checking subagent"]
    G465 --> P47["4.7 · Branch Finishing\nfinishing-a-development-branch subagent"]
    P47 --> DONE(["Phase 4 Complete — Branch Ready"])

    class T43,T45,T451 subagent
    class G463,G464,G465,P47 subagent
    class G461,G462,T44 gate
    class DONE terminal

    subgraph LEGEND["Legend"]
        LS["Subagent Dispatch"]:::subagent
        LG["Quality Gate"]:::gate
        LT(["Terminal"]):::terminal
    end
```

---

## Direct / Lightweight Path

Fast path when all need-flags are zero. Three guardrails re-route to the flagged path if thresholds are breached; otherwise proceeds under a lighter review floor.

```mermaid
flowchart TD
    classDef subagent fill:#4a9eff,color:#fff,stroke:#2d7dd2
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc5555
    classDef terminal fill:#51cf66,color:#fff,stroke:#3da854

    DPS(["Direct Path Start\nall need-flags = zero"]) --> D1["D1 · Lightweight Research\nexplore subagent · ≤5 files · 1-paragraph summary"]
    D1 --> GD1{"Output > 1 paragraph\nOR > 5 files read?"}
    GD1 -->|"yes"| RF1["Set needs_research\nre-run flag wizard"]
    RF1 --> REFLAG(["Return to flagged path"])
    GD1 -->|"no"| D2["D2 · Inline Plan\n≤5 numbered steps · user confirms"]
    D2 --> GD2{"Plan > 5 steps?"}
    GD2 -->|"yes"| RF2["Set surfaced flag\nre-run flag wizard"]
    RF2 --> REFLAG
    GD2 -->|"no"| D3["D3 · Implementation\nunder lighter review floor"]
    D3 --> GD3{"> 5 impl files\nOR > 3 test files?"}
    GD3 -->|"yes"| RF3["Pause · re-flag"]
    RF3 --> REFLAG
    GD3 -->|"no"| EOGATE["End-of-phase gates\n4.6.1 comprehensive audit · 4.6.2 test suite\n4.6.3 green mirage · 4.7 branch finishing\n4.6.4 fact-check OMITTED (no research/design flags)"]
    EOGATE --> DONE(["Direct Path Complete"])

    class D1 subagent
    class REFLAG,DONE terminal

    subgraph REVIEWFLOOR["Lighter Review Floor (zero flags)"]
        RFA["Per task: 4.3 TDD · 4.5 code review · 4.5.1 fact-check"]:::subagent
        RFB["End-of-phase: 4.6.1 audit · 4.6.2 tests · 4.6.3 green mirage · 4.7 finish"]:::gate
        RFC["4.6.4 comprehensive fact-check — OMITTED (no research/design flags)"]
    end

    subgraph LEGEND["Legend"]
        LS["Subagent Dispatch"]:::subagent
        LG["Quality Gate"]:::gate
        LT(["Terminal"]):::terminal
    end
```

---

## Cross-Reference Table

| Overview Node | Detail Diagram | Steps Covered |
|---|---|---|
| Phase 0: Configuration Wizard | Phase 0 diagram | 0.1 escape hatch · 0.2 WHY · 0.3 WHAT · 0.4 SESSION_PREFERENCES · 0.5 continuation · 0.6 refactor mode · 0.7 flag wizard (Q-RESEARCH / Q-DESIGN / Q-INFRA / Q-SIZE) |
| Phase 1: Research | Phases 1 + 1.5 diagram | 1.1 strategy · 1.2 explore subagent · GATE 1.4 research quality (100%) |
| Phase 1.5: Informed Discovery | Phases 1 + 1.5 diagram | 1.5.0 disambiguation · 1.5.1 7-category questions · 1.5.2 discovery wizard · 1.5.3 glossary · 1.5.4 design_context synthesis · GATE 1.5.5 completeness (100%) · 1.5.6 understanding doc · 1.5.7 dehallucination subagent · 1.6 devil's-advocate subagent |
| Phase 2: Design | Phases 2 + 3 diagram | 2.1 design-exploration (SYNTHESIS) · 2.2 reviewing-design-docs · GATE 2.3 user approval · 2.4 executing-plans (fix loop) · 2.5 fact-checking (assumption verification) |
| Phase 3: Impl Planning | Phases 2 + 3 diagram | 3.1 writing-plans · 3.2 reviewing-impl-plans · GATE 3.3 user approval (per mode) · 3.4 executing-plans (fix loop) · 3.4.5 execution mode analysis |
| Phase 4: Implementation | Phase 4 diagram | 4.0 env gate · 4.1 worktrees · task batching (<8 / 8–12 / >12) · per-task loop (4.3 TDD · 4.4 inline audit · 4.5 code review · 4.5.1 fact-check) · 4.2.5 smart merge · 4.6.1 comprehensive audit · 4.6.2 test suite · 4.6.3 green mirage · 4.6.4 comprehensive fact-check · 4.6.5 pre-PR fact-check · 4.7 finishing |
| Direct / Lightweight Path | Direct Path diagram | D1 lightweight research (explore, ≤5 files) · D2 inline plan (≤5 steps) · D3 implementation (lighter review floor) · three guardrails that re-route to flagged path on threshold breach |
