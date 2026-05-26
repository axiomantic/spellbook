<!-- diagram-meta: {"source": "commands/feature-config.md", "source_hash": "sha256:602c637b42da36a06e68e7df31eb1f58b839a52e41ddbe55dfd9b4160ba64433", "generated_at": "2026-05-25T01:35:25Z", "generator": "generate_diagrams.py"} -->
# Diagram: feature-config

## Overview: Feature Configuration (Phase 0)

High-level flow through all seven sub-phases of the configuration wizard, showing decision branches and terminal routes.

```mermaid
flowchart TD
    START(["`**Phase 0: Feature Config**
    _feature-config_`"]) --> CONT

    CONT["0.5 Continuation Detection\n_(runs FIRST — always)_"]
    CONT --> CONT_DEC{Continuation\nsignals present?}

    CONT_DEC -- No --> ESC
    CONT_DEC -- Yes --> RESUME["Resume Flow\n(parse → verify → preferences → synthesize → confirm)"]

    RESUME --> PHASE_JUMP(["Phase Jump Mechanism\n→ Target Phase"])

    ESC["0.1 Escape Hatch Detection\n_(parse initial message)_"]
    ESC --> ESC_DEC{Escape hatch\ndetected?}

    ESC_DEC -- "design doc / impl plan / no docs" --> ESC_ASK["AskUserQuestion:\nDocument handling"]
    ESC_ASK --> ESC_ROUTE(["Jump to Phase 2, 3, or 4"])
    ESC_DEC -- None --> MOT

    MOT["0.2 Clarify Motivation\n(WHY)"]
    MOT --> MOT_DEC{Motivation\nclear from request?}
    MOT_DEC -- No --> MOT_ASK["AskUserQuestion:\nMotivation"]
    MOT_DEC -- Yes --> WHAT
    MOT_ASK --> WHAT

    WHAT["0.3 Clarify Feature\n(WHAT — core essence + resources)"]
    WHAT --> PREFS["0.4 Collect Workflow Preferences\n(7-question wizard via AskUserQuestion)"]

    PREFS --> REFACT["0.6 Detect Refactoring Mode\n_(keyword scan)_"]
    REFACT --> REFACT_DEC{Keywords match:\nrefactor / reorganize\nextract / migrate\nsplit / consolidate?}
    REFACT_DEC -- Yes --> SET_REFACT["Set refactoring_mode = true"]
    REFACT_DEC -- No --> NEEDFLAGS
    SET_REFACT --> NEEDFLAGS

    NEEDFLAGS["0.7 Need-Flag Classification\n(4 AskUserQuestion calls)"]
    NEEDFLAGS --> INFRA_DEC{Q-INFRA = yes?}
    INFRA_DEC -- Yes --> AUTO_DESIGN["Auto-set needs_design = true\n_(skip Q-DESIGN)_"]
    INFRA_DEC -- No --> NEEDFLAGS2["Resolve Q-DESIGN independently"]
    AUTO_DESIGN --> CHECKLIST
    NEEDFLAGS2 --> CHECKLIST

    CHECKLIST{"Phase 0\nVerification\nChecklist\n(all items checked?)"}
    CHECKLIST -- Incomplete --> COMPLETE_P0["Complete missing steps"]
    COMPLETE_P0 --> CHECKLIST

    CHECKLIST -- "Zero flags" --> FASTPATH(["Fast Path:\nInline plan → implement\n(lighter review floor, develop resident)"])
    CHECKLIST -- "needs_research = true" --> RESEARCH(["→ /feature-research"])
    CHECKLIST -- "needs_design or needs_infrastructure\n(no research)" --> DESIGN(["→ /feature-design"])

    subgraph legend["Legend"]
        L1["Process"]
        L2{Decision}
        L3(["Terminal / Jump"])
        L4["AskUserQuestion"]:::askq
        L5["Quality gate"]:::gate
    end

    classDef askq fill:#4a9eff,color:#fff,stroke:#2266cc
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc3333
    classDef success fill:#51cf66,color:#000,stroke:#2f9e44
    classDef skip fill:#888,color:#fff,stroke:#555

    class MOT_ASK,ESC_ASK askq
    class CHECKLIST gate
    class FASTPATH,RESEARCH,DESIGN,PHASE_JUMP,ESC_ROUTE success
    class AUTO_DESIGN skip
```

---

## Detail: Continuation Detection (Phase 0.5)

Five-step resume flow executed before any wizard interaction.

