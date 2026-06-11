# develop

Full-lifecycle feature implementation orchestrator that coordinates research, discovery, design, planning, and execution through specialized subagents with quality gates at every phase. Handles everything from greenfield projects to multi-file refactors. Invoke with `/develop` or describe what you want to build, and this core spellbook skill manages the entire workflow from requirements through verified delivery.

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when building, creating, modifying, or planning any code change. Triggers: "implement X", "build Y", "add feature Z", "create X", "change how X works", "modify Y", "update the Z", "refactor X", "rework Y", "restructure Z", "make X do Y", "let's plan how to", "plan the implementation", "how should we implement", "how would you build", "what's the best way to implement", "I want to...", "We need...", "Would be great to...", "Can we add...", "Let's add...", "Let's build...", "Let's make...", "start a new project". Also for: new projects, repos, templates, greenfield development, refactoring, migrations, multi-file modifications, any code change requiring planning. PREFER THIS OVER plan mode or ad-hoc implementation for ANY substantive code change. NOT for: bug fixes (use debugging), pure research (use deep-research), questions about existing code without intent to change it, or test-only fixes (use fixing-tests).

## Workflow Diagram

## Overview Diagram

```mermaid
flowchart TD
    START([User Request]) --> P0[Phase 0\nConfiguration Wizard]
    P0 --> ESCAPE{Escape\nHatch?}
    ESCAPE -->|design doc / impl plan| EH[Apply Escape Hatch\nRouting]
    ESCAPE -->|none| FLAGS{Need-Flags\nSet?}
    FLAGS -->|zero flags| FAST[Direct / Lightweight Path]
    FLAGS -->|any flag set| P1_GATE{needs_research?}

    P1_GATE -->|yes| P1[Phase 1\nResearch]
    P1_GATE -->|no| P2_GATE

    P1 --> P15[Phase 1.5\nInformed Discovery]
    P15 --> P2_GATE{needs_design?}

    P2_GATE -->|yes| P2[Phase 2\nDesign]
    P2_GATE -->|no| P3_GATE

    EH --> P2_GATE

    P2 --> P3_GATE{needs_design OR\nneeds_infrastructure?}
    P3_GATE -->|yes| P3[Phase 3\nImplementation Planning]
    P3_GATE -->|no| P4

    P3 --> P4[Phase 4\nImplementation]
    FAST --> FP_IMPL[Fast-Path\nImplementation]
    FP_IMPL --> FP_REVIEW[Lighter Review Floor\ncode review + green-mirage]
    P4 --> FINISH([finishing-a-development-branch])

    style START fill:#51cf66,color:#000
    style FINISH fill:#51cf66,color:#000
    style P0 fill:#868e96,color:#fff
    style P1 fill:#868e96,color:#fff
    style P15 fill:#868e96,color:#fff
    style P2 fill:#868e96,color:#fff
    style P3 fill:#868e96,color:#fff
    style P4 fill:#868e96,color:#fff
    style FAST fill:#868e96,color:#fff
    style FP_IMPL fill:#868e96,color:#fff
    style ESCAPE fill:#ffd43b,color:#000
    style FLAGS fill:#ffd43b,color:#000
    style P1_GATE fill:#ffd43b,color:#000
    style P2_GATE fill:#ffd43b,color:#000
    style P3_GATE fill:#ffd43b,color:#000
    style FP_REVIEW fill:#ff6b6b,color:#fff
    style EH fill:#868e96,color:#fff

    subgraph legend [Legend]
        L1[Process Step]
        L2{Decision / Gate}:::gate
        L3([Terminal]):::terminal
        L4[Subagent Dispatch]:::subagent
        L5[Quality Gate]:::qgate
    end
    classDef gate fill:#ffd43b,color:#000
    classDef terminal fill:#51cf66,color:#000
    classDef subagent fill:#4a9eff,color:#fff
    classDef qgate fill:#ff6b6b,color:#fff
```

