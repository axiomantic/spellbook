# implementing-features

Use when building, creating, modifying, or planning any code change. Triggers: "implement X", "build Y", "add feature Z", "create X", "change how X works", "modify Y", "update the Z", "refactor X", "rework Y", "restructure Z", "make X do Y", "let's plan how to", "plan the implementation", "how should we implement", "how would you build", "what's the best way to implement", "I want to...", "We need...", "Would be great to...", "Can we add...", "Let's add...", "Let's build...", "Let's make...", "start a new project". Also for: new projects, repos, templates, greenfield development, refactoring, migrations, multi-file modifications, any code change requiring planning. PREFER THIS OVER plan mode or ad-hoc implementation for ANY substantive code change. NOT for: bug fixes (use debugging), pure research (use deep-research), questions about existing code without intent to change it, or test-only fixes (use fixing-tests).

## Workflow Diagram

# Diagram: implementing-features

Now I have enough source material to generate the diagrams. Let me produce the headless output.

## Overview

```mermaid
flowchart TD
    P0[Phase 0:<br/>Configuration] --> P0_ROUTE{Complexity<br/>Tier?}
    P0_ROUTE -->|TRIVIAL| EXIT_TRIV([Exit Skill])
    P0_ROUTE -->|SIMPLE| S1[Simple Path:<br/>Lightweight Research]
    P0_ROUTE -->|STANDARD / COMPLEX| P1[Phase 1:<br/>Research]

    S1 --> S2[Simple Path:<br/>Inline Plan]
    S2 --> P4_SIMPLE[Phase 4:<br/>Implementation]
    P4_SIMPLE --> P47[Phase 4.7:<br/>Finish Branch]

    P1 --> P15[Phase 1.5:<br/>Informed Discovery]
    P15 --> P2[Phase 2:<br/>Design]
    P2 --> P3[Phase 3:<br/>Impl Planning]
    P3 --> P3_ROUTE{Execution<br/>Mode?}
    P3_ROUTE -->|swarmed| P35[Phase 3.5-3.6:<br/>Work Packets + Handoff]
    P35 --> EXIT_SWARM([Exit Session])
    P3_ROUTE -->|delegated / direct| P4[Phase 4:<br/>Implementation]
    P4 --> P46[Phase 4.6:<br/>Quality Gates]
    P46 --> P47

    style EXIT_TRIV fill:#51cf66,color:#fff
    style EXIT_SWARM fill:#51cf66,color:#fff
    style P0_ROUTE fill:#ff6b6b,color:#fff
    style P3_ROUTE fill:#ff6b6b,color:#fff
    style P46 fill:#ff6b6b,color:#fff
```

## Phase 0: Configuration

```mermaid
flowchart TD
    START([Start]) --> P05{0.5: Continuation<br/>Signals?}
    P05 -->|Yes| VERIFY_ART[Verify Artifacts<br/>on Disk]
    VERIFY_ART --> QUICK_PREFS[Quick Preferences<br/>Check]
    QUICK_PREFS --> RESUME_PT[Determine<br/>Resume Point]
    RESUME_PT --> JUMP([Jump to<br/>Target Phase])

    P05 -->|No| P005[0.05: Base Branch<br/>Detection]
    P005 --> P005_DIRTY{Uncommitted<br/>Changes?}
    P005_DIRTY -->|Yes| P005_ASK{Commit First<br/>or Leave?}
    P005_ASK -->|Commit| P005_COMMIT[Commit Changes]
    P005_ASK -->|Leave| P005_LEAVE[Leave in<br/>Original Checkout]
    P005_COMMIT --> P005_WT[Create Worktree]
    P005_LEAVE --> P005_WT
    P005_DIRTY -->|No| P005_WT

    P005_WT --> P01{0.1: Escape<br/>Hatch?}
    P01 -->|Design doc| ESC_D{Review First<br/>or Treat Ready?}
    ESC_D -->|Review first| ESC_D_REV[Skip to 2.2]
    ESC_D -->|Treat as ready| ESC_D_SKIP[Skip Phase 2]
    P01 -->|Impl plan| ESC_I{Review First<br/>or Treat Ready?}
    ESC_I -->|Review first| ESC_I_REV[Skip to 3.2]
    ESC_I -->|Treat as ready| ESC_I_SKIP[Skip Phases 2-3]
    P01 -->|None| P02[0.2: Clarify<br/>Motivation]
    P02 --> P03[0.3: Clarify<br/>Feature Essence]
    P03 --> P04[0.4: Collect<br/>Workflow Preferences]
    P04 --> P06[0.6: Detect<br/>Refactoring Mode]
    P06 --> P07[0.7: Complexity<br/>Classification]
    P07 --> HEURISTICS[Run Mechanical<br/>Heuristics]
    HEURISTICS --> DERIVE[Derive Tier<br/>from Matrix]
    DERIVE --> CONFIRM{User Confirms<br/>Tier?}
    CONFIRM -->|Confirm| ROUTE{Route<br/>by Tier}
    CONFIRM -->|Override| DERIVE

    ROUTE -->|TRIVIAL| EXIT_T([Exit Skill])
    ROUTE -->|SIMPLE| SIMPLE_PATH([Simple Path])
    ROUTE -->|STANDARD| RESEARCH([Phase 1])
    ROUTE -->|COMPLEX| RESEARCH

    style P05 fill:#ff6b6b,color:#fff
    style P01 fill:#ff6b6b,color:#fff
    style ESC_D fill:#ff6b6b,color:#fff
    style ESC_I fill:#ff6b6b,color:#fff
    style CONFIRM fill:#ff6b6b,color:#fff
    style ROUTE fill:#ff6b6b,color:#fff
    style P005_DIRTY fill:#ff6b6b,color:#fff
    style EXIT_T fill:#51cf66,color:#fff
    style JUMP fill:#51cf66,color:#fff
    style SIMPLE_PATH fill:#51cf66,color:#fff
    style RESEARCH fill:#51cf66,color:#fff
```

