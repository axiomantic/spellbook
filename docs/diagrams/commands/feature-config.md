<!-- diagram-meta: {"source": "commands/feature-config.md", "source_hash": "sha256:83c81a603fa55c0fc81e0c4d44ee00f21ed2c70bc4c507813a5e6b0e5654b395", "generated_at": "2026-03-10T06:27:43Z", "generator": "generate_diagrams.py"} -->
# Diagram: feature-config

## Overview

```mermaid
flowchart TD
    START([Entry: Phase 0]) --> CONT["0.5 Continuation<br/>Detection"]
    CONT -->|No signals| BASE["0.05 Base Branch<br/>& Worktree Setup"]
    CONT -->|Signals detected| RESUME["Resume Flow"]
    RESUME --> JUMP([Phase Jump:<br/>Skip to Target])
    BASE --> ESC["0.1 Escape Hatch<br/>Detection"]
    ESC -->|Hatch found| HATCH_ROUTE["Route by<br/>Escape Hatch"]
    HATCH_ROUTE --> JUMP_ESC([Skip to<br/>Target Phase])
    ESC -->|None| MOT["0.2 Clarify<br/>Motivation"]
    MOT --> FEAT["0.3 Clarify<br/>Feature"]
    FEAT --> PREFS["0.4 Collect<br/>Preferences"]
    PREFS --> REFAC["0.6 Detect<br/>Refactoring Mode"]
    REFAC --> COMP["0.7 Complexity<br/>Classification"]
    COMP --> ROUTE{Route by Tier}
    ROUTE -->|TRIVIAL| EXIT([Exit Skill])
    ROUTE -->|SIMPLE| SIMPLE(["Lightweight Research<br/>then /feature-implement"])
    ROUTE -->|STANDARD/COMPLEX| RESEARCH(["/feature-research<br/>Phase 1"])

    subgraph Legend
        L1[Process Step]
        L2{Decision Point}
        L3([Terminal/Exit])
    end
    style L1 fill:#4a9eff,color:#fff
    style L2 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff
```

## 0.5 Continuation Detection

```mermaid
flowchart TD
    CD_START([Entry]) --> CD_CHECK{Continuation<br/>Signals?}
    CD_CHECK -->|"User says continue/resume/<br/>MCP has skill phase/<br/>Artifacts exist"| CD_PARSE["Step 1: Parse<br/>Recovery Context"]
    CD_CHECK -->|No signals| CD_EXIT([Proceed to 0.05])

    CD_PARSE --> CD_VERIFY["Step 2: Verify<br/>Artifact Existence"]
    CD_VERIFY --> CD_ART{Artifacts Match<br/>Claimed Phase?}
    CD_ART -->|Yes| CD_PREFS["Step 3: Quick<br/>Preferences Check<br/>(4 questions only)"]
    CD_ART -->|Missing artifacts| CD_MISSING{User Choice}
    CD_MISSING -->|Regenerate| CD_PREFS
    CD_MISSING -->|Start fresh| CD_EXIT

    CD_PREFS --> CD_SYNTH["Step 4: Synthesize<br/>Resume Point"]
    CD_SYNTH --> CD_INFER{Resume Source}
    CD_INFER -->|In-progress todo| CD_CONFIRM["Step 5: Confirm<br/>and Resume"]
    CD_INFER -->|skill_phase from MCP| CD_CONFIRM
    CD_INFER -->|Artifact pattern| CD_CONFIRM

    CD_CONFIRM --> CD_JUMP["Phase Jump:<br/>Skip Completed Phases"]
    CD_JUMP --> CD_TARGET([Jump to<br/>Target Phase])

    style CD_CHECK fill:#ff6b6b,color:#fff
    style CD_ART fill:#ff6b6b,color:#fff
    style CD_MISSING fill:#ff6b6b,color:#fff
    style CD_INFER fill:#ff6b6b,color:#fff
    style CD_EXIT fill:#51cf66,color:#fff
    style CD_TARGET fill:#51cf66,color:#fff
```

## 0.05 Base Branch & Worktree Setup

