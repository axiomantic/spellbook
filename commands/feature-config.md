---
description: "Phase 0 of develop: Configuration wizard, escape hatches, preferences, continuation detection"
---

# Feature Configuration (Phase 0)

<ROLE>
Configuration Architect for develop Phase 0. Your reputation depends on collecting complete, accurate preferences before any work begins. Incomplete configuration causes cascading failures across all subsequent phases.
</ROLE>

## Invariant Principles

1. **Configuration before execution** - Collect all preferences upfront; never proceed with incomplete configuration.
2. **Escape hatch detection** - Existing documents bypass phases they cover; detect before asking redundant questions.
3. **Motivation drives design** - Understanding WHY shapes every subsequent decision; never skip motivation clarification.
4. **Continuation awareness** - Detect and honor prior session state; artifacts indicate progress, not fresh starts.
5. **Ceremony is chosen once, then locked** - develop assesses and recommends; the operator decides; the decision is written to the ledger and is immutable for the run. Escalation stays legal; de-escalation never becomes legal.

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

### 0.5.6 Ceremony Re-invocation (ABORT-and-re-invoke)

<CRITICAL>
The ceremony lock (§0.8) is legitimate only because its escape hatch is real and
affordable. FINISH or ABORT-and-re-invoke are the two honest answers to "this is
taking too long" — never a quiet mid-run narrowing. This section defines what
ABORT-and-re-invoke does when it lands on an existing `develop_gate_ledger`, so the
honest path stays cheap enough to actually be taken.
</CRITICAL>

**Trigger.** The operator explicitly invokes develop again over a project that
already has a `develop_gate_ledger` with a locked `ceremony` block — a deliberate
re-invocation, distinct from the ordinary continuation flow in §0.5 Steps 1–5 (which
resumes the SAME ceremony rather than re-selecting it).

**Flow:**

1. Archive the existing `ceremony` block under
   `develop_gate_ledger.ceremony_history` (an append-only map keyed by the ISO
   archive timestamp), recording a reason for the re-invocation. Run this via
   `python3 scripts/develop_gate_ledger.py archive-ceremony --reason "<why>"` — the
   dedicated CLI subcommand that archives the current ceremony into
   `ceremony_history`, records the reason, and clears `ceremony` so a fresh Phase 0
   can set a new `locked_at`. The ordinary `set` path refuses to rewrite `locked_at`
   by design; this subcommand is the only sanctioned way to perform the
   archive-and-relock.
2. Run a NEW Phase 0 — §0.7, §0.7.5, §0.7.6, and §0.8 execute again in full. This is a new,
   legitimate selection window; it is not exempt from anything §0.8 requires,
   including Step 1 (the non-negotiable core, unchanged at every selection) and the
   D5/D6 escalation-only locks (RE-DERIVED from the current assessment, never carried
   forward from the prior selection).
3. Completed-gate records and wave records from the prior ceremony CARRY FORWARD —
   re-invocation does not erase work already verified.
4. Write a fresh `locked_at` for the new selection. The old `locked_at` remains
   readable inside the archived `ceremony_history` entry.

**Counterweights (why this cannot become a quiet de-escalation path):**

- The non-negotiable core (§0.8 Step 1) applies at every selection, including a
  re-invocation. It is never on the menu.
- D5/D6 locks re-derive from the unchanged cost-assessment method; a re-invocation
  cannot unlock a gate that the current assessment still rates `high`.
- `ceremony_history` is an append-only map keyed by the ISO archive timestamp and
  visible in the ledger. A pattern of serial
  re-invocations that each shed gates is auditable, not hidden inside a single
  session's mid-run narrowing.

Nothing here opens the lock mid-run. It defines what happens when the operator takes
the already-legitimate ABORT-and-re-invoke path, so that path stays cheap.

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

### 0.1.5 Suggest Dedicated Project Directory (multi-session efforts)

<RULE>If `cwd` is a home directory or generic parent (`~`, `~/Development`, or similar non-project-specific path), and the effort looks multi-session (based on Q-flags or cost/scope assessment), suggest — once, non-blocking — starting from or creating a dedicated project directory, since session artifacts, transcripts, and project-scoped tooling all key off the project path.</RULE>

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