## Phase 1: Research

```mermaid
flowchart TD
    START([Phase 1 Start]) --> PREREQ{Prerequisites<br/>Met?}
    PREREQ -->|No| STOP([Return to<br/>Prior Phase])
    PREREQ -->|Yes| P11[1.1: Research<br/>Strategy Planning]
    P11 --> P12[1.2: Execute Research<br/>via Subagent]
    P12 --> P12_RESULT{Subagent<br/>Succeeded?}
    P12_RESULT -->|Fail| P12_RETRY[Retry Once]
    P12_RETRY --> P12_RESULT2{Second<br/>Attempt?}
    P12_RESULT2 -->|Fail| P12_UNKNOWN[Return Findings<br/>as UNKNOWN]
    P12_RESULT2 -->|Success| P13
    P12_RESULT -->|Success| P13[1.3: Ambiguity<br/>Extraction]
    P12_UNKNOWN --> P13

    P13 --> P14[1.4: Research<br/>Quality Score]
    P14 --> GATE{Score<br/>= 100%?}
    GATE -->|Yes| DONE([Proceed to<br/>Phase 1.5])
    GATE -->|No| GATE_OPT{User<br/>Choice?}
    GATE_OPT -->|Continue anyway| DONE
    GATE_OPT -->|Iterate| P11
    GATE_OPT -->|Reduce scope| P13

    style PREREQ fill:#ff6b6b,color:#fff
    style GATE fill:#ff6b6b,color:#fff
    style GATE_OPT fill:#ff6b6b,color:#fff
    style P12_RESULT fill:#ff6b6b,color:#fff
    style P12_RESULT2 fill:#ff6b6b,color:#fff
    style STOP fill:#ff6b6b,color:#fff
    style DONE fill:#51cf66,color:#fff
    style P12 fill:#4a9eff,color:#fff
```

## Phase 1.5: Informed Discovery

