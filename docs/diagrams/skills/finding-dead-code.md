<!-- diagram-meta: {"source": "skills/finding-dead-code/SKILL.md","source_hash": "sha256:29b8f229b4c47a3ff87e62a6f3cba53562914d96e7007534a162c1660e5cca57","generator": "stamp"} -->
# Finding Dead Code - Workflow Diagrams

The finding-dead-code skill orchestrates dead code analysis through 4 sequential commands spanning 8 phases (0-7). Each command depends on state from the previous.

## Cross-Reference Table

| Overview Node | Detail Diagram | Phases | Source |
|---------------|---------------|--------|--------|
| Setup | [Setup & Scope](#setup--scope-detail-phases-0-1) | 0-1 | `commands/dead-code-setup.md` |
| Analyze | [Analysis](#analysis-detail-phases-2-5) | 2-5 | `commands/dead-code-analyze.md` |
| Report | [Report](#report-detail-phase-6) | 6 | `commands/dead-code-report.md` |
| Implement | [Implementation](#implementation-detail-phase-7) | 7 | `commands/dead-code-implement.md` |

## Overview Diagram

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{{Decision}}
        L3([Terminal])
        L4[/Quality Gate/]:::gate
        L5[Skill Invocation]:::subagent
    end

    START([User invokes<br>finding-dead-code]) --> SETUP

    subgraph SETUP ["/dead-code-setup -- Phases 0-1"]
        direction TB
        GIT[Phase 0: Git Safety] --> SCOPE[Phase 1: Scope Selection]
    end

    SETUP --> ANALYZE

    subgraph ANALYZE ["/dead-code-analyze -- Phases 2-5"]
        direction TB
        EXTRACT[Phase 2: Code Item Extraction] --> TRIAGE[Phase 3: Initial Triage]
        TRIAGE --> VERIFY[Phase 4: Verification]
        VERIFY --> RESCAN[Phase 5: Iterative Re-scan]
    end

    ANALYZE --> REPORT

    subgraph REPORT ["/dead-code-report -- Phase 6"]
        direction TB
        GEN[Phase 6: Report Generation]
    end

    REPORT --> IMPL

    subgraph IMPL ["/dead-code-implement -- Phase 7"]
        direction TB
        EXEC[Phase 7: Implementation]
    end

    IMPL --> DONE([Analysis Complete]):::success

    classDef gate fill:#ff6b6b,stroke:#d63031,color:#fff
    classDef subagent fill:#4a9eff,stroke:#2d7dd2,color:#fff
    classDef success fill:#51cf66,stroke:#2f9e44,color:#fff
```

## Setup & Scope Detail (Phases 0-1)

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{{Decision}}
        L3([Terminal])
        L4[/Quality Gate/]:::gate
        L5[Skill Invocation]:::subagent
    end

    START([/dead-code-setup]) --> STATUS

    subgraph Phase0 ["Phase 0: Git Safety"]
        STATUS["Run git status<br>--porcelain"] --> DIRTY{{Uncommitted<br>changes?}}

        DIRTY -->|Yes| PRESENT_CHANGES["Present changes<br>to user"]
        DIRTY -->|No| WORKTREE_Q

        PRESENT_CHANGES --> COMMIT_Q{{User choice}}
        COMMIT_Q -->|"Yes, commit"| DO_COMMIT["Ask commit message<br>and create commit"]
        COMMIT_Q -->|"No, proceed"| WARN_RISK["Warn about risks"]
        COMMIT_Q -->|Abort| ABORT([Abort analysis])

        DO_COMMIT --> WORKTREE_Q
        WARN_RISK --> WORKTREE_Q

        WORKTREE_Q{{"Create worktree?<br>(Recommended)"}}
        WORKTREE_Q -->|Yes| CREATE_WT["Invoke using-git-worktrees<br>Branch: dead-code-hunt-<br>YYYY-MM-DD-HHMM"]:::subagent
        WORKTREE_Q -->|No| WARN_DIRECT["Warn: working in<br>current directory<br>Require explicit approval<br>for modifications"]
    end

    CREATE_WT --> SCOPE
    WARN_DIRECT --> SCOPE

    subgraph Phase1 ["Phase 1: Scope Selection"]
        SCOPE["AskUserQuestion:<br>Select analysis scope"] --> SCOPE_CHOICE{{Scope}}

        SCOPE_CHOICE -->|"A: Branch changes"| BRANCH_DIFF["git diff merge-base<br>--diff-filter=AM<br>--name-only"]
        SCOPE_CHOICE -->|"B: Uncommitted"| UNCOMMITTED["git diff +<br>git diff --cached<br>--diff-filter=AM"]
        SCOPE_CHOICE -->|"C: Specific files"| USER_FILES["User provides<br>file paths"]
        SCOPE_CHOICE -->|"D: Full repo"| ALL_FILES["All code files<br>matching language patterns"]

        BRANCH_DIFF --> FILES_READY
        UNCOMMITTED --> FILES_READY
        USER_FILES --> FILES_READY
        ALL_FILES --> FILES_READY

        FILES_READY[/Target files identified/]:::gate
    end

    subgraph ARH ["ARH Response Processing"]
        ARH_CHECK{{User response<br>pattern}}
        ARH_CHECK -->|"RESEARCH_REQUEST"| ARH_RESEARCH["Dispatch research<br>subagent"]:::subagent
        ARH_CHECK -->|"UNKNOWN"| ARH_UNKNOWN["Dispatch research<br>subagent"]:::subagent
        ARH_CHECK -->|"CLARIFICATION"| ARH_CLARIFY["Answer clarification<br>then re-ask"]
        ARH_CHECK -->|"SKIP"| ARH_SKIP["Proceed to next item"]
    end

    FILES_READY --> NEXT([Proceed to<br>/dead-code-analyze]):::success

    classDef gate fill:#ff6b6b,stroke:#d63031,color:#fff
    classDef subagent fill:#4a9eff,stroke:#2d7dd2,color:#fff
    classDef success fill:#51cf66,stroke:#2f9e44,color:#fff
```

## Analysis Detail (Phases 2-5)

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{{Decision}}
        L3([Terminal])
        L4[/Quality Gate/]:::gate
    end

    START([/dead-code-analyze]) --> EXTRACT_START

    subgraph Phase2 ["Phase 2: Code Item Extraction"]
        EXTRACT_START["For each file in scope"] --> DIFF["Get diff of added lines"]
        DIFF --> PARSE["Parse declarations:<br>procs, types, fields,<br>imports, constants,<br>macros, iterators,<br>getters/setters"]
        PARSE --> RECORD["Record: type, name,<br>location, signature"]
        RECORD --> GROUP_SYM["Group symmetric pairs:<br>get/set/clear, foo/foo="]
        GROUP_SYM --> MAP_WO["Map setter/store to<br>corresponding getter/read"]
    end

    MAP_WO --> PRESENT

    subgraph Phase3 ["Phase 3: Initial Triage"]
        PRESENT["Present ALL items<br>grouped by type<br>with counts"] --> SHOW_PAIRS["Show symmetric<br>pairs detected"]
        SHOW_PAIRS --> PROCEED_Q{{"Proceed with<br>verification?"}}
        PROCEED_Q -->|No| STOP([User stops])
        PROCEED_Q -->|Yes| ITEM_START
    end

    ITEM_START --> CLAIM

    subgraph Phase4 ["Phase 4: Verification"]
        CLAIM["Generate dead code<br>claim for item"] --> GREP["Search entire codebase:<br>grep -rn name"]
        GREP --> EXCLUDE_DEF["Exclude definition<br>from results"]
        EXCLUDE_DEF --> EVIDENCE{{Evidence<br>category}}

        EVIDENCE -->|Zero callers| DEAD_DIRECT["DEAD"]
        EVIDENCE -->|Self-call only| DEAD_SELF["DEAD<br>(self-recursive)"]
        EVIDENCE -->|Test-only callers| MAYBE_TEST["MAYBE DEAD<br>Ask user: keep<br>as test utility?"]
        EVIDENCE -->|Dead caller only| MARK_TRANS["TRANSITIVE DEAD"]
        EVIDENCE -->|Live callers| ALIVE["ALIVE"]
        EVIDENCE -->|Exported API| MAYBE_API["MAYBE ALIVE<br>Flag for user"]
        EVIDENCE -->|Dynamic possible| INVESTIGATE["Search eval, reflect,<br>getattr, dispatch"]

        INVESTIGATE --> DYN_FOUND{{Dynamic dispatch<br>found?}}
        DYN_FOUND -->|Yes| MAYBE_DYN["MAYBE ALIVE<br>Flag for user"]
        DYN_FOUND -->|No| DEAD_NO_DYN["DEAD<br>(no dynamic dispatch)"]

        DEAD_DIRECT --> SYM_CHECK
        DEAD_SELF --> SYM_CHECK
        MAYBE_TEST --> SYM_CHECK
        MARK_TRANS --> SYM_CHECK
        ALIVE --> SYM_CHECK
        MAYBE_API --> SYM_CHECK
        MAYBE_DYN --> SYM_CHECK
        DEAD_NO_DYN --> SYM_CHECK

        SYM_CHECK["Symmetric Pair<br>Analysis"] --> SYM_Q{{Pair status}}
        SYM_Q -->|All dead| SYM_DEAD["Entire group dead"]
        SYM_Q -->|All alive| SYM_ALIVE["Group alive"]
        SYM_Q -->|Mixed| SYM_MIXED["Flag asymmetry<br>for user decision"]

        SYM_DEAD --> REMOVE_Q
        SYM_ALIVE --> NEXT_ITEM
        SYM_MIXED --> NEXT_ITEM

        REMOVE_Q{{"Offer remove<br>and test?"}}
        REMOVE_Q -->|Yes| EXP_REMOVE["Create temp branch<br>Remove code<br>Run tests"]
        REMOVE_Q -->|No| NEXT_ITEM

        EXP_REMOVE --> TEST_RESULT{{Tests pass?}}
        TEST_RESULT -->|Pass| CONFIRMED["Definitive proof:<br>code was dead"]
        TEST_RESULT -->|Fail| RESTORE["Restore from git"]
        CONFIRMED --> NEXT_ITEM
        RESTORE --> NEXT_ITEM

        NEXT_ITEM{{More items?}}
        NEXT_ITEM -->|Yes| CLAIM
        NEXT_ITEM -->|No| WO_CHECK
    end

    subgraph WO ["Write-Only Detection"]
        WO_CHECK["For each setter/store"] --> WO_GREP["Search for<br>corresponding getter/read"]
        WO_GREP --> WO_RESULT{{Getter has<br>callers?}}
        WO_RESULT -->|"Setter called,<br>getter unused"| WO_DEAD["WRITE-ONLY DEAD<br>(both setter+getter)"]
        WO_RESULT -->|Both have callers| WO_ALIVE["Feature is alive"]
    end

    WO_DEAD --> RESCAN_START
    WO_ALIVE --> RESCAN_START

    subgraph Phase5 ["Phase 5: Iterative Re-scan"]
        RESCAN_START["Mark initial dead code"] --> REEXAMINE["Re-examine remaining<br>items, excluding<br>already-dead"]
        REEXAMINE --> REVERIFY["Re-run verification"]
        REVERIFY --> TRANS_RECHECK["Check newly<br>transitive dead"]
        TRANS_RECHECK --> WO_RECHECK["Check newly<br>write-only dead"]
        WO_RECHECK --> NEW_DEAD{{New dead<br>code found?}}
        NEW_DEAD -->|Yes| REEXAMINE
        NEW_DEAD -->|No| FIXED_POINT[/Fixed-point reached/]:::gate
    end

    FIXED_POINT --> DONE([Proceed to<br>/dead-code-report]):::success

    classDef gate fill:#ff6b6b,stroke:#d63031,color:#fff
    classDef subagent fill:#4a9eff,stroke:#2d7dd2,color:#fff
    classDef success fill:#51cf66,stroke:#2f9e44,color:#fff
```

## Report Detail (Phase 6)

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{{Decision}}
        L3([Terminal])
        L4[/Quality Gate/]:::gate
    end

    START([/dead-code-report]) --> COMPILE

    subgraph Phase6 ["Phase 6: Report Generation"]
        COMPILE["Compile all verdicts<br>and evidence"] --> SUMMARY["Generate summary table:<br>Dead / Alive / Transitive<br>counts by category"]

        SUMMARY --> HIGH_CONF["Document High Confidence<br>findings: location, grep<br>evidence, symmetric pair<br>status, removal complexity"]

        HIGH_CONF --> TRANS_FINDINGS["Document Transitive<br>Dead Code: call chains<br>showing dead dependency"]

        TRANS_FINDINGS --> WO_FINDINGS["Document Write-Only<br>Dead Code: setter/getter<br>mismatch, stored-but-<br>never-read"]

        WO_FINDINGS --> ALIVE_SECTION["Document Alive Code:<br>callers, locations,<br>verification proof"]

        ALIVE_SECTION --> IMPL_PLAN["Generate Implementation Plan:<br>Phase 1: Simple deletions<br>Phase 2: Transitive deletions<br>Phase 3: Write-only cleanup"]

        IMPL_PLAN --> VERIFY_CMDS["Generate Verification<br>Commands: grep checks<br>and test suite runs"]

        VERIFY_CMDS --> RISK["Generate Risk<br>Assessment table"]

        RISK --> SAVE["Save report to<br>~/.local/spellbook/docs/<br>project-encoded/reports/"]

        SAVE --> EVIDENCE_GATE[/Evidence-complete gate:<br>Every finding has grep proof?<br>Every deletion ordered?<br>Risk levels assigned?/]:::gate
    end

    EVIDENCE_GATE --> DONE([Proceed to<br>/dead-code-implement]):::success

    classDef gate fill:#ff6b6b,stroke:#d63031,color:#fff
    classDef success fill:#51cf66,stroke:#2f9e44,color:#fff
```

## Implementation Detail (Phase 7)

```mermaid
flowchart TD
    subgraph Legend
        L1[Process]
        L2{{Decision}}
        L3([Terminal])
        L4[/Quality Gate/]:::gate
    end

    START([/dead-code-implement]) --> PROMPT

    subgraph Phase7 ["Phase 7: Implementation"]
        PROMPT["Present options:<br>A: Remove all automatically<br>B: Remove one-by-one<br>C: Create cleanup branch<br>D: Keep report only"]

        PROMPT --> CHOICE{{User choice}}

        CHOICE -->|D| DONE_D([Keep report<br>No action]):::success

        CHOICE -->|C| BRANCH["Create branch:<br>dead-code-cleanup/date<br>Apply all deletions<br>Push branch"]
        BRANCH --> DONE_C([Branch created<br>for review]):::success

        CHOICE -->|"A or B"| SHOW

        subgraph LOOP ["Ordered Deletion Loop"]
            direction TB
            SHOW["Show code to remove:<br>exact lines, location"]
            SHOW --> SHOW_GREP["Show grep verification:<br>paste unused proof"]
            SHOW_GREP --> APPLY["Apply deletion"]
            APPLY --> REVERIFY["Re-verify with grep:<br>no references remain"]

            REVERIFY --> TEST_Q{{"Run tests?"}}
            TEST_Q -->|Yes| RUN_TESTS["Run test suite"]
            TEST_Q -->|No| NEXT_IN_PHASE

            RUN_TESTS --> TEST_OK{{Tests pass?}}
            TEST_OK -->|Yes| NEXT_IN_PHASE
            TEST_OK -->|Fail| HALT["HALT"]

            HALT --> FAIL_CHOICE{{Recovery}}
            FAIL_CHOICE -->|"A: Revert"| REVERT["Revert deletion<br>Skip item"]
            FAIL_CHOICE -->|"B: Fix"| FIX["Fix failure<br>then continue"]
            FAIL_CHOICE -->|"C: Keep"| KEEP_FAIL["Keep deletion<br>Document failure"]

            REVERT --> NEXT_IN_PHASE
            FIX --> NEXT_IN_PHASE
            KEEP_FAIL --> NEXT_IN_PHASE

            NEXT_IN_PHASE{{More items<br>in phase?}}
            NEXT_IN_PHASE -->|Yes| SHOW
        end

        NEXT_IN_PHASE -->|No| COMMIT["Commit phase group"]
        COMMIT --> MORE_PHASES{{More phases<br>in plan?}}
        MORE_PHASES -->|Yes| SHOW
        MORE_PHASES -->|No| FINAL_VERIFY

        FINAL_VERIFY["Run full test suite"] --> FINAL_SCAN["Verify no new dead<br>code from cleanup"]
        FINAL_SCAN --> FINAL_GATE[/All tests pass?<br>No new dead code?/]:::gate
    end

    FINAL_GATE --> DONE([Implementation<br>Complete]):::success

    classDef gate fill:#ff6b6b,stroke:#d63031,color:#fff
    classDef success fill:#51cf66,stroke:#2f9e44,color:#fff
```

## Detection Patterns Reference

```mermaid
flowchart LR
    subgraph Patterns ["7 Detection Patterns"]
        direction TB
        P1["P1: Asymmetric API<br>get/set/clear group:<br>any member zero callers<br>= that member dead"]
        P2["P2: Convenience Wrapper<br>foo only calls bar:<br>zero callers for foo<br>= dead wrapper"]
        P3["P3: Transitive Dead<br>All callers are dead<br>= item is dead<br>iterate to fixed-point"]
        P4["P4: Field + Accessors<br>field + getter + setter:<br>all three zero usage<br>= dead feature"]
        P5["P5: Test-Only Usage<br>All callers in test files<br>= ask user, do not auto-mark"]
        P6["P6: Write-Only Dead<br>Setter called, getter unused<br>= both dead<br>stored but never read"]
        P7["P7: Iterator No Consumers<br>Iterator defined but<br>never used in for loops<br>= dead iterator"]
    end
```

## Source Cross-Reference

| Diagram Node | Source Reference |
|-------------|----------------|
| Phase 0: Git Safety | `commands/dead-code-setup.md` Phase 0, `SKILL.md` Invariant 4 |
| Phase 1: Scope Selection | `commands/dead-code-setup.md` Phase 1 |
| Phase 2: Code Item Extraction | `commands/dead-code-analyze.md` Phase 2 |
| Phase 3: Initial Triage | `commands/dead-code-analyze.md` Phase 3 |
| Phase 4: Verification | `commands/dead-code-analyze.md` Phase 4 (Steps 1-6) |
| Write-Only Detection | `commands/dead-code-analyze.md` Phase 4 Step 3, `SKILL.md` Pattern 6 |
| Phase 5: Iterative Re-scan | `commands/dead-code-analyze.md` Phase 5, `SKILL.md` Pattern 3 |
| Fixed-point gate | `SKILL.md` Invariant 2: Full-Graph Verification |
| Evidence-complete gate | `SKILL.md` Invariant 5: Evidence Over Confidence |
| Phase 6: Report Generation | `commands/dead-code-report.md` Phase 6 |
| Phase 7: Implementation | `commands/dead-code-implement.md` Phase 7 |
| ARH Response Processing | `SKILL.md` ARH_INTEGRATION block |
| Symmetric Pair Analysis | `commands/dead-code-analyze.md` Phase 4 Step 6, `SKILL.md` Pattern 1 |
| Remove and Test | `commands/dead-code-analyze.md` Phase 4 Step 5 |
| Test failure recovery | `commands/dead-code-implement.md` Phase 7: Test failure recovery |
| Detection Patterns P1-P7 | `SKILL.md` Detection Patterns section |