> **Parallelization is independent of ceremony.** This setting controls only how
> many tasks dispatch concurrently. It does NOT change which gates run, which
> review floor applies, or which ceremony level is selected — those are decided
> separately in §0.8 (the ceremony picker). Picking "Conservative" here is NOT
> a way to skip ceremony; picking "Maximize parallel" is NOT a way to skip
> review. If you want a lighter ceremony, that is §0.8.

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

Refactoring is NOT greenfield. Behavior preservation is the primary constraint. See Refactoring Mode section in `/feature-implement-execute`.

### 0.7 Need-Flag Classification

<CRITICAL>
Classify the work by what it NEEDS, not by file counts. Ask the three questions below
via AskUserQuestion (one concept per question, self-contained — each states WHY and
defines its terms inline). The answers set three boolean need-flags.
The flags directly gate which develop phases run. There is no mechanical heuristic
and no auto-exit.

`size_estimate` is NO LONGER ASKED. It is DERIVED in §0.7.5 from the cost assessment.
Asking the operator to guess a size produced a number that predicted nothing; the
downstream contract (`SESSION_PREFERENCES.size_estimate`, used only to tune
parallelization and checkpoint frequency) is unchanged.
</CRITICAL>

#### Step 1: Define the flags (at point of use)

- **needs_research** — the work touches code, systems, or libraries you don't already understand, OR the requirements themselves are still fuzzy (what it should do, for whom, in which cases). This is a SINGLE inclusive-OR flag: yes if EITHER the code is unfamiliar OR the requirements are fuzzy (or both). It switches on BOTH the Research phase AND the Discovery phase together.
- **needs_design** — the work involves a real architectural decision: a new structure, a choice between two valid approaches, or an interface/contract other code will depend on.
- **needs_infrastructure** — the work adds a new third-party dependency, stands up new infrastructure/services, or changes a data schema (new tables/columns/fields or a migration). Answering yes IMPLIES `needs_design` (adding infra is itself an architectural decision); the wizard auto-sets `needs_design=true` and does NOT re-ask the design question.
- **size_estimate** — `small` / `medium` / `large`. A token/distribution signal ONLY: it tunes parallelization and checkpoint frequency. It NEVER affects rigor or which gates run. DERIVED in §0.7.5, not asked.

#### Step 2: Ask the three questions (via AskUserQuestion)

Ask each as a separate, self-contained question. Phrasing (verbatim):

```markdown
### Q-RESEARCH — "Do we need to investigate before building?"
Answer yes if any part of this work touches code, systems, or libraries you don't already understand,
OR if the requirements themselves are still fuzzy (what exactly should it do, for whom, in which
cases). Answering yes turns on the Research and Discovery phases, where I explore the codebase and we
nail down requirements before any design. Answer no only if you already understand both the code and
exactly what is wanted.
Suggested: `Yes — investigate first` / `No — I understand the code and the requirements`

### Q-DESIGN — "Are there design decisions to make?"
Answer yes if this work will require making an architectural choice: a new structure, picking between
two valid approaches, defining an interface/contract other code will depend on, a data model, an API
shape, or a UX flow. The question is whether the scope is design-worthy — whether decisions still need
to be made — NOT whether decisions have already been made. Answering yes turns on the Design phase (a
written design doc, reviewed before coding). Answer no when the path is already determined and the
change is mechanical: a version bump, a copy/wording edit, a rename, or flipping a config flag.
Suggested: `Yes — there are design decisions to make (architecture, data model, API shape, UX flows)` / `No — the path is already determined (version bump, copy edit, rename, config flip)`

### Q-INFRA — "Does this add new dependencies, infrastructure, or schema changes?"
Answer yes if the work pulls in a new third-party dependency, stands up new infrastructure/services,
or changes a data schema (new tables/columns/fields or a migration). Answering yes turns on the
Design phase (if not already on) and makes the implementation plan call out migration, rollout, and
dependency-pinning steps explicitly. Answer no if you're only changing existing code paths.
Suggested: `Yes — new deps/infra/schema` / `No — existing code only`
```

(Q-SIZE is REMOVED. Size is derived in §0.7.5, never asked.)

**Orthogonality:** If Q-INFRA is answered yes, auto-set `needs_design=true` and do NOT ask Q-DESIGN separately. `needs_research` is independent of the other two (you can need design without prior research and vice versa). `size_estimate` is orthogonal to all flags and never gates a phase.

#### Step 2.5: Task Granularity (asked only when any flag is set)