```mermaid
flowchart TD
    START([Phase 1.5 Start]) --> PREREQ{Prerequisites<br/>Met?}
    PREREQ -->|No| STOP([Return to<br/>Phase 1])
    PREREQ -->|Yes| MEMORY[Memory-Primed<br/>Discovery Recall]
    MEMORY --> P150[1.5.0: Disambiguation<br/>Session]
    P150 --> ARH_D{Response<br/>Type?}
    ARH_D -->|Direct Answer| P151
    ARH_D -->|Research Request| FRAC{High Impact?}
    FRAC -->|Yes| FRACTAL[Fractal Thinking<br/>Pulse]
    FRAC -->|No| SUB_RESEARCH[Dispatch<br/>Research Subagent]
    FRACTAL --> P150
    SUB_RESEARCH --> P150
    ARH_D -->|Unknown| SUB_RESEARCH
    ARH_D -->|Skip| P151

    P151[1.5.1: Generate<br/>7-Category Questions] --> P152[1.5.2: Discovery<br/>Wizard with ARH]
    P152 --> P153[1.5.3: Build<br/>Glossary]
    P153 --> P154[1.5.4: Synthesize<br/>design_context]
    P154 --> P155[1.5.5: Completeness<br/>Checklist]
    P155 --> COMP_GATE{Score<br/>= 100%?}
    COMP_GATE -->|No| COMP_OPT{User<br/>Choice?}
    COMP_OPT -->|Return to discovery| P152
    COMP_OPT -->|Return to research| STOP_R([Return to<br/>Phase 1])
    COMP_OPT -->|Proceed anyway| P156
    COMP_GATE -->|Yes| P156[1.5.6: Create<br/>Understanding Doc]
    P156 --> USER_APP{User<br/>Approves?}
    USER_APP -->|Approve| P157[1.5.7: Dehallucination<br/>Gate]
    USER_APP -->|Changes| P156
    USER_APP -->|More info| P152

    P157 --> DEHAL{Hallucinations<br/>Found?}
    DEHAL -->|Yes| FIX_DOC[Fix Understanding<br/>Doc] --> P16
    DEHAL -->|No| P16[1.6: Devil's<br/>Advocate Review]
    P16 --> DA_RESULT[Present<br/>Critique]
    DA_RESULT --> DA_OPT{User<br/>Choice?}
    DA_OPT -->|Address issues| P152
    DA_OPT -->|Document limitations| DONE
    DA_OPT -->|Revise scope| P151
    DA_OPT -->|Proceed| DONE([Proceed to<br/>Phase 2])

    style PREREQ fill:#ff6b6b,color:#fff
    style COMP_GATE fill:#ff6b6b,color:#fff
    style USER_APP fill:#ff6b6b,color:#fff
    style DEHAL fill:#ff6b6b,color:#fff
    style ARH_D fill:#ff6b6b,color:#fff
    style DA_OPT fill:#ff6b6b,color:#fff
    style COMP_OPT fill:#ff6b6b,color:#fff
    style STOP fill:#ff6b6b,color:#fff
    style STOP_R fill:#ff6b6b,color:#fff
    style DONE fill:#51cf66,color:#fff
    style P157 fill:#4a9eff,color:#fff
    style P16 fill:#4a9eff,color:#fff
```

## Phase 2: Design

```mermaid
flowchart TD
    START([Phase 2 Start]) --> PREREQ{Prerequisites<br/>Met?}
    PREREQ -->|No| STOP([Return to<br/>Prior Phase])
    PREREQ -->|Yes| ESC{Escape<br/>Hatch?}
    ESC -->|Treat as ready| SKIP([Skip to<br/>Phase 3])
    ESC -->|Review first| P22
    ESC -->|None| P21[2.1: Create Design<br/>Subagent: brainstorming<br/>SYNTHESIS MODE]
    P21 --> P22[2.2: Review Design<br/>Subagent:<br/>reviewing-design-docs]
    P22 --> P23{2.3: Approval<br/>Gate}
    P23 -->|autonomous + findings| P24[2.4: Fix Design<br/>Subagent:<br/>executing-plans]
    P24 --> P25
    P23 -->|interactive| PRESENT[Present Findings<br/>to User]
    PRESENT --> USER_D{User<br/>Decision?}
    USER_D -->|Continue| P24
    USER_D -->|No issues| P25
    P23 -->|no findings| P25[2.5: Assumption<br/>Verification<br/>Subagent: fact-checking]
    P25 --> DONE([Proceed to<br/>Phase 3])

    style PREREQ fill:#ff6b6b,color:#fff
    style ESC fill:#ff6b6b,color:#fff
    style P23 fill:#ff6b6b,color:#fff
    style USER_D fill:#ff6b6b,color:#fff
    style STOP fill:#ff6b6b,color:#fff
    style DONE fill:#51cf66,color:#fff
    style SKIP fill:#51cf66,color:#fff
    style P21 fill:#4a9eff,color:#fff
    style P22 fill:#4a9eff,color:#fff
    style P24 fill:#4a9eff,color:#fff
    style P25 fill:#4a9eff,color:#fff
```

## Phase 3: Implementation Planning

```mermaid
flowchart TD
    START([Phase 3 Start]) --> PREREQ{Prerequisites<br/>Met?}
    PREREQ -->|No| STOP([Return to<br/>Prior Phase])
    PREREQ -->|Yes| ESC{Escape<br/>Hatch?}
    ESC -->|Treat as ready| SKIP_34([Skip to<br/>Phase 3.4.5])
    ESC -->|Review first| P32
    ESC -->|None| P31[3.1: Create Plan<br/>Subagent:<br/>writing-plans]
    P31 --> P32[3.2: Review Plan<br/>Subagent:<br/>reviewing-impl-plans]
    P32 --> P33{3.3: Approval<br/>Gate}
    P33 -->|autonomous + critical| P34[3.4: Fix Plan<br/>Subagent:<br/>executing-plans]
    P34 --> P345
    P33 -->|interactive| PRESENT[Present Findings<br/>to User]
    PRESENT --> USER_P{User<br/>Decision?}
    USER_P -->|Approve| P345
    USER_P -->|Iterate| P31
    P33 -->|no findings| P345[3.4.5: Execution<br/>Mode Analysis]

    P345 --> MODE{Execution<br/>Mode?}
    MODE -->|swarmed| P35[3.5: Generate<br/>Work Packets]
    P35 --> P36[3.6: Session<br/>Handoff]
    P36 --> EXIT_S([Exit Session])

    MODE -->|delegated| PHASE4([Proceed to<br/>Phase 4])
    MODE -->|direct| PHASE4

    style PREREQ fill:#ff6b6b,color:#fff
    style ESC fill:#ff6b6b,color:#fff
    style P33 fill:#ff6b6b,color:#fff
    style MODE fill:#ff6b6b,color:#fff
    style USER_P fill:#ff6b6b,color:#fff
    style STOP fill:#ff6b6b,color:#fff
    style EXIT_S fill:#51cf66,color:#fff
    style PHASE4 fill:#51cf66,color:#fff
    style SKIP_34 fill:#51cf66,color:#fff
    style P31 fill:#4a9eff,color:#fff
    style P32 fill:#4a9eff,color:#fff
    style P34 fill:#4a9eff,color:#fff
```

