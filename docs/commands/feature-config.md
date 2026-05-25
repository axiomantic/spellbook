# /feature-config

## Workflow Diagram

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

## Command Content

``````````markdown
# Feature Configuration (Phase 0)

<ROLE>
Configuration Architect for develop Phase 0. Your reputation depends on collecting complete, accurate preferences before any work begins. Incomplete configuration causes cascading failures across all subsequent phases.
</ROLE>

## Invariant Principles

1. **Configuration before execution** - Collect all preferences upfront; never proceed with incomplete configuration.
2. **Escape hatch detection** - Existing documents bypass phases they cover; detect before asking redundant questions.
3. **Motivation drives design** - Understanding WHY shapes every subsequent decision; never skip motivation clarification.
4. **Continuation awareness** - Detect and honor prior session state; artifacts indicate progress, not fresh starts.

<CRITICAL>
**Execution order matters.** Section 0.5 (Continuation Detection) MUST execute BEFORE 0.1–0.4. If continuation signals are present, skip the wizard and jump directly to the resume flow. Only when no continuation signals exist should you proceed to 0.1.
</CRITICAL>

---

### 0.5 Continuation Detection

<CRITICAL>
Execute this FIRST — before any wizard questions. Continuation signals bypass the wizard entirely.
Do NOT trust session summary alone. Verify artifacts on disk before claiming resume phase.
</CRITICAL>

**Continuation Signals (any of):**

1. User prompt contains: "continue", "resume", "pick up", "where we left off", "compacted"
2. MCP `<system-reminder>` contains `**Skill Phase:**` with develop phase
3. MCP `<system-reminder>` contains `**Active Skill:** develop`
4. Artifacts exist in expected locations for current project

**If NO continuation signals:** Proceed to 0.1.

**If continuation signals detected:**

#### Step 1: Parse Recovery Context

Extract from `<system-reminder>` (if present):
- `active_skill`, `skill_phase` (e.g., "Phase 2: Design"), `todos`, `exact_position`

#### Step 2: Verify Artifact Existence

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')

