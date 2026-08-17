# Develop Skill Discipline

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.develop-discipline`.

Phase non-fungibility inside the develop skill, and the thoroughness contract that invoking develop establishes.

**Why keep it:** Stops the develop skill from collapsing its own phases into a single dispatch.

**If you decline:** The agent may combine develop phases into one dispatch and may compress phases when it judges the work small or the session short.

**Related artifacts:**

- `skills/develop`
- `commands/feature-design`
- `commands/feature-implement`
- `commands/feature-implement-execute`

## Rule Content

```markdown
<CRITICAL>
### Develop Skill Phase Non-Fungibility

Inside /develop or any of its sub-skills (feature-config, feature-research,
feature-discover, feature-design, feature-implement, feature-implement-execute),
every Task() dispatch executes EXACTLY ONE row of the dispatch table at
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

Every item in that list is a phase-collapse rationalization. Recognizing one is
the signal to stop, not a sign the situation is exceptional. The dispatch table
has no exception column.

The ceremony is selectable at Phase 0, so the dispatch table alone is not a
sufficient referent. Every Phase Declaration must ALSO cite the exact gate line
it satisfies, copied VERBATIM from `develop_gate_ledger.ceremony` (`selected` or
`core`). A cited line that appears in neither is an invalid dispatch. A line in
`ceremony.declined` may be run only after promotion to `selected` with a
recorded reason. Nothing ever moves the other way.

A Phase Declaration block must precede each Task() dispatch inside /develop (see
`$SPELLBOOK_DIR/skills/develop/SKILL.md` "Pre-Dispatch Ritual"). It makes phase
collapse mechanically detectable in real time. A dispatch without one is a
process failure even if the work product is correct.

### Develop = Thoroughness Mode (Operator Contract)

If the `core-philosophy` module is installed, its "steady correctness over speed"
rule is the general form of this contract.

Invoking develop is the operator's explicit opt-in to thoroughness, and a
durable instruction: correctness outranks speed for the duration of the work. An
operator who wants speed will say so and will not invoke develop. The presence
of develop in the active skill list IS the contract.

**Thoroughness is CHOSEN ONCE, then FIXED.** The ceremony is selectable in a
single window, and never afterward.

- **Elision vs repositioning.** ELISION is running FEWER gates than the locked
  ceremony selected. It is forbidden, always. REPOSITIONING is running EVERY
  selected gate at a declared boundary recorded in the ledger — a Phase-0 choice
  (`gate_position: per_task | per_group`), locked at `locked_at` with everything
  else. Changing gate position after the lock requires the same
  ABORT-and-re-invoke path as any other ceremony change.
- **The selection window is Phase 0, before any work begins.** develop assesses
  the request across its cost dimensions and RECOMMENDS a ceremony. The
  operator's answer is the SOURCE OF TRUTH and overrides the recommendation. It
  is written to `develop_gate_ledger.ceremony` and LOCKED (`locked_at`). This is
  the only moment ceremony is negotiable.
- **A non-negotiable core is never on the menu.** If the develop skill is
  installed, its review floor defines that core: code review, green-mirage
  auditing, the test run when tests cover the touched code, and TDD-first for
  anything carrying behavioral logic. If a rule or command establishing the Iron
  Law is present (no skill written or edited without a failing test first), the
  Iron Law belongs to that core too. Gates implied by high verification
  difficulty or high silent-failure potential are locked on and cannot be
  deselected.
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
  wave records carry forward, and `locked_at` is set fresh. The escape hatch
  must stay affordable: if the honest path costs a full restart, quiet erosion
  becomes the cheap path. This does not loosen the lock: the non-negotiable core
  applies at EVERY selection, the D5/D6 escalation-only locks re-derive from the
  unchanged assessment, and `ceremony_history` makes serial de-escalation
  auditable. Re-invoking ritually to shed gates is itself a phase-collapse
  rationalization, already covered by the forbidden-rationalizations list in
  this module.
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
  dispatch with the SAME ceremony still in force. The skill treats that as a
  parallelism change only; the locked `ceremony.selected` is unchanged.

They answer different questions. Parallelism is "how much work in flight at
once?"; ceremony is "what verification must each piece of work pass?"
Re-deriving ceremony from a parallelism preference would let time pressure erode
the review floor, which is what the lock prevents. The skill reads the two
fields independently and never conflates them.

### Wave Discipline (the §24.6 check)

If the plan organizes tasks into waves (`Wave N:` headers or `W<n>-` row
identifiers in the plan file), develop records a §24.6 wave-discipline check for
each wave before any "Wave X done" claim may be written. Three statuses:

- `passed` -- every row in the wave is closed. The `Wave X done` claim may be
  written.
- `failed` -- at least one row in the wave is still open. The open-row
  identifiers are recorded; the `Wave X done` claim is REFUSED until the rows
  are closed and the check is re-run.
- `n_a` -- the plan has no wave structure (flat task list). Recorded so the
  absence of the check is itself visible at review.

`scripts/develop_gate_ledger.py` implements the check and is the only path that
may write the entry. Hand-writing the JSON is a full overwrite that clobbers
sibling fields written by other develop writes. The module refuses
`status=failed` without an `open_rows` list, so a false pass cannot be written by
accident. Refusing a wave-done claim is the only enforcement; without it, the
claim becomes silently broken work the next phase inherits. See the
nmg2-emulator handoff (2026-08-10): "Wave 3a done" markings made without §24.6
verification propagated across handoffs because no subsequent step re-checked.

### Stop Semantics in Batched Dispatches

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

### Incidentals: Mid-Implementation Departures Must Be Integrated, Not Improvised

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
```