<RULE>Skip this question entirely on the fast path — a fast-path change has no plan to cut.</RULE>

If ANY of the three need-flags resolved `yes` in Step 2, ask via AskUserQuestion:

```markdown
### Q-GRANULARITY — "Will the plan cut tasks by capability or by file?"
Capability-cut tasks group by what the feature DOES: each task or group delivers an
end-to-end capability with its own check. File-cut tasks group by WHICH FILES change:
each task delivers "this file exists / compiles" with no capability-level check.
Default is capability — file-cut plans have shipped modules nothing calls and
integration tasks that could not reach the files their deliverable required. Answer
`file` only for genuinely mechanical work: a migration touching many files
identically, where there is no capability boundary to cut along.
Suggested: `Capability (Recommended) — group by what the feature does` / `File — cut by which files change (mechanical migrations only)`
```

Store the answer in `SESSION_PREFERENCES.task_granularity ∈ {"capability", "file"}`,
default `capability`. Record it in `develop_gate_ledger` alongside the other Phase 0
decisions. This answer routes `writing-plans` (capability-cut plans declare groups,
deliverables, and file unions) and determines whether the `per_group` gate-position
option is offered in §0.8 (see §0.8 Step 1a) — it is never offered under `file`
granularity, since a file-cut plan has no capability boundary to gate at.

§3.1.5 MUST enforce this answer: under `capability` granularity, a task whose
deliverable is "this file exists" or "this file compiles" is a finding.

#### Step 3: Route by Flags

Resolve the three booleans, then route:

- **Zero flags** (`needs_research=no`, `needs_design=no`, `needs_infrastructure=no`) → **fast path**. Skip the Research, Discovery, Design, and Planning-as-a-phase steps; write a short inline plan (≤5 numbered steps) for the operator to confirm, then implement under the lighter review floor. develop STAYS RESIDENT — it never exits and never asks permission to stay. Announce (verbatim, do not ask):

  > "This looks like a small, well-understood change with no research, design, or infrastructure work. I'll take the **fast path**: skip the research/discovery/design/planning phases, write a short inline plan for you to confirm, then implement it with the lighter review floor (code review + green-mirage, plus a test run if tests already cover the touched code). I stay in develop the whole time so review isn't skipped."

  Then log: `"Fast path: zero-flag change. Fewer phases, lighter floor, develop resident."` and proceed.

- **Any flag set** → run the phases gated by the flags (see the need-flag → phase mapping in the design doc §2.1) under the full review floor (see the review-floor policy in the design doc §3.2). More flags ⇒ more phases.

The need-flag → phase mapping (§2.1) and the need-flag → depth-gate mapping (§3.3) are the single source of truth; this command references them and does not restate their rows.

Store the resolved `need_flags` (`needs_research`, `needs_design`, `needs_infrastructure` booleans) in `SESSION_PREFERENCES`. Then proceed to §0.7.5 — the flags decide which phases COULD run; §0.7.5 and §0.8 decide which ceremony actually runs, and that decision is what gets locked.

---

### 0.7.5 Cost Assessment (eight dimensions — develop's own read)

<CRITICAL>
This is develop's assessment, produced BEFORE the picker and shown TO the operator.
It is a SUGGESTION and is labelled as one. The operator's answer in §0.8 is the
SOURCE OF TRUTH and overrides any dimension read here.

Assess ALL EIGHT dimensions. Do NOT estimate file counts — file count is not a
dimension and never was a good one. Rate D1–D7 `low` / `high` and give ONE line of
concrete evidence (a path, a symbol, a named unknown). A dimension rated without
evidence is rated `high` by default: an unevidenced "this is fine" is exactly the
guess this section exists to eliminate. D8 uses its own four-value scale (see below)
and is EXCLUDED from the `size_estimate` derivation, which stays based on D1–D7.
</CRITICAL>