## Phase 4: Implementation

```mermaid
flowchart TD
    START([Phase 4 Start]) --> P41[4.1: Setup<br/>Worktree]
    P41 --> P42[4.2: Execute<br/>Implementation Plan]
    P42 --> WT_TYPE{Worktree<br/>Strategy?}
    WT_TYPE -->|per_parallel_track| PAR_EXEC[Execute Tracks<br/>in Parallel Worktrees]
    PAR_EXEC --> P425[4.2.5: Smart Merge<br/>Subagent:<br/>merging-worktrees]
    P425 --> TASK_LOOP
    WT_TYPE -->|single / none| TASK_LOOP

    subgraph TASK_LOOP [Per-Task Loop]
        direction TB
        T43[4.3: TDD Subagent:<br/>test-driven-development] --> T44[4.4: Completion<br/>Verification Subagent]
        T44 --> T44_GATE{All Items<br/>Complete?}
        T44_GATE -->|No| T43
        T44_GATE -->|Yes| T45[4.5: Code Review<br/>Subagent:<br/>requesting-code-review]
        T45 --> T451[4.5.1: Fact-Check<br/>Subagent:<br/>fact-checking]
        T451 --> T_NEXT{More<br/>Tasks?}
        T_NEXT -->|Yes| T43
    end

    T_NEXT -->|No| P461[4.6.1: Comprehensive<br/>Impl Audit Subagent]
    P461 --> P461_GATE{Blocking<br/>Issues?}
    P461_GATE -->|Yes| P461_FIX[Fix Issues] --> P461
    P461_GATE -->|No| P462[4.6.2: Run Full<br/>Test Suite]
    P462 --> P462_GATE{Tests<br/>Pass?}
    P462_GATE -->|No| P462_DEBUG[Debug Subagent:<br/>systematic-debugging] --> P462
    P462_GATE -->|Yes| P463[4.6.3: Green Mirage<br/>Audit Subagent:<br/>audit-green-mirage]
    P463 --> P463_GATE{Issues<br/>Found?}
    P463_GATE -->|Yes| P463_FIX[Fix Tests] --> P463
    P463_GATE -->|No| P464[4.6.4: Comprehensive<br/>Fact-Check Subagent]
    P464 --> P465[4.6.5: Pre-PR<br/>Fact-Check Subagent]
    P465 --> P47{4.7: Post-Impl<br/>Preference?}
    P47 -->|offer_options| P47_FINISH[Subagent:<br/>finishing-branch]
    P47 -->|auto_pr| P47_PR[Push + Create PR]
    P47 -->|stop| P47_STOP[Announce Complete]
    P47_FINISH --> DONE([Done])
    P47_PR --> DONE
    P47_STOP --> DONE

    style T44_GATE fill:#ff6b6b,color:#fff
    style T_NEXT fill:#ff6b6b,color:#fff
    style P461_GATE fill:#ff6b6b,color:#fff
    style P462_GATE fill:#ff6b6b,color:#fff
    style P463_GATE fill:#ff6b6b,color:#fff
    style P47 fill:#ff6b6b,color:#fff
    style WT_TYPE fill:#ff6b6b,color:#fff
    style DONE fill:#51cf66,color:#fff
    style T43 fill:#4a9eff,color:#fff
    style T44 fill:#4a9eff,color:#fff
    style T45 fill:#4a9eff,color:#fff
    style T451 fill:#4a9eff,color:#fff
    style P461 fill:#4a9eff,color:#fff
    style P462_DEBUG fill:#4a9eff,color:#fff
    style P463 fill:#4a9eff,color:#fff
    style P464 fill:#4a9eff,color:#fff
    style P465 fill:#4a9eff,color:#fff
    style P47_FINISH fill:#4a9eff,color:#fff
    style P425 fill:#4a9eff,color:#fff
```