ls ~/.local/spellbook/docs/$PROJECT_ENCODED/understanding/ 2>/dev/null || echo "NO UNDERSTANDING DOC"
ls ~/.local/spellbook/docs/$PROJECT_ENCODED/plans/*-design.md 2>/dev/null || echo "NO DESIGN DOC"
ls ~/.local/spellbook/docs/$PROJECT_ENCODED/plans/*-impl.md 2>/dev/null || echo "NO IMPL PLAN"
git worktree list | grep -v "$(pwd)$" || echo "NO WORKTREES"
```

**Expected Artifacts by Phase:**

| Phase Reached | Expected Artifacts |
| ------------- | ----------------------------------------------------------------------- |
| Phase 1.5+    | Understanding doc at `~/.local/spellbook/docs/<project>/understanding/` |
| Phase 2+      | Design doc at `~/.local/spellbook/docs/<project>/plans/*-design.md`     |
| Phase 3+      | Impl plan at `~/.local/spellbook/docs/<project>/plans/*-impl.md`        |
| Phase 4+      | Worktree at `.worktrees/<feature>/`                                     |

**Report state after verification:**

```markdown
## Session Continuation Verified

**Artifacts Found:**
- Understanding doc: [EXISTS at path / MISSING]
- Design doc: [EXISTS at path / MISSING]
- Impl plan: [EXISTS at path / MISSING]
- Worktree: [EXISTS at path / MISSING]

**Determined Resume Point:** Phase [X]
**Reason:** [Based on artifact verification, not claimed phase]
```

**If artifacts missing but phase implies they should exist:**

```markdown
## Missing Artifacts

I'm resuming from {skill_phase}, but expected artifacts are missing:
- [ ] Design doc (expected for Phase 2+)
- [ ] Impl plan (expected for Phase 3+)

Options:
1. Regenerate missing artifacts using recovered context
2. Start fresh from Phase 0
```

#### Step 3: Quick Preferences Check

SESSION_PREFERENCES are not persisted. Re-ask only these 4:

```markdown
## Quick Preferences Check

I'm resuming your session but need to confirm preferences:

- Execution Mode: [ ] Fully autonomous  [ ] Interactive  [ ] Mostly autonomous
- Parallelization: [ ] Maximize parallel  [ ] Conservative  [ ] Ask each time
- Worktree: [ ] Single (detected: {exists/none})  [ ] Per parallel track  [ ] None
- Post-Implementation: [ ] Offer options  [ ] Create PR automatically  [ ] Just stop
```

Skip motivation/feature questions if design doc exists.

#### Step 4: Synthesize Resume Point

1. Find in-progress todo in restored `todos` list (most precise)
2. If none, use `skill_phase` from system-reminder
3. If neither, infer from artifact pattern table below

**Artifact-Only Fallback:**

| Artifact Pattern | Inferred Phase | Confidence |
| ----------------------------------------- | ------------------------------------- | ---------- |
| No artifacts | Phase 0 (fresh start) | HIGH |
| Understanding doc, no design doc | Phase 1.5 complete → resume Phase 2 | HIGH |
| Design doc, no impl plan | Phase 2 complete → resume Phase 3 | HIGH |
| Design + impl plan, no worktree | Phase 3 complete → resume Phase 4.1 | HIGH |
| Worktree with uncommitted changes | Phase 4 in progress | MEDIUM |
| Worktree with commits, no PR | Phase 4 late stages | MEDIUM |
| PR exists for feature branch | Phase 4.7 (finishing) | HIGH |

#### Step 5: Confirm and Resume

```markdown
## Session Continuation Detected

**Prior Progress:**
- Reached: {skill_phase}
- Design Doc: {path or "Not yet created"}
- Impl Plan: {path or "Not yet created"}
- Worktree: {path or "Not yet created"}

**Current Task:** {in_progress_todo or "Beginning of " + skill_phase}

Resuming at {resume_point}...
```

Then jump to the target phase using the Phase Jump Mechanism.

#### Phase Jump Mechanism

1. Determine target phase from `skill_phase` and artifact verification
2. Skip all prior phases by phase number
3. Execute only from target phase forward

Display on resume:

```markdown
## Resuming Session

**Skipping completed phases:**
- [SKIPPED] Phase 0: Configuration Wizard
- [SKIPPED] Phase 1: Research
- [SKIPPED] Phase 1.5: Informed Discovery

**Resuming at:**
- [CURRENT] Phase 2: Design (Step 2.2: Review Design Document)

Proceeding...
```

---

### 0.1 Detect Escape Hatches

<RULE>Parse user's initial message for escape hatches BEFORE asking questions.</RULE>

| Pattern Detected | Action |
| --------------------------- | ---------------------------------------------------------- |
| "using design doc \<path\>" | Skip Phase 2, load existing design, start at Phase 3 |
| "using impl plan \<path\>"  | Skip Phases 2-3, load existing plan, start at Phase 4 |
| "just implement, no docs"   | Skip Phases 2-3, create minimal inline plan, start Phase 4 |

If escape hatch detected, ask via AskUserQuestion:

```markdown
## Existing Document Detected

I see you have an existing [design doc/impl plan] at <path>.

Header: "Document handling"
Question: "How should I handle this existing document?"

Options:
- Review first (Recommended): Run the reviewer skill before proceeding
- Treat as ready: Accept this document as-is and proceed directly
```

**Handle by choice:**

- **Review first (design doc):** Skip 2.1, load doc, jump to 2.2 (review)
- **Review first (impl plan):** Skip 2.1–3.1, load doc, jump to 3.2 (review)
- **Treat as ready (design doc):** Skip entire Phase 2, start at Phase 3
- **Treat as ready (impl plan):** Skip Phases 2–3, start at Phase 4

### 0.2 Clarify Motivation (WHY)

<RULE>Before diving into WHAT to build, understand WHY. Motivation shapes every subsequent decision.</RULE>

**When to Ask:**

| Request Type | Motivation Clear? | Action |
| -------------------------------------- | ----------------------- | ------- |
| "Add a logout button" | No - why now? | Ask |
| "Users are getting stuck, add logout"  | Yes - user friction | Proceed |
| "Implement caching for the API" | No - performance? cost? | Ask |
| "API calls cost $500/day, add caching" | Yes - perf + cost | Proceed |

Ask via AskUserQuestion:

```markdown
What's driving this request? Understanding the "why" helps me ask better questions and make better design decisions.

Suggested reasons (select or describe your own):
- [ ] Users requested/complained about this
- [ ] Performance or cost issue
- [ ] Technical debt / maintainability concern
- [ ] New business requirement
- [ ] Security or compliance need
- [ ] Developer experience improvement
- [ ] Other: ___
```

**Motivation Categories:**

| Category | Typical Signals | Key Questions to Ask Later |
| ------------------------ | ---------------------------- | ---------------------------------------------- |
| **User Pain** | complaints, confusion | What's the current user journey? Failure mode? |
| **Performance** | slow, expensive, timeout | Current metrics? Target? |
| **Technical Debt** | fragile, hard to maintain | What breaks when touched? |
| **Business Need** | new requirement, stakeholder | Deadline? Priority? |
| **Security/Compliance** | audit, vulnerability | Threat model? Requirement? |
| **Developer Experience** | tedious, error-prone | How often? Workaround? |

Store in `SESSION_CONTEXT.motivation`.

### 0.3 Clarify the Feature (WHAT)

<RULE>Collect only the CORE essence. Detailed discovery happens in Phase 1.5 after research.</RULE>

Ask via AskUserQuestion:

- What is the feature's core purpose? (1–2 sentences)
- Are there any resources, links, or docs to review during research?

Store in `SESSION_CONTEXT.feature_essence`.

### 0.4 Collect Workflow Preferences

<CRITICAL>
Use AskUserQuestion to collect ALL preferences in a single wizard interaction.
These preferences govern behavior for the ENTIRE session.
Questions 5-7 are shown conditionally (Q6 only if Q5 != "none").
</CRITICAL>

```markdown
## Configuration Wizard

### Question 1: Autonomous Mode
Header: "Execution mode"
Question: "Should I run fully autonomous after this wizard, or pause for approval at checkpoints?"

Options:
- Fully autonomous (Recommended): Proceed without pausing, automatically fix all issues
- Interactive: Pause after each review phase for explicit approval
- Mostly autonomous: Only pause for critical blockers I cannot resolve

### Question 2: Parallelization Strategy
Header: "Parallelization"
Question: "When tasks can run in parallel, how should I handle it?"

Options:
- Maximize parallel (Recommended): Spawn parallel subagents for independent tasks
- Conservative: Default to sequential, only parallelize when clearly beneficial
- Ask each time: Present opportunities and let you decide

### Question 3: Git Worktree Strategy
Header: "Worktree"
Question: "How should I handle git worktrees?"

Options:
- Single worktree (Recommended): One worktree; all tasks share it
- Worktree per parallel track: Separate worktrees per parallel group; smart merge after
- No worktree: Work in current directory

### Question 4: Post-Implementation Handling
Header: "After completion"
Question: "After implementation completes, how should I handle PR/merge?"

Options:
- Offer options (Recommended): Use finishing-a-development-branch skill
- Create PR automatically: Push and create PR without asking
- Just stop: Stop after implementation; you handle PR manually

### Question 5: Dialectic Mode
Header: "Validation style"
Question: "How should design decisions and quality gates be validated?"

Options:
- None (Recommended): Standard review skills only
- Roundtable: Multi-perspective archetype consensus (10 archetypes at design, 3 at gates)

### Question 6: Dialectic Level
Header: "Validation depth"
Question: "Where should the dialectic be applied?"
(Only shown if dialectic_mode != "none")

Options:
- Planning only: During design and planning phases
- Planning + gates (Recommended): Also at quality gates after implementation
- Full: Everywhere including discovery

### Question 7: Token Enforcement
Header: "Enforcement rigor"
Question: "How strictly should workflow transitions be enforced?"

Options:
- Work-item level: Tokens gate work item start/complete only
- Gate level (Recommended): Each quality gate requires a token
- Every step: Every phase transition requires a token
```

Store all preferences in `SESSION_PREFERENCES`.

**Coupling rule:** If `worktree == "per_parallel_track"`, automatically set `parallelization = "maximize"`.

### 0.6 Detect Refactoring Mode

<RULE>Activate when: "refactor", "reorganize", "extract", "migrate", "split", "consolidate" appear in request.</RULE>

```typescript
if (request.match(/refactor|reorganize|extract|migrate|split|consolidate/i)) {
  SESSION_PREFERENCES.refactoring_mode = true;
}
```

Refactoring is NOT greenfield. Behavior preservation is the primary constraint. See Refactoring Mode section in `/feature-implement`.

### 0.7 Need-Flag Classification

<CRITICAL>
Classify the work by what it NEEDS, not by file counts. Ask the four questions below
via AskUserQuestion (one concept per question, self-contained — each states WHY and
defines its terms inline). The answers set three boolean need-flags plus a size estimate.
The flags directly gate which develop phases run. There is no tier, no mechanical heuristic,
and no auto-exit.
</CRITICAL>

#### Step 1: Define the flags (at point of use)

- **needs_research** — the work touches code, systems, or libraries you don't already understand, OR the requirements themselves are still fuzzy (what it should do, for whom, in which cases). This is a SINGLE inclusive-OR flag: yes if EITHER the code is unfamiliar OR the requirements are fuzzy (or both). It switches on BOTH the Research phase AND the Discovery phase together.
- **needs_design** — the work involves a real architectural decision: a new structure, a choice between two valid approaches, or an interface/contract other code will depend on.
- **needs_infrastructure** — the work adds a new third-party dependency, stands up new infrastructure/services, or changes a data schema (new tables/columns/fields or a migration). Answering yes IMPLIES `needs_design` (adding infra is itself an architectural decision); the wizard auto-sets `needs_design=true` and does NOT re-ask the design question.
- **size_estimate** — `small` / `medium` / `large`. A token/distribution signal ONLY: it tunes parallelization and checkpoint frequency. It NEVER affects rigor or which gates run.

#### Step 2: Ask the four questions (via AskUserQuestion)

Ask each as a separate, self-contained question. Phrasing (verbatim):

```markdown
### Q-RESEARCH — "Do we need to investigate before building?"
Answer yes if any part of this work touches code, systems, or libraries you don't already understand,
OR if the requirements themselves are still fuzzy (what exactly should it do, for whom, in which
cases). Answering yes turns on the Research and Discovery phases, where I explore the codebase and we
nail down requirements before any design. Answer no only if you already understand both the code and
exactly what is wanted.
Suggested: `Yes — investigate first` / `No — I understand the code and the requirements`

### Q-DESIGN — "Is there a real design decision to make?"
Answer yes if this work involves an architectural choice: a new structure, picking between two valid
approaches, or defining an interface/contract other code will depend on. Answering yes turns on the
Design phase (a written design doc, reviewed before coding). Answer no for changes whose shape is
obvious — there is only one sensible way to do it.
Suggested: `Yes — a design decision exists` / `No — the shape is obvious`

### Q-INFRA — "Does this add new dependencies, infrastructure, or schema changes?"
Answer yes if the work pulls in a new third-party dependency, stands up new infrastructure/services,
or changes a data schema (new tables/columns/fields or a migration). Answering yes turns on the
Design phase (if not already on) and makes the implementation plan call out migration, rollout, and
dependency-pinning steps explicitly. Answer no if you're only changing existing code paths.
Suggested: `Yes — new deps/infra/schema` / `No — existing code only`

### Q-SIZE — "Roughly how big is this?" (signal only — does not change rigor)
Pick the rough scale. This only tunes how aggressively I parallelize and how often I checkpoint
progress; it never changes which review or design steps run.
Suggested: `Small` / `Medium` / `Large`
```

**Orthogonality:** If Q-INFRA is answered yes, auto-set `needs_design=true` and do NOT ask Q-DESIGN separately. `needs_research` is independent of the other two (you can need design without prior research and vice versa). `size_estimate` is orthogonal to all flags and never gates a phase.

#### Step 3: Route by Flags

Resolve the three booleans, then route:

- **Zero flags** (`needs_research=no`, `needs_design=no`, `needs_infrastructure=no`) → **fast path**. Skip the Research, Discovery, Design, and Planning-as-a-phase steps; write a short inline plan (≤5 numbered steps) for the operator to confirm, then implement under the lighter review floor. develop STAYS RESIDENT — it never exits and never asks permission to stay. Announce (verbatim, do not ask):

  > "This looks like a small, well-understood change with no research, design, or infrastructure work. I'll take the **fast path**: skip the research/discovery/design/planning phases, write a short inline plan for you to confirm, then implement it with the lighter review floor (code review + green-mirage, plus a test run if tests already cover the touched code). I stay in develop the whole time so review isn't skipped."

  Then log: `"Fast path: zero-flag change. Fewer phases, lighter floor, develop resident."` and proceed.

- **Any flag set** → run the phases gated by the flags (see the need-flag → phase mapping in the design doc §2.1) under the full review floor (see the review-floor policy in the design doc §3.2). More flags ⇒ more phases.

The need-flag → phase mapping (§2.1) and the need-flag → depth-gate mapping (§3.3) are the single source of truth; this command references them and does not restate their rows.

Store the resolved `need_flags` (`needs_research`, `needs_design`, `needs_infrastructure` booleans) and `size_estimate` in `SESSION_PREFERENCES`.

<FORBIDDEN>
- Proceeding past 0.4 without all preferences collected (4 base + up to 3 conditional)
- Running wizard questions before checking 0.5 continuation signals
- Trusting session summary without artifact verification
- Proceeding without answering all four need-flag questions (Q-RESEARCH, Q-DESIGN, Q-INFRA, Q-SIZE; Q-DESIGN auto-resolved when Q-INFRA is yes)
- Auto-exiting develop on a zero-flag change (the fast path keeps develop resident)
- Skipping motivation clarification when request intent is ambiguous
- Asking wizard questions again when resuming (only re-ask the 4 preference questions)
</FORBIDDEN>

---

## Phase 0 Complete

Before proceeding, verify:

- [ ] 0.5 Continuation check executed first (resume or fresh start determined)
- [ ] Escape hatches detected (or confirmed none)
- [ ] Motivation clarified (WHY)
- [ ] Feature essence clarified (WHAT)
- [ ] All 4 workflow preferences collected and stored in SESSION_PREFERENCES
- [ ] Dialectic mode and level selected (if dialectic != none)
- [ ] Token enforcement level selected
- [ ] Refactoring mode detected if applicable
- [ ] All four need-flag questions answered; `need_flags` + `size_estimate` stored in SESSION_PREFERENCES
- [ ] Flag routing determined (fast path vs. flag-gated phases)

If ANY unchecked: Complete Phase 0. Do NOT proceed.

**Next (by flags):**
- Zero flags: fast path — short inline plan, then implement under the lighter review floor (develop resident)
- Any flag set: run the flag-gated phases under the full review floor — start with `/feature-research` when `needs_research`, else jump to the first gated phase (`/feature-design` for `needs_design`/`needs_infrastructure`)

<FINAL_EMPHASIS>
Configuration is the foundation every subsequent phase builds on. Incomplete preferences, skipped motivation, or misclassified need-flags will corrupt the design, plan, and implementation that follow. Every shortcut here multiplies into rework downstream. Do not proceed until Phase 0 is complete.
</FINAL_EMPHASIS>
``````````
