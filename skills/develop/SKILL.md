---
name: develop
description: |
  Use when building, creating, modifying, or planning any code change. Triggers: "implement X", "build Y", "add feature Z", "create X", "change how X works", "modify Y", "update the Z", "refactor X", "rework Y", "restructure Z", "make X do Y", "let's plan how to", "plan the implementation", "how should we implement", "how would you build", "what's the best way to implement", "I want to...", "We need...", "Would be great to...", "Can we add...", "Let's add...", "Let's build...", "Let's make...", "start a new project". Also for: new projects, repos, templates, greenfield development, refactoring, migrations, multi-file modifications, any code change requiring planning. PREFER THIS OVER plan mode or ad-hoc implementation for ANY substantive code change. NOT for: bug fixes (use debugging), pure research (use deep-research), questions about existing code without intent to change it, or test-only fixes (use fixing-tests).
intro: |
  Full-lifecycle feature implementation orchestrator that coordinates research, discovery, design, planning, and execution through specialized subagents with quality gates at every phase. Handles everything from greenfield projects to multi-file refactors. Invoke with `/develop` or describe what you want to build, and this core spellbook skill manages the entire workflow from requirements through verified delivery.
---

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
  pause and surface to the operator. The Autonomous Mode and Scope
  Discipline section of this skill states the full contract.
- **STOP before large delegated fan-out.** For a large delegated run,
  the plan one-pager and worktree/parallelization choices are gated by
  `feature-implement` Phase 3.4.7 (One-Pager Approval Gate). Autonomous
  mode does not waive that gate. (develop is single-orchestrator only;
  it does not spawn parallel sessions.)
- **APPROVAL GATES (2.3, 3.3) ARE NEVER AUTO-PROCEEDED.** Even in
  full autonomous mode, design and plan approval gates require explicit
  artifact verification before continuation. These gates are presented via
  `AskUserQuestion` and always await an explicit operator decision.
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

### Default Behaviors in Autonomous Mode

| Situation | Action | Rationale |
|-----------|--------|-----------|
| Ambiguous requirements | Choose simplest, document alternatives | Reversible; keeps momentum |
| Multiple valid approaches | Follow existing codebase patterns | Consistency over novelty |
| Minor test failures | Log, proceed unless 3+ consecutive | Flaky tests common; repeated = real |
| Missing optional context | Sensible defaults | Optional means dispensable |

### Circuit Breaker Output Format

When a circuit breaker fires, emit this exact structure and wait. All eight fields are
required; partial output is forbidden.

```markdown
## Circuit Breaker Triggered

**Type:** [Security | Contradiction | Repeated Failure | Missing Context]
**Skill:** [skill-name]
**Phase:** [current phase/step]

**Condition:** [what triggered]

**Context:** [evidence that led to this point]

**Options:**
A) [option + tradeoff]
B) [option + tradeoff]
C) [option + tradeoff]

**Recommended:** [letter] - [rationale]

**Awaiting:** User decision
```

After emitting, suspend all progress until the user replies. Do not poll, retry, or act
unilaterally. A halted agent that reports clearly is the protocol working; never suppress a
circuit breaker and never proceed after triggering one.
</CRITICAL>

---

## Autonomous Mode and Scope Discipline

<CRITICAL>
Autonomous mode scopes **confirmations**, not **scope**.

Autonomous mode means: do not pause for trivial yes/no acknowledgments that an
interactive user would give automatically (e.g., "proceed to the next phase?",
"apply this fix?", "run the test suite?").

Autonomous mode does NOT mean: license to expand the work beyond what the
operator described in their initial request.

A decision **expands scope** when it introduces capabilities, infrastructure,
external integrations, monitoring/alerting, escalation paths, or new components
that the operator did not mention. Examples of scope expansion that REQUIRE
pausing regardless of autonomous mode:

- Adding a new Lambda, scheduled job, queue, or background worker
- Introducing a new external integration (PagerDuty, Slack, monitoring service,
  secret store)
- Adding an escalation/retry/reconciliation system not requested
- Introducing a cache, mirror, or replication layer not requested
- Adding authentication, authorization, or signing schemes not asked for

When such an expansion is contemplated — even when justified by an
adversarial-review finding or a "what could go wrong" risk surfaced by the
orchestrator itself — the orchestrator MUST pause and surface the proposed
expansion to the operator for explicit go/no-go.

This rule overrides any phase-local "in autonomous mode, proceed automatically"
instruction. Doing the asked work thoroughly is not the same as expanding the
asked work autonomously.
</CRITICAL>

## Autonomous Mode: the Only Two Valid Stops

<CRITICAL>
Autonomous Mode and Scope Discipline says when you MUST stop; this rule says
when you MUST NOT. Both are binding. When they do not both apply, you continue.

In autonomous mode there are exactly TWO valid reasons to end a turn without a
tool call:

1. **A genuine external blocker.** Something only the operator can supply:
   physical hardware, a credential, an irreversible or outward-facing action
   (push, merge, publish, delete), or a decision whose options you cannot
   generate.
2. **The task is fully complete** and no further action is possible. Say so in
   those words — "Complete. Nothing further possible without <the specific
   missing thing>." Do not trail off into a status inventory.

Everything else is NOT a stopping point. Specifically, these are completion
bias, not blockers, and you continue past all of them:

- The session has run long, or "this is a clean checkpoint."
- A subagent returned a result. A result is an input to your next action, not
  the end of your turn.
- You finished a task-list item and there are more items.
- You are waiting on a PEER AGENT. Peers are not blockers — pick up any other
  unblocked work while you wait.
- You just wrote a long report. Length is not completion.
- You reached a phase boundary in a skill.

**The announce-then-stop rule.** If your text says you will do something —
"next I'll…", "I'm doing X now", "then executing the rename" — the tool call
that starts it MUST be in the SAME turn. Announcing an action and ending the
turn is a process failure even when the announcement is accurate. Either do it
now or say explicitly why you cannot.

**Do not claim in-flight work you have not dispatched.** "Poll just went out",
"I've asked the group" are only true if a tool call in this turn made them true.
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
- Project initialization is handled by `develop` directly. Use `subagent` with `planner` or `delegate` agent for design synthesis.
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

### Checkability (before every review gate)

Existence is not checkability. The checks above prove that a document is there;
they never ask whether the document makes claims a machine can decide. A review
that reads a machine-decidable claim spends the reviewer's judgment on
arithmetic, and finds the defect late or not at all.