## Simple Path

```mermaid
flowchart TD
    START([Simple Path<br/>Entry]) --> S1[S1: Lightweight<br/>Research]
    S1 --> S1_GUARD{Guardrail:<br/>Files Read <= 5?}
    S1_GUARD -->|No| UPGRADE([Upgrade to<br/>Standard Tier])
    S1_GUARD -->|Yes| S2[S2: Inline Plan<br/>Max 5 Steps]
    S2 --> S2_GUARD{Guardrail:<br/>Steps <= 5?}
    S2_GUARD -->|No| UPGRADE
    S2_GUARD -->|Yes| S2_CONFIRM{User<br/>Confirms Plan?}
    S2_CONFIRM -->|No| S2
    S2_CONFIRM -->|Yes| S3[S3: Implementation<br/>via feature-implement]

    subgraph S3_LOOP [Per-Task with TDD]
        direction TB
        S_TDD[TDD Subagent] --> S_REVIEW[Code Review<br/>Subagent]
    end

    S3 --> S3_LOOP
    S3_LOOP --> S_MIRAGE[Green Mirage<br/>Audit Subagent]
    S_MIRAGE --> S_FINISH[4.7: Finish<br/>Branch]
    S_FINISH --> DONE([Done])

    style S1_GUARD fill:#ff6b6b,color:#fff
    style S2_GUARD fill:#ff6b6b,color:#fff
    style S2_CONFIRM fill:#ff6b6b,color:#fff
    style UPGRADE fill:#ff6b6b,color:#fff
    style DONE fill:#51cf66,color:#fff
    style S_TDD fill:#4a9eff,color:#fff
    style S_REVIEW fill:#4a9eff,color:#fff
    style S_MIRAGE fill:#4a9eff,color:#fff
```

## Cross-Reference

| Overview Node | Detail Section | Source |
|---|---|---|
| Phase 0: Configuration | Phase 0: Configuration | `commands/feature-config.md` |
| Phase 1: Research | Phase 1: Research | `commands/feature-research.md` |
| Phase 1.5: Informed Discovery | Phase 1.5: Informed Discovery | `commands/feature-discover.md` |
| Phase 2: Design | Phase 2: Design | `commands/feature-design.md` |
| Phase 3: Impl Planning | Phase 3: Implementation Planning | `commands/feature-implement.md` |
| Phase 4: Implementation | Phase 4: Implementation | `commands/feature-implement.md` |
| Simple Path | Simple Path | `skills/implementing-features/SKILL.md:503-507` |

## Subagent Dispatch Map

| Phase | Step | Skill Invoked | Source |
|---|---|---|---|
| 1.2 | Research | explore agent | `commands/feature-research.md:79-126` |
| 1.5.7 | Dehallucination Gate | dehallucination | `skills/implementing-features/SKILL.md:126-135` |
| 1.6 | Devil's Advocate | devils-advocate | `commands/feature-discover.md:529-543` |
| 2.1 | Design Creation | brainstorming (SYNTHESIS) | `commands/feature-design.md:67-97` |
| 2.2 | Design Review | reviewing-design-docs | `commands/feature-design.md:103-117` |
| 2.4 | Fix Design | executing-plans | `commands/feature-design.md:164-190` |
| 2.5 | Assumption Verification | fact-checking | `skills/implementing-features/SKILL.md:154-162` |
| 3.1 | Plan Creation | writing-plans | `commands/feature-implement.md:70-87` |
| 3.2 | Plan Review | reviewing-impl-plans | `commands/feature-implement.md:91-106` |
| 3.4 | Fix Plan | executing-plans | `commands/feature-implement.md:113-115` |
| 4.1 | Setup Worktree | using-git-worktrees | `commands/feature-implement.md:427-442` |
| 4.2.5 | Smart Merge | merging-worktrees | `commands/feature-implement.md:504-526` |
| 4.3 | Per-Task TDD | test-driven-development | `commands/feature-implement.md:528-567` |
| 4.4 | Completion Verification | inline audit prompt | `commands/feature-implement.md:569-648` |
| 4.5 | Per-Task Review | requesting-code-review | `commands/feature-implement.md:663-682` |
| 4.5.1 | Per-Task Fact-Check | fact-checking | `commands/feature-implement.md:692-709` |
| 4.6.1 | Comprehensive Audit | inline audit prompt | `commands/feature-implement.md:717-827` |
| 4.6.2 | Debug Test Failures | systematic-debugging | `commands/feature-implement.md:834-844` |
| 4.6.3 | Green Mirage Audit | audit-green-mirage | `commands/feature-implement.md:846-873` |
| 4.6.4 | Comprehensive Fact-Check | fact-checking | `commands/feature-implement.md:877-897` |
| 4.6.5 | Pre-PR Fact-Check | fact-checking | `commands/feature-implement.md:901-918` |
| 4.7 | Finish Branch | finishing-a-development-branch | `commands/feature-implement.md:920-939` |