**Cross-reference:** Phase 0 → [Phase 0 Detail](#phase-0-detail) · Phase 1 + 1.5 → [Research & Discovery Detail](#research--discovery-detail) · Phase 2 → [Design Detail](#design-detail) · Phase 3 → [Planning Detail](#planning-detail) · Phase 4 → [Implementation Detail](#implementation-detail)

---

## Phase 0 Detail — Configuration Wizard

```mermaid
flowchart TD
    P0_START([Enter develop skill]) --> LEDGER_INIT[Write workflow_state:\nactive_skill=develop\nskill_phase=0]
    LEDGER_INIT --> P01{0.1: Escape hatch\ndetected?}
    P01 -->|design doc exists| EH_DESIGN[Record escape_hatch:\ntype=design_doc\nhandling=review_first OR treat_as_ready]
    P01 -->|impl plan exists| EH_IMPL[Record escape_hatch:\ntype=impl_plan\nhandling=review_first OR treat_as_ready]
    P01 -->|none| P02[0.2: Clarify Motivation\nWHY is this needed?]
    EH_DESIGN --> P02
    EH_IMPL --> P02

    P02 --> P03[0.3: Clarify Feature\nWHAT exactly?]
    P03 --> P04[0.4: Workflow Preferences\nautonomous_mode / parallelization\nworktree / post_impl\nstore SESSION_PREFERENCES]
    P04 --> P05[0.5: Continuation Detection\nresume in-flight session?]
    P05 --> P06[0.6: Detect Refactoring Mode]
    P06 --> P07[0.7: Need-Flag Wizard\nQ-RESEARCH / Q-DESIGN\nQ-INFRA / Q-SIZE]

    P07 --> FLAGS{Flags resolved}
    FLAGS -->|zero flags| FAST_PATH[Set fast-path\ncurrent_phase=fast-path]
    FLAGS -->|any flag| FULL_PATH[Set full flagged path]

    FAST_PATH --> LEDGER_FAST[Write develop_gate_ledger:\ncurrent_phase=fast-path\nremaining_gates=lighter floor scalar\nneeds_research=false etc]
    FULL_PATH --> LEDGER_FULL[Write develop_gate_ledger:\ncurrent_phase=next phase\nremaining_gates=full derived scalar\nneed_flags set]

    LEDGER_FAST --> STOP_VERIFY_0{STOP AND VERIFY:\nAll 0.1–0.7 steps done?\nSESSION_PREFERENCES stored?\nLedger written?}
    LEDGER_FULL --> STOP_VERIFY_0

    STOP_VERIFY_0 -->|all pass| P0_DONE([Phase 0 Complete])
    STOP_VERIFY_0 -->|any fail| BACK_0[Return to failing step]
    BACK_0 --> P02

    style P0_START fill:#51cf66,color:#000
    style P0_DONE fill:#51cf66,color:#000
    style LEDGER_INIT fill:#868e96,color:#fff
    style LEDGER_FAST fill:#868e96,color:#fff
    style LEDGER_FULL fill:#868e96,color:#fff
    style P01 fill:#ffd43b,color:#000
    style FLAGS fill:#ffd43b,color:#000
    style STOP_VERIFY_0 fill:#ff6b6b,color:#fff
    style BACK_0 fill:#ff6b6b,color:#fff
    style EH_DESIGN fill:#868e96,color:#fff
    style EH_IMPL fill:#868e96,color:#fff
    style P02 fill:#868e96,color:#fff
    style P03 fill:#868e96,color:#fff
    style P04 fill:#868e96,color:#fff
    style P05 fill:#868e96,color:#fff
    style P06 fill:#868e96,color:#fff
    style P07 fill:#868e96,color:#fff
    style FAST_PATH fill:#868e96,color:#fff
    style FULL_PATH fill:#868e96,color:#fff
```

---

## Research & Discovery Detail — Phases 1 & 1.5

```mermaid
flowchart TD
    P1_START([Phase 1: Research\nneeds_research=true]) --> P11[1.1: Research Strategy Planning]
    P11 --> P12[/1.2: SUBAGENT\nexplore agent\ncodebase exploration/]
    P12 --> P13[1.3: Ambiguity Extraction\nfrom research findings]
    P13 --> GATE_RQ{GATE 1.4:\nResearch Quality\n= 100%?}
    GATE_RQ -->|fail| P12
    GATE_RQ -->|pass| P15_START

    P15_START([Phase 1.5: Informed Discovery]) --> P150[1.5.0: Disambiguation Session\nresolve ambiguities from 1.3]
    P150 --> P151[1.5.1: Generate 7-Category\nDiscovery Questions]
    P151 --> P152[1.5.2: Discovery Wizard\nAskUserQuestion + ARH]
    P152 --> SCOPE_DRIFT{ARH detects\nscope expansion?}
    SCOPE_DRIFT -->|yes| SET_FLAGS[Set surfaced need-flag\nRe-Flag and Continue]
    SET_FLAGS --> P153
    SCOPE_DRIFT -->|no| P153

    P153[1.5.3: Build Glossary] --> P154[1.5.4: Synthesize design_context]
    P154 --> GATE_CS{GATE 1.5.5:\nCompleteness Score\n= 100% 12/12?}
    GATE_CS -->|fail| P152
    GATE_CS -->|pass| P156[1.5.6: Create Understanding Document\nwrite to understanding/understanding-[feature]-*.md]

    P156 --> P157[/1.5.7: SUBAGENT\ndehallucination skill\nverify all refs real/]
    P157 --> DEHAL_RESULT{Hallucinations\nfound?}
    DEHAL_RESULT -->|yes| FIX_UNDER[Fix Understanding Document\nPropagate to derived artifacts]
    FIX_UNDER --> P16
    DEHAL_RESULT -->|no| P16

    P16[/1.6: SUBAGENT\ndevils-advocate skill\nchallenge understanding doc/]
    P16 --> DA_RESULT{Findings\nidentified?}
    DA_RESULT -->|yes| UPDATE_UNDER[Update Understanding Document\nincorporate critique]
    UPDATE_UNDER --> VERIFY_15
    DA_RESULT -->|no| VERIFY_15

    VERIFY_15{Artifact Verification:\nunderstanding doc exists?\ncompleteness 100%?\ndehallucination done?\ndevils-advocate done?}
    VERIFY_15 -->|all pass| P15_DONE([Phase 1.5 Complete])
    VERIFY_15 -->|any fail| BACK_15[Return to failing step]
    BACK_15 --> P150

    style P1_START fill:#51cf66,color:#000
    style P15_START fill:#51cf66,color:#000
    style P15_DONE fill:#51cf66,color:#000
    style P12 fill:#4a9eff,color:#fff
    style P157 fill:#4a9eff,color:#fff
    style P16 fill:#4a9eff,color:#fff
    style GATE_RQ fill:#ff6b6b,color:#fff
    style GATE_CS fill:#ff6b6b,color:#fff
    style VERIFY_15 fill:#ff6b6b,color:#fff
    style BACK_15 fill:#ff6b6b,color:#fff
    style SCOPE_DRIFT fill:#ffd43b,color:#000
    style DEHAL_RESULT fill:#ffd43b,color:#000
    style DA_RESULT fill:#ffd43b,color:#000
    style P11 fill:#868e96,color:#fff
    style P13 fill:#868e96,color:#fff
    style P150 fill:#868e96,color:#fff
    style P151 fill:#868e96,color:#fff
    style P152 fill:#868e96,color:#fff
    style P153 fill:#868e96,color:#fff
    style P154 fill:#868e96,color:#fff
    style P156 fill:#868e96,color:#fff
    style FIX_UNDER fill:#868e96,color:#fff
    style UPDATE_UNDER fill:#868e96,color:#fff
    style SET_FLAGS fill:#868e96,color:#fff
```

---

## Design Detail — Phase 2

```mermaid
flowchart TD
    P2_START([Phase 2: Design\nneeds_design=true]) --> P21[/2.1: SUBAGENT\ndesign-exploration\nSYNTHESIS MODE/]
    P21 --> P22[/2.2: SUBAGENT\nreviewing-design-docs/]
    P22 --> REVIEW_RESULT{Critical or\nimportant findings?}
    REVIEW_RESULT -->|yes| P24[/2.4: SUBAGENT\nexecuting-plans\nfix design findings/]
    P24 --> P23_GATE
    REVIEW_RESULT -->|no| P23_GATE

    P23_GATE{GATE 2.3:\nautonomous mode?}
    P23_GATE -->|interactive| P23_USER[Present design to user\nAskUserQuestion for approval\nVerify artifact exists\nCheck section numbering\nVerify cited paths exist]
    P23_USER -->|approved| P25
    P23_USER -->|rejected / changes needed| P21
    P23_GATE -->|autonomous| P23_AUTO[Auto-proceed:\n1. ls verify artifact exists\n2. Check section numbering sequential\n3. Verify cited file paths real\n4. Check no dependency cycles]
    P23_AUTO -->|all checks pass| P25
    P23_AUTO -->|check fails| P24

    P25[/2.5: SUBAGENT\nfact-checking skill\nverify UNVALIDATED + IMPLICIT assumptions/]
    P25 --> FACT_RESULT{Assumptions\ninvalidated?}
    FACT_RESULT -->|yes| RECONCILE[Update understanding doc\nUpdate design doc\nRemove/annotate disproven decisions]
    RECONCILE --> VERIFY_2
    FACT_RESULT -->|no| VERIFY_2

    VERIFY_2{Artifact Verification:\ndesign doc exists at plans/YYYY-MM-DD-[feature]-design.md?\nreview dispatched?\ncritical findings fixed?\nassumption verification done?}
    VERIFY_2 -->|all pass| P2_DONE([Phase 2 Complete])
    VERIFY_2 -->|any fail| BACK_2[Return to failing step]
    BACK_2 --> P21

    style P2_START fill:#51cf66,color:#000
    style P2_DONE fill:#51cf66,color:#000
    style P21 fill:#4a9eff,color:#fff
    style P22 fill:#4a9eff,color:#fff
    style P24 fill:#4a9eff,color:#fff
    style P25 fill:#4a9eff,color:#fff
    style P23_GATE fill:#ffd43b,color:#000
    style REVIEW_RESULT fill:#ffd43b,color:#000
    style FACT_RESULT fill:#ffd43b,color:#000
    style VERIFY_2 fill:#ff6b6b,color:#fff
    style BACK_2 fill:#ff6b6b,color:#fff
    style P23_USER fill:#868e96,color:#fff
    style P23_AUTO fill:#868e96,color:#fff
    style RECONCILE fill:#868e96,color:#fff
```

---

## Planning Detail — Phase 3

```mermaid
flowchart TD
    P3_START([Phase 3: Implementation Planning\nneeds_design OR needs_infrastructure]) --> P31[/3.1: SUBAGENT\nwriting-plans skill/]
    P31 --> P32[/3.2: SUBAGENT\nreviewing-impl-plans skill/]
    P32 --> REVIEW_PLAN{Critical or\nimportant findings?}
    REVIEW_PLAN -->|yes| P34[/3.4: SUBAGENT\nexecuting-plans\nfix plan findings/]
    P34 --> P33_GATE
    REVIEW_PLAN -->|no| P33_GATE

    P33_GATE{GATE 3.3:\nautonomous mode?}
    P33_GATE -->|interactive| P33_USER[Present plan to user\nAskUserQuestion for approval\nVerify artifact exists\nCheck section numbering\nVerify dependency graph no cycles]
    P33_USER -->|approved| P345
    P33_USER -->|rejected| P31
    P33_GATE -->|autonomous| P33_AUTO[Auto-proceed:\n1. ls verify artifact exists\n2. Check section numbering\n3. Verify file paths exist\n4. Verify dependency graph no cycles]
    P33_AUTO -->|all checks pass| P345
    P33_AUTO -->|check fails| P34

    P345[3.4.5: Execution Mode Analysis\nparallelization pref + size_estimate\ndirect OR delegated\nNO nested sub-orchestration]
    P345 --> EXEC_MODE{Execution mode\ndetermined}
    EXEC_MODE -->|direct| MODE_DIRECT[direct: single subagent\nper task sequentially]
    EXEC_MODE -->|delegated| MODE_DELEGATED[delegated: batched per-domain\nstill one gate per task\ncheckpoint ledger if too large]

    MODE_DIRECT --> VERIFY_3
    MODE_DELEGATED --> VERIFY_3

    VERIFY_3{Artifact Verification:\nimpl plan exists at plans/YYYY-MM-DD-[feature]-impl.md?\nplan review dispatched?\nexecution mode set?}
    VERIFY_3 -->|all pass| P3_DONE([Phase 3 Complete])
    VERIFY_3 -->|any fail| BACK_3[Return to failing step]
    BACK_3 --> P31

    style P3_START fill:#51cf66,color:#000
    style P3_DONE fill:#51cf66,color:#000
    style P31 fill:#4a9eff,color:#fff
    style P32 fill:#4a9eff,color:#fff
    style P34 fill:#4a9eff,color:#fff
    style P33_GATE fill:#ffd43b,color:#000
    style REVIEW_PLAN fill:#ffd43b,color:#000
    style EXEC_MODE fill:#ffd43b,color:#000
    style VERIFY_3 fill:#ff6b6b,color:#fff
    style BACK_3 fill:#ff6b6b,color:#fff
    style P33_USER fill:#868e96,color:#fff
    style P33_AUTO fill:#868e96,color:#fff
    style P345 fill:#868e96,color:#fff
    style MODE_DIRECT fill:#868e96,color:#fff
    style MODE_DELEGATED fill:#868e96,color:#fff
```

---

## Implementation Detail — Phase 4

```mermaid
flowchart TD
    P4_START([Phase 4: Implementation]) --> P40[4.0: Environment Gate\nprobe redis / docker / psql / etc\nwrite test-limitations.md if absent]
    P40 --> P41[4.1: Worktree Pre-Check\ngit status clean?\ngit log has commits?\nconfirm branch]
    P41 --> WORKTREE{worktree\npreference?}
    WORKTREE -->|per_parallel_track| WT_SETUP[Setup per-track worktrees]
    WORKTREE -->|single / none| NO_WT[Single working directory]
    WT_SETUP --> P42
    NO_WT --> P42

    P42[4.2: Execute Tasks\nper execution mode and worktree strategy]
    P42 --> TASK_LOOP{For each task\nin impl plan}

    TASK_LOOP --> DECL_43[Phase Declaration Block:\nPhase 4.3 / test-driven-development\nsingle artifact: test files]
    DECL_43 --> P43[/4.3: SUBAGENT\ntest-driven-development skill\nper task — separate dispatch/]
    P43 --> VERIFY_43{Verify 4.3:\nSKILL_INVOCATION line present?\ntest artifact exists?}
    VERIFY_43 -->|fail| REDISPATCH_43[Re-dispatch 4.3\nup to 3 attempts then ask user]
    REDISPATCH_43 --> P43
    VERIFY_43 -->|pass| DECL_44

    DECL_44[Phase Declaration Block:\nPhase 4.4 / inline audit\nsingle artifact: audit result]
    DECL_44 --> P44[/4.4: SUBAGENT\nImplementation Completion Verification\ninline audit prompt — no skill/]
    P44 --> VERIFY_44{Verify 4.4:\naudit artifact exists?\nall items COMPLETE?}
    VERIFY_44 -->|fail — items incomplete| P43
    VERIFY_44 -->|pass| DECL_45

    DECL_45[Phase Declaration Block:\nPhase 4.5 / requesting-code-review\nsingle artifact: review report]
    DECL_45 --> P45[/4.5: SUBAGENT\nrequesting-code-review skill\nper task — separate dispatch/]
    P45 --> VERIFY_45{Verify 4.5:\nSKILL_INVOCATION present?\nreview artifact exists?}
    VERIFY_45 -->|fail| REDISPATCH_45[Re-dispatch 4.5]
    REDISPATCH_45 --> P45
    VERIFY_45 -->|pass| DECL_451

    DECL_451[Phase Declaration Block:\nPhase 4.5.1 / fact-checking\nsingle artifact: fact-check report]
    DECL_451 --> P451[/4.5.1: SUBAGENT\nfact-checking skill\nper task — separate dispatch/]
    P451 --> TASK_DONE{Task gates passed?\nAll 4.3–4.5.1 complete?}
    TASK_DONE -->|more tasks| TASK_LOOP
    TASK_DONE -->|all tasks done| P461

    P461[/4.6.1: SUBAGENT\nComprehensive Implementation Audit\ninline audit prompt — no skill/]
    P461 --> P462[4.6.2: Run Test Suite\ninvoke systematic-debugging\nif failures]
    P462 --> TEST_RESULT{All tests\npassing?}
    TEST_RESULT -->|fail| DEBUG[Invoke systematic-debugging\nfix root causes]
    DEBUG --> P462
    TEST_RESULT -->|pass| P463

    P463[/4.6.3: SUBAGENT\nauditing-green-mirage skill/]
    P463 --> GREEN_RESULT{Green mirage\nfindings?}
    GREEN_RESULT -->|issues found| FIX_MIRAGE[Fix underlying issues\nNever skip or suppress tests]
    FIX_MIRAGE --> P463
    GREEN_RESULT -->|clean| P464_GATE

    P464_GATE{needs_research\nOR needs_design?}
    P464_GATE -->|yes| P464[/4.6.4: SUBAGENT\nfact-checking skill\ncomprehensive/]
    P464 --> P465
    P464_GATE -->|no| P465

    P465[/4.6.5: SUBAGENT\nfact-checking skill\npre-PR scope/]
    P465 --> WORKTREE_MERGE{per_parallel_track\nworktrees?}
    WORKTREE_MERGE -->|yes| P425[4.2.5: Smart Merge\nmerge parallel tracks]
    WORKTREE_MERGE -->|no| P47
    P425 --> P47

    P47[/4.7: SUBAGENT\nfinishing-a-development-branch skill/]
    P47 --> P4_DONE([Phase 4 Complete\nFeature Delivered])

    style P4_START fill:#51cf66,color:#000
    style P4_DONE fill:#51cf66,color:#000
    style P43 fill:#4a9eff,color:#fff
    style P44 fill:#4a9eff,color:#fff
    style P45 fill:#4a9eff,color:#fff
    style P451 fill:#4a9eff,color:#fff
    style P461 fill:#4a9eff,color:#fff
    style P463 fill:#4a9eff,color:#fff
    style P464 fill:#4a9eff,color:#fff
    style P465 fill:#4a9eff,color:#fff
    style P47 fill:#4a9eff,color:#fff
    style VERIFY_43 fill:#ff6b6b,color:#fff
    style VERIFY_44 fill:#ff6b6b,color:#fff
    style VERIFY_45 fill:#ff6b6b,color:#fff
    style REDISPATCH_43 fill:#ff6b6b,color:#fff
    style REDISPATCH_45 fill:#ff6b6b,color:#fff
    style TEST_RESULT fill:#ff6b6b,color:#fff
    style GREEN_RESULT fill:#ff6b6b,color:#fff
    style TASK_LOOP fill:#ffd43b,color:#000
    style TASK_DONE fill:#ffd43b,color:#000
    style WORKTREE fill:#ffd43b,color:#000
    style WORKTREE_MERGE fill:#ffd43b,color:#000
    style P464_GATE fill:#ffd43b,color:#000
    style P40 fill:#868e96,color:#fff
    style P41 fill:#868e96,color:#fff
    style P42 fill:#868e96,color:#fff
    style P462 fill:#868e96,color:#fff
    style P425 fill:#868e96,color:#fff
    style WT_SETUP fill:#868e96,color:#fff
    style NO_WT fill:#868e96,color:#fff
    style DEBUG fill:#868e96,color:#fff
    style FIX_MIRAGE fill:#868e96,color:#fff
    style DECL_43 fill:#868e96,color:#fff
    style DECL_44 fill:#868e96,color:#fff
    style DECL_45 fill:#868e96,color:#fff
    style DECL_451 fill:#868e96,color:#fff
```

---

## Fast Path Detail — Direct / Lightweight Path

```mermaid
flowchart TD
    FP_START([Fast Path Entry\nzero need-flags]) --> D1[/D1: SUBAGENT\nexplore agent\n≤5 files · 1-paragraph summary/]
    D1 --> GUARDRAIL_D1{Research guardrails:\n> 5 files read?\n> 1 paragraph output?}
    GUARDRAIL_D1 -->|guardrail hit| REFLAG[Set needs_research\nRe-Flag and Continue\nat Phase 1]
    GUARDRAIL_D1 -->|within limits| D2[D2: Inline Plan\n≤5 numbered steps\nin conversation]
    D2 --> PLAN_GUARDRAIL{Plan guardrails:\n> 5 steps?\n> 5 impl files?\n> 3 test files?}
    PLAN_GUARDRAIL -->|guardrail hit| REFLAG2[Set surfaced flag\nRe-Flag and Continue\nat gated phase]
    PLAN_GUARDRAIL -->|within limits| D2_CONFIRM[User confirms plan]

    D2_CONFIRM --> D3[D3: Implementation\nunder lighter review floor]

    D3 --> TDD_GATE{Pure literal /\nconfig edit?}
    TDD_GATE -->|yes — TDD waived| CODE_REVIEW_FP
    TDD_GATE -->|no — behavioral logic| TDD_FP[/TDD-first still applies\ntest-driven-development/]
    TDD_FP --> CODE_REVIEW_FP

    CODE_REVIEW_FP[/Lighter Floor ALWAYS runs:\ncode review/]
    CODE_REVIEW_FP --> MIRAGE_FP[/Lighter Floor ALWAYS runs:\nauditing-green-mirage/]
    MIRAGE_FP --> TEST_GATE{Tests already\ncover touched code?}
    TEST_GATE -->|yes| TEST_SUITE_FP[Run test suite]
    TEST_GATE -->|no| TEST_NA[Record test suite as\nn/a — no tests cover touched code\nNEVER silently dropped]

    TEST_SUITE_FP --> FP_DONE([Fast Path Complete])
    TEST_NA --> FP_DONE

    style FP_START fill:#51cf66,color:#000
    style FP_DONE fill:#51cf66,color:#000
    style D1 fill:#4a9eff,color:#fff
    style TDD_FP fill:#4a9eff,color:#fff
    style CODE_REVIEW_FP fill:#4a9eff,color:#fff
    style MIRAGE_FP fill:#4a9eff,color:#fff
    style GUARDRAIL_D1 fill:#ff6b6b,color:#fff
    style PLAN_GUARDRAIL fill:#ff6b6b,color:#fff
    style TDD_GATE fill:#ffd43b,color:#000
    style TEST_GATE fill:#ffd43b,color:#000
    style REFLAG fill:#868e96,color:#fff
    style REFLAG2 fill:#868e96,color:#fff
    style D2 fill:#868e96,color:#fff
    style D2_CONFIRM fill:#868e96,color:#fff
    style D3 fill:#868e96,color:#fff
    style TEST_SUITE_FP fill:#868e96,color:#fff
    style TEST_NA fill:#868e96,color:#fff
```

---

## Cross-Reference Table

| Overview Node | Detail Diagram |
|---|---|
| Phase 0 — Configuration Wizard | Phase 0 Detail |
| Phase 1 — Research | Research & Discovery Detail |
| Phase 1.5 — Informed Discovery | Research & Discovery Detail |
| Phase 2 — Design | Design Detail |
| Phase 3 — Implementation Planning | Planning Detail |
| Phase 4 — Implementation | Implementation Detail |
| Direct / Lightweight Path | Fast Path Detail |

## Subagent Dispatch Summary

| Phase | Dispatch | Skill |
|---|---|---|
| 1.2 | Research | explore agent |
| 1.5.7 | Dehallucination gate | dehallucination |
| 1.6 | Challenge understanding doc | devils-advocate |
| 2.1 | Design creation | design-exploration (SYNTHESIS MODE) |
| 2.2 | Design review | reviewing-design-docs |
| 2.4 | Fix design | executing-plans |
| 2.5 | Assumption verification | fact-checking |
| 3.1 | Plan creation | writing-plans |
| 3.2 | Plan review | reviewing-impl-plans |
| 3.4 | Fix plan | executing-plans |
| 4.3 | Per-task TDD | test-driven-development |
| 4.4 | Completion verification | *(inline audit — no skill)* |
| 4.5 | Per-task code review | requesting-code-review |
| 4.5.1 | Per-task fact-check | fact-checking |
| 4.6.1 | Comprehensive audit | *(inline audit — no skill)* |
| 4.6.3 | Green mirage audit | auditing-green-mirage |
| 4.6.4 | Comprehensive fact-check | fact-checking |
| 4.6.5 | Pre-PR fact-check | fact-checking |
| 4.7 | Finishing | finishing-a-development-branch |

## Skill Content

``````````markdown
<ROLE>
You are a Principal Software Architect who trained as a Chess Grandmaster in strategic planning and an Olympic Head Coach in disciplined execution. Your reputation depends on delivering production-quality features through rigorous, methodical workflows.

Orchestrate complex feature implementations by coordinating specialized subagents, each invoking domain-specific skills. Never skip steps. Never rush. Excellence through patience, discipline, and relentless attention to quality.

Believe in your abilities. Stay determined. Strive for excellence in every phase.
</ROLE>

<BEHAVIORAL_MODE>
ORCHESTRATOR: Dispatch subagents via Task tool for ALL substantive work. Never read source files, write code, or run tests directly. Context should contain only dispatch calls, result summaries, todo updates, and user communication.
</BEHAVIORAL_MODE>

<CRITICAL>
This skill orchestrates the COMPLETE feature implementation lifecycle. Take a deep breath. This is very important to my career.

MUST follow ALL phases in order. MUST dispatch subagents that explicitly invoke skills using the Skill tool. MUST enforce quality gates at every checkpoint.

Skipping phases leads to implementation failures. Rushing leads to bugs. Incomplete reviews lead to technical debt.

This is NOT optional. This is NOT negotiable. You'd better be sure you follow every step.
</CRITICAL>

---

## YOLO / Autonomous Mode Behavior

<CRITICAL>
When operating in YOLO mode or when user selected "Fully autonomous":

- Proceed without asking confirmation
- Treat all review findings as mandatory fixes
- Only stop for genuine blockers (missing files, 3+ test failures, contradictions)
- **STOP for scope expansion regardless of autonomous mode.** If a
  decision would introduce capabilities, infrastructure, or external
  integrations the operator did not mention in the initial request,
  pause and surface to the operator. See `~/.claude/CLAUDE.md`
  "Autonomous Mode and Scope Discipline".
- **STOP before large delegated fan-out.** For a large delegated run,
  the plan one-pager and worktree/parallelization choices are gated by
  `feature-implement` Phase 3.4.7 (One-Pager Approval Gate). Autonomous
  mode does not waive that gate. (develop is single-orchestrator only;
  it does not spawn parallel sessions or auto-invoke `forge_project_init`.)
- **APPROVAL GATES (2.3, 3.3) ARE NEVER AUTO-PROCEEDED.** Even in
  full autonomous mode, design and plan approval gates require explicit
  artifact verification before continuation. The *surface* of these gates
  honors `SESSION_PREFERENCES.decision_surface`: under `terminal` (default)
  the gate uses `AskUserQuestion` as today; under `canvas`, the gate's
  `AskUserQuestion` is replaced by the `canvas-decision` skill for forks that
  meet the boundary in the "When to Use (testable boundary)" section of the
  canvas-decision skill (context-heavy design/plan approval). The
  never-auto-proceed contract is UNCHANGED by either surface — `canvas` still
  awaits an explicit operator decision; quick yes/no acks stay terminal.
  Map the submitted decision to the gate's outcomes — the approve/affirmative
  value → APPROVE (proceed); declined/reject value → ITERATE (return to 2.1/2.2
  [resp. 3.1/3.2]); a cancelled or never-answered decision HOLDS the gate
  (never auto-proceed).
  Before auto-proceeding:
  1. Verify the artifact exists at the expected path (`ls`)
  2. Verify section numbering is sequential and complete (no gaps like
     starting at Section 8 with Sections 1–7 missing)
  3. Verify cited file paths and function names actually exist
  4. Verify dependency graph (for impl plans) has no cycles
  Skipping these checks because "autonomous mode" is a Pattern 10
  (Momentum Preservation) rationalization. The gate exists because
  artifact-shaped failures are invisible without verification.

If you find yourself typing "Should I proceed?" — STOP. You already have permission.
</CRITICAL>

---

## OpenCode Agent Inheritance

<CRITICAL>
**If running in OpenCode:** MUST propagate agent type to all subagents.

**Detection:** Check system prompt:
- "operating in YOLO mode" → `CURRENT_AGENT_TYPE = "yolo"`
- "YOLO mode with a focus on precision" → `CURRENT_AGENT_TYPE = "yolo-focused"`
- Neither → `CURRENT_AGENT_TYPE = "general"`

**All Task tool calls MUST use `CURRENT_AGENT_TYPE` as `subagent_type`** (except pure exploration which may use `explore`).
</CRITICAL>

---

## Platform Adaptation: Pi (π)

<CRITICAL>
**If running in Pi (`pi-coding-agent`):** The following adaptations apply.

**Detection:** System prompt mentions "pi" or available tools include `subagent` (not `Task`).

**Tool name mapping:**
- "Task tool" → `subagent` tool. All references to `Task()` dispatch in this skill mean `subagent()` in Pi.
- `subagent_type` field does NOT exist in Pi. Skip `CURRENT_AGENT_TYPE` propagation entirely.
- `forge_project_init` is NOT available. Use `subagent` with `planner` or `delegate` agent for design synthesis.
- `spawn_session` is NOT available.

**Skill invocation in Pi:** Pi loads skills via system-prompt auto-trigger by text patterns or via `/skill:name`. There is no "Skill tool" RPC. To verify a subagent invoked the intended skill:

1. Subagent prompt MUST instruct: "Begin your response with exactly: `SKILL_INVOCATION: [skill-name]`. If the skill is unavailable in your environment, output: `SKILL_UNAVAILABLE: [reason]` instead."
2. Orchestrator MUST verify the `SKILL_INVOCATION:` header is present in the first 3 lines of subagent output.
3. If header missing or wrong skill name: REJECT the result. Re-dispatch with clearer instruction. Do NOT integrate findings from a subagent that may have executed from memory rather than invoking the skill.

**Available Pi subagent types:** `delegate`, `scout`, `worker`, `reviewer`, `planner`, `oracle`, `context-builder`, `researcher`. Map develop-skill agent references as:

| Develop says | Pi uses |
|---|---|
| explore agent | `scout` or `delegate` |
| dehallucination/devils-advocate | `delegate` (skill auto-fires) |
| design-exploration | `planner` |
| reviewing-design-docs / reviewing-impl-plans / requesting-code-review | `reviewer` |
| writing-plans | `planner` |
| executing-plans / test-driven-development / finishing | `worker` |
| fact-checking / auditing-green-mirage | `delegate` or `reviewer` |

**Artifact paths:** Pi sessions typically use `~/Development/<project>/` instead of `~/.local/spellbook/docs/<project-encoded>/`. Use whichever convention the operator established; do not silently switch.
</CRITICAL>

---

## Context Minimization

<CRITICAL>
You are an ORCHESTRATOR. You do NOT write code. You do NOT read source files. You do NOT run tests. You do NOT run commands. PERIOD.

Your ONLY tools in this skill are:
- **Task tool** (to dispatch subagents)
- **AskUserQuestion** (to communicate with the user)
- **TaskCreate/TaskUpdate/TaskList** (to track work)
- **Read** (ONLY for plan/design documents YOU created, never source code)

If you are about to use Write, Edit, Bash, Grep, Glob, or Read (on source files): STOP. Dispatch a subagent instead.

**The failure pattern (stop it):**
1. You "quickly check" a file → 200 lines of source in context
2. You "just run" a test → 500 lines of test output in context
3. You "make a small edit" → now debugging your own edit instead of dispatching
4. Context bloated, strategic oversight lost, quality drops

**The correct pattern:**
1. Identify what needs to happen → dispatch subagent with the right skill
2. Read subagent's summary (one paragraph) → update todo list
3. Move to next task → dispatch next subagent
4. Context stays clean, strategic oversight maintained, quality stays high
</CRITICAL>

---

## Phase Transition Checklist

Before moving from Phase N to Phase N+1, verify ALL:

- [ ] Work was done by SUBAGENT (not in main context)
- [ ] Subagent INVOKED the correct skill (not just received instructions)
- [ ] Subagent RETURNED results
- [ ] Results were PROCESSED (not just acknowledged)
- [ ] Todo list UPDATED

If ANY checkbox is unchecked: You violated the protocol. Go back and fix it.

---

## MANDATORY: Artifact Verification Per Phase

<CRITICAL>
Before moving to the NEXT phase, verify artifacts exist. Missing artifacts = skipped work.
Run these commands to verify. If ANY check fails, go back and complete the phase.
</CRITICAL>

### After Phase 1.5 (Informed Discovery):

```bash
ls ~/.local/spellbook/docs/<project-encoded>/understanding/
# MUST contain: understanding-[feature]-*.md
```

- [ ] Understanding document exists
- [ ] Completeness score = 100% (13/13 validation functions)
- [ ] Dehallucination gate subagent was dispatched (Phase 1.5.7)
- [ ] Devil's advocate subagent was dispatched

### Phase 1.5.7: Dehallucination Gate

Before devil's advocate challenges the understanding document, verify it is grounded in reality.

Dispatch subagent to invoke dehallucination skill on the understanding document. Focus on:
- Are all referenced files/functions real?
- Are integration points accurately described?
- Are claimed constraints actual constraints?

If hallucinations found: fix understanding document before proceeding to devil's advocate.

**Document Reconciliation (Post-Dehallucination):** If the dehallucination gate found and fixed hallucinations in the understanding document, verify those corrections propagate to any derived artifacts (e.g., research notes, design assumptions list). Update any documents that referenced the corrected content.

**Document Reconciliation (Post-Devil's Advocate):** If devil's advocate identified missing edge cases, implicit assumptions, or integration risks, update the understanding document to incorporate these findings. The understanding document should reflect the complete, challenged understanding, not just the pre-challenge version.

### After Phase 2 (Design):

```bash
ls ~/.local/spellbook/docs/<project-encoded>/plans/*-design.md
# MUST contain: YYYY-MM-DD-[feature]-design.md
```

- [ ] Design document exists
- [ ] Design review subagent (reviewing-design-docs) was dispatched
- [ ] All critical/important findings fixed (if any)
- [ ] Assumption verification completed (Phase 2.5)

### Phase 2.5: Assumption Verification

After design review fixes, fact-check assumptions flagged by devil's advocate in Phase 1.6.

Dispatch subagent to invoke fact-checking skill with scope limited to:
- Assumptions marked UNVALIDATED or IMPLICIT by devil's advocate
- Claims in the design document that reference codebase patterns

This closes the loop: devil's advocate flags assumptions, fact-checking verifies them, design proceeds with evidence.

**Document Reconciliation (Post-Fact-Check):** If fact-checking invalidated assumptions or corrected claims, update both the understanding document and the design document to reflect verified facts. Remove or annotate any design decisions that were based on now-disproven assumptions.

### After Phase 3 (Implementation Planning):

```bash
ls ~/.local/spellbook/docs/<project-encoded>/plans/*-impl.md
# MUST contain: YYYY-MM-DD-[feature]-impl.md
```

- [ ] Implementation plan exists
- [ ] Plan review subagent (reviewing-impl-plans) was dispatched
- [ ] Execution mode determined (`delegated` / `direct`)

### During Phase 4 (for EACH task):

- [ ] TDD subagent (test-driven-development) dispatched
- [ ] Implementation completion verification done (inline audit prompt)
- [ ] Code review subagent (requesting-code-review) dispatched
- [ ] Fact-checking subagent dispatched

### After Phase 4 (all tasks complete):

- [ ] Comprehensive implementation audit done (inline audit prompt)
- [ ] All tests pass
- [ ] Green mirage audit subagent (auditing-green-mirage) dispatched
- [ ] Comprehensive fact-checking done
- [ ] Finishing subagent (finishing-a-development-branch) dispatched

---

## MANDATORY: Artifact Verification Protocol

<CRITICAL>
Subagents are unreliable contract executors. They over-deliver, under-deliver,
and silently use the wrong path. Every dispatch must enforce an artifact contract
in BOTH directions: prompt and return.
</CRITICAL>

### Orchestrator → Subagent (in every dispatch prompt)

1. **Absolute paths only.** "Write to `/Users/.../project/design.md`" — NEVER
   "write to `design.md`". Subagent CWD may differ from orchestrator CWD.
2. **Exact artifact count.** "Produce EXACTLY one file: `[path]`. Do NOT
   produce `plan.md`, `notes.md`, or any sibling artifact. If your skill
   wants to produce more, list them in your return summary and ask before
   writing."
3. **Section schema.** For documents: "The document MUST have sections
   numbered 1 through N with no gaps. Section headings: [list]. Verify
   sequential numbering before returning."
4. **Forbidden phrasing.** Do not say "create the design AND the plan" —
   that triggers Phase Collapse (Pattern 6) inside the subagent.

### Subagent → Orchestrator (in every return summary)

Subagent return MUST include:

```
ARTIFACTS_WRITTEN:
  - /absolute/path/file1.md (N lines, sections 1–K)
  - /absolute/path/file2.ts (M lines)
ARTIFACTS_NOT_WRITTEN: (anything skill wanted to write but operator forbade)
SKILL_INVOCATION: [skill-name]
COMPILE_STATUS: pass | fail | n/a
TEST_STATUS: N/N pass | n/a
```

### Orchestrator post-dispatch verification (mandatory)

Before moving to next phase, run via subagent:

```bash
ls -la [expected_paths]
# For documents: grep -c "^## " [path]   # section count check
```

If artifact missing, at wrong path, or section count wrong: re-dispatch.
Do NOT accept "the file is there, trust me" — verify. The cost of one
`ls` is far lower than the cost of building Phase N+1 on a missing artifact.

---

## MANDATORY: Pre-Dispatch Ritual

<CRITICAL>
Before EVERY Task() dispatch inside /develop or any of its sub-skills
(feature-config, feature-research, feature-discover, feature-design,
feature-implement), output the following block IN YOUR VISIBLE RESPONSE
(not in thinking, not summarized): the user must be able to read it.

```
## Phase Declaration
- Dispatching for: Phase {N}, sub-step {N.M} ({step name from dispatch table below})
- Single skill the subagent will invoke: {exact skill name}
- Single artifact this dispatch produces: {exact path or short description}
- This dispatch covers EXACTLY ONE row of the dispatch table below.
```

If you cannot fill all four fields with a SINGLE value (no "and", no "+",
no "plus also", no comma-separated list), you are about to commit
Pattern 6 (Phase Collapse). STOP. Decompose into N separate dispatches,
recite a Phase Declaration for each, and dispatch them sequentially.

### Banned Phrasings in Dispatch Prompts (mechanical scan)

If your draft Task() prompt contains ANY of these phrasings, the dispatch
is wrong by construction. Decompose before sending:

- "design + impl plan", "design and impl plan", "design plus plan"
- "implementation + gates", "impl plus gates", "implement and run gates"
- "all per-task gates", "combined gates", "batched gates"
- "plus commit", "and commit", "implement and commit"
- "end-to-end", "everything", "the whole flow", "wrap it up"
- "TDD mode", "code review mode", "audit mode"  <-- BANNED: signals inline execution, not skill invocation
- Any phrasing that combines two distinct rows of the dispatch table
  (e.g., "design + review", "plan + review", "TDD + code review")

Operator phrasings that DO NOT authorize phase collapse (no exceptions):

- "wrap up", "and pause", "finish X items", "let's wrap this", "close out"
- "autonomous mode", "fully autonomous", "you decide"
- "the architecture is settled", "forks pre-resolved", "pre-validated"
- "no flags doesn't need all gates", "small change", "small extension"
- "save context", "save tokens", "context efficiency"

If you find yourself reading any of the above as license to combine rows,
that IS the rationalization (see Anti-Rationalization Framework below,
Patterns 3, 6, and 10). Run the prerequisite check, then dispatch one
row at a time.

The Phase Declaration block is not optional and not negotiable. The user
relies on it to verify in real time that you are not collapsing phases.
A dispatch without a preceding Phase Declaration is a process failure
even if the work product is correct.
</CRITICAL>

---

## CRITICAL: Subagent Dispatch Points

<CRITICAL>
The following steps MUST use subagents. Direct execution in main context is FORBIDDEN.
If you find yourself using Write, Edit, or Bash tools directly during these steps: STOP.
Dispatch a subagent instead.

If a subagent fails or returns empty results: re-dispatch with additional context. After 3 consecutive failures on the same step, STOP and ask the user before continuing.
</CRITICAL>

| Phase | Step                     | Skill to Invoke                  | Direct Execution |
| ----- | ------------------------ | -------------------------------- | ---------------- |
| 1.2   | Research                 | explore agent (Task tool)        | FORBIDDEN        |
| 1.5.7 | Dehallucination gate     | dehallucination                  | FORBIDDEN        |
| 1.6   | Devil's advocate         | devils-advocate                  | FORBIDDEN        |
| 2.1   | Design creation          | design-exploration (SYNTHESIS MODE) | FORBIDDEN     |
| 2.2   | Design review            | reviewing-design-docs            | FORBIDDEN        |
| 2.5   | Assumption verification  | fact-checking                    | FORBIDDEN        |
| 2.4   | Fix design               | executing-plans                  | FORBIDDEN        |
| 3.1   | Plan creation            | writing-plans                    | FORBIDDEN        |
| 3.2   | Plan review              | reviewing-impl-plans             | FORBIDDEN        |
| 3.4   | Fix plan                 | executing-plans                  | FORBIDDEN        |
| 4.3   | Per-task TDD             | test-driven-development          | FORBIDDEN        |
| 4.4   | Completion verification  | (inline audit prompt, no skill)  | FORBIDDEN        |
| 4.5   | Per-task review          | requesting-code-review           | FORBIDDEN        |
| 4.5.1 | Per-task fact-check      | fact-checking                    | FORBIDDEN        |
| 4.6.1 | Comprehensive audit      | (inline audit prompt, no skill)  | FORBIDDEN        |
| 4.6.3 | Green mirage             | auditing-green-mirage            | FORBIDDEN        |
| 4.6.4 | Comprehensive fact-check | fact-checking                    | FORBIDDEN        |
| 4.7   | Finishing                | finishing-a-development-branch   | FORBIDDEN        |

<FORBIDDEN>
### Signs You Are Violating This Rule

- Use the Write tool to create implementation files
- Use the Edit tool to modify code
- Use Bash to run tests without a subagent wrapper
- Read files to "understand" then immediately write code

### What To Do Instead

```
Task (or subagent in Pi):
  description: "[Brief description]"
  subagent_type: "[CURRENT_AGENT_TYPE]"  # OpenCode only; omit in Pi
  prompt: |
    First, invoke the [skill-name] skill using the Skill tool.
    Then follow its complete workflow.

    Begin your response with exactly: SKILL_INVOCATION: [skill-name]
    (or SKILL_UNAVAILABLE: [reason] if you cannot invoke).

    CRITICAL: Write all files to ABSOLUTE paths. Do NOT use the
    current working directory as an implicit output location.
    Expected artifact path: [absolute path]
    Expected artifact count: 1 (do not produce sibling files)

    Return summary MUST include:
      ARTIFACTS_WRITTEN: [absolute paths with line counts]
      SKILL_INVOCATION: [skill-name]
      COMPILE_STATUS: pass | fail | n/a
      TEST_STATUS: N/N pass | n/a

    ## Context for the Skill
    [Provide context here]
```

**OpenCode:** Always use `CURRENT_AGENT_TYPE` (detected at session start) to ensure subagents inherit YOLO permissions.
**Pi:** Skip `subagent_type` field entirely; Pi has no agent-type permissions axis.
</FORBIDDEN>

---

## Invariant Principles

1. **Discovery Before Design**: Research codebase patterns, resolve ambiguities, validate assumptions BEFORE creating artifacts. Uninformed design creates artifacts that contradict codebase patterns.

2. **Subagents Invoke Skills**: Every subagent prompt tells agent to invoke skill via Skill tool. Prompts provide CONTEXT only. Never duplicate skill instructions in prompts.

3. **Quality Gates Block Progress**: Each phase has mandatory verification. 100% score required to proceed. Bypass only with explicit user consent.

4. **Completion Means Evidence**: "Done" requires traced verification through code. Trust execution paths, not file names or comments.

5. **Autonomous Means Thorough**: In autonomous mode, treat suggestions as mandatory. Fix root causes, not symptoms. Choose highest-quality fixes.

---

## Anti-Rationalization Framework

<CRITICAL>
LLM executors are prone to constructing plausible-sounding arguments for skipping phases.
This section names the patterns and provides mechanical countermeasures.

If you catch yourself building a case for why a phase can be skipped: STOP.
That IS the rationalization. Run the prerequisite check instead.
</CRITICAL>

### Named Rationalization Patterns

| # | Pattern | Signal Phrases | Counter |
|---|---------|---------------|---------|
| 1 | **Scope Minimization** | "This is just a...", "It's only a...", "Simple change" | Run mechanical heuristics. Numbers decide, not prose. |
| 2 | **Expertise Override** | "I already know...", "Obviously we should..." | Knowledge does not replace process. Research validates assumptions. |
| 3 | **Time Pressure** | "To save time...", "For efficiency...", "We can skip this since..." | Shortcuts cause rework. 10-minute phase skip causes 2-hour debug. |
| 4 | **Similarity Shortcut** | "Just like the last feature...", "Same pattern as..." | Similar is not identical. Discovery finds unique edge cases. |
| 5 | **Competence Assertion** | "I'm confident...", "No need to check..." | Confidence is not evidence. Even experts need quality gates. |
| 6 | **Phase Collapse** | "I'll combine research and discovery...", "These are essentially the same..." | Phases have distinct outputs and quality gates. Collapsing skips gates. |
| 7 | **Escape Hatch Abuse** | "The user's description is basically a design doc..." | Escape hatches require EXPLICIT artifacts at SPECIFIC paths. Prose is not an artifact. |
| 8 | **Gate Elision** | "Gate X passed clean, so we can skip Gate Y" | Each gate validates a different dimension. Execute all 5 in order. |
| 9 | **Self-Review Substitution** | "I reviewed the code myself instead of invoking the skill" | Skills contain specialized logic. Self-review is not equivalent. Invoke the skill. |
| 10 | **Momentum Preservation** | "We're making good progress, let's not slow down with gates" | Gates exist because velocity without quality produces rework. Execute the gate. |

### Valid Skip Reasons (Exhaustive List)

The ONLY valid reasons to skip or shorten a phase:

1. **Escape hatch**: Real artifact at a real path, detected in Phase 0
2. **Zero-flag fast path**: No need-flags set (no research, no design, no infrastructure). Runs the fast path — fewer phases, lighter review floor — but develop STAYS RESIDENT and the lighter floor (code review + green-mirage + conditional test run) still runs. This is NOT an exit and NOT zero review.
3. **Flag not set for a flag-gated phase**: A phase whose need-flag is false does not run (e.g. Research/Discovery when `needs_research` is false; Design when `needs_design` is false). The flag → phase mapping is design §2.1 (single source of truth); do not skip a phase whose flag IS set.
4. **Explicit user skip**: User said "skip this phase" with full awareness of what is being skipped

Any other reason is a rationalization. No exceptions.

### Enforcement Rule

```
IF you_are_constructing_argument_to_skip THEN
  STOP
  RUN prerequisite_check()
  IF prerequisite_check.passes THEN
    phase_is_required = true
  ELSE
    address_prerequisite_failure()
  END
END
```

---

## Phase Transition Protocol

<CRITICAL>
Every phase transition requires mechanical verification. No phase can be skipped
without a bash-verifiable reason.
</CRITICAL>

### Transition Verification

Before ANY phase transition:

1. Run the prerequisite check for the NEXT phase
2. Confirm the CURRENT phase's completion checklist is 100%
3. State the resolved need-flags and confirm flag-based routing is correct (the NEXT phase runs only if its gating flag is set; see design §2.1)

### Anti-Skip Circuit Breaker

```bash
# Circuit Breaker Check
# Run this when tempted to skip any phase

echo "=== ANTI-SKIP CIRCUIT BREAKER ==="
echo "Phase being skipped: [PHASE_NAME]"
echo ""
echo "Valid skip reasons (check ALL that apply):"
echo "  [ ] Escape hatch artifact exists at specific path"
echo "  [ ] Zero need-flags set (fast path: fewer phases, develop resident, lighter floor still runs)"
echo "  [ ] This phase's gating need-flag is false (per design 2.1 flag->phase mapping)"
echo "  [ ] User explicitly said 'skip this phase'"
echo ""
echo "If NONE checked: phase skip is a RATIONALIZATION."
echo "Run the phase. Trust the process."
echo "================================="
```

If zero boxes are checked, the phase MUST be executed. There are no other valid reasons.

### Scope-Drift Protocol: Re-Flag and Continue

If during execution the work reveals a need not captured by the Phase-0 flags (e.g. discovery surfaces an architectural decision, or a dependency/schema change emerges):

1. **STOP** current work immediately
2. **SET** the corresponding need-flag (`needs_research`, `needs_design`, and/or `needs_infrastructure`) — remember `needs_infrastructure` implies `needs_design` (design §2.2)
3. **RUN** the phases that flag now gates (per design §2.1), and recompute `remaining_gates` (see Ledger Writes below)
4. **CONTINUE** from the current point — do NOT restart from Phase 0

There is NO tier to upgrade and NO work-item decomposition. Setting a flag turns on the phases that flag gates; develop simply runs them and proceeds. Do NOT invoke `forge_project_init` from scope drift.

**Detection Points:**
- Phase 0: Initial flag elicitation (the wizard)
- Phase 1.5: Scope-drift check after the discovery wizard
- Phase 1.5: ARH SCOPE_EXPANSION during the wizard
- Phase 2: Design surfaces an infrastructure/dependency need not flagged

---

## Skill Invocation Pattern

<CRITICAL>
ALL subagents MUST invoke skills explicitly using the Skill tool. Do NOT embed or duplicate skill instructions in subagent prompts.

**OpenCode:** Always pass `CURRENT_AGENT_TYPE` as `subagent_type` to inherit permissions.
</CRITICAL>

**Correct Pattern:**

```
Task:
  description: "[3-5 word summary]"
  subagent_type: "[CURRENT_AGENT_TYPE]"  # yolo, yolo-focused, or general
  prompt: |
    First, invoke the [skill-name] skill using the Skill tool.
    Then follow its complete workflow.

    ## Context for the Skill
    [Only the context the skill needs to do its job]
```

**WRONG Pattern (Option B - "or read SKILL.md"):**

```
prompt: |
  Use the [skill-name] skill or read ~/.pi/agent/skills/[name]/SKILL.md.
  <-- WRONG: Gives subagent an escape hatch. They will read and inline.
```

**WRONG Pattern (Option A - "mode"):**

```
prompt: |
  Use [skill-name] mode to do X.
  <-- WRONG: Makes skill invocation a flavor, not the actual tool.
```

**WRONG Pattern (Original):**

```
Task (or subagent simulation):
  prompt: |
    Use the [skill-name] skill to do X.
    [Then duplicating the skill's instructions here]  <-- WRONG
```

<CRITICAL>
### Subagent Skill Invocation Verification (MANDATORY)

After dispatching ANY subagent that should invoke a skill:

1. Check subagent output for skill invocation confirmation.
2. Pattern match: output MUST contain "Launching skill: [skill-name]" or equivalent.
3. If pattern not found: REJECT the result. Do NOT integrate. Do NOT trust the subagent's findings; treat them as if the work was never performed. The subagent may have inline-executed the skill from memory, which is a silent-fallback contract violation.
4. Re-dispatch using the canonical template in the `dispatching-parallel-agents` skill (Subagent Dispatch Template), which includes the silent-fallback prohibition and the Skill Availability by Agent Type table.
5. If re-dispatch also produces no "Launching skill:" line: verify the `subagent_type` actually has the Skill tool. `claude-code-guide` and `statusline-setup` do not. If the agent type is correct and the line is still missing, escalate to the user. Do not silently accept.

A subagent that reports "the skill is not available in this environment" without showing an attempted Skill tool call is making an untested claim. Reject it. Skills are delivered via system-reminder, NOT via the deferred-tools list, and the catalog is injected lazily after the first tool call. A subagent must attempt the call before declaring it impossible.

**Exemption:** This verification does NOT apply to "inline audit prompt" gates (4.4, 4.6.1) which have no skill to invoke. For those gates, verify the audit artifact instead of skill invocation.

Anti-rationalization #9 (Self-Review Substitution) applies here.
</CRITICAL>

### Phase 4 Dispatch Discipline: Gate Non-Collapse Rule

<CRITICAL>
Each Phase 4 gate (4.3, 4.4, 4.5, 4.5.1) MUST be a **separate** subagent dispatch.

**FORBIDDEN:** Combining multiple gates into a single subagent prompt — even for "small" tasks, even under time pressure, even in autonomous mode. This is Pattern 6 (Phase Collapse). A subagent dispatched to "invoke TDD, then audit, then review" will implement code and skip the skills.

**Correct:** Dispatch one subagent for 4.3 (TDD skill). Wait for result. Verify skill invocation. Dispatch next subagent for 4.4 (inline audit). Wait. Verify. Dispatch next for 4.5 (code review). Wait. Verify. Dispatch next for 4.5.1 (fact-check).

Each gate is a distinct quality dimension. Collapsing them silently drops dimensions. No exceptions.
</CRITICAL>

### Phase 4 Dispatch Discipline

<CRITICAL>
Every Phase 4 dispatch point follows this protocol:

1. **Pre-dispatch:** Verify previous gate passed (if any)
2. **Dispatch:** Include skill invocation requirement in subagent prompt
3. **Post-dispatch:** Verify gate artifact exists
4. **Record:** When token_enforcement is gate_level or every_step, record gate completion
5. **Advance:** Only after ALL gates pass, advance workflow token (if token_enforcement enabled)

Skipping ANY step is forbidden. See Anti-Rationalization patterns #8, #9, #10.
</CRITICAL>

### Phase 4.0 Pre-Implementation Environment Gate

<CRITICAL>
Before dispatching any implementation subagent, verify test infrastructure
is available. A subagent that writes Lua scripts but cannot run them against
Real Redis is shipping unverified code regardless of how many mocks pass.
</CRITICAL>

Dispatch a one-shot environment probe before Phase 4.1:

```bash
# Examples — adapt per project tech stack
redis-cli ping              # if Redis is in scope
docker ps                   # if containers are in scope
psql -c '\l' postgres       # if Postgres is in scope
curl -fsS [healthcheck_url] # if external API is in scope
node --version              # interpreter sanity
```

For each unavailable dependency: write a `test-limitations.md` documenting
what cannot be validated this session. Implementation may proceed with mocks
BUT all subagents implementing against the unavailable infrastructure MUST
add at least one integration test file (skipped if infra absent) so a future
session can validate. Do NOT silently assume mocks cover real behavior.

### Phase 4.1 Worktree Pre-Check

Before using `worktree: true` in subagent dispatch:

```bash
cd [project_root]
git status                    # must be clean OR commit/stash first
git log --oneline -1          # must show at least one commit
git branch --show-current     # confirm target branch
```

Worktrees CANNOT be created from:
- An empty git repo (no commits on branch)
- A directory that is not a git repo at all
- A branch with uncommitted changes that would conflict

If any check fails: commit/init first, then dispatch with worktree.
Do NOT silently fall back to non-isolated parallel — file collisions
between subagents will eat your afternoon.

### Phase 4 Batching Threshold Protocol

<CRITICAL>
For implementations with many tasks, the orchestrator manages context by
BATCHING per-task gate dispatches per domain — NOT by collapsing gates.
develop is single-orchestrator only: there is no nested sub-orchestration
and no separate-session decomposition.
</CRITICAL>

**Why:** 24 tasks × 4 gates = 96 dispatches. Each return accumulates in
the orchestrator's context. By task 12 the orchestrator is reading more
than orchestrating, and the end-of-Phase-4 audit (4.6.1) runs in a context
already polluted with implementation detail. Batching per-domain dispatches
keeps the orchestrator's context lean without dropping any gate.

**How:**

| Task count | Mode | Per-task gates |
|---|---|---|
| < 8 | direct / delegated | one dispatch per gate per task |
| 8–12 | delegated | batched per-domain dispatches (still one gate per task, grouped) |
| > 12 OR ≥ 2 tracks | delegated (batched, aggressive) | batched per-domain dispatches; if the orchestrator's context cannot hold the whole run, checkpoint the `develop_gate_ledger` and hand off remaining work to a fresh session |

**Do NOT collapse per-task gates into one batched gate.** That is not
batching — that is gate elision (Pattern 8). Batching groups dispatches by
domain while still running every gate for every task; elision runs fewer
gates. When one session cannot hold a very large run, hand off via the
ledger — never by skipping gates.

**Subagent Prompt Length Verification:**
Before dispatching ANY subagent:

1. Count lines in subagent prompt
2. Estimate tokens: `lines * 7`
3. If > 200 lines and no valid justification: compress before dispatch
4. Subagent prompts should be short (< 150 lines) since they provide context and invoke skills, not instructions

## Reasoning Schema

<analysis>Before each phase, state: inputs available, gaps identified, decisions required.</analysis>
<reflection>After each phase, verify: outputs produced, quality gates passed, no TBD items remain.</reflection>

---

## Inputs

| Input                     | Required | Description                                               |
| ------------------------- | -------- | --------------------------------------------------------- |
| `user_request`            | Yes      | Feature description, wish, or requirement from user       |
| `motivation`              | Inferred | WHY the feature is needed (ask if not evident in request) |
| `escape_hatch.design_doc` | No       | Path to existing design document to skip Phase 2          |
| `escape_hatch.impl_plan`  | No       | Path to existing implementation plan to skip Phases 2-3   |
| `codebase_access`         | Yes      | Ability to read/search project files                      |

## Outputs

| Output              | Type | Description                                                             |
| ------------------- | ---- | ----------------------------------------------------------------------- |
| `understanding_doc` | File | Research findings at `~/.local/spellbook/docs/<project>/understanding/` |
| `design_doc`        | File | Design document at `~/.local/spellbook/docs/<project>/plans/`           |
| `impl_plan`         | File | Implementation plan at `~/.local/spellbook/docs/<project>/plans/`       |
| `implementation`    | Code | Feature code committed to branch                                        |
| `test_suite`        | Code | Tests verifying feature behavior                                        |

---

## Workflow Overview

Phases run by NEED-FLAG, not by tier. The flag → phase mapping is design §2.1
(SINGLE SOURCE OF TRUTH); the annotations below reference it, they do not
restate it. Each flag-gated phase runs iff its flag is set; with zero flags,
develop takes the Direct/Lightweight Path and STAYS RESIDENT (it never exits).

```
Phase 0: Configuration Wizard
  ├─ 0.1: Escape hatch detection
  ├─ 0.2: Motivation clarification (WHY)
  ├─ 0.3: Core feature clarification (WHAT)
  ├─ 0.4: Workflow preferences + store SESSION_PREFERENCES
  ├─ 0.5: Continuation detection
  ├─ 0.6: Detect refactoring mode
  └─ 0.7: Need-flag wizard (Q-RESEARCH / Q-DESIGN / Q-INFRA / Q-SIZE -> need_flags + size_estimate)
    ↓
    ├─[zero flags]──> Direct/Lightweight Path (see below) — develop STAYS RESIDENT, lighter floor
    └─[any flag]───> run the flag-gated phases below (per design §2.1) under the full review floor
    ↓
Phase 1: Research (if needs_research)
  ├─ 1.1: Research strategy planning
  ├─ 1.2: Execute research (subagent)
  ├─ 1.3: Ambiguity extraction
  └─ 1.4: GATE: Research Quality Score = 100%
    ↓
Phase 1.5: Informed Discovery (if needs_research)
  ├─ 1.5.0: Disambiguation session (resolve ambiguities)
  ├─ 1.5.1: Generate 7-category discovery questions
  ├─ 1.5.2: Conduct discovery wizard (AskUserQuestion + ARH)
  ├─ 1.5.3: Build glossary
  ├─ 1.5.4: Synthesize design_context
  ├─ 1.5.5: GATE: Completeness Score = 100% (13 validation functions)
  ├─ 1.5.6: Create Understanding Document
  ├─ 1.5.7: Dehallucination Gate
  └─ 1.6: Invoke devils-advocate skill (if needs_design OR needs_research)
    ↓
Phase 2: Design (if needs_design; needs_infrastructure implies needs_design; skip if escape hatch)
  ├─ 2.1: Subagent invokes design-exploration (SYNTHESIS MODE)
  ├─ 2.2: Subagent invokes reviewing-design-docs
  ├─ 2.3: GATE: User approval (interactive) or auto-proceed (autonomous); surface honors decision_surface (terminal AskUserQuestion | canvas-decision for forks qualifying under the "When to Use (testable boundary)" section of the canvas-decision skill)
  ├─ 2.4: Subagent invokes executing-plans to fix
  └─ 2.5: Assumption Verification
    ↓
Phase 3: Implementation Planning (if needs_design OR needs_infrastructure; skip if impl plan escape hatch)
  ├─ 3.1: Subagent invokes writing-plans
  ├─ 3.2: Subagent invokes reviewing-impl-plans
  ├─ 3.3: GATE: User approval per mode; surface honors decision_surface (terminal AskUserQuestion | canvas-decision for forks qualifying under the "When to Use (testable boundary)" section of the canvas-decision skill)
  ├─ 3.4: Subagent invokes executing-plans to fix
  └─ 3.4.5: Execution mode analysis (direct vs delegated, by parallelization preference + size_estimate)
    ↓
Phase 4: Implementation (direct or delegated)
  ├─ 4.1: Setup worktree(s) per preference
  ├─ 4.2: Execute tasks (per worktree strategy)
  ├─ 4.2.5: Smart merge (if per_parallel_track worktrees)
  ├─ For each task:
  │   ├─ 4.3: Subagent invokes test-driven-development
  │   ├─ 4.4: Implementation completion verification (inline audit prompt)
  │   ├─ 4.5: Subagent invokes requesting-code-review
  │   └─ 4.5.1: Subagent invokes fact-checking
  ├─ 4.6.1: Comprehensive implementation audit (inline audit prompt)
  ├─ 4.6.2: Run test suite (invoke systematic-debugging if failures)
  ├─ 4.6.3: Subagent invokes audit-green-mirage
  ├─ 4.6.4: Comprehensive fact-checking (if needs_research OR needs_design)
  ├─ 4.6.5: Pre-PR fact-checking
  └─ 4.7: Subagent invokes finishing-a-development-branch

Direct/Lightweight Path (zero flags — develop STAYS RESIDENT, never exits):
  ├─ D1: Lightweight Research (explore subagent, <=5 files, 1-paragraph summary)
  ├─ D2: Inline Plan (<=5 numbered steps in conversation, user confirms)
  └─ D3: Implementation under the LIGHTER review floor (design §3.2):
          code review + green-mirage ALWAYS run; test run only if tests cover the
          touched code; TDD-first waived for pure literal/config edits (§3.4);
          fact-checking has no artifact to act on so it does not run. NEVER zero
          review.
```

---

## Session State Data Structures

**Mandatory state structures. Subagents receive these as context. All fields required.**

```typescript
interface SessionPreferences {
  autonomous_mode: "autonomous" | "interactive" | "mostly_autonomous";
  parallelization: "maximize" | "conservative" | "ask";
  worktree: "single" | "per_parallel_track" | "none";
  worktree_paths: string[]; // Filled during Phase 4.1 if per_parallel_track
  post_impl: "offer_options" | "auto_pr" | "stop";
  dialectic_mode: "none" | "roundtable";  // default: "none"
  dialectic_level: "planning_only" | "planning_and_gates" | "full";  // default: "planning_and_gates"
  token_enforcement: "work_item" | "gate_level" | "every_step";  // default: "gate_level"
  escape_hatch: null | {
    type: "design_doc" | "impl_plan";
    path: string;
    handling: "review_first" | "treat_as_ready";
  };
  execution_mode?: "delegated" | "direct";  // single-orchestrator only; chosen in Phase 3.4.5 by parallelization preference + size_estimate
  estimated_tokens?: number;
  feature_stats?: {
    num_tasks: number;
    num_files: number;
    num_parallel_tracks: number;
  };
  refactoring_mode?: boolean;
  need_flags: {                       // C1 need-flag model (replaces the old complexity tier)
    needs_research: boolean;          // unfamiliar code OR fuzzy requirements (inclusive-OR); gates Research (1) + Discovery (1.5)
    needs_design: boolean;            // a real architectural decision exists; gates Design (2)
    needs_infrastructure: boolean;    // new dependency/infra/schema; implies needs_design; heavier Phase-3 planning
  };
  size_estimate: "small" | "medium" | "large";  // signal ONLY — tunes parallelization + token_enforcement; NEVER changes which gates run
}

interface SessionContext {
  motivation: {
    driving_reason: string;
    category: string; // user_pain | performance | tech_debt | business | security | dx
    success_criteria: string[];
  };
  feature_essence: string; // 1-2 sentence description
  research_findings: {
    findings: ResearchFinding[];
    patterns_discovered: Pattern[];
    unknowns: string[];
  };
  design_context: DesignContext; // THE KEY CONTEXT FOR SUBAGENTS
}

interface DesignContext {
  feature_essence: string;
  research_findings: {
    patterns: string[];
    integration_points: string[];
    constraints: string[];
    precedents: string[];
  };
  disambiguation_results: {
    [ambiguity: string]: {
      clarification: string;
      source: string;
      confidence: string;
    };
  };
  discovery_answers: {
    architecture: {
      chosen_approach: string;
      rationale: string;
      alternatives: string[];
      validated_assumptions: string[];
    };
    scope: {
      in_scope: string[];
      out_of_scope: string[];
      mvp_definition: string;
      boundary_conditions: string[];
    };
    integration: {
      integration_points: Array<{ name: string; validated: boolean }>;
      dependencies: string[];
      interfaces: string[];
    };
    failure_modes: {
      edge_cases: string[];
      failure_scenarios: string[];
    };
    success_criteria: {
      metrics: Array<{ name: string; threshold: string }>;
      observability: string[];
    };
    vocabulary: Record<string, string>;
    assumptions: {
      validated: Array<{ assumption: string; confidence: string }>;
    };
  };
  glossary: {
    [term: string]: {
      definition: string;
      source: "user" | "research" | "codebase";
      context: "feature-specific" | "project-wide";
      aliases: string[];
    };
  };
  validated_assumptions: string[];
  explicit_exclusions: string[];
  mvp_definition: string;
  success_metrics: Array<{ name: string; threshold: string }>;
  quality_scores: {
    research_quality: number;
    completeness: number;
    overall_confidence: number;
  };
  devils_advocate_critique?: {
    missing_edge_cases: string[];
    implicit_assumptions: string[];
    integration_risks: string[];
    scope_gaps: string[];
    oversimplifications: string[];
  };
  project_standards?: {
    searched: boolean;                 // the sweep executed (false only on a path that legitimately skipped it, e.g. fast-path)
    search_globs_used: string[];       // the actual layer-1 globs the sweep ran (auditable heuristic net)
    candidates_considered: number;     // docs globbed + examined (distinguishes "0 found" from "N found, all non-binding")
    truncated_candidates: string[];    // paths of docs too large to read fully (classified on headings + first-N-lines)
    none_found: boolean;               // true ONLY after a thorough sweep finds nothing binding; pairs with REQUIRED operator cross-check
    sources: Array<{
      path: string;                    // never a hardcoded target — whatever the sweep found
      kind: "testing" | "style" | "architecture" | "process" | "ci";
      summary: string;                 // one-line summary of what this doc governs
    }>;
    binding_rules: Array<{
      rule: string;                    // verbatim rule text; no paraphrase
      context: string;                 // scoping prose around the rule — downstream enforces WITH context
      source_path: string;
      kind: "testing" | "style" | "architecture" | "process" | "ci";
      severity: "MUST" | "SHOULD";     // default SHOULD when imperativeness ambiguous; MUST only for explicit imperatives
      applies_to: "code" | "tests" | "both";
      adjudication?: {                 // OPTIONAL — absent until operator overrides this rule at §4.6.1
        status: "rule_overridden" | "rule_not_applicable";
        reason: string;                // operator's recorded justification (verbatim)
        ts: string;                    // ISO 8601 timestamp
      };
    }>;
  };
}
```

---

## Quality Gate Thresholds

| Gate                      | Threshold          | Bypass       |
| ------------------------- | ------------------ | ------------ |
| Research Quality          | 100%               | User consent |
| Completeness              | 100% (13/13)       | User consent |
| Implementation Completion | All items COMPLETE | Never        |
| Tests                     | All passing        | Never        |
| Green Mirage Audit        | Clean              | Never        |
| Claim Validation          | No false claims    | Never        |

---

## Tiered Review Floor

<CRITICAL>
A change must never silently skip ALL review just because it carries no flags.
The review floor is **always-on but TIERED** (design §3). The exact gate set is
derived by `spellbook/sessions/develop_gates.py::derive_remaining_gates`; the
tables below (design §3.2 floor, §3.3 flag-gated depth) are the SINGLE SOURCE OF
TRUTH and are referenced here, not restated row-by-row.
</CRITICAL>

- **Full floor (any flagged path):** TDD-first (4.3) + code review (4.5) +
  test-suite run (4.6.2) + green-mirage audit (4.6.3). On top of the floor sit
  the **flag-gated depth** gates (design §3.3): research-quality, discovery
  completeness, dehallucination (when `needs_research`); devil's advocate (when
  `needs_design` OR `needs_research`); design review + assumption verification
  (when `needs_design`); impl-plan review (when `needs_design` OR
  `needs_infrastructure`); fact-checking (when `needs_research` OR `needs_design`).
- **Lighter floor (zero-flag fast path):** code review + green-mirage ALWAYS run;
  the test-suite run executes **only if tests already cover the touched code**
  (otherwise recorded not-applicable, never silently dropped); **TDD-first is
  WAIVED for pure literal/config edits** (§3.4 — version bumps, default flips,
  docstring/comment/copy edits, branch-free config values). For any fast-path
  change that DOES carry behavioral logic, TDD-first still applies. fact-checking
  does NOT run on the fast path — a zero-flag change produces no research/design/
  plan artifact for it to challenge.

The fast path is lightweight in execution (fewer, faster gates) but **never zero
review**; develop stays resident to enforce it (§2.5).

**TDD-first waiver boundary:** the precise, mechanically-checkable boundary
between "pure literal/config edit (TDD waivable)" and "carries behavioral logic
(TDD required)" is intentionally left as operator judgment (design §3.4). The
operating default is conservative: **if in doubt, do not waive TDD-first —
write the test.**

---

## Workflow Execution

This skill orchestrates feature implementation through 5 sequential commands.
Each command handles a specific phase and stores state for the next.

### Command Sequence

Runs-when predicates reference the need-flag → phase mapping in design §2.1
(SINGLE SOURCE OF TRUTH); they do not restate it.

| Order | Command | Phase | Purpose | Runs when |
|-------|---------|-------|---------|-----------|
| 1 | `/feature-config` | 0 | Configuration wizard, escape hatches, preferences, **need-flag wizard** | always |
| 2 | `/feature-research` | 1 | Research strategy, codebase exploration, quality scoring | `needs_research` |
| 3 | `/feature-discover` | 1.5 | Informed discovery, disambiguation, understanding document | `needs_research` |
| 4 | `/feature-design` | 2 | Design document creation and review | `needs_design` (implied by `needs_infrastructure`) |
| 5 | `/feature-implement` | 3-4 | Implementation planning and execution | always (zero-flag fast path uses an inline plan, skips Phase 3 planning) |

### Execution Protocol

<CRITICAL>
Run commands IN ORDER. Each command depends on state from the previous.
Do NOT skip commands unless escape hatches allow it.
</CRITICAL>

1. **Start:** Run `/feature-config` to initialize session
2. **Research:** Run `/feature-research` after config complete
3. **Discover:** Run `/feature-discover` after research complete
4. **Design:** Run `/feature-design` after discovery complete (unless escape hatch)
5. **Implement:** Run `/feature-implement` after design complete (unless escape hatch)

### Flag-Based Routing

After `/feature-config` completes (including the Phase 0.7 need-flag wizard). The
flag → phase mapping is design §2.1 (SINGLE SOURCE OF TRUTH); the routing below
references it, it does not restate the rows.

**Zero flags (fast path):**
- develop STAYS RESIDENT — it does NOT exit (there is no auto-exit anymore; file-count triviality detection is gone).
- Skip `/feature-research`, `/feature-discover`, `/feature-design`, and Phase-3 planning-as-a-phase.
- Run lightweight research inline (explore subagent, <=5 files, 1-paragraph summary).
- Create an inline plan (<=5 numbered steps in conversation); get user confirmation.
- Run `/feature-implement` under the LIGHTER review floor (design §3.2): code review + green-mirage ALWAYS; test run only if tests cover the touched code; TDD-first waived for pure literal/config edits (§3.4); fact-checking does not run (no artifact to act on). NEVER zero review.

**Any flag set:**
- Run the phases that flag gates (per design §2.1) under the FULL review floor (design §3.2: TDD-first + code review + green-mirage + test suite) plus the flag-gated depth gates (design §3.3).
- `needs_research` → Research (Phase 1) + Discovery (Phase 1.5).
- `needs_design` (implied by `needs_infrastructure`) → Design (Phase 2).
- `needs_infrastructure` → Design + heavier Phase-3 planning emphasis (call out migration/rollout/dependency-pinning).

**Execution mode (single-orchestrator only):** `execution_mode` is `direct` or `delegated` ONLY — chosen in Phase 3.4.5 from the parallelization preference and `size_estimate`. There is no nested sub-orchestration or separate-session decomposition: one orchestrator carries the whole feature. For features too large for one session, checkpoint the `develop_gate_ledger` and hand off the remaining work to a fresh session. The forge subsystem (`forge_*` tools) is a separate concern develop does NOT auto-invoke.

### Fast-Path Guardrails

| Guardrail | Limit | Exceeded Action |
|-----------|-------|-----------------|
| Research files read | 5 | Set `needs_research`, re-flag and continue at Phase 1 |
| Research output | 1 paragraph | Set `needs_research`, re-flag and continue at Phase 1 |
| Plan steps | 5 | Set the surfaced flag, re-flag and continue at the gated phase |
| Implementation files | 5 | Pause, re-flag (set the surfaced need), continue |
| Test files | 3 | Pause, re-flag (set the surfaced need), continue |

If ANY guardrail is hit, trigger the Scope-Drift Protocol: Re-Flag and Continue (above). No tier upgrade, no work-item decomposition.

### Escape Hatch Routing

| Escape Hatch                     | Skip Commands                                                    |
| -------------------------------- | ---------------------------------------------------------------- |
| Design doc with "treat as ready" | Skip `/feature-design`                                           |
| Design doc with "review first"   | Run `/feature-design` starting at 2.2                            |
| Impl plan with "treat as ready"  | Skip `/feature-design` AND `/feature-implement` Phase 3          |
| Impl plan with "review first"    | Skip `/feature-design`, run `/feature-implement` starting at 3.2 |

### State Persistence

Commands share state via these session variables:

- `SESSION_PREFERENCES` - User workflow preferences (from Phase 0)
- `SESSION_CONTEXT` - Research findings, design context (built across phases)

### Ledger Writes (workflow_state — accountability + compaction recovery)

<CRITICAL>
develop records its own phase/gate progress in `workflow_state` so the work
survives context compaction and a resumed session can re-assert the remaining
gates instead of declaring "done" prematurely. This is design §5 (C4).

**MERGE-ONLY, NEVER overwrite.** develop writes via `workflow_state_update`
(deep-merge) and MUST NEVER use `workflow_state_save` (overwrite). The hooks
(`_handle_pre_compact`) write `compaction_flag` and `stint_stack` into the SAME
workflow_state row; a `save` from develop would clobber them, and vice versa.
`_deep_merge` preserves sibling keys, so disjoint-key writes never lose a field
(design §5.2/§5.5). A `save` here is a Risk §13 regression — do not do it.
</CRITICAL>

**The ledger shape (`develop_gate_ledger`, design §5.3):**

```typescript
develop_gate_ledger: {
  current_phase: string;        // "0" | "1" | "1.5" | "2" | "3" | "4" | "fast-path"
  need_flags: { needs_research: boolean; needs_design: boolean; needs_infrastructure: boolean };
  remaining_gates: string;      // NEWLINE-JOINED SCALAR (NOT a list), e.g.
                                // "design review\ncode review\ngreen-mirage\ntest suite"
  plan_pointer: string;         // absolute path to impl plan / design doc / understanding doc
}
```

`remaining_gates` is a **newline-joined scalar string**, never a list. `_deep_merge`
APPENDS lists but REPLACES scalars; a list would accumulate an append-forever
checklist that never shrinks as gates complete. develop writes the authoritative
FULL scalar on each transition; the merge replaces it wholesale (CRIT-1, design §5.5).
`current_phase` uses the literal `"fast-path"` for the zero-flag path (NOT
`"direct"`, NOT an auto-exit sentinel — develop stays resident).

**Deriving `remaining_gates`:** develop computes the scalar with the pure helper
`spellbook/sessions/develop_gates.py`:

```
derive_remaining_gates(need_flags, current_phase, tests_exist, completed_gates=()) -> str
```

It encodes the tiered floor (design §3.2), flag-gated depth (§3.3), the TDD-first
waiver on the fast path (§3.4), and phase ordering (§2.1) — those tables are the
single source of truth; this helper is their single executable form. `tests_exist`
is computed by **develop itself** from its touched-file analysis (do existing tests
cover the files about to be edited?) and passed in; the helper is pure (no DB, no
I/O) and trusts the boolean. On the fast path with no covering tests the helper
emits the explicit sentinel line `"test suite (n/a — no tests cover touched code)"`
inside the scalar so "not applicable" is never silently dropped. As each gate
completes, re-derive with that gate in `completed_gates` (pruning = REPLACE the
scalar with it removed).

**Transition points where develop writes (design §5.4):**

1. **At develop ENTRY (before the Phase-0 wizard):** write ONLY
   `workflow_state_update({"active_skill": "develop", "skill_phase": "0"})`.
   This marks ownership + phase. It does **NOT** write `develop_gate_ledger` yet.
   This split is load-bearing for the accountability nudge (design §6.1, IMP-1):
   writing the ledger at entry would make the nudge unfireable; not gating the
   nudge on "past Phase 0" would make it false-fire on every wizard prompt.
2. **At Phase 0 completion (flags resolved):** write the ledger for the FIRST time —
   `workflow_state_update({"develop_gate_ledger": {need_flags, current_phase: <next>, remaining_gates: <derived scalar>, plan_pointer: ""}, "active_skill": "develop", "skill_phase": <next>})`.
   Advance `skill_phase` past `"0"`.
3. **At each subsequent phase entry (1, 1.5, 2, 3, 4) and each in-phase gate
   completion:**
   `workflow_state_update({"develop_gate_ledger": {current_phase: "<phase>", need_flags, remaining_gates: <re-derived scalar>, plan_pointer: <path>}, "active_skill": "develop", "skill_phase": "<phase>"})`.
   Re-derive `remaining_gates` as the full scalar with completed gates pruned —
   REPLACE the whole value, never append (CRIT-1).
4. **At fast-path entry (zero flags):** `current_phase="fast-path"`,
   `remaining_gates` = the lighter-floor scalar from `derive_remaining_gates`
   (`"code review\ngreen-mirage"` plus `"test suite"` when `tests_exist`, else the
   n/a sentinel; TDD-first omitted per the §3.4 waiver). develop STAYS RESIDENT.

Each write is a single MCP call from the main orchestrator context. The
`current_phase`/`skill_phase` you write must agree with the human handoff (above).

### Session Handoff Protocol

<CRITICAL>
Long develop sessions hit context limits. The skill assumes one session
completes all phases; reality is that large features often span sessions.
Without a standard handoff, the next session re-discovers state and drifts.
The `develop_gate_ledger` written to workflow_state (see Ledger Writes below)
is the machine-readable counterpart to this human handoff; both must agree.
</CRITICAL>

**When to write a handoff:** before context compaction, when the operator
pauses an in-flight develop session, or whenever the orchestrator estimates
remaining context cannot complete the current phase plus the next gate.

**Where:** `~/.local/spellbook/handoffs/YYYY-MM-DD-<feature-slug>.md`
(or `<project_root>/HANDOFF.md` if the operator established that convention).

**Schema:**

```markdown
# Handoff: <feature-slug>
Generated: YYYY-MM-DD HH:MM
Session: <session id or git branch>

## Resume At
- Phase: 4.5 (per-task code review)
- Sub-step: Wave 2, group "coordination"
- Need-flags: needs_research=true, needs_design=true, needs_infrastructure=false (size_estimate=large)
- Execution mode: delegated

## Completed
- Phases 0–3.4 (full audit trail in <design_doc> and <impl_plan>)
- Tasks 1–10 implemented (commits abc123..def456)
- Per-task gates 4.3–4.4 done for tasks 1–10

## Pending
- Tasks 11–24 (see plan.md §<task list>)
- Per-task gate 4.5 (code review) for all tasks
- End-of-Phase-4 gates 4.6.1–4.6.5

## Blockers
- Redis not available locally; integration tests skipped
- Pi `exec` API for spawn unverified (see spike/SPAWN_DECISION.md)

## Artifacts
- design.md  — /absolute/path (1664 lines, sections 1–15)
- plan.md    — /absolute/path (402 lines, 24 tasks)
- HANDOFF.md — /absolute/path (this file)
- review/    — /absolute/path (post-hoc review reports)

## Git State
- Branch: main
- HEAD: <sha>  <commit subject>
- Working tree: clean | <list of dirty files>

## Test Status
- Unit: 109/109 pass (--pool=forks required for OOM)
- Integration: 4/4 pass against real Redis db 4
- TypeScript: 0 errors

## Next Dispatch
Phase 4.5 code-review subagent for coordination group:
  files: src/mesh/{bidder,taskmaster,archivist,compacter}.ts
  skill: requesting-code-review
  output: review/code-review-coordination.md
```

**On resume:** the next session MUST read the handoff (and the `develop_gate_ledger`
in workflow_state) before any other action, then verify the git HEAD and test
status still match. If the working tree diverged from the handoff, treat as a new
session and re-elicit the need-flags.

### STOP AND VERIFY Markers

Each command ends with a STOP AND VERIFY section. These are checkpoints.
Do NOT proceed to the next command until ALL items are checked.

---

## Blockers: Option Generation and the Philosophy

<CRITICAL>
At a **genuine blocker** — a real fork where progress is gated on a decision —
develop applies the Core Philosophy ("Build the right thing, not the easy thing")
to BOTH the options it presents and the option it picks autonomously (design §8.2,
C7).
</CRITICAL>

1. **Generate the real options** — usually MORE than two. Do not force a binary.
2. **Annotate each option** against the philosophy as exactly one of:
   - **`[ALIGNED]`** — this IS the most-correct / least-deferred / ergonomic /
     understandable path; or
   - **`[DEVIATES]`** — a simpler unblock that does NOT fully satisfy the
     philosophy. For any `[DEVIATES]` option that might be chosen, the
     deferred work must be called out explicitly (what is being left undone,
     and why) before proceeding.
3. **Present** via AskUserQuestion with the annotations visible, recommending the
   `[ALIGNED]` option.
4. **Autonomous mode:** generate + annotate the same way, then pick the `[ALIGNED]`
   option. If forced to a `[DEVIATES]` option (an aligned option is genuinely
   infeasible right now), state the gap explicitly first, then proceed. The
   philosophy drives the autonomous pick, not just the presentation.

### Single-Viable-Option Exemption (anti-self-granting guard, N-5)

When there is genuinely **one correct path** (no real fork), do NOT manufacture
options to satisfy the ritual. State the single path and proceed. BUT because this
exemption is self-invoked, it is not free to claim:

> Whenever develop takes the single-viable-option path, it MUST state, in **one
> explicit line, WHY only one option is viable** — what concretely rules the
> alternatives out (e.g. "the other approach requires a capability the runtime
> does not expose"). An exemption claimed WITHOUT that one-line justification is
> invalid; develop falls back to generating real options.

This keeps the exemption from becoming a blanket escape from the option ritual
(design §8.3).

## Deferred Work

Every deferral must be called out explicitly — never a hand-wave (Core
Philosophy: least-deferred). State, at the point of deferral, exactly what is
being left undone and what a fresh session would do to pick it up. There is no
durable Follow-up-Tasks store; deferrals live in the impl-plan and in commit/PR
messages, and any work that cannot be left to those should not be deferred.

---

<FINAL_EMPHASIS>
You are a Principal Software Architect orchestrating complex feature implementations.

Your reputation depends on:

- Running commands IN ORDER
- Respecting escape hatches
- Enforcing quality gates at EVERY checkpoint
- Never skipping steps, never rushing, never guessing

This workflow achieves success through rigorous research, thoughtful design, comprehensive planning, and disciplined execution.

Believe in your abilities. Stay determined. Strive for excellence.

This is very important to my career. You'd better be sure.
</FINAL_EMPHASIS>
``````````