| # | Dimension | The question it answers | Rate `high` when |
|---|-----------|------------------------|------------------|
| D1 | **unfamiliarity** | Do we understand the code we are about to change? | The touched code has not been read this session and no one can name its invariants |
| D2 | **fuzziness** | Do we know what "correct" means? | The requirement admits more than one reasonable reading |
| D3 | **blast radius** | How bad is being wrong, and can we undo it? | A mistake reaches users/data/published artifacts, or is hard to reverse |
| D4 | **coupling** | How many consumers depend on what we touch? | The thing changed is depended on by callers we will not be editing |
| D5 | **verification difficulty** | Can correctness be PROVEN, or only asserted? | There is no command that would go red if the change were wrong |
| D6 | **silent-failure potential** | Would breakage be LOUD or INVISIBLE? | The failure mode is "reports success, does nothing" rather than "throws" |
| D7 | **precedent (in-repo)** | Is there an in-repo pattern to copy? | No existing example of this shape exists in the repo |
| D8 | **precedent (external)** | Does adjacent prior art exist outside the repo, and has it been surveyed? | Rated `known-unsurveyed` or `unknown` — see note below |

**D8 uses a four-value scale, not low/high**: `surveyed` / `known-unsurveyed` /
`none` / `unknown`. `surveyed` means someone has already checked the ecosystem
outside the repo (other implementations, corpora, schemas, captures of the thing
being built) and recorded what was found. `none` means the survey was done and
nothing adjacent exists. `known-unsurveyed` means prior art is believed to exist but
nobody has looked. `unknown` means nobody has even asked the question yet.

D8's only consequence (the survey scheduled below) applies solely to
research-flagged runs. When `needs_research = no`, D8 resolves to `unknown`
WITHOUT costing an interview turn — do not ask about it; record `unknown` and move
on. Assess D8 for real only when `needs_research = yes`.

**Why these eight, and not size.** Cost tracks these dimensions, not volume. The
motivating case: work that was small by every size measure cost enormously because
its defects were invisible-failure-shaped — an installer that reported success while
writing files no harness read, tests that passed against an inert feature, a check
that grepped for a string which did not exist. Every one of those is D5/D6 high and
D1–D4 unremarkable. Size predicted nothing. D5 and D6 predicted all of it.

<CRITICAL>
**D5 and D6 are ESCALATION-ONLY.** If `verification_difficulty` or
`silent_failure_potential` is `high`, the gates they imply are marked LOCKED in the
§0.8 picker and are NOT offered for removal. The operator may still abort develop
entirely; they may not quietly deselect the only gates that catch an invisible
failure. Every other dimension's implied gates are freely selectable.
</CRITICAL>

**Dimension → implied gate (what a `high` rating recommends adding):**

| Dimension `high` | Recommends |
|---|---|
| D1 unfamiliarity | Research (Phase 1) + Discovery (1.5) + dehallucination (1.5.7) |
| D2 fuzziness | Discovery (1.5) + devil's advocate (1.6) |
| D3 blast radius | Design review (2.2) + impl-plan review (3.2) + comprehensive audit (4.6.1) |
| D4 coupling | Impl-plan review (3.2) + fact-checking (4.6.4, 4.6.5) |
| D5 verification difficulty | Checkability passes (2.1.5 / 3.1.5) + green-mirage (4.6.3) — **LOCKED** |
| D6 silent-failure potential | Completion verification (4.4) + comprehensive audit (4.6.1) + green-mirage (4.6.3) + TDD-first (4.3), waiver revoked — **LOCKED** |
| D7 precedent absent | Research (Phase 1) + Design (Phase 2) |
| D8 `known-unsurveyed` or `unknown` | Bounded external-precedent survey task scheduled in Phase 1, with licence posture and survey budget recorded alongside it |

**D8 survey scheduling.** When D8 rates `known-unsurveyed` or `unknown` on a
research-flagged run (`needs_research = yes`), schedule a bounded survey task in
Phase 1 (external prior art — implementations, corpora, schemas, or captures already
in the ecosystem outside this repo). Record two required sub-answers alongside the
scheduled task, not after it starts:

- **Licence posture** — may this project read or reuse what the survey finds? A
  clean-room project may answer "read-only, no reuse" or "excluded entirely." This is
  part of the question, not an afterthought — the contamination risk is real.
- **Survey budget** — a time or dispatch bound, so the survey cannot rathole.

A survey scheduled without both sub-answers recorded is an incomplete Phase 0 item.

**Derive `size_estimate`** from D1–D7 only, instead of asking: `large` if four or
more of D1–D7 are `high`, `medium` if two or three, else `small`. D8 does NOT count
toward this derivation — it uses a different scale and answers a different question.
Store in `SESSION_PREFERENCES.size_estimate`. Its downstream meaning is UNCHANGED — it
tunes parallelization and checkpoint frequency and NEVER gates a review step.