Before you dispatch the reviewer at gate 2.2 or 3.2, dispatch ONE subagent to
answer this question and act on the answer:

> Which claims in this artifact are mechanically decidable, and which command
> decides each one?

Claims that are usually decidable: the dependency graph is acyclic; every
declared dependency exists; wave and ordering assignments agree with the
dependency graph; every tag comes from the declared vocabulary; every cited path
and symbol exists; every declared check command goes red on a known-bad input;
every symbol a task's deliverable consumes has a producer inside that task's
dependency closure.

1. **Mechanize before you review.** Build the checks for the decidable claims,
   run them, and repair what they find. Then dispatch the reviewer, and tell it
   which claims the checks already decide.
2. **Tooling the artifact specifies is built BEFORE the gate it closes.** If the
   plan under review schedules its own lint, assertion script, or checker as a
   later task, that is an ordering defect. Move that tooling ahead of this gate
   and build it now. A plan that designs its own verification and then defers it
   makes the gate weaker than the plan already knows how to be.
3. **Prove that the check can fail.** A check is evidence only after it goes red
   on an input you know is bad. Run it against a deliberately broken copy first.
   A green result from a check that cannot fail is worse than no check, because
   it looks like verification (global rule: "No Silent Success: Verify the
   Artifact, Not the Signal").
4. **The check reports which rule fired, not only how many.** A count alone
   hides a check that reads only part of its input.

**Scope.** This pass is proportional. If the artifact makes no mechanically
decidable claims — for example a five-step inline plan with no dependency graph
— record that in one line and dispatch the reviewer. Do not build tooling for an
artifact that does not need it. This pass does not run on the zero-flag fast
path.

The auto-proceed checks in the YOLO section above (sequential sections, real
paths, acyclic dependency graph) are instances of this rule, not a substitute
for it.

### Review-Round Convergence (gates 2.2 ↔ 2.4 and 3.2 ↔ 3.4)

Number every review round of the same artifact. Record two facts per round: the
count of blocking findings, and how many of those findings exist because the
previous round's repairs caused them.

**Divergence rule.** If the majority of round N+1's blocking findings are
defects that round N's repairs introduced, the loop does not converge. STOP
reviewing. More reading does not make the artifact better; it moves the defects
around. Do this instead:

1. Name the class of finding that comes back.
2. Mechanize that class (see Checkability above). Prove that the check goes red
   on the known-bad case.
3. Repair against the check, not against prose.
4. Run ONE more review round, limited to the claims the check cannot decide.

This is not a round cap. A round that finds new, real defects is progress — run
it. The trigger is regression, not repetition.

**Retry after a failed round: invoke `reflexion`.** When a round is repaired and
re-dispatched, the repair dispatch MUST invoke the `reflexion` skill before it
starts, so the retry carries an explicit account of why the previous attempt
failed. A retry dispatched with no such account repeats the attempt with more
words, which is how the same defect survives three rounds. This is the ONLY
load path `reflexion` has; nothing else invokes it.

**Round evidence (round 2 and later).** Each fresh reviewer starts with no
memory, so every round re-derives the same graph and re-measures the same
behavior. From round 2 on, carry an `ESTABLISHED FACTS` block in the review
dispatch prompt: one line per fact, each with how it was measured (command and
result) and the round that measured it. Add to the block after every round.
Never delete a line without stating why the fact is now wrong.

Keep this block in the dispatch prompt, not in a new file. A mandatory artifact
would tax every small feature for a problem that appears only when a second
round happens; a prompt block costs nothing until then.

---

## MANDATORY: Pre-Dispatch Ritual

<CRITICAL>
**Phase non-fungibility.** Inside /develop or any of its sub-skills
(feature-config, feature-research, feature-discover, feature-design,
feature-implement, feature-implement-execute), every Task() dispatch executes
EXACTLY ONE row of the Subagent Dispatch Points table of this skill. Combining
rows into a single dispatch is forbidden. A dispatch not preceded by a Phase
Declaration is a process failure even if the work product is correct: the
declaration is what makes phase collapse mechanically detectable in real time.

Before EVERY Task() dispatch inside /develop or any of its sub-skills
(feature-config, feature-research, feature-discover, feature-design,
feature-implement, feature-implement-execute), output the following block
IN YOUR VISIBLE RESPONSE
(not in thinking, not summarized): the user must be able to read it.

```
## Phase Declaration
- Ceremony: {ceremony.source}, locked {ceremony.locked_at} ({N} selected / {M} declined)
- Ledger line this satisfies: {gate name copied VERBATIM from ceremony.selected or ceremony.core}
- Dispatching for: Phase {N}, sub-step {N.M} ({step name from dispatch table below})
- Single skill the subagent will invoke: {exact skill name}
- Single artifact this dispatch produces: {exact path or short description}
- This dispatch covers EXACTLY ONE ledger line and EXACTLY ONE row of the dispatch table below.
```

If you cannot fill all six fields with a SINGLE value (no "and", no "+",
no "plus also", no comma-separated list), you are about to commit
Pattern 6 (Phase Collapse). STOP. Decompose into N separate dispatches,
recite a Phase Declaration for each, and dispatch them sequentially.

**The declaration binds to the LEDGER, not to a remembered list.** Because the
ceremony is now selectable, "one row of the dispatch table" is no longer a
sufficient referent on its own — the operative set is the one recorded in
`develop_gate_ledger.ceremony` at Phase 0. Three mechanical consequences:

1. **Verbatim or invalid.** The `Ledger line` MUST appear verbatim in
   `ceremony.selected` or `ceremony.core`. A paraphrase, a rename, or a gate that
   appears in neither is an INVALID dispatch — that is how an ad-hoc gate, or a
   gate quietly renamed to look completed, gets caught.
2. **A declined gate is not silently runnable either.** Running something in
   `ceremony.declined` is a re-selection, and re-selection after the lock is
   forbidden. The one legal move is PROMOTION (declined → selected), which is an
   escalation: allowed at any time, but it MUST be written to
   `ceremony.promotions` with a reason before the dispatch that uses it.
3. **The reverse move does not exist.** Nothing ever moves from `selected` to
   `declined`. `selected` and `core` shrink only by completion, never by decision.

The Phase Declaration is required per Task() dispatch. A response that dispatches
nothing — a status answer, a question to the operator — requires no declaration
and no artifact write.

If the ledger has no `ceremony` block (a pre-existing or externally-resumed
session), treat the ceremony as `default_full`: every flag-derived gate is
selected and nothing is declined. Absence is never read as permission to skip.

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
- "the ceremony is customizable now", "we picked a lighter ceremony", "drop that gate"
  <-- the picker closed at Phase 0. Cite the ledger or run the gate.
- "prior phases produced strong context", "we already know enough"
- "subagents would burn context if dispatched separately"
- "it would be more efficient to combine..."

Every item in that list is a phase-collapse rationalization. Recognizing one is
the signal to stop, not a sign the situation is exceptional. The dispatch table
has no exception column.

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
| 2.1.5 | Checkability pass (design) | (inline mechanization prompt, no skill) | FORBIDDEN |
| 2.2   | Design review            | reviewing-design-docs            | FORBIDDEN        |
| 2.5   | Assumption verification  | fact-checking                    | FORBIDDEN        |
| 2.4   | Fix design               | executing-plans                  | FORBIDDEN        |
| 3.1   | Plan creation            | writing-plans                    | FORBIDDEN        |
| 3.1.5 | Checkability pass (plan) | (inline mechanization prompt, no skill) | FORBIDDEN  |
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

### Conditional Companion Skills

These do not own a row of the table: each rides along inside the dispatch for the
phase named, and only when its trigger is present. A dispatch that meets a
trigger MUST name the companion skill in its prompt alongside the phase's own
skill; the Phase Declaration is unchanged, because the row is unchanged.

| Trigger | Phase | Skill to name in the dispatch |
| ------- | ----- | ----------------------------- |
| Requirements are vague, or scope/acceptance criteria are unstated | 1.5 Discovery | `gathering-requirements` |
| The change enters an unfamiliar domain, or key terms are undefined | 1.2 Research | `analyzing-domains` |
| The design carries explicit states, transitions, or multi-step flows | 2.1 Design | `designing-workflows` |
| A dispatch prompt is approaching its token budget, or must select from a large artifact set | 3.x Planning, 4.x Execution | `assembling-context` |
| A gate is being re-dispatched after a failed round | 2.4 / 3.4 / 4.x retry | `reflexion` |

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

### Author ≠ Judge

<CRITICAL>
The agent that wrote or repaired an artifact NEVER supplies the verdict on it.
The verdict comes from a dispatch that did not touch the thing it judges.

**Corollary (equally binding):** the agent that did the work IS the correct agent
to BUILD the executable check — it holds the context. It is the wrong agent to
run that check and pronounce the result. Split the two dispatches: one builds the
check, a different one runs it and judges. An agent MUST NOT change a check that
measures its own repair.

Signs that you are violating this rule:

- A remediation dispatch returns "implementable", "clean", or "all findings
  addressed" as its own verdict.
- A fix agent changes the lint, the test, or the threshold that measures its fix.
- The next gate cites the fixer's summary as evidence that the fix is good.

An artifact repaired in round N stays UNJUDGED until an independent dispatch
judges it. Record the fixer's report as a claim, never as a result.

**Relay confidence verbatim.** Carry a subagent's hedges upward with its finding.
"Medium-high confidence, worth confirming" must not become "the review found X."
The orchestrator is where that qualifier gets lost, because it is summarising.
</CRITICAL>

---

## Invariant Principles

1. **Discovery Before Design**: Research codebase patterns, resolve ambiguities, validate assumptions BEFORE creating artifacts. Uninformed design creates artifacts that contradict codebase patterns.

2. **Subagents Invoke Skills**: Every subagent prompt tells agent to invoke skill via Skill tool. Prompts provide CONTEXT only. Never duplicate skill instructions in prompts.

3. **Quality Gates Block Progress**: Each phase has mandatory verification. 100% score required to proceed. Bypass only with explicit user consent.

4. **Completion Means Evidence**: "Done" requires traced verification through code. Trust execution paths, not file names or comments.

5. **Autonomous Means Thorough**: In autonomous mode, treat suggestions as mandatory. Fix root causes, not symptoms. Choose highest-quality fixes.

---

## Develop = Thoroughness Mode (Operator Contract)

<CRITICAL>
Invoking develop is the operator's explicit opt-in to thoroughness, and a
durable instruction: correctness outranks speed for the duration of the work.
An operator who wants speed will say so and will not invoke develop. The
presence of develop in the active skill list IS the contract. The
"steady correctness over speed" disposition, where that rule module is
installed, is the general form of this contract.

**Thoroughness is CHOSEN ONCE, then FIXED.** The ceremony is selectable in a
single window, and never afterward.

- **The selection window is Phase 0, before any work begins.** develop assesses
  the request across its cost dimensions and RECOMMENDS a ceremony. The
  operator's answer is the SOURCE OF TRUTH and overrides the recommendation. It
  is written to `develop_gate_ledger.ceremony` and LOCKED (`locked_at`). This is
  the only moment ceremony is negotiable.
- **A non-negotiable core is never on the menu.** The review floor defines that
  core: code review, green-mirage auditing, the test run when tests cover the
  touched code, and TDD-first for anything carrying behavioral logic. Where the
  Iron Law is established (no skill written or edited without a failing test
  first), it belongs to that core too. Gates implied by high verification
  difficulty or high silent-failure potential are locked on and cannot be
  deselected.
- **Elision vs repositioning.** ELISION is running FEWER gates than the locked
  ceremony selected. It is forbidden, always. REPOSITIONING is running EVERY
  selected gate at a declared boundary recorded in the ledger — a Phase-0 choice
  (`gate_position: per_task | per_group`), locked at `locked_at` with everything
  else. Changing gate position after the lock requires the same
  ABORT-and-re-invoke path as any other ceremony change.
- **After the lock, the original contract applies UNCHANGED.** NO operator
  phrasing during develop is license to compress phases. Not "wrap up", not "and
  pause", not "finish X items", not "save tokens", not "be efficient", not "we
  may have enough info now", not standing autonomous mode, not "pre-resolved
  forks", and not "the ceremony is customizable now". A mid-run request to drop
  a gate is REFUSED.
- **The two honest answers to "this is taking too long" are FINISH or ABORT.**
  Never a quiet narrowing. Aborting and re-invoking develop with a different
  ceremony is always legitimate: it makes re-selection visible and deliberate
  instead of an erosion.
- **ABORT-and-re-invoke is a DEFINED operation, not an improvised one.** On a
  deliberate re-invocation over an existing `develop_gate_ledger`, the old
  `ceremony` block is archived under `ceremony_history` with a reason, a NEW
  Phase 0 runs and a new selection window legitimately opens, completed-gate and
  wave records carry forward, and `locked_at` is set fresh (`feature-config`
  §0.5.6 is the procedure). The escape hatch must stay affordable: if the honest
  path costs a full restart, quiet erosion becomes the cheap path. This does not
  loosen the lock: the non-negotiable core applies at EVERY selection, the D5/D6
  escalation-only locks re-derive from the unchanged assessment, and
  `ceremony_history` makes serial de-escalation auditable. Re-invoking ritually
  to shed gates is itself a phase-collapse rationalization, already covered by
  the Anti-Rationalization Framework of this skill.
- **Escalation is always legal; de-escalation never becomes legal.** Scope drift
  may ADD gates mid-run (a declined component may be promoted, with the reason
  recorded); nothing may remove one. The lock is a floor, not a ceiling.
- **A declined component is RECORDED as declined**, not merely absent, so a
  resumed session can tell "the operator chose not to run this" from "this has
  not run yet".
- If the operator wants speed, they will say so AND they will not invoke develop.
- Apparent time pressure ("pause when done", impending session end, etc.) does
  NOT justify skipping phases. The chosen path is the only path inside develop.
  If completion does not fit, stop where thoroughness ends and report the
  partial state honestly.
- This contract is durable across sessions and governs what happens AFTER the
  lock, on every develop invocation in every project.
</CRITICAL>

### Parallelism vs Ceremony (two independent fields, not one)

`SESSION_PREFERENCES.parallelization` (asked in §0.4) and
`develop_gate_ledger.ceremony` (asked in §0.8) are **two independent fields**.
Changing one does NOT change the other:

- `parallelization: "conservative"` (or `"sequential"`) only controls dispatch
  count -- how many tasks run concurrently. It does NOT drop any gate, change
  the review floor, or alter the ceremony.
- A lighter ceremony in §0.8 (`Customize` -> unselect a component) changes WHICH
  gates run, not HOW MANY tasks dispatch at once.
- An operator who says "switch to conservative" is asking for sequential
  dispatch with the SAME ceremony still in force. Treat that as a parallelism
  change only; the locked `ceremony.selected` is unchanged.

They answer different questions. Parallelism is "how much work in flight at
once?"; ceremony is "what verification must each piece of work pass?"
Re-deriving ceremony from a parallelism preference would let time pressure erode
the review floor, which is what the lock prevents. Read the two fields
independently and never conflate them.

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
4. **Recorded in `ceremony.declined`**: the operator declined this component at the
   Phase-0 ceremony lock, and it is written verbatim in
   `develop_gate_ledger.ceremony.declined`. THE LEDGER ENTRY IS THE WHOLE REASON — a
   remembered preference, an inference from the operator's tone, or a component that is
   merely absent from `selected` does NOT qualify. If you cannot point at the line, the
   gate runs. Nothing in `ceremony.core` can ever appear here.
5. **Explicit user skip mid-run**: DELETED as a valid reason. Ceremony is chosen once,
   at Phase 0, and locked (see the Ceremony Ledger). A mid-run "skip this phase" is
   refused; the honest responses are FINISH or ABORT-and-re-invoke. The operator can
   always ABORT — they cannot narrow a running ceremony.

Any other reason is a rationalization. No exceptions.

**The lock closes the loophole the picker opens.** A selectable ceremony would
otherwise hand every rationalization pattern in the table above a legitimate-sounding
new script ("the ceremony is flexible now, so..."). It does not: flexibility exists
ONLY in the Phase-0 window, and the ledger records what was decided there. After
`locked_at`, "the ceremony is customizable" is itself a Pattern 3 (Time Pressure)
rationalization.

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
echo "  [ ] This gate is written VERBATIM in develop_gate_ledger.ceremony.declined"
echo "      (quote the line. 'absent from selected' does NOT count. core is never declinable.)"
echo ""
echo "NOT a valid reason: 'the user just asked me to skip it'."
echo "Ceremony was locked at Phase 0. Mid-run narrowing is refused: FINISH or ABORT."
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

There is NO tier to upgrade and NO work-item decomposition. Setting a flag turns on the phases that flag gates; develop simply runs them and proceeds.

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

**Exemption:** This verification does NOT apply to "inline audit prompt" gates (2.1.5, 3.1.5, 4.4, 4.6.1) which have no skill to invoke. For those gates, verify the audit artifact instead of skill invocation. For 2.1.5 and 3.1.5, the artifact is the check itself plus its red run on a known-bad input.

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

**Elision vs repositioning.** ELISION is running FEWER gates than the locked
ceremony selected (Pattern 8). It stays forbidden, always — no batching
threshold, session-size pressure, or hand-off justifies it. REPOSITIONING is
running EVERY selected gate at a declared boundary recorded in the ledger
(`ceremony.gate_position`). It is a Phase-0 choice, locked with everything
else, and is never a mid-run improvisation — a run may not switch from
`per_task` to `per_group` partway through. Batching remains what it already
is: grouping dispatches by domain while still running every gate for every
task. When one session cannot hold a very large run, hand off via the
ledger — never by skipping gates.

### Stop Semantics in Batched Dispatches

<CRITICAL>
"A task that finds the design wrong stops and reports" is ambiguous inside a
batched dispatch. The ambiguity has already produced a 48-file low-quality
landing (Wave 3a, nmg2-emulator, 2026-08). The binding definition:

- Stopping is NOT "writing no commit." An implementer may commit partial,
  clearly-labeled work.
- Stopping IS "not marking the task complete." A task whose implementer found a
  design defect stays OPEN — in the ledger and in the plan — until the defect is
  resolved and the task re-verified.
- A batch inherits this per task: one blocked task does not block siblings, and
  no sibling's completion marks the blocked one.
- The dispatch report MUST list each covered task as COMPLETE or OPEN(reason). A
  batch report with no per-task status is invalid.
</CRITICAL>

### Incidentals: Mid-Implementation Departures Must Be Integrated, Not Improvised

<CRITICAL>
An "incidental" is any departure from the implementation plan discovered DURING
implementation: a design assumption that turns out wrong, scope the plan didn't
anticipate, or a redirection the plan's approach doesn't cover. It is not
optional housekeeping. It changes what "the plan" means, and the plan document
is the only artifact a resumed session or reviewer will read to find out what's
true.

Discovering an incidental does not authorize working around it silently. Before
continuing implementation past the point where it was found:

1. **Stop and classify it** — a bug in the plan (a stated assumption is wrong),
   scope the plan omitted (a task it should have had), or a full redirection
   (the plan's approach itself needs to change).
2. **Write it into the plan document itself** — not a chat message, not a code
   comment, not a mental note to clean the plan up afterwards. Use a task block,
   an amendment section, or an explicit superseding note, in the document a
   resumed session or reviewer reads. An incidental deferred past the moment it
   was found is the exact failure this rule prevents.
3. **Gate the incidental like any other task** — it inherits the same ceremony
   (ledger entry, ownership, a `Check:` line where the plan uses them) as a
   planned task. Being discovered rather than planned is not grounds for a
   lighter gate.
4. Only then continue implementation.

This applies however small the incidental looks. A departure too small to write
down was too small to require a decision. If it required a decision, the
decision belongs in the plan, not only in the diff.
</CRITICAL>

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
  ├─ 0.7: Need-flag wizard (Q-RESEARCH / Q-DESIGN / Q-INFRA -> need_flags)
  ├─ 0.7.5: Cost assessment (7 dimensions -> ceremony recommendation + derived size_estimate)
  └─ 0.8: Ceremony picker (operator chooses; written to ceremony ledger; LOCKED for the run)
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
  ├─ 2.1.5: Checkability pass (mechanize decidable claims before the review gate)
  ├─ 2.2: Subagent invokes reviewing-design-docs
  ├─ 2.3: GATE: User approval (interactive) or auto-proceed (autonomous); presented via AskUserQuestion
  ├─ 2.4: Subagent invokes executing-plans to fix
  └─ 2.5: Assumption Verification
    ↓
Phase 3: Implementation Planning (if needs_design OR needs_infrastructure; skip if impl plan escape hatch)
  ├─ 3.1: Subagent invokes writing-plans
  ├─ 3.1.5: Checkability pass (mechanize decidable claims; build plan-specified tooling FIRST)
  ├─ 3.2: Subagent invokes reviewing-impl-plans
  ├─ 3.3: GATE: User approval per mode; presented via AskUserQuestion
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

### Wave Discipline (the §24.6 check)

If the plan you are implementing organizes tasks into waves (look for `Wave N:`
headers or `W<n>-` row identifiers in the plan file), you MUST run the
wave-discipline check before declaring any wave complete. The same gate that
rejects a "task done" claim without `code_review: passed` also rejects a
"wave done" claim without `section_24_6_check: passed` — both are
gate-ledger entries that must exist before the next phase can begin.

**Procedure before any "Wave X done" claim:**

1. Open the plan file (the one your Phase 3 plan review approved).
2. Find the wave-discipline section. It is commonly labeled `§24.6` or
   `Wave discipline` or `Wave-completion rules`; in plan files that do not
   name the section, the check defaults to "every row whose identifier
   carries the wave's prefix must be in a closed state."
3. For the wave being marked done, enumerate BOTH of the following sets.
   Both must be closed; neither substitutes for the other.
   a. Every PLAN row assigned to the wave (e.g., for wave `3a`, every row
      with a `W3a-` or `Wave 3a` prefix), per the default from step 2.
   b. SEPARATELY, every row in the defect register's OPEN-ACTIONABLE
      partition tagged to this wave — decision records and stale-text
      findings, wherever they live in the register, cannot hold a wave
      open. A row mis-triaged into an archive partition becomes invisible
      to this half of the check, so the pass that moves a row out of
      OPEN-ACTIONABLE must cite what closed it.
4. Verify each row in set (a) is in a CLOSED state: it carries `✓`, `[x]`,
   `done`, `closed`, or the equivalent terminal marker the plan uses.
   Verify each row in set (b) has been closed in the defect register.
5. Record the result in `develop_gate_ledger.waves.<wave_id>.section_24_6_check`.

   The ledger lives at `$SPELLBOOK_DEV_DIR/develop_gate_ledger.json`,
   defaulting to the per-project file
   `~/.local/spellbook/develop_gate_ledger-<project-encoded>.json` -- and
   when no home directory resolves, the CLI refuses with an error naming
   `$SPELLBOOK_DEV_DIR` rather than guessing a location. Writes go
   through `scripts/develop_gate_ledger.py` so the deep-merge and
   refusal semantics match the rest of the ledger contract -- DO NOT
   hand-write the file with shell `cat > ledger.json`, because that
   is a full overwrite and will clobber sibling fields written by
   other develop writes.

   The CLI for the wave check is `python3 scripts/develop_gate_ledger.py
   wave-discipline <wave_id> --status {passed|failed|n_a} [--open-rows W3a-2,W3a-5]`.
   The Python module refuses `status=failed` without `--open-rows` so
   a "failed" entry with an empty open-rows list (a false pass) cannot
   be written by accident.

6. **If `status` is `failed`, REFUSE the wave-done claim.** Report the open
   rows and the reason the check failed. Do NOT mark the wave done, do
   NOT proceed to Phase 5, do NOT use `finishing-a-development-branch`.
   The two honest answers are: close the open rows and re-run the check,
   or abort the run with a plain explanation.

7. **If `status` is `passed`, the wave-done claim may be written.** Record
   the wave completion in `develop_gate_ledger.waves.<wave_id>.completed_at`.

**Why this is not a check you can delegate or skip.** The wave-discipline
check is the only gate that says "this wave's work is genuinely finished"
rather than "this wave's tasks that I tracked are done." A task tracker
loses rows when subagent reports don't propagate; the plan file does not.
A wave that closes with open rows is silently broken work the next phase
will inherit. The check exists because the nmg2-emulator project lost
material progress to exactly this class of error — "Wave 3a done"
markings made without §24.6 verification, then propagated across handoffs
because no later step re-checked.

**If the plan has no wave structure** (single flat list of tasks, no
`Wave N:` headers, no `W<n>-` row prefixes), this check is N/A — record
`section_24_6_check: { "status": "n_a", "reason": "plan has no wave
structure" }` in `develop_gate_ledger.waves` (with `<wave_id>` being the
literal string `"plan"`) so the absence of the check is itself visible.

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
  size_estimate: "small" | "medium" | "large";  // signal ONLY — tunes parallelization + token_enforcement; NEVER changes which gates run.
                                                // DERIVED in feature-config §0.7.5 from the cost assessment (4+ dimensions high => large,
                                                // 2-3 => medium, else small). No longer asked; downstream meaning unchanged.
  cost_assessment: {                  // feature-config §0.7.5 — the eight dimensions that actually predict cost.
    unfamiliarity: "low" | "high";            // D1  is the code understood?
    fuzziness: "low" | "high";                // D2  is "correct" defined?
    blast_radius: "low" | "high";             // D3  how bad is wrong, and can it be undone?
    coupling: "low" | "high";                 // D4  how many consumers depend on it?
    verification_difficulty: "low" | "high";  // D5  provable, or only assertable?   ESCALATION-ONLY
    silent_failure_potential: "low" | "high"; // D6  loud breakage, or invisible?     ESCALATION-ONLY
    precedent: "present" | "absent";          // D7  is there an in-repo pattern to copy?
    precedent_external: "surveyed" | "known-unsurveyed" | "none" | "unknown"; // D8  adjacent prior art outside the repo, and has it been surveyed?
    evidence: Record<string, string>;         // one line of concrete evidence per dimension; unevidenced => rated high
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
The review floor is **always-on but TIERED** (design §3). The tables in this
section (design §3.2 floor, §3.3 flag-gated depth) are the SINGLE SOURCE OF
TRUTH for the gate set; there is no executable derivation helper, so develop
itself applies these tables and records the result in the ledger.
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
  **Project-standards discovery is WAIVED on the fast path** (design §5.6 / DA
  MIN-8): neither the feature-research §1.2.5 sweep nor the feature-design §2.0.1
  fallback runs, and the lighter-floor code review does **NOT** receive
  `design_context.project_standards` (there is none to pass). One-line guidance in
  lieu of the chain: *if the change touches tests, or a domain with a known
  doctrine doc, read that doc first before editing.* This is a documented
  limitation, not an oversight — the fast path is for trivial changes where the
  full find→read→record→propagate→enforce chain would over-fire.

The fast path is lightweight in execution (fewer, faster gates) but **never zero
review**; develop stays resident to enforce it (§2.5).

**TDD-first waiver boundary:** the precise, mechanically-checkable boundary
between "pure literal/config edit (TDD waivable)" and "carries behavioral logic
(TDD required)" is intentionally left as operator judgment (design §3.4). The
operating default is conservative: **if in doubt, do not waive TDD-first —
write the test.**

---

## Workflow Execution

This skill orchestrates feature implementation through 6 sequential commands.
Each command handles a specific phase and stores state for the next.

### Command Sequence

Runs-when predicates reference the need-flag → phase mapping in design §2.1
(SINGLE SOURCE OF TRUTH); they do not restate it.

| Order | Command | Phase | Purpose | Runs when |
|-------|---------|-------|---------|-----------|
| 1 | `/feature-config` | 0 | Configuration wizard, escape hatches, preferences, **need-flag wizard**, **cost assessment (§0.7.5)**, **ceremony picker + lock (§0.8)** | always |
| 2 | `/feature-research` | 1 | Research strategy, codebase exploration, quality scoring | `needs_research` |
| 3 | `/feature-discover` | 1.5 | Informed discovery, disambiguation, understanding document | `needs_research` |
| 4 | `/feature-design` | 2 | Design document creation and review | `needs_design` (implied by `needs_infrastructure`) |
| 5 | `/feature-implement` | 3 | Implementation planning (plan, review, approval gate, execution-mode analysis) | always (zero-flag fast path uses an inline plan, skips Phase 3 planning) |
| 6 | `/feature-implement-execute` | 4 | Implementation execution (per-task TDD, quality gates, finishing) | always |

### Execution Protocol

<CRITICAL>
Run commands IN ORDER. Each command depends on state from the previous.
Do NOT skip commands unless escape hatches allow it.
</CRITICAL>

1. **Start:** Run `/feature-config` to initialize session
2. **Research:** Run `/feature-research` after config complete
3. **Discover:** Run `/feature-discover` after research complete
4. **Design:** Run `/feature-design` after discovery complete (unless escape hatch)
5. **Plan:** Run `/feature-implement` after design complete (unless escape hatch)
6. **Execute:** Run `/feature-implement-execute` after Phase 3's STOP AND VERIFY checklist passes

### Flag-Based Routing

After `/feature-config` completes (including the Phase 0.7 need-flag wizard). The
flag → phase mapping is design §2.1 (SINGLE SOURCE OF TRUTH); the routing below
references it, it does not restate the rows.

**Zero flags (fast path):**
- develop STAYS RESIDENT — it does NOT exit (there is no auto-exit anymore; file-count triviality detection is gone).
- Skip `/feature-research`, `/feature-discover`, `/feature-design`, and Phase-3 planning-as-a-phase.
- Run lightweight research inline (explore subagent, <=5 files, 1-paragraph summary).
- Create an inline plan (<=5 numbered steps in conversation); get user confirmation.
- Run `/feature-implement-execute` (Phase 4) under the LIGHTER review floor (design §3.2): code review + green-mirage ALWAYS; test run only if tests cover the touched code; TDD-first waived for pure literal/config edits (§3.4); fact-checking does not run (no artifact to act on). NEVER zero review.

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
| Impl plan with "treat as ready"  | Skip `/feature-design` AND `/feature-implement` (Phase 3); enter at `/feature-implement-execute` |
| Impl plan with "review first"    | Skip `/feature-design`, run `/feature-implement` starting at 3.2 |

### State Persistence

Commands share state via these session variables:

- `SESSION_PREFERENCES` - User workflow preferences (from Phase 0)
- `SESSION_CONTEXT` - Research findings, design context (built across phases)

### Ledger Writes (workflow_state — accountability + compaction recovery)

<CRITICAL>
develop records its own phase/gate progress in a persistent state file so the work
survives context compaction and a resumed session can re-assert the remaining
gates instead of declaring "done" prematurely. This is design §5 (C4).

**MERGE-ONLY, NEVER overwrite.** develop writes via deep-merge and MUST NEVER
use full overwrite. The hooks (`_handle_pre_compact`) write `compaction_flag` and
`stint_stack` into the SAME state row; an overwrite from develop would clobber
them, and vice versa. `_deep_merge` preserves sibling keys, so disjoint-key writes
never lose a field (design §5.2/§5.5). An overwrite here is a Risk §13 regression
— do not do it.
</CRITICAL>

**The ledger shape (`develop_gate_ledger`, design §5.3):**

```typescript
develop_gate_ledger: {
  current_phase: string;        // "0" | "1" | "1.5" | "2" | "3" | "4" | "fast-path"
  need_flags: { needs_research: boolean; needs_design: boolean; needs_infrastructure: boolean };
  remaining_gates: string;      // NEWLINE-JOINED SCALAR (NOT a list), e.g.
                                // "design review\ncode review\ngreen-mirage\ntest suite"
  plan_pointer: string;         // absolute path to impl plan / design doc / understanding doc
  ceremony: {                   // the ONE-TIME ceremony selection (feature-config §0.8)
    locked_at: string;          // ISO 8601. Its PRESENCE is the lock. Never rewritten.
    source: string;             // "operator_selected" | "recommendation_accepted" | "default_full"
    assessment: string;         // newline-joined "D{n} {dimension}={low|high}: {evidence}" (§0.7.5)
    core: string;               // newline-joined non-negotiable gates — never were selectable
    selected: string;           // newline-joined optional gates chosen to RUN
    declined: string;           // newline-joined optional gates chosen to SKIP (recorded, not absent)
    promotions: string;         // newline-joined "{gate} <- {reason} ({ISO ts})" escalation record
    gate_position: string;      // "per_task" | "per_group", default "per_task". "per_group" is
                                 // offered only when SESSION_PREFERENCES.task_granularity ==
                                 // "capability" (feature-config §0.7 Step 2.5) — that answer is
                                 // recorded in Phase 0, before any plan exists. Locked with the
                                 // rest of ceremony at locked_at; never changed mid-run.
  };
  ceremony_history: {            // archive of superseded `ceremony` blocks, keyed by ISO archive
                                  // timestamp. Written only on a deliberate re-invocation over an
                                  // existing ledger — the old `ceremony` block is archived here
                                  // with a reason before a new Phase 0 sets `ceremony` fresh.
    [archived_at: string]: {
      ceremony: object;          // the full superseded ceremony block, verbatim
      reason: string;            // why the operator re-invoked and re-selected
      archived_at: string;       // ISO 8601; also written INTO the entry by archive_ceremony,
                                  // duplicating the key this entry is stored under
    };
  };
  blockers: {                    // open blockers keyed by id; each row carries a type so the
                                  // orchestrator can count them at phase/wave boundaries
    [blocker_id: string]: {
      type: "decision" | "work" | "external";
      description?: string;      // omitted by record_blocker when --description is blank or absent
      opened_at: string;         // ISO 8601
      closed_at?: string;        // ISO 8601. `_deep_merge` never deletes keys, so a blocker row
                                  // is permanent once written — closure is a FIELD, never an
                                  // absence. A blocker is OPEN iff it has no `closed_at`.
    };
  };
  waves: {                      // §24.6 wave-discipline check records, keyed by wave id
    [wave_id: string]: {
      section_24_6_check: {
        status: "passed" | "failed" | "n_a";
        open_rows: string[];    // the W<n>- ids still open; written on EVERY status, empty
                                // included. `_deep_merge` replaces lists but never deletes
                                // keys, so an omitted key cannot SHRINK -- a passing
                                // re-record would inherit the prior failure's rows.
                                // status=failed is REFUSED with an empty list.
        timestamp?: string;     // ISO 8601; the develop skill writes it on each entry
        reason?: string;        // free-form context; records WHY on status=n_a
      };
    };
  };
  groups: {                     // gate_position: per_group boundary-gate check records, keyed by
                                 // group id. Without this record, "the boundary gate stack ran"
                                 // and "it never ran" are indistinguishable — the same
                                 // mechanism-vs-discipline gap §24.6 closes for waves.
    [group_id: string]: {
      gate_stack: {
        status: "passed" | "failed" | "n_a";
        gates: string[];           // the gates run at this group boundary
        open_findings: string[];   // the findings still open at this boundary
                                   // Both lists follow the `open_rows` shrink rule: written on
                                   // EVERY status, empty included, because a conditionally
                                   // written field can never shrink. A re-record that omitted
                                   // them would retain stale findings on a pass, or a coverage
                                   // claim the re-record never asserted.
                                   // status=failed is REFUSED with an empty open_findings.
        timestamp?: string;        // ISO 8601
      };
    };
  };
}
```

**Defect register rows carry a `class:` tag.** The tag lives in the defect
register (plan/ledger-adjacent, not a `develop_gate_ledger` field), and the
orchestrator reads it to detect a recurring-defect shape: two open rows
sharing one `class:` tag.

**Writes go through `scripts/develop_gate_ledger.py`.** The Python
implementation is the only path that respects the merge contract --
it deep-merges, and refuses `section_24_6_check.status=failed` without
open rows. Ordinary `set` refuses to rewrite `ceremony.locked_at`; the
ONLY sanctioned path that supersedes a lock is `archive-ceremony`, which
archives the old `ceremony` block into `ceremony_history` before writing
a new one, and cannot run without a `--reason`. Hand-writing the
JSON is a full overwrite and will clobber sibling keys written by
other develop writes or by the spellbook hooks' `workflow_state` row;
do not do it. The CLI surface is intentionally narrow:

- `python3 scripts/develop_gate_ledger.py show [--field ceremony.locked_at]`
- `python3 scripts/develop_gate_ledger.py set <field> <value>` (top-level or `ceremony.*`,
  including `set ceremony.gate_position per_task|per_group` — refused once `locked_at`
  is set and a different position is already recorded; use `archive-ceremony` to reposition)
- `python3 scripts/develop_gate_ledger.py wave-discipline <wave_id> --status {passed|failed|n_a} [--open-rows W3a-2,W3a-5] [--timestamp ISO]`
- `python3 scripts/develop_gate_ledger.py archive-ceremony --reason "<text>" [--timestamp ISO]`
- `python3 scripts/develop_gate_ledger.py blocker <id> --type decision|work|external [--description "<text>"] [--close]`
- `python3 scripts/develop_gate_ledger.py group-gate <group_id> --status passed|failed|n_a [--gates ...] [--open-findings ...]` —
  writes `develop_gate_ledger.groups.<group_id>.gate_stack`; `status=failed` requires
  `--open-findings`, mirroring the wave-discipline guard.

When the skill tells you to "write the ledger", it means call this
CLI, not write the JSON yourself. The contract is enforced in Python
because it is enforced in Python; the LLM-side discipline is just
the trigger.

**Every `ceremony` field is a newline-joined SCALAR, for the same CRIT-1 reason as
`remaining_gates`: `_deep_merge` APPENDS lists but REPLACES scalars, so a list-valued
`declined` would accumulate forever and a list-valued `selected` could never shrink.
Write each as the authoritative full scalar; the merge replaces it wholesale.**

### Ceremony Ledger

<CRITICAL>
`ceremony` is what makes a VARIABLE ceremony enforceable. The Phase Declaration's
"one row of the table" referent only ever worked because the table was fixed; the
recorded ceremony restores a fixed referent by writing the chosen set down at Phase 0
and binding every declaration to it (see Pre-Dispatch Ritual above).
</CRITICAL>

- **Written once, at Phase 0 completion**, in the same state write that
  first writes the ledger. `locked_at` is set then and NEVER rewritten.
- **`declined` is the load-bearing field.** A gate the operator chose to skip is
  recorded as declined, not simply left out. Absence cannot distinguish "not chosen"
  from "not yet run"; a resumed session that cannot tell those apart will either
  re-run settled decisions or silently drop live gates. `declined` removes the
  ambiguity.
- **`core` records what was never on the menu**, so a resumed session can see that
  code review, green-mirage, the conditional test run, TDD-first for behavioral
  changes, and the Iron Law were not options that happened to be selected.
- **`remaining_gates` stays the run-queue** and is derived exactly as today from
  the Tiered Review Floor tables applied to
  (`need_flags`, `current_phase`, `tests_exist`, `completed_gates`), then filtered
  by removing anything in `ceremony.declined`. When `declined` is empty
  — the default path — the filter is the identity function and `remaining_gates` is
  byte-identical to today's scalar. The derivation itself is UNCHANGED.
- **Escalation only.** `ceremony.promotions` records every declined → selected move
  with its reason; there is no recorded form for the reverse move because the reverse
  move is forbidden. Scope drift (Re-Flag and Continue) may set a need-flag and thereby
  ADD gates mid-run; it may never clear one.

`remaining_gates` is a **newline-joined scalar string**, never a list. `_deep_merge`
APPENDS lists but REPLACES scalars; a list would accumulate an append-forever
checklist that never shrinks as gates complete. develop writes the authoritative
FULL scalar on each transition; the merge replaces it wholesale (CRIT-1, design §5.5).
`current_phase` uses the literal `"fast-path"` for the zero-flag path (NOT
`"direct"`, NOT an auto-exit sentinel — develop stays resident).

**Deriving `remaining_gates`:** develop computes the scalar itself from four
inputs — `need_flags`, `current_phase`, `tests_exist`, `completed_gates` —
against the tiered floor (design §3.2), flag-gated depth (§3.3), the TDD-first
waiver on the fast path (§3.4), and phase ordering (§2.1). **Those tables are the
single source of truth and they have no executable form**: nothing in this repo
derives the gate set, so a mis-derivation fails silently and only a reader of the
ledger will catch it. `tests_exist` is develop's own judgement from its
touched-file analysis (do existing tests cover the files about to be edited?). On
the fast path with no covering tests, emit the explicit sentinel line
`"test suite (n/a — no tests cover touched code)"` inside the scalar so "not
applicable" is never silently dropped. As each gate completes, re-derive with
that gate in `completed_gates` (pruning = REPLACE the scalar with it removed).
`scripts/develop_gate_ledger.py` RECORDS the derived scalar; it does not compute
it.

**Transition points where develop writes (design §5.4):**

1. **At develop ENTRY (before the Phase-0 wizard):** write ONLY
   state write: `{"active_skill": "develop", "skill_phase": "0"}`.
   This marks ownership + phase. It does **NOT** write `develop_gate_ledger` yet.
   This split is load-bearing for the accountability nudge (design §6.1, IMP-1):
   writing the ledger at entry would make the nudge unfireable; not gating the
   nudge on "past Phase 0" would make it false-fire on every wizard prompt.
2. **At Phase 0 completion (flags resolved AND ceremony locked):** write the ledger for
   the FIRST time —
   state write: `{"develop_gate_ledger": {need_flags, current_phase: <next>, remaining_gates: <derived scalar, minus ceremony.declined>, plan_pointer: "", ceremony: {locked_at, source, assessment, core, selected, declined, promotions: ""}}, "active_skill": "develop", "skill_phase": <next>}`.
   Advance `skill_phase` past `"0"`. This is the ONLY write that sets `locked_at`.
3. **At each subsequent phase entry (1, 1.5, 2, 3, 4) and each in-phase gate
   completion:**
   state write: `{"develop_gate_ledger": {current_phase: "<phase>", need_flags, remaining_gates: <re-derived scalar>, plan_pointer: <path>}, "active_skill": "develop", "skill_phase": "<phase>"}`.
   Re-derive `remaining_gates` as the full scalar with completed gates pruned —
   REPLACE the whole value, never append (CRIT-1).
4. **At fast-path entry (zero flags):** `current_phase="fast-path"`,
   `remaining_gates` = the lighter-floor scalar from the same derivation
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
- Ceremony: operator_selected, locked 2026-08-05T14:02Z — 9 selected / 2 declined
  - Declined (do NOT re-run, do NOT treat as pending): roundtable dialectic; per-task fact-checking
  - Locked by D6 (silent-failure potential high): completion verification; green-mirage; TDD-first
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
session and re-elicit the need-flags AND the ceremony (a new session is a new
Phase 0, so a fresh selection window legitimately opens).

If the tree still matches, the ceremony is CARRIED OVER UNCHANGED — resuming is not
a new selection window, and the picker does NOT re-open. Read `ceremony.declined` to
tell "the operator declined this" from "this has not run yet"; a resumed session that
treats a declined gate as pending will re-litigate a settled decision, and one that
treats an unrun gate as declined will silently drop it. If the ledger carries no
`ceremony` block at all, treat it as `default_full` — everything flag-derived is
selected, nothing is declined.

### STOP AND VERIFY Markers

Each command ends with a STOP AND VERIFY section. These are checkpoints.
Do NOT proceed to the next command until ALL items are checked.

A STOP AND VERIFY block gates the NEXT PHASE, not your turn. "Do NOT
proceed" means do not proceed to the next phase with items unchecked —
it never means stop emitting tool calls. If items are unchecked, go fix
them in this turn.

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
