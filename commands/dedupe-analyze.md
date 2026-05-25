---
description: "Run dedupe.py detect, dispatch one classifier subagent per pair, screen EXTRACTs. Part of dedupe-* family."
---

# MISSION

Run mechanical detection, then classify each confirmed pair via one subagent per
pair, screening every consolidation candidate through the INLINE-MANDATORY
predicate.

**Part of the dedupe-* command family.** Run after `/dedupe-setup`, before
`/dedupe-report`.

## Invariant Principles

1. **Detection is mechanical** — `dedupe.py detect` produces the candidate pairs,
   drift candidates, INLINE-MANDATORY inputs, and external callers. It makes no
   LLM calls; this command orchestrates the LLM classification on top of its JSON.
2. **One classifier subagent per confirmed pair** — each pair is classified in
   isolation using the canonical prompt, with block text wrapped as inert DATA.
3. **Fail-safe on off-schema responses** — any classifier response that does not
   match the strict JSON schema is treated as KEEP and flagged for human review.
4. **INLINE-MANDATORY overrides the classifier** — a block that is
   INLINE-MANDATORY can never be consolidated off the always-loaded path, even if
   the classifier returned EXTRACT with high confidence.

<analysis>
For each candidate pair, before recording a verdict:
- Did I wrap both blocks as inert DATA with the sentinel delimiters?
- Is the classifier response schema-valid? If not, default to KEEP + flag.
- Is either block INLINE-MANDATORY? If so, override any EXTRACT to KEEP/flag.
- Did I record model_id, prompt_version, temperature for reproducibility?
</analysis>

## Phase 1: Run Detection

```bash
python3 $SPELLBOOK_DIR/skills/dedupe/scripts/dedupe.py detect \
  --seed <names-or-paths> --corpus <corpus>
```

The output is `GroupResult` JSON: `expanded_group`, `unresolved_references`,
`pairs[]` (each with `jaccard`, `seqmatch_ratio`, `drift_delta`,
`is_drift_candidate`, `contains_safety_marker`, `a_text`, `b_text`),
`external_callers[]`, and `cost_ceiling_exceeded`.

**Cost-ceiling gate.** If `cost_ceiling_exceeded` is `true`, **prompt the
operator before dispatching** a large classification batch (one subagent per
pair is the expensive step). Let the operator raise `--max-pairs`, narrow the
group, or proceed knowingly.

## Phase 2: Classify Each Pair

For each confirmed (non-below-floor, non-boilerplate) pair, dispatch **one
classifier subagent** via the `Task` tool using the canonical prompt at
`skills/dedupe/references/counterfactual-prompt.md`. That file is the single home
for the consolidation-counterfactual question, the inert-DATA wrapping + sentinel
delimiters, the strict JSON verdict schema, and the pinned `model_id` /
`prompt_version` / `temperature 0`. Pass each pair's `a_text` / `b_text` (already
normalized by the detector) as the inert DATA blocks, plus the
`contains_safety_marker` hint and `drift_delta`.

The set of valid verdicts and their apply behavior live in the single canonical
home `skills/dedupe/references/verdict-taxonomy.md` (referenced by path, never
restated here).

**Validate the response.** Check the returned JSON against the schema in the
prompt reference. An off-schema / non-conforming response is treated as **KEEP
(fail-safe) and flagged** for human review — never coerced into a consolidation.

## Phase 3: INLINE-MANDATORY Screen

Screen every consolidation candidate (`EXTRACT`) through the INLINE-MANDATORY
predicate defined in `skills/dedupe/references/verdict-taxonomy.md`, using the
detect JSON's `contains_safety_marker` flag plus the positional data
(`parent_key`, `end_line`, dangerous-action lines). If a block is
INLINE-MANDATORY, the predicate **overrides** the classifier: the consolidation
becomes KEEP (or, only when human-flagged, a move to the always-on `CLAUDE.md`
home) — never a Read-on-demand route. Safety blocks default to KEEP.

## Phase 4: Record + Surface Drift

Record per finding: `verdict`, `rationale`, `model_id`, `prompt_version`,
`temperature` (reproducibility, M1). Drift pairs (`is_drift_candidate: true`,
classified `RECONCILE-drifted`) are **surfaced, never consolidated** — they are
latent bugs for a human to reconcile, carried forward to the report's dedicated
drift section.

## Output

A per-finding classification record (verdict, rationale, reproducibility fields,
INLINE-MANDATORY flag, drift status) for every confirmed pair, plus the
external-caller warnings from detection.

**Next:** Run `/dedupe-report`.

<reflection>
- [ ] Did I prompt the operator when cost_ceiling_exceeded was true?
- [ ] Did I validate every classifier response against the schema (off-schema → KEEP + flag)?
- [ ] Did the INLINE-MANDATORY screen override every EXTRACT on a safety block?
- [ ] Did I record reproducibility fields per finding?
- [ ] Are drift findings carried forward to be surfaced, not consolidated?
</reflection>