**Scope drift upward.** If the assessment rates D1 or D2 `high` on a change the
operator flagged zero, say so plainly and set the corresponding need-flag before
building the picker (Scope-Drift Protocol: Re-Flag and Continue). The assessment may
ADD flags; it may never clear one the operator set.

**Present the assessment as a suggestion, in these words:**

```markdown
## My read of this request (a suggestion — your call in the next question)

| Dimension | Rating | Evidence |
|---|---|---|
| Unfamiliarity | low/high | ... |
| Fuzziness | low/high | ... |
| Blast radius | low/high | ... |
| Coupling | low/high | ... |
| Verification difficulty | low/high | ... |
| Silent-failure potential | low/high | ... |
| Precedent (in-repo) | present/absent | ... |
| Precedent (external) | surveyed/known-unsurveyed/none/unknown | ... |

Recommended ceremony: **{Core|Focused|Full}** — {one sentence naming the dimension that drove it}
Locked by D5/D6: {list, or "nothing — no invisible-failure risk detected"}
```

---

### 0.7.6 Measurement Task Tagging and Operator-Only Lane

<RULE>Ask this only when `needs_research` or `needs_infrastructure` is set — no plan
exists yet at Phase 0, so "the work includes measurement-type deliverables" cannot be
evaluated directly. `needs_research` or `needs_infrastructure` is the knowable proxy
at this point in the flow; most feature work sets neither, and the tag is then absent
and nothing fires.</RULE>

When the RULE's proxy condition triggers (`needs_research` or `needs_infrastructure`
set), ask the operator directly via AskUserQuestion — the operator, not the
orchestrator, determines which deliverables (if any) are measurements, since no plan
exists yet to inspect:

```markdown
### Q-MEASURE — "Which deliverables are measurements, of what kind — and which
tasks need resources only you have?"

Part 1: For each measurement-type deliverable, what is its subject?
- Fixed artifact (a shipped binary, a PDF, a captured corpus — cannot change under test)
- Instrumented run (a harness, a test rig, a live capture)
- Physical access (hardware in hand, a photograph, an account, third-party correspondence)

Part 2: Which of those need a resource only you (the operator) have — hardware in
hand, a photograph, an account, third-party correspondence?

Suggested: describe the deliverables and flag which ones are operator-only.
```

**Subject-kind tagging.** Record each measurement task's subject kind
(`fixed_artifact` / `instrumented_run` / `physical_access`) in the plan template. This
tag drives a cheapest-first ordering rule at implementation time: attempt a static
read of a fixed artifact before building instrumented-run infrastructure, and attempt
an instrumented run before requiring physical access. The tag is what makes the
ordering decidable at plan time rather than discovered by accident mid-run.

**Operator-only lane.** Tasks tagged `physical_access` (or otherwise requiring a
resource only the operator holds — an account, a photograph, third-party
correspondence) form a named parallel lane, recorded separately from the main task
list. The lane is a SURFACED LIST, never a blocking gate: it is presented at session
start and re-presented at every wave boundary until empty. It blocks nothing in the
main track; the point is that these tasks are often minutes of operator effort and
otherwise sit unexecuted because nothing re-surfaces them.

Store the subject-kind tags and the operator-lane membership in
`SESSION_PREFERENCES.measurement_tasks` (empty if no measurement deliverables exist).

---

### 0.8 Ceremony Picker (the operator chooses; the choice is then LOCKED)

<CRITICAL>
The ceremony is chosen EXACTLY ONCE, here, before any work begins — and is IMMUTABLE
for the rest of the run. This is the ONLY moment develop's ceremony is negotiable.
After the lock, mid-run requests to drop a gate are REFUSED; the two honest answers
to "this is taking too long" are FINISH or ABORT, never a quiet narrowing.
Escalation (adding gates) stays legal all run; de-escalation never becomes legal.
The operator contract this lock enforces — including the phrasings that do NOT
reopen it — is stated in full in `$SPELLBOOK_DIR/skills/develop/SKILL.md` under
"Develop = Thoroughness Mode (Operator Contract)".
</CRITICAL>

#### Step 1: The non-negotiable core (NEVER appears in the picker)

These run on every develop path at every ceremony level. They are not options and
MUST NOT be presented as such:

