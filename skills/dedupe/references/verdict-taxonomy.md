# Verdict Taxonomy

This file is the **canonical home** for the 5-verdict taxonomy used by the
`dedupe` skill's classifier. Every downstream artifact (SKILL.md, phase
commands, classifier prompt) references this file by path and MUST NOT
restate these definitions inline (per M6 anti-irony, design §16).

The taxonomy classifies an unordered pair of instruction blocks `(block_a,
block_b)` whose contents express the same instruction or have drifted from
a once-shared instruction. Exactly one verdict applies per pair.

`INLINE-MANDATORY` is an **orthogonal flag**, NOT a verdict. See the
INLINE-MANDATORY section at the bottom.

---

## The 5 verdicts

### EXTRACT

EXTRACT — consolidate to a single canonical home.

**Definition.** The two blocks express the same instruction with no
load-bearing positional, contextual, or reinforcement reason to keep both
in place. The instruction has a single intended meaning, and consolidating
into one canonical home in `skills/shared-references/<slug>.md` (with
single-line references at the original sites) loses no signal.

**When to use.** Use EXTRACT when:
- Both blocks could be replaced with a reference to a third file without
  any reader losing information.
- The counterfactual "what would be lost if these were consolidated?"
  answers `nothing` (or `nothing of operational significance`).
- Neither block is INLINE-MANDATORY (see below). An INLINE-MANDATORY block
  is never EXTRACT-eligible regardless of paraphrase strength.

**Example.** Two skills both contain a paragraph explaining the
`branch-context.sh` invocation in identical terms, with no surrounding
context that depends on the paragraph's exact position. Consolidating into
`skills/shared-references/branch-context-invocation.md` loses nothing.
EXTRACT.

---

### KEEP-placement

KEEP-placement — same instruction, locations are load-bearing.

**Definition.** The two blocks express the same instruction, BUT the
specific location of each block is load-bearing — the block orients the
rest of its file, signals a section boundary, or anchors a reader at a
checkpoint where extracting it (and replacing with a reference) would
degrade comprehension.

**When to use.** Use KEEP-placement when:
- Either block functions as a section opener, table-of-contents anchor,
  or "here is what this file is about" header.
- A reader landing on the file mid-task would lose orientation if the
  block were a reference link.
- The counterfactual answers `the file's structural readability is lost`.

**Example.** Both `skills/develop/SKILL.md` and
`skills/debugging/SKILL.md` open with a one-paragraph statement of the
skill's purpose and inputs. The paragraphs are nearly identical in
structure, but each is the load-bearing first paragraph of its own
skill. Extracting would force the operator to follow a reference link
just to learn what the skill does. KEEP-placement.

---

### KEEP-reinforcement

KEEP-reinforcement — intentional repetition for safety / cognitive reinforcement.

**Definition.** The two blocks express the same instruction, and the
repetition is **intentional and load-bearing** — typically because the
instruction is safety-critical and is repeated at multiple checkpoints to
ensure it is encountered no matter which path the reader takes through
the artifact.

**When to use.** Use KEEP-reinforcement when:
- The instruction is safety-, correctness-, or destructive-action-related
  (irreversible operations, data loss, security violations).
- Replacing one instance with a reference would create a path where the
  reader could miss the instruction.
- The counterfactual answers `a reader on path P would not encounter the
  instruction, increasing the chance of the unsafe action`.

**Example.** `CLAUDE.md`'s "Inviolable Rules" section contains "NEVER push
to a protected branch without permission," and the same rule is restated
near the bottom inside the `<FORBIDDEN>` block. The repetition is a
deliberate safety reinforcement because the reader may scan top-down OR
skip to the forbidden-actions block. KEEP-reinforcement.

---

### KEEP-contextual

KEEP-contextual — each instance is parameterized by surrounding context.

**Definition.** The two blocks express what reads as the same instruction,
BUT each instance is parameterized by its surrounding context such that
consolidating into a single canonical statement would lose the
parameterization. The blocks are paraphrases on the surface; in context,
they are different instructions.