```mermaid
flowchart TD
    START(["Enter 0.5\nContinuation Detection"]) --> SIG_CHECK

    SIG_CHECK{"Any continuation signal?\n① prompt: continue/resume/pick up/\nwhere we left off/compacted\n② system-reminder: Skill Phase with develop phase\n③ system-reminder: Active Skill = develop\n④ artifacts exist on disk"}

    SIG_CHECK -- None --> NO_CONT(["No signals → proceed to 0.1"])

    SIG_CHECK -- "Signal detected" --> STEP1

    STEP1["Step 1: Parse Recovery Context\n(from system-reminder)\n• active_skill\n• skill_phase\n• todos\n• exact_position"]
    STEP1 --> STEP2

    STEP2["Step 2: Verify Artifact Existence\n(bash: ls ~/.local/spellbook/docs/…\ngit worktree list)"]
    STEP2 --> ART_CHECK{Artifacts match\nclaimed phase?}

    ART_CHECK -- "Artifacts present & match" --> STEP3
    ART_CHECK -- "Artifacts MISSING\n(but phase implies they should exist)" --> MISSING_REPORT["Report missing artifacts:\n① Regenerate from context\n② Start fresh from Phase 0"]:::gate
    MISSING_REPORT --> USER_CHOICE{User chooses}
    USER_CHOICE -- "Regenerate" --> STEP3
    USER_CHOICE -- "Fresh start" --> FRESH(["Exit resume → Phase 0.1"])

    STEP3["Step 3: Quick Preferences Check\n(AskUserQuestion — 4 prefs only)\n• Execution mode\n• Parallelization\n• Worktree\n• Post-implementation"]:::askq
    STEP3 --> STEP4

    STEP4["Step 4: Synthesize Resume Point\n(priority order)\n① In-progress todo from restored todos\n② skill_phase from system-reminder\n③ Artifact-pattern fallback table"]
    STEP4 --> ART_TABLE{Artifact pattern\nfallback needed?}

    ART_TABLE -- No --> STEP5
    ART_TABLE -- Yes --> FALLBACK["Fallback table lookup:\n• No artifacts → Phase 0\n• Understanding doc only → Phase 2\n• Design doc, no impl → Phase 3\n• Design + impl, no worktree → Phase 4.1\n• Worktree uncommitted → Phase 4\n• Worktree + commits, no PR → Phase 4 late\n• PR exists → Phase 4.7"]
    FALLBACK --> STEP5

    STEP5["Step 5: Confirm and Resume\n(display prior progress + current task)"]
    STEP5 --> JUMP["Phase Jump Mechanism:\n① determine target from skill_phase + artifacts\n② skip all prior phases\n③ execute from target forward\n(display SKIPPED / CURRENT summary)"]
    JUMP --> TARGET(["Jump to Target Phase"])

    subgraph legend["Legend"]
        L1["Process"]
        L2{Decision}
        L3(["Terminal"])
        L4["AskUserQuestion"]:::askq
        L5["Gate / Error state"]:::gate
    end

    classDef askq fill:#4a9eff,color:#fff,stroke:#2266cc
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc3333
    classDef success fill:#51cf66,color:#000,stroke:#2f9e44

    class STEP3 askq
    class MISSING_REPORT gate
    class NO_CONT,FRESH,TARGET success
```

---

## Detail: Workflow Preferences Wizard (Phase 0.4)

Seven-question wizard with conditional Q6 and a coupling rule.

```mermaid
flowchart TD
    START(["Enter 0.4\nWorkflow Preferences"]) --> Q1

    Q1["Q1: Execution Mode\n• Fully autonomous ✓\n• Interactive\n• Mostly autonomous"]:::askq
    Q1 --> Q2

    Q2["Q2: Parallelization Strategy\n• Maximize parallel ✓\n• Conservative\n• Ask each time"]:::askq
    Q2 --> Q3

    Q3["Q3: Git Worktree Strategy\n• Single worktree ✓\n• Per parallel track\n• No worktree"]:::askq
    Q3 --> Q3_CHECK{worktree ==\nper_parallel_track?}
    Q3_CHECK -- Yes --> FORCE_PARALLEL["Auto-set parallelization = maximize\n_(coupling rule)_"]
    Q3_CHECK -- No --> Q4
    FORCE_PARALLEL --> Q4

    Q4["Q4: Post-Implementation Handling\n• Offer options ✓\n• Create PR automatically\n• Just stop"]:::askq
    Q4 --> Q5

    Q5["Q5: Dialectic Mode\n• None ✓\n• Roundtable"]:::askq
    Q5 --> Q5_CHECK{dialectic_mode\n≠ none?}
    Q5_CHECK -- No --> Q7
    Q5_CHECK -- Yes --> Q6

    Q6["Q6: Dialectic Level\n• Planning only\n• Planning + gates ✓\n• Full"]:::askq
    Q6 --> Q7

    Q7["Q7: Token Enforcement\n• Work-item level\n• Gate level ✓\n• Every step"]:::askq
    Q7 --> STORE["Store all in SESSION_PREFERENCES"]
    STORE --> DONE(["0.4 Complete → 0.6"])

    subgraph legend["Legend"]
        L1["AskUserQuestion"]:::askq
        L2{Decision}
        L3["Auto-derived"]
        L4(["Terminal"])
    end

    classDef askq fill:#4a9eff,color:#fff,stroke:#2266cc
    classDef success fill:#51cf66,color:#000,stroke:#2f9e44

    class Q1,Q2,Q3,Q4,Q5,Q6,Q7 askq
    class DONE success
```