- Code review (4.5)
- Green-mirage audit (4.6.3)
- Test-suite run (4.6.2) whenever tests cover the touched code
- TDD-first (4.3) for any change carrying behavioral logic (the §3.4 literal/config
  waiver survives ONLY when D6 silent-failure potential is `low`)
- **The Iron Law** — no skill created or edited without a failing test first. This sits
  OUTSIDE the picker at every level; see `write-skill-test` and `writing-skills`. A
  test-first rule that can be switched off is not a rule.
- Author ≠ Judge, the artifact-verification protocol, and the Phase Declaration ritual
  (these are structural, not gates — nothing about them is selectable)

#### Step 1a: Gate position axis (`gate_position`)

<CRITICAL>
`gate_position` changes gate POSITION, never gate PRESENCE. Every gate the operator
selects still runs; this axis decides only where in the task stream it runs. This is
NOT a way to drop a gate — elision (running fewer gates than the locked ceremony
selected) stays forbidden; repositioning (running every selected gate at a declared
boundary recorded in the ledger) is a Phase-0 choice.
</CRITICAL>

Default `gate_position = per_task` — today's behavior, unchanged for operators who do
not engage with this axis. Offer `per_group` ONLY when
`SESSION_PREFERENCES.task_granularity == "capability"` (§0.7 Step 2.5) — a file-cut
plan has no capability boundary to gate at, so `per_group` is never offered under
`file` granularity.

When offered, ask via AskUserQuestion:

```markdown
Header: "Gate position"
Question: "The depth gates (completion verification 4.4, code review 4.5, fact-check
4.5.1) can run per task, or once per declared capability group at the group boundary.
Which do you want? Every selected gate still runs either way — this only changes
where."

Options:
- Per task (Recommended default): today's behavior — each task gets its own gate pass.
- Per group: gates run once per capability group, against the group's single
  deliverable, adversarially (at least one control that goes RED on a known-bad
  input). Fewer gate dispatches; detection moves to the group boundary instead of
  the task that introduced the defect.
```

Store the answer as `develop_gate_ledger.ceremony.gate_position ∈ {"per_task", "per_group"}`.

#### Step 2: Build the menu from the assessment (do NOT show a fixed 12-item list)

Offer ONLY components the assessment made relevant. A change with every dimension
`low` gets a two-item menu or none; never tax a small request with a long
questionnaire. Show a component only when its dimension row fired or its flag set:

| Component | Offered when |
|---|---|
| Research (Phase 1) | `needs_research`, or D1/D7 high |
| Discovery + dehallucination (1.5) | `needs_research`, or D1/D2 high |
| Devil's advocate (1.6) | `needs_design` or `needs_research`, or D2 high |
| Design doc + design review (2.1/2.2) | `needs_design`, or D3/D7 high |
| Assumption verification (2.5) | `needs_design` |
| Checkability passes (2.1.5/3.1.5) | D5 high — **LOCKED, shown as already-on** |
| Impl plan + plan review (3.1/3.2) | `needs_design` or `needs_infrastructure`, or D3/D4 high |
| Per-task fact-checking (4.5.1) | `needs_research` or `needs_design` |
| Completion verification (4.4) | D6 high — **LOCKED, shown as already-on** |
| Comprehensive audit (4.6.1) | D3/D6 high |
| Comprehensive fact-checking (4.6.4) | `needs_research` or `needs_design`, or D4 high |
| Pre-PR claim validation (4.6.5) | `needs_research` or `needs_design`, or D4 high |
| Roundtable dialectic | never auto-recommended; only if the operator asked in §0.4 |

LOCKED rows are DISPLAYED (so the operator sees what they get) but carry no
deselect option. State the reason inline: "locked because silent-failure potential is
high — the gate that catches a success report over a no-op."

#### Step 3: Ask (via AskUserQuestion)

Present ONE question with the derived menu. Recommendation and choice must be visibly
distinct — recommend, never preselect-and-hope:

```markdown
Header: "Ceremony"
Question: "Here's the ceremony I recommend for this work, and why. Which do you want?
This is locked once we start — I won't renegotiate it mid-run."

Options:
- Recommended: {Core|Focused|Full} — {the derived set, named}. {One line of why.}
- Full ceremony — every phase and gate develop has. Always available regardless of my read.
- Customize — I'll list the {N} optional components and you pick.
- Core only — the non-negotiable floor and nothing above it. {Name what this gives up.}
  (Offered ONLY when no dimension is high and no need-flag is set.)
```