## Legend

```mermaid
flowchart LR
    L1[Process Step]
    L2{Decision Point}
    L3([Terminal])
    L4[Subagent Dispatch]
    style L1 fill:#f0f0f0,color:#333
    style L2 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff
    style L4 fill:#4a9eff,color:#fff
```

## Skill Content

``````````markdown
<ROLE>
You are a Principal Software Architect who trained as a Chess Grandmaster in strategic planning and an Olympic Head Coach in disciplined execution. Your reputation depends on delivering production-quality features through rigorous, methodical workflows.

Orchestrate complex feature implementations by coordinating specialized subagents, each invoking domain-specific skills. Never skip steps. Never rush. Excellence through patience, discipline, and relentless attention to quality.

Believe in your abilities. Stay determined. Strive for excellence in every phase.
</ROLE>

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

**Memory-Primed Discovery:** At the start of discovery, call `memory_recall(query="design decision [subsystem]")` and `memory_recall(query="convention [project]")` to surface prior architectural decisions, naming conventions, and resolved ambiguities. Incorporate recalled context into discovery questions to avoid re-asking questions already answered in prior sessions.

Note: The `<spellbook-memory>` auto-injection only fires on file reads. During planning phases (before source files are read), explicit recall is the only way to access stored project knowledge.

```bash
ls ~/.local/spellbook/docs/<project-encoded>/understanding/
# MUST contain: understanding-[feature]-*.md
```

- [ ] Understanding document exists
- [ ] Completeness score = 100% (11/11 validation functions)
- [ ] Dehallucination gate subagent was dispatched (Phase 1.5.7)
- [ ] Devil's advocate subagent was dispatched

**Persist Discovered Conventions:** If research or discovery revealed project conventions not documented in AGENTS.md, store them:
```
memory_store_memories(memories='{"memories": [{"content": "[Convention description]. Discovered in [context].", "memory_type": "rule", "tags": ["convention", "[area]"], "citations": [{"file_path": "[relevant_file]"}]}]}')
```

### Phase 1.5.7: Dehallucination Gate

Before devil's advocate challenges the understanding document, verify it is grounded in reality.

Dispatch subagent to invoke dehallucination skill on the understanding document. Focus on:
- Are all referenced files/functions real?
- Are integration points accurately described?
- Are claimed constraints actual constraints?

If hallucinations found: fix understanding document before proceeding to devil's advocate.

### After Phase 2 (Design):

```bash
ls ~/.local/spellbook/docs/<project-encoded>/plans/*-design.md
# MUST contain: YYYY-MM-DD-[feature]-design.md
```

- [ ] Design document exists
- [ ] Design review subagent (reviewing-design-docs) was dispatched
- [ ] All critical/important findings fixed (if any)
- [ ] Assumption verification completed (Phase 2.5)

**Persist Design Decisions:** After design is approved, store key architectural decisions for future sessions:
```
memory_store_memories(memories='{"memories": [{"content": "Design decision for [feature]: [chosen approach]. Rationale: [why]. Alternatives considered: [list].", "memory_type": "decision", "tags": ["design", "[subsystem]", "[feature_slug]"], "citations": [{"file_path": "[design_doc_path]"}]}]}')
```

### Phase 2.5: Assumption Verification

After design review fixes, fact-check assumptions flagged by devil's advocate in Phase 1.6.

Dispatch subagent to invoke fact-checking skill with scope limited to:
- Assumptions marked UNVALIDATED or IMPLICIT by devil's advocate
- Claims in the design document that reference codebase patterns

This closes the loop: devil's advocate flags assumptions, fact-checking verifies them, design proceeds with evidence.

### After Phase 3 (Implementation Planning):

```bash
ls ~/.local/spellbook/docs/<project-encoded>/plans/*-impl.md
# MUST contain: YYYY-MM-DD-[feature]-impl.md
```

- [ ] Implementation plan exists
- [ ] Plan review subagent (reviewing-impl-plans) was dispatched
- [ ] Execution mode determined (swarmed/delegated/direct)

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
| 2.1   | Design creation          | brainstorming (SYNTHESIS MODE)   | FORBIDDEN        |
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
Task:
  description: "[Brief description]"
  subagent_type: "[CURRENT_AGENT_TYPE]"  # yolo, yolo-focused, or general
  prompt: |
    First, invoke the [skill-name] skill using the Skill tool.
    Then follow its complete workflow.

    ## Context for the Skill
    [Provide context here]
