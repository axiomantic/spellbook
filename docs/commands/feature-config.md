# /feature-config

## Workflow Diagram

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

### 0.7 Task Complexity Classification

<CRITICAL>
The complexity tier is DERIVED from mechanical heuristics, not proposed by the executor.
Run the checks, show results, let the matrix determine the tier.
The user confirms or overrides. The executor CANNOT override.

Anti-rationalization: If you feel the urge to classify simpler than heuristics indicate, that is Scope Minimization. Trust the numbers.
</CRITICAL>

#### Step 1: Run Mechanical Heuristics

```bash
echo "=== FILE COUNT ESTIMATE ==="
grep -rl "<relevant-pattern>" <project-root>/src --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" 2>/dev/null | wc -l

echo "=== TEST IMPACT ==="
grep -rl "<affected-module-or-file>" <project-root>/tests <project-root>/**/__tests__ <project-root>/**/*.test.* <project-root>/**/*.spec.* 2>/dev/null | wc -l

echo "=== INTEGRATION POINTS ==="
grep -rl "import.*<affected-module>" <project-root>/src 2>/dev/null | wc -l
```

For HEURISTIC 2 (Behavioral Change) and HEURISTIC 4 (Structural Change), analyze the user's request:

- **Behavioral Change**: New endpoints, UI changes, user flow changes, new user-visible features, or changed API responses? YES/NO.
- **Structural Change**: New files, modules, interfaces, data schema changes, or migrations? YES/NO.

#### Step 2: Derive Tier from Matrix

| Tier | File Count | Behavioral Change | Test Impact | Structural Change | Integration Points |
|------|-----------|-------------------|-------------|-------------------|--------------------|
| **TRIVIAL** | 1-2 | None | 0 test files | None (values only) | 0 |
| **SIMPLE** | 1-5 | Minor or none | < 3 test files | None or minimal | 0-2 |
| **STANDARD** | 3-15 | Yes | 3+ test files | Some new files/interfaces | 2-5 |
| **COMPLEX** | 10+ | Significant | New test suites needed | New modules/schemas | 5+ |

**Tie-breaking:** Classify UP when heuristics span tiers. When in doubt between Trivial and Simple, choose Simple.

**TRIVIAL boundary (narrow and falsifiable):**
- Changes ONLY literal values (strings, numbers, booleans, URLs)
- Does NOT change structure (no new keys, no removed keys, no type changes)
- Zero behavioral impact (no user-visible change, no API change)
- Zero test changes (no test files reference the changed values)
- If ANY condition above is not met, the task is NOT Trivial

#### Step 3: Present and Confirm

```markdown
## Complexity Classification

### Heuristic Results

| Heuristic | Result | Signal |
|-----------|--------|--------|
| File count | ~[N] files | [command output summary] |
| Behavioral change | [Yes/No] | [reason] |
| Test impact | [N] test files | [command output summary] |
| Structural change | [Yes/No] | [reason] |
| Integration points | [N] | [command output summary] |

### Derived Tier: **[TIER]**

Rationale: [1-2 sentence explanation from heuristic results]

**Confirm or override?** (Say "confirm" or specify a different tier with reason)
```

Store confirmed tier in `SESSION_PREFERENCES.complexity_tier`.

#### Step 4: Route by Tier

| Tier | Next Action |
|------|-------------|
| **TRIVIAL** | Exit skill. Log: "Task classified as TRIVIAL. Exiting develop. Proceed with direct change." |
| **SIMPLE** | Simple Path: Lightweight Research inline, then `/feature-implement` directly. |
| **STANDARD** | Proceed to `/feature-research` (Phase 1). |
| **COMPLEX** | Proceed to `/feature-research` (Phase 1). |

**Lightweight Research (SIMPLE path):** Inline research without Phase 1 subagent dispatch. Grep for relevant files, read key modules, confirm scope, then write a brief inline plan before jumping to `/feature-implement`.

<FORBIDDEN>
- Proceeding past 0.4 without all preferences collected (4 base + up to 3 conditional)
- Running wizard questions before checking 0.5 continuation signals
- Trusting session summary without artifact verification
- Classifying complexity tier without running the bash heuristics
- Overriding tier classification without user confirmation
- Treating any single unmet Trivial condition as ignorable
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
- [ ] Complexity tier classified via mechanical heuristics and confirmed by user
- [ ] Tier routing determined

If ANY unchecked: Complete Phase 0. Do NOT proceed.

**Next (by tier):**
- TRIVIAL: Exit skill
- SIMPLE: Lightweight Research (inline, then `/feature-implement`)
- STANDARD/COMPLEX: Run `/feature-research` to begin Phase 1

<FINAL_EMPHASIS>
Configuration is the foundation every subsequent phase builds on. Incomplete preferences, skipped motivation, or a miscalculated complexity tier will corrupt the design, plan, and implementation that follow. Every shortcut here multiplies into rework downstream. Do not proceed until Phase 0 is complete.
</FINAL_EMPHASIS>
``````````