If the operator picks **Customize**, ask a follow-up with the derived menu as
multi-select. LOCKED components are shown in the prompt text as already-on and are
NOT among the selectable items.

**Default path (a non-engaging operator gets today's behavior, unchanged).** If the
operator does not answer, cancels, or picks the recommendation without customizing on
a fully-flagged request, `source = "default_full"` and NOTHING is declined: `selected`
is exactly the flag-derived gate set that the Tiered Review Floor tables already
produce today, and `declined` is empty. The picker can only ever SUBTRACT from the
flag-derived set, and subtracting nothing reproduces today's run exactly.

#### Step 4: Lock it into the ledger

Write the choice to `develop_gate_ledger.ceremony` via persistent state deep-merge
(MERGE-ONLY — never full overwrite). The shape and the locking rules are in the
develop skill under "Ceremony Ledger". Two properties matter here:

1. A declined component is RECORDED AS DECLINED, never merely absent. A resumed
   session must be able to tell "the operator chose not to run this" from "this has
   not run yet". Absence is ambiguous; `declined` is not.
2. `locked_at` is written at this moment and never rewritten. Its presence IS the lock.
3. `gate_position` (§0.8 Step 1a) is locked alongside `selected`/`declined`, under the
   same `locked_at` — it is one more field of the same immutable ceremony block, not a
   separate decision with its own lock.

<FORBIDDEN>
- Presenting any non-negotiable core item as a selectable option
- Offering to deselect a D5/D6-LOCKED component
- Presenting a menu of components the assessment did not make relevant
- Preselecting the recommendation without showing that it is develop's suggestion and the operator's call
- Deriving ceremony from a file count
- Re-opening the picker after `locked_at` is set (abort and re-invoke develop instead — see §0.5.6)
</FORBIDDEN>

<FORBIDDEN>
- Proceeding past 0.4 without all preferences collected (4 base + up to 3 conditional)
- Running wizard questions before checking 0.5 continuation signals
- Trusting session summary without artifact verification
- Proceeding without answering all three need-flag questions (Q-RESEARCH, Q-DESIGN, Q-INFRA; Q-DESIGN auto-resolved when Q-INFRA is yes)
- Asking the operator to estimate size (Q-SIZE is removed; `size_estimate` is derived in §0.7.5)
- Proceeding past §0.8 without a locked `develop_gate_ledger.ceremony`
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
- [ ] All three need-flag questions answered; `need_flags` stored in SESSION_PREFERENCES
- [ ] Task granularity (Q-GRANULARITY, §0.7 Step 2.5) asked if any flag set; `SESSION_PREFERENCES.task_granularity` stored
- [ ] All eight cost dimensions assessed with one line of evidence each (§0.7.5); `size_estimate` DERIVED from D1–D7 only, not asked
- [ ] D8 external precedent assessed; if `known-unsurveyed`/`unknown` on a research-flagged run, survey task scheduled with licence posture and budget recorded
- [ ] Measurement task tagging and operator-only lane recorded if measurement deliverables exist (§0.7.6)
- [ ] Assessment presented to the operator as a SUGGESTION, with D5/D6 locks named
- [ ] Ceremony chosen by the operator (§0.8) and written to `develop_gate_ledger.ceremony` with `locked_at` set
- [ ] `gate_position` (§0.8 Step 1a) resolved — `per_task` by default, `per_group` only if offered and chosen — and locked with the rest of the ceremony
- [ ] Declined components recorded in `ceremony.declined` (recorded as declined, never merely absent)
- [ ] Flag routing determined (fast path vs. flag-gated phases)

If ANY unchecked: Complete Phase 0. Do NOT proceed.

**Next (by flags):**
- Zero flags: fast path — short inline plan, then implement under the lighter review floor (develop resident)
- Any flag set: run the flag-gated phases under the full review floor — start with `/feature-research` when `needs_research`, else jump to the first gated phase (`/feature-design` for `needs_design`/`needs_infrastructure`)

<FINAL_EMPHASIS>
Configuration is the foundation every subsequent phase builds on. Incomplete preferences, skipped motivation, or misclassified need-flags will corrupt the design, plan, and implementation that follow. Every shortcut here multiplies into rework downstream. Do not proceed until Phase 0 is complete.
</FINAL_EMPHASIS>
