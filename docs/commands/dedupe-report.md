# /dedupe-report
## Command Content

``````````markdown
# MISSION

Render a human-readable, actionable dedup report and obtain explicit per-finding
approval before anything is applied.

**Part of the dedupe-* command family.** Run after `/dedupe-analyze`, before
`/dedupe-apply`.

## Invariant Principles

1. **Report to the user dir, never the project dir** — the report is written
   under `~/.local/spellbook/docs/<project-encoded>/`, never into the repository.
2. **Every finding is fully evidenced** — locations, scores, verdict, rationale,
   reproducibility record, INLINE-MANDATORY flag, routing home, external-caller
   warnings, and a labeled token estimate.
3. **Zero auto-edit** — no finding is applied without an explicit per-finding
   approval token from the operator.
4. **Drift is prominent** — drifted copies are surfaced in a dedicated section
   with a diff, never folded silently into the consolidation list.

<analysis>
Before writing the report, confirm:
- The report path is under ~/.local, not the project dir.
- Each finding carries its scores, verdict, rationale, and reproducibility record.
- INLINE-MANDATORY findings show the flag and a routing home that is NOT
  Read-on-demand.
- The token estimate is labeled an estimate and only shown for off-always-loaded
  moves.
- Drift findings are sectioned separately with a diff.
</analysis>

## Phase 1: Write the Report

Write the report to:

```
~/.local/spellbook/docs/<project-encoded>/dedupe-report-YYYY-MM-DD-HHMM.md
```

<RULE>NEVER write the report into the project directory (design §5.1).</RULE>

### Per-finding render

For each finding, show:

- Both block locations (`file:line`) and granularity.
- Scores: `jaccard`, `seqmatch_ratio`, `drift_delta`.
- Verdict + rationale + reproducibility record (`model_id`, `prompt_version`,
  `temperature`). The verdict's meaning and apply behavior are defined in
  `skills/dedupe/references/verdict-taxonomy.md` (referenced by path, never
  restated here). Present the rationale as a **hypothesis to be checked**, not a
  fact.
- The INLINE-MANDATORY flag (from the predicate in the taxonomy reference).
- The proposed canonical **routing home** (see the routing table below).
- External-caller warnings (design §5.4): any out-of-group block similar to the
  candidate, so the operator understands the blast radius.
- For consolidation candidates only: the **token-removed estimate** —
  `chars_removed / 4`, explicitly labeled "estimate (chars/4 heuristic), not a
  tokenizer count", shown **only** for blocks whose canonical home moves OFF the
  always-loaded path, reported against the pre-apply baseline. A move between two
  Read-on-demand homes contributes 0.

### Routing-home table (design §5.5)

| Home | When | Auto-applicable? |
|------|------|------------------|
| `skills/shared-references/<topic>.md` (Read-on-demand) | **Preferred** for non-in-flow reference content shared across the group | Yes (with approval) |
| Per-skill `references/<topic>.md` (Read-on-demand) | Reference material specific to one skill family | Yes (with approval) |
| Callable shared skill | Procedural blocks better invoked than read | Yes (with approval), if not INLINE-MANDATORY |
| `CLAUDE.md` (always-on) | ONLY for INLINE-MANDATORY content needing an always-on home | **Human-flagged ONLY, never auto** |

INLINE-MANDATORY blocks are barred from the three Read-on-demand homes.

### Drift section

Drifted findings appear in a **dedicated, prominent section** even when there are
no consolidation candidates. For each, render the `difflib.unified_diff` of the
two normalized blocks so the human can see exactly what diverged. Drift is never
auto-resolved.

## Phase 2: Per-Finding Approval

<RULE>Present findings and require EXPLICIT per-finding approval via
AskUserQuestion before anything is applied. No finding is applied without an
explicit approval token. This is the zero-auto-edit guarantee.</RULE>

Offer per-finding approve / skip, or a batch-approve-with-review affordance.
Carry the approval tokens forward to apply.

## Output

The report artifact path plus the set of approved findings.

**Next:** Run `/dedupe-apply`.

<reflection>
- [ ] Is the report under ~/.local (not the project dir)?
- [ ] Does every finding carry scores, verdict, rationale, reproducibility,
      INLINE-MANDATORY flag, routing home, external-caller warnings?
- [ ] Is the token figure labeled an estimate and only shown for off-always-loaded moves?
- [ ] Are drift findings in their own section with a diff?
- [ ] Did I obtain explicit per-finding approval (zero auto-edit)?
</reflection>
``````````