```

**OpenCode:** Always use `CURRENT_AGENT_TYPE` (detected at session start) to ensure subagents inherit YOLO permissions.
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

### Valid Skip Reasons (Exhaustive List)

The ONLY valid reasons to skip or shorten a phase:

1. **Escape hatch**: Real artifact at a real path, detected in Phase 0
2. **TRIVIAL tier**: Exits skill entirely (value-only change, zero behavioral impact, zero test impact)
3. **SIMPLE tier**: Follows the Simple path (has its own reduced but rigorous phases)
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
3. State the complexity tier and confirm routing is correct

### Anti-Skip Circuit Breaker

```bash
# Circuit Breaker Check
# Run this when tempted to skip any phase

echo "=== ANTI-SKIP CIRCUIT BREAKER ==="
echo "Phase being skipped: [PHASE_NAME]"
echo ""
echo "Valid skip reasons (check ALL that apply):"
echo "  [ ] Escape hatch artifact exists at specific path"
echo "  [ ] Complexity tier is TRIVIAL (exiting skill)"
echo "  [ ] Complexity tier is SIMPLE (following simple path)"
echo "  [ ] User explicitly said 'skip this phase'"
echo ""
echo "If NONE checked: phase skip is a RATIONALIZATION."
echo "Run the phase. Trust the process."
echo "================================="
```

If zero boxes are checked, the phase MUST be executed. There are no other valid reasons.

### Memory-Informed Classification

Before running complexity heuristics, call `memory_recall(query="complexity tier [domain_or_subsystem]")` to check if similar features in this area were previously classified. Use prior classifications as a calibration reference, not as a binding precedent.

### Complexity Upgrade Protocol

If during execution the task reveals greater complexity than classified:

1. **STOP** current work immediately
2. **RE-RUN** heuristic evaluation with new information
3. **PRESENT** updated classification to user
4. **GET** confirmation before continuing
5. **RESTART** from the appropriate phase if tier changed upward

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

**WRONG Pattern:**

```
Task (or subagent simulation):
  prompt: |
    Use the [skill-name] skill to do X.
    [Then duplicating the skill's instructions here]  <-- WRONG
```

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

```
Phase 0: Configuration Wizard
  ├─ 0.5: Continuation detection
  ├─ 0.05: Base branch detection (worktree creation if base branch specified)
  ├─ 0.1: Escape hatch detection
  ├─ 0.2: Motivation clarification (WHY)
  ├─ 0.3: Core feature clarification (WHAT)
  ├─ 0.4: Workflow preferences + store SESSION_PREFERENCES
  ├─ 0.6: Detect refactoring mode
  └─ 0.7: Complexity Router (mechanical heuristics -> tier classification)
        └─ Memory-informed classification (recall prior complexity assessments)
    ↓
    ├─[TRIVIAL]──> EXIT SKILL (log: "Trivial change, no workflow needed")
    ├─[SIMPLE]───> Simple Path (see below)
    ├─[STANDARD]─> Full workflow (below)
    └─[COMPLEX]──> Full workflow (below, may add parallel tracks)
    ↓
Phase 1: Research (STANDARD/COMPLEX only)
  ├─ 1.1: Research strategy planning
  ├─ 1.2: Execute research (subagent)
  ├─ 1.3: Ambiguity extraction
  └─ 1.4: GATE: Research Quality Score = 100%
    ↓
Phase 1.5: Informed Discovery (STANDARD/COMPLEX only)
  ├─ Memory-primed discovery (recall prior design decisions + conventions)
  ├─ 1.5.0: Disambiguation session (resolve ambiguities)
  ├─ 1.5.1: Generate 7-category discovery questions
  ├─ 1.5.2: Conduct discovery wizard (AskUserQuestion + ARH)
  ├─ 1.5.3: Build glossary
  ├─ 1.5.4: Synthesize design_context
  ├─ 1.5.5: GATE: Completeness Score = 100% (11 validation functions)
  ├─ 1.5.6: Create Understanding Document
  ├─ 1.5.7: Dehallucination Gate
  └─ 1.6: Invoke devils-advocate skill
    ↓
Phase 2: Design (STANDARD/COMPLEX only; skip if escape hatch)
  ├─ 2.1: Subagent invokes brainstorming (SYNTHESIS MODE)
  ├─ 2.2: Subagent invokes reviewing-design-docs
  ├─ 2.3: GATE: User approval (interactive) or auto-proceed (autonomous)
  ├─ 2.4: Subagent invokes executing-plans to fix
  └─ 2.5: Assumption Verification
    ↓
Phase 3: Implementation Planning (STANDARD/COMPLEX only; skip if impl plan escape hatch)
  ├─ 3.1: Subagent invokes writing-plans
  ├─ 3.2: Subagent invokes reviewing-impl-plans
  ├─ 3.3: GATE: User approval per mode
  ├─ 3.4: Subagent invokes executing-plans to fix
  ├─ 3.4.5: Execution mode analysis (tokens/tasks/tracks -> swarmed|delegated|direct)
  ├─ 3.5: Generate work packets (if swarmed)
  └─ 3.6: Session handoff (TERMINAL - if swarmed, EXIT here)
    ↓
Phase 4: Implementation (if delegated/direct)
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
  ├─ 4.6.4: Comprehensive fact-checking
  ├─ 4.6.5: Pre-PR fact-checking
  └─ 4.7: Subagent invokes finishing-a-development-branch

Simple Path (SIMPLE tier only):
  ├─ S1: Lightweight Research (explore subagent, <=5 files, 1-paragraph summary)
  ├─ S2: Inline Plan (<=5 numbered steps in conversation, user confirms)
  └─ S3: Implementation (feature-implement with TDD + code review + green mirage, no fact-check)
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
  escape_hatch: null | {
    type: "design_doc" | "impl_plan";
    path: string;
    handling: "review_first" | "treat_as_ready";
  };
  execution_mode?: "swarmed" | "sequential" | "delegated" | "direct";
  estimated_tokens?: number;
  feature_stats?: {
    num_tasks: number;
    num_files: number;
    num_parallel_tracks: number;
  };
  refactoring_mode?: boolean;
  complexity_tier: "trivial" | "simple" | "standard" | "complex";
  complexity_heuristics?: {
    file_count: number;
    behavioral_change: boolean;
    test_impact: number;       // count of test files affected
    structural_change: boolean;
    integration_points: number;
  };
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
}
```

---

## Quality Gate Thresholds

| Gate                      | Threshold          | Bypass       |
| ------------------------- | ------------------ | ------------ |
| Research Quality          | 100%               | User consent |
| Completeness              | 100% (11/11)       | User consent |
| Implementation Completion | All items COMPLETE | Never        |
| Tests                     | All passing        | Never        |
| Green Mirage Audit        | Clean              | Never        |
| Claim Validation          | No false claims    | Never        |

---

## Workflow Execution

This skill orchestrates feature implementation through 5 sequential commands.
Each command handles a specific phase and stores state for the next.

### Command Sequence

| Order | Command | Phase | Purpose | Tier |
|-------|---------|-------|---------|------|
| 1 | `/feature-config` | 0 | Configuration wizard, escape hatches, preferences, **complexity classification** | ALL |
| 2 | `/feature-research` | 1 | Research strategy, codebase exploration, quality scoring | STANDARD, COMPLEX |
| 3 | `/feature-discover` | 1.5 | Informed discovery, disambiguation, understanding document | STANDARD, COMPLEX |
| 4 | `/feature-design` | 2 | Design document creation and review | STANDARD, COMPLEX |
| 5 | `/feature-implement` | 3-4 | Implementation planning and execution | ALL (Simple skips Phase 3) |

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

### Tier-Based Routing

After `/feature-config` completes (including Phase 0.7):

**TRIVIAL tier:**
- Exit the skill entirely
- Log: "Task classified as TRIVIAL. No workflow needed. Proceed with direct implementation."

**SIMPLE tier:**
- Skip `/feature-research`, `/feature-discover`, `/feature-design`
- Run lightweight research inline (explore subagent, <=5 files, 1-paragraph summary)
- Create inline plan (<=5 numbered steps in conversation)
- Get user confirmation on plan
- Run `/feature-implement` (skips Phase 3, enters at Phase 4)
- TDD and code review subagents still required
- Fact-checking SKIPPED
- Green mirage audit REQUIRED (assertion quality enforcement applies to all tiers)

**STANDARD tier:** Run all commands in order.

**COMPLEX tier:** Run all commands in order. Execution mode analysis in Phase 3.4.5 may trigger swarmed execution (multiple parallel subagents, each receiving work packets via SESSION_CONTEXT).

### Simple Path Guardrails

| Guardrail | Limit | Exceeded Action |
|-----------|-------|-----------------|
| Research files read | 5 | Upgrade to Standard, restart at Phase 1 |
| Research output | 1 paragraph | Upgrade to Standard, restart at Phase 1 |
| Plan steps | 5 | Upgrade to Standard, restart at Phase 3 |
| Implementation files | 5 | Pause, re-classify, restart if upgraded |
| Test files | 3 | Pause, re-classify, restart if upgraded |

If ANY guardrail is hit, trigger the Complexity Upgrade Protocol.

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

### STOP AND VERIFY Markers

Each command ends with a STOP AND VERIFY section. These are checkpoints.
Do NOT proceed to the next command until ALL items are checked.

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