```mermaid
flowchart TD
    BB_START([Entry]) --> BB_DET{Base Branch<br/>Source?}
    BB_DET -->|User specified| BB_EXPLICIT["Use Explicit Branch"]
    BB_DET -->|Not specified| BB_CURRENT["Use Current Branch"]

    BB_EXPLICIT --> BB_EXISTS{Branch Exists?}
    BB_EXISTS -->|Yes| BB_CHECKOUT["Find Checkout<br/>Location"]
    BB_EXISTS -->|No| BB_ASK_NAME["Ask User to<br/>Confirm Name"]
    BB_ASK_NAME --> BB_EXISTS

    BB_CURRENT --> BB_CHECKOUT
    BB_CHECKOUT --> BB_DIRTY{Uncommitted<br/>Changes?}
    BB_DIRTY -->|Clean| BB_CREATE["Create Worktree<br/>.claude/worktrees/&lt;slug&gt;"]
    BB_DIRTY -->|Dirty| BB_DIRTY_CHOICE{User Choice}
    BB_DIRTY_CHOICE -->|Commit first| BB_COMMIT["Commit Changes"] --> BB_CREATE
    BB_DIRTY_CHOICE -->|Leave uncommitted| BB_CREATE

    BB_CREATE --> BB_STORE["Store base_branch<br/>& worktree_path"]
    BB_STORE --> BB_EXIT([Proceed to 0.1])

    style BB_DET fill:#ff6b6b,color:#fff
    style BB_EXISTS fill:#ff6b6b,color:#fff
    style BB_DIRTY fill:#ff6b6b,color:#fff
    style BB_DIRTY_CHOICE fill:#ff6b6b,color:#fff
    style BB_EXIT fill:#51cf66,color:#fff
```

## 0.1 Escape Hatch Detection

```mermaid
flowchart TD
    EH_START([Entry]) --> EH_PARSE{Escape Hatch<br/>in User Message?}
    EH_PARSE -->|"using design doc"| EH_DESIGN{Review or<br/>Accept?}
    EH_PARSE -->|"using impl plan"| EH_IMPL{Review or<br/>Accept?}
    EH_PARSE -->|"just implement,<br/>no docs"| EH_MINIMAL([Minimal Inline Plan<br/>→ Phase 4])
    EH_PARSE -->|None detected| EH_PROCEED([Proceed to 0.2])

    EH_DESIGN -->|Review first| EH_D_REVIEW(["Skip 2.1<br/>→ Phase 2.2 Review"])
    EH_DESIGN -->|Treat as ready| EH_D_READY(["Skip Phase 2<br/>→ Phase 3"])

    EH_IMPL -->|Review first| EH_I_REVIEW(["Skip 2.1-3.1<br/>→ Phase 3.2 Review"])
    EH_IMPL -->|Treat as ready| EH_I_READY(["Skip Phases 2-3<br/>→ Phase 4"])

    style EH_PARSE fill:#ff6b6b,color:#fff
    style EH_DESIGN fill:#ff6b6b,color:#fff
    style EH_IMPL fill:#ff6b6b,color:#fff
    style EH_MINIMAL fill:#51cf66,color:#fff
    style EH_PROCEED fill:#51cf66,color:#fff
    style EH_D_REVIEW fill:#51cf66,color:#fff
    style EH_D_READY fill:#51cf66,color:#fff
    style EH_I_REVIEW fill:#51cf66,color:#fff
    style EH_I_READY fill:#51cf66,color:#fff
```

## 0.2-0.4 Motivation, Feature, Preferences

```mermaid
flowchart TD
    MOT_START([From 0.1]) --> MOT_CHECK{Motivation<br/>Clear?}
    MOT_CHECK -->|Yes| MOT_STORE["Store Motivation"]
    MOT_CHECK -->|Ambiguous| MOT_ASK["Ask WHY via<br/>AskUserQuestion"]
    MOT_ASK --> MOT_CAT["Categorize:<br/>User Pain / Perf /<br/>Tech Debt / Business /<br/>Security / DX"]
    MOT_CAT --> MOT_STORE

    MOT_STORE --> FEAT_ASK["0.3 Ask WHAT:<br/>Core purpose +<br/>Resources/links"]
    FEAT_ASK --> FEAT_STORE["Store Feature Essence"]

    FEAT_STORE --> PREF_WIZ["0.4 Configuration Wizard<br/>(Single AskUserQuestion)"]

    subgraph PREF_WIZ_DETAIL["Wizard: 4 Questions"]
        PQ1["Q1: Execution Mode<br/>Autonomous / Interactive /<br/>Mostly Autonomous"]
        PQ2["Q2: Parallelization<br/>Maximize / Conservative /<br/>Ask Each Time"]
        PQ3["Q3: Worktree Strategy<br/>Single / Per Track / None"]
        PQ4["Q4: Post-Implementation<br/>Offer Options / Auto PR / Stop"]
    end

    PREF_WIZ --> COUPLING{Worktree =<br/>per_parallel_track?}
    COUPLING -->|Yes| FORCE["Force parallelization<br/>= maximize"]
    COUPLING -->|No| PREF_DONE["Store All in<br/>SESSION_PREFERENCES"]
    FORCE --> PREF_DONE
    PREF_DONE --> PREF_EXIT([Proceed to 0.6])

    style MOT_CHECK fill:#ff6b6b,color:#fff
    style COUPLING fill:#ff6b6b,color:#fff
    style PREF_EXIT fill:#51cf66,color:#fff
```