**When to use.** Use KEEP-contextual when:
- Each block applies to a different subject (different skill, different
  phase, different tool) and the surrounding prose carries the parameter.
- Extracting to a single canonical home would require the canonical home
  to carry conditional "when in skill X, do A; when in skill Y, do B"
  branching — which defeats consolidation.
- The counterfactual answers `each instance is specialized to its
  surroundings; consolidation would require re-stating the surroundings`.

**Example.** Two skills both say "before dispatching a subagent, prepare
context for it." In `develop`, this means assembling design/research
artifacts; in `debugging`, it means assembling stack traces and repro
steps. Same surface instruction, different operational meaning.
KEEP-contextual.

Also: when fallback / coercion-on-failure logic resolves to this verdict
because the classifier returned off-schema output, the pair lands here
with `off_schema_coerced=true`. The semantic intent of KEEP-contextual
(consolidation would erase context) is the safest default for an
unknowable verdict.

---

### RECONCILE-drifted

RECONCILE-drifted — once-shared instruction has diverged; latent bug.

**Definition.** The two blocks were once the same instruction (their
overlap in topic, structure, and key terms is too high to be
coincidence) but they have **diverged**. They now express different — and
possibly contradictory — instructions. This is a latent bug surfaced by
the dedupe pass.

**When to use.** Use RECONCILE-drifted when:
- The blocks share a clear common ancestor in topic and structure.
- They now disagree in a substantive detail: a numeric threshold, a
  command, a required step, an exception, a policy.
- A reader following one block and a reader following the other would
  take different actions.

**RECONCILE-drifted is NEVER auto-resolved.** The dedupe skill surfaces
the drift in a dedicated report section; the operator chooses which
direction to reconcile (or to leave both, having confirmed both are
correct in their own context). The skill does not select a winning
version.

**Example.** Two skills' "PR description" instructions both say PRs need
a Summary, but one says "include a Test plan section" and the other says
"NEVER include a Test plan section." Same ancestor (PR conventions),
substantive divergence. RECONCILE-drifted.

---

## INLINE-MANDATORY (orthogonal flag)

`INLINE-MANDATORY` is **NOT a verdict**. It is an orthogonal per-block
flag with the predicate:

> This block MUST remain on the always-loaded path. It may not be
> extracted into a referenced file, regardless of paraphrase strength
> with any other block.

INLINE-MANDATORY is set by **two cumulative sources**:

1. **The mechanical safety-marker floor** (see
   `safety-markers.md`). The orchestrator applies the regex table to
   every block during Phase 1 (setup); matching blocks are force-marked
   `inline_mandatory_mechanical=true` BEFORE classifier dispatch.
2. **The LLM classifier's safety screen** (see `counterfactual-prompt.md`).
   The per-pair classifier may additionally set `inline_mandatory=true`
   on its returned verdict if the prose itself indicates safety-critical
   status.

**Critical invariant.** The LLM screen may **only ADD** INLINE-MANDATORY
status to a block. It may **never SUBTRACT** the status that the
mechanical floor has assigned. The orchestrator enforces this at verdict
collection time: if `inline_mandatory_mechanical=true` and the classifier
returned `inline_mandatory=false`, the orchestrator overrides to `true`
and records `mechanical_override=true` in the finding row.

**Interaction with verdicts.** A pair where either block is
INLINE-MANDATORY is **never** EXTRACT-eligible. The classifier dispatch
for such a pair is short-circuited: verdict = `KEEP-contextual`,
`inline_mandatory=true`, source = `mechanical_floor`. No classifier
subagent is invoked.

---

## Cross-references

- The consolidation-counterfactual prompt that elicits these verdicts:
  `counterfactual-prompt.md`.
- The regex table that drives the mechanical INLINE-MANDATORY floor:
  `safety-markers.md`.
- The block segmentation protocol that determines what constitutes a
  block (and therefore a pair): `segmentation-protocol.md`.
