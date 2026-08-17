---
id: develop-discipline
name: Develop Skill Discipline
class: preference
default: "on"
description: >
  Phase non-fungibility inside the develop skill, and the thoroughness contract
  that invoking develop establishes.
benefit: >
  Stops the develop skill from collapsing its own phases into a single dispatch.
declining_means: >
  The agent may combine develop phases into one dispatch and may compress phases
  when it judges the work small or the session short.
related:
  - skills/develop
  - commands/feature-design
  - commands/feature-implement
  - commands/feature-implement-execute
renamed_from: []
superseded_by: null
paths: []
---

<CRITICAL>
### Develop Skill Phase Non-Fungibility

When inside /develop or any of its sub-skills (feature-config, feature-research,
feature-discover, feature-design, feature-implement,
feature-implement-execute), every Task() dispatch
executes EXACTLY ONE row of the dispatch table at
`$SPELLBOOK_DIR/skills/develop/SKILL.md` "Subagent Dispatch Points" section.

Combining rows into a single dispatch is forbidden EVEN WHEN:

- The feature is "small" or classified STANDARD ("doesn't need all gates")
- The architecture is "pre-validated" or the operator "pre-resolved forks"
- The operator said "wrap up", "and pause", "finish X items", or "close out"
- Standing autonomous mode is active
- Prior phases produced strong context
- Subagents would burn context if dispatched separately
- "It would be more efficient to combine..."
- "We're trying to wrap up..."
- "The user wants to pause..."
- "The ceremony is customizable now" / "we picked a lighter ceremony"

ALL of those listed rationalizations are phase-collapse rationalizations.
Recognizing the rationalization IS the signal to stop, not the signal that
the situation is exceptional. The dispatch table has no exception column.

Because the ceremony is selectable at Phase 0, the dispatch table alone is no
longer a sufficient referent. Every Phase Declaration must ALSO cite the exact
gate line it satisfies, copied VERBATIM from `develop_gate_ledger.ceremony`
(`selected` or `core`). A cited line that appears in neither is an invalid
dispatch; a line in `ceremony.declined` may be run only after being promoted
to `selected` with a recorded reason. Nothing ever moves the other way.

Each Task() dispatch inside /develop must be preceded by a Phase Declaration
block (see `$SPELLBOOK_DIR/skills/develop/SKILL.md` "Pre-Dispatch Ritual").
The block makes phase collapse mechanically detectable to the operator in
real time. A dispatch without a preceding Phase Declaration is a process
failure even if the work product is correct.

### Develop = Thoroughness Mode (Operator Contract)

If the `core-philosophy` module is installed, its "steady correctness over speed"
rule is the general form of this contract.

Invoking the develop skill is the operator's explicit opt-in to thoroughness.
Treat that invocation as a durable instruction that correctness and thoroughness
always outrank speed for the duration of the work. An operator who wants speed
will say so explicitly and will not invoke the develop skill; the presence of
develop in the active skill list IS the contract.

**Thoroughness is CHOSEN ONCE, then FIXED.** develop's ceremony is selectable
— but only in a single window, and never afterward.

- **The selection window is Phase 0, before any work begins.** develop assesses
  the request across its cost dimensions and RECOMMENDS a ceremony; the
  operator's answer is the SOURCE OF TRUTH and overrides the recommendation.
  The result is written to `develop_gate_ledger.ceremony` and LOCKED
  (`locked_at`). This is the only moment ceremony is negotiable.
- **A non-negotiable core is never on the menu.** If the develop skill is
  installed, its review floor defines that core: code review, green-mirage
  auditing, the test run when tests cover the touched code, and TDD-first for
  anything carrying behavioral logic. If a rule or command establishing the
  Iron Law is present (no skill written or edited without a failing test
  first), the Iron Law belongs to that core as well. Gates implied by high
  verification difficulty or high silent-failure potential are locked on and
  cannot be deselected.
- **After the lock, the original contract applies UNCHANGED.** NO operator
  phrasing during develop is license to compress phases. Not "wrap up", not
  "and pause", not "finish X items", not "save tokens", not "be efficient",
  not "we may have enough info now", not standing autonomous mode, not
  "pre-resolved forks", and not "the ceremony is customizable now". A mid-run
  request to drop a gate is REFUSED.