---

## Detail: Need-Flag Classification (Phase 0.7)

Four-question classification that routes the entire develop session into fast path or flag-gated phases.

```mermaid
flowchart TD
    START(["Enter 0.7\nNeed-Flag Classification"]) --> QRESEARCH

    QRESEARCH["Q-RESEARCH:\n'Do we need to investigate before building?'\n(unfamiliar code OR fuzzy requirements)\nYes → turns on Research + Discovery phases"]:::askq
    QRESEARCH --> QINFRA

    QINFRA["Q-INFRA:\n'New dependencies, infrastructure, or schema changes?'\n(new 3P dep / new service / table-column-field / migration)\nYes → auto-sets needs_design"]:::askq
    QINFRA --> INFRA_CHECK{Q-INFRA = yes?}

    INFRA_CHECK -- Yes --> AUTO_DESIGN["Auto-set needs_design = true\n_(skip Q-DESIGN — infra implies design)_"]
    INFRA_CHECK -- No --> QDESIGN

    QDESIGN["Q-DESIGN:\n'Is there a real design decision to make?'\n(new structure / choice between approaches /\ninterface other code will depend on)\nYes → turns on Design phase"]:::askq
    QDESIGN --> QSIZE

    AUTO_DESIGN --> QSIZE

    QSIZE["Q-SIZE:\n'Roughly how big is this?'\nSmall / Medium / Large\n(signal only — tunes parallelization +\ncheckpoints; NEVER affects rigor or gates)"]:::askq
    QSIZE --> RESOLVE

    RESOLVE["Resolve booleans:\n• needs_research\n• needs_design\n• needs_infrastructure\n• size_estimate\n→ store in SESSION_PREFERENCES"]
    RESOLVE --> FLAG_EVAL{Any flag\nset to true?}

    FLAG_EVAL -- "Zero flags" --> FAST_ANNOUNCE["Announce fast path (verbatim):\n'This looks like a small, well-understood change…\nI'll take the fast path: skip research/discovery/\ndesign/planning, write a short inline plan for\nyou to confirm, then implement…'"]
    FAST_ANNOUNCE --> LOG_FAST["Log: 'Fast path: zero-flag change.\nFewer phases, lighter floor, develop resident.'"]
    LOG_FAST --> FASTPATH(["Fast Path:\nShort inline plan → operator confirm → implement\n(lighter review floor, develop STAYS resident)"])

    FLAG_EVAL -- "needs_research = true" --> RESEARCH_FIRST(["→ /feature-research\n(then design/plan/implement per flags)"])

    FLAG_EVAL -- "needs_design or needs_infrastructure\n(no research)" --> DESIGN_FIRST(["→ /feature-design"])

    subgraph note["Orthogonality rules"]
        N1["needs_research ⊥ needs_design ⊥ needs_infrastructure\nsize_estimate ⊥ all flags (never gates a phase)\nQ-INFRA=yes ⟹ needs_design=true (auto, no re-ask)"]
    end

    subgraph legend["Legend"]
        L1["AskUserQuestion"]:::askq
        L2{Decision}
        L3(["Terminal / Route"]):::success
        L4["Gate"]:::gate
    end

    classDef askq fill:#4a9eff,color:#fff,stroke:#2266cc
    classDef gate fill:#ff6b6b,color:#fff,stroke:#cc3333
    classDef success fill:#51cf66,color:#000,stroke:#2f9e44

    class QRESEARCH,QINFRA,QDESIGN,QSIZE askq
    class FASTPATH,RESEARCH_FIRST,DESIGN_FIRST success
    class FLAG_EVAL gate
```

---

## Cross-Reference: Overview Nodes → Detail Diagrams

| Overview Node | Detail Diagram |
|---|---|
| `0.5 Continuation Detection` | Detail: Continuation Detection (Phase 0.5) |
| `0.4 Collect Workflow Preferences` | Detail: Workflow Preferences Wizard (Phase 0.4) |
| `0.7 Need-Flag Classification` | Detail: Need-Flag Classification (Phase 0.7) |
| `0.1 Escape Hatch Detection` | Covered inline in Overview (three patterns, two user choices each) |
| `0.2 / 0.3 Motivation + WHAT` | Covered inline in Overview (single AskUserQuestion per step) |
| `0.6 Refactoring Mode` | Covered inline in Overview (keyword scan, boolean set) |