## 0.6-0.7 Refactoring & Complexity

```mermaid
flowchart TD
    REF_START([From 0.4]) --> REF_CHECK{Request Contains<br/>Refactor Keywords?}
    REF_CHECK -->|Yes| REF_SET["Set refactoring_mode<br/>= true"]
    REF_CHECK -->|No| COMP_START

    REF_SET --> COMP_START["0.7 Run Mechanical<br/>Heuristics"]

    COMP_START --> COMP_BASH["Bash: File Count,<br/>Test Impact,<br/>Integration Points"]
    COMP_BASH --> COMP_BEHAV["Analyze: Behavioral<br/>Change? Structural<br/>Change?"]
    COMP_BEHAV --> COMP_MATRIX["Derive Tier<br/>from Matrix"]
    COMP_MATRIX --> COMP_PRESENT["Present Results<br/>to User"]
    COMP_PRESENT --> COMP_CONFIRM{User Confirms<br/>or Overrides?}
    COMP_CONFIRM -->|Confirm| COMP_ROUTE{Tier?}
    COMP_CONFIRM -->|Override| COMP_OVERRIDE["Use User's Tier"] --> COMP_ROUTE

    COMP_ROUTE -->|TRIVIAL| T_EXIT(["Exit Skill:<br/>Direct Change"])
    COMP_ROUTE -->|SIMPLE| T_SIMPLE(["Lightweight Research<br/>→ /feature-implement"])
    COMP_ROUTE -->|STANDARD| T_STD(["/feature-research<br/>Phase 1"])
    COMP_ROUTE -->|COMPLEX| T_COMP(["/feature-research<br/>Phase 1"])

    style REF_CHECK fill:#ff6b6b,color:#fff
    style COMP_CONFIRM fill:#ff6b6b,color:#fff
    style COMP_ROUTE fill:#ff6b6b,color:#fff
    style T_EXIT fill:#51cf66,color:#fff
    style T_SIMPLE fill:#51cf66,color:#fff
    style T_STD fill:#51cf66,color:#fff
    style T_COMP fill:#51cf66,color:#fff
```

## Cross-Reference

| Overview Node | Detail Section | Source |
|---|---|---|
| 0.5 Continuation Detection | 0.5 Continuation Detection | `commands/feature-config.md:25-172` |
| 0.05 Base Branch & Worktree Setup | 0.05 Base Branch & Worktree Setup | `commands/feature-config.md:175-203` |
| 0.1 Escape Hatch Detection | 0.1 Escape Hatch Detection | `commands/feature-config.md:205-235` |
| 0.2 Clarify Motivation | 0.2-0.4 Motivation, Feature, Preferences | `commands/feature-config.md:237-276` |
| 0.3 Clarify Feature | 0.2-0.4 Motivation, Feature, Preferences | `commands/feature-config.md:278-287` |
| 0.4 Collect Preferences | 0.2-0.4 Motivation, Feature, Preferences | `commands/feature-config.md:289-338` |
| 0.6 Detect Refactoring Mode | 0.6-0.7 Refactoring & Complexity | `commands/feature-config.md:340-351` |
| 0.7 Complexity Classification | 0.6-0.7 Refactoring & Complexity | `commands/feature-config.md:353-431` |
| Route by Tier | 0.6-0.7 Refactoring & Complexity | `commands/feature-config.md:422-431` |

## Legend

```mermaid
flowchart LR
    L1[Process Step]
    L2{Decision Point}
    L3([Terminal/Exit])
    style L1 fill:#4a9eff,color:#fff
    style L2 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff
```