- **The two honest answers to "this is taking too long" are FINISH or ABORT.**
  Never a quiet narrowing. Aborting and re-invoking develop with a different
  ceremony is always available and is fully legitimate — it makes re-selection
  visible and deliberate instead of an erosion. Silently dropping gates is not
  a third option.
- **Escalation is always legal; de-escalation never becomes legal.** Scope
  drift may ADD gates mid-run (a declined component may be promoted, with the
  reason recorded); nothing may remove one. The lock is a floor, not a ceiling.
- **A declined component is RECORDED as declined**, not merely absent, so a
  resumed session can tell "the operator chose not to run this" from "this has
  not run yet".
- If the operator wants speed, they will say so AND they will not invoke
  develop.
- Apparent time pressure ("pause when done", impending session end, etc.)
  is NOT a circumstance that justifies skipping phases. The chosen path is
  the only path inside develop. If completion does not fit, stop where
  thoroughness ends and report the partial state honestly.
- This contract is durable across sessions and governs what happens AFTER the
  lock, on every develop invocation in every project.

### Parallelism vs Ceremony (two independent fields, not one)

`SESSION_PREFERENCES.parallelization` (asked in §0.4) and
`develop_gate_ledger.ceremony` (asked in §0.8) are **two independent fields**.
Changing one does NOT change the other. Specifically:

- Picking `parallelization: "conservative"` (or `"sequential"`) only controls
  dispatch count -- how many tasks run concurrently. It does NOT drop any
  gate, change the review floor, or alter the ceremony.
- Picking a lighter ceremony in §0.8 (`Customize` -> unselect a component)
  changes WHICH gates run, not HOW MANY tasks dispatch at once.
- An operator who says "switch to conservative" is asking for sequential
  dispatch with the SAME ceremony still in force. The skill treats that as
  a parallelism change only; the locked `ceremony.selected` is unchanged.

The two are independent because they answer two different questions.
Parallelism is "how much work in flight at once?"; ceremony is "what
verification must each piece of work pass?" Asking the operator to
re-derive ceremony from a parallelism preference would let time pressure
quietly erode the review floor, which is exactly what the lock prevents.
The skill reads parallelism from `SESSION_PREFERENCES` and ceremony from
`develop_gate_ledger.ceremony` independently and never conflates the two.

### Wave Discipline (the §24.6 check)

If the plan you are implementing organizes tasks into waves (`Wave N:`
headers or `W<n>-` row identifiers in the plan file), the develop skill
records a §24.6 wave-discipline check for each wave before any
"Wave X done" claim may be written. The check has three statuses:

- `passed` -- every row assigned to the wave is in a closed state. The
  `Wave X done` claim may be written.
- `failed` -- at least one row assigned to the wave is still open. The
  open-row identifiers are recorded; the `Wave X done` claim is REFUSED
  until the rows are closed and the check is re-run.
- `n_a` -- the plan has no wave structure (flat task list). Recorded so the
  absence of the check is itself visible at review.

The check is implemented in `scripts/develop_gate_ledger.py` and is the
only path that may write the entry; hand-writing the JSON is a full
overwrite that clobbers sibling fields written by other develop writes.
The Python module refuses `status=failed` without an `open_rows` list so
a false pass (failed status with no rows to fix) cannot be written by
accident. Refusing a wave-done claim is the only enforcement; if the
skill does not refuse, the wave-done claim is silently broken work the
next phase will inherit. The motivating failure mode is documented in
the nmg2-emulator handoff (2026-08-10): "Wave 3a done" markings made
without §24.6 verification propagated across handoffs because no later
step re-checked.

### Stop Semantics in Batched Dispatches

"A task that finds the design wrong stops and reports" is ambiguous inside
a batched dispatch, and the ambiguity has already produced a 48-file
low-quality landing (Wave 3a, nmg2-emulator, 2026-08). The binding
definition:

- Stopping is NOT "writing no commit." An implementer may commit partial,
  clearly-labeled work.
- Stopping IS "not marking the task complete." A task whose implementer
  found a design defect stays OPEN — in the ledger and in the plan — until
  the defect is resolved and the task re-verified.
- A batched dispatch inherits this per task: one blocked task does not
  block siblings, and no sibling's completion marks the blocked one.
- The dispatch report MUST list each covered task as COMPLETE or
  OPEN(reason). A batch report with no per-task status is invalid.
</CRITICAL>
