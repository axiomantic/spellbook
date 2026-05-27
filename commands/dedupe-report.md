---
name: dedupe-report
description: "Phase 3 of the dedupe skill family. Aggregates verdicts into a human-readable report and drives per-finding disposition approval. Read-only; no file mutations."
---

# MISSION

Phase 3 of the `dedupe` skill: consume the verdicts artifact produced by
`/dedupe-analyze`, render a human-readable markdown report, and drive
per-finding disposition approval via `AskUserQuestion`.

This command is **read-only** with respect to the source markdown
tree. The only file it writes is the report artifact itself. It NEVER
edits skill or command files. It NEVER auto-chains to `/dedupe-apply`.

**Part of the dedupe-* command family.** Run after `/dedupe-analyze`.
Run before `/dedupe-apply`.

## Invariant Principles

1. **Read-only with respect to source files** — this phase produces a
   report; the apply phase produces edits. They are separate, gated by
   explicit operator invocation.
2. **No auto-chain to apply** — `/dedupe-apply` is invoked explicitly by
   the operator after they review the report. This command never
   triggers it.
3. **Per-finding disposition is gated** — EXTRACT candidates each receive
   one `AskUserQuestion` prompt. There is no "apply all" affordance at
   this phase.
4. **Drift is surfaced, never auto-resolved** — RECONCILE-drifted
   findings appear in their own section with no apply option.

**No-auto-chain invariant:** This command never auto-chains to
`/dedupe-apply`. The operator explicitly invokes apply only after
reviewing the report and its recorded dispositions. Auto-chaining
would bypass the report-review gate that exists for safety.

---

## Invocation

```
/dedupe-report <verdicts-path>
```

- `<verdicts-path>` — the artifact produced by `/dedupe-analyze`. Required.

---

## Inputs

- The verdicts artifact at `<verdicts-path>`. Read it to recover the
  per-pair findings, the reproducibility footnote, and the resolved
  seed paths.

If the verdicts artifact records `analyze_halted=true`, this command
renders only the halt summary section and exits. No EXTRACT candidates
are surfaced; the operator must rerun `/dedupe-analyze` after
addressing the halt cause.

---

## Phase 3.1 — Aggregate verdicts

Parse the verdicts artifact and group findings by verdict family:

- **EXTRACT candidates** — every pair with the EXTRACT verdict; surfaced
  individually for disposition.
- **KEEP findings** — every pair with a KEEP-flavored verdict; collapsed
  into a single table.
- **Drift candidates** — every pair with the RECONCILE-drifted verdict;
  surfaced individually without an apply option.

Verdict names and definitions are authoritative in
`skills/dedupe/references/verdict-taxonomy.md`. This command groups by
verdict identifier; it does not restate the definitions.

For each EXTRACT candidate, also derive:

- a proposed canonical home path under
  `skills/shared-references/<slug>.md`. The slug is lowercased and
  dash-separated from the heading chain of block A, truncated at 60
  chars, with collision-disambiguating `-N` suffix if a file at that
  path already exists (`test -e` via the harness Bash tool).
- a reference-plumbing snippet that the apply phase will substitute
  into the source file in place of the original block:

  ```
  See [<slug>](../shared-references/<slug>.md).
  ```

---

## Phase 3.2 — Render the report

Compute the report artifact path:

```
~/.local/spellbook/docs/<project-encoded>/dedupe-report-YYYY-MM-DD-<seed-slug>.md
```

The project-encoded prefix and seed slug are inherited from the
verdicts artifact header. `YYYY-MM-DD` is today's date in UTC, obtained
via `date -u +%Y-%m-%d`. Create the parent directory with `mkdir -p`
if it does not exist.

The report contains the following sections, in order:

### Header

- Verdicts source path.
- Resolved seed paths (echoed).
- Run timestamp (ISO 8601 UTC).
- Pair count and verdict distribution (count per verdict).
- Reproducibility footnote: `model_id`, `prompt_version`, `temperature`
  (echoed from the verdicts header).

### Section 1 — EXTRACT candidates

For each EXTRACT candidate, one subsection of the form:

```
### EXTRACT-<finding_id_pair>

- Block A: <file>:<heading_chain> (finding_id <fid_a>)
- Block B: <file>:<heading_chain> (finding_id <fid_b>)
- Confidence: <high|medium|low>
- Rationale: <prose echoed from verdict>
- Counterfactual loss: <prose echoed from verdict>
- Proposed canonical home: skills/shared-references/<slug>.md
- Reference plumbing: See [<slug>](../shared-references/<slug>.md).
- Disposition: <set by AskUserQuestion below>
```

### Section 2 — KEEP findings (collapsed)

A single markdown table aggregating every KEEP-flavored finding. Columns:

| `pair_id` | `verdict_kind` | `inline_mandatory` | `confidence` | `block_a` | `block_b` | `source` |

`source` is `classifier` or `mechanical_floor`.

The verdict identifier in the `verdict_kind` column is a name token used
as an identifier; the per-verdict definitions live in the canonical
home (`skills/dedupe/references/verdict-taxonomy.md`).

### Section 3 — Drift candidates

For each RECONCILE-drifted finding, one subsection mirroring Section 1
in shape, but with NO "Proposed canonical home" and NO "Reference
plumbing" and NO "Disposition" line. Drift is surfaced for human
reconciliation only.

### Section 4 — Halt / failure summary

Present only if the verdicts artifact recorded `analyze_halted=true`.
Echoes the halt cause, the halt stage, and (for off-schema halts) the
rolling rate trajectory.

---

## Phase 3.3 — Per-finding disposition gate

After the report is written to disk, walk the EXTRACT candidates in
order. For each EXTRACT candidate, drive `AskUserQuestion` with the
following options:

| Option | Effect on disposition field |
|---|---|
| `apply` | Record `Disposition: apply` in the report subsection. The apply phase will surface this finding for the final pre-edit checkpoint. |
| `skip-this` | Record `Disposition: skip-this`. The apply phase will skip this finding silently. |
| `defer-to-drift` | Record `Disposition: defer-to-drift`. The finding is reclassified as drift in the report (moved to the drift section) and is not applied. |
| `mark-keep` | Record `Disposition: mark-keep`. The finding is reclassified as a KEEP outcome in the report (moved to the KEEP table) and is not applied. |

After each prompt, update the report artifact in place so the
disposition is persisted before moving to the next candidate. This
makes the workflow resumable: if the operator interrupts, the dispositions
recorded so far are durable.

There is no "apply all" affordance at this phase. Bulk approval is
intentionally absent. If the operator wants to defer most of the work,
they should narrow the cost ceiling during `/dedupe-analyze` (Stage 5)
rather than rubber-stamping at this phase.

---

## Output

This command produces exactly one artifact:

```
~/.local/spellbook/docs/<project-encoded>/dedupe-report-YYYY-MM-DD-<seed-slug>.md
```

with every EXTRACT candidate's `Disposition` line populated.

**Next:** Operator reviews the report. When ready, runs
`/dedupe-apply <report-path>`. This command does NOT auto-chain.

---

## References

- Verdict catalog and INLINE-MANDATORY predicate semantics:
  `skills/dedupe/references/verdict-taxonomy.md`.
- Per-pair finding fields, reproducibility footnote, and halt-summary
  shape are inherited from the verdicts artifact produced by
  `/dedupe-analyze`, which is documented in `commands/dedupe-analyze.md`
  and grounded in
  `skills/dedupe/references/counterfactual-prompt.md`.
