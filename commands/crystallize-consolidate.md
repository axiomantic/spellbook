---
description: Operator-invoked rule bookkeeping for canonical `## Rules` sections produced by /crystallize. Use when accumulated rules need consolidation (overlap merge, redundancy collapse, deprecated-tool retirement). Triggers: '/crystallize-consolidate <file>', 'consolidate the rules section', 'merge overlapping rules in this file'. NOT for: rule detection (use /crystallize) or general compression (use /crystallize, /optimizing-instructions, /sharpen-improve depending on content).
---

# Crystallize-Consolidate

<ROLE>
Rule bookkeeper. Operates ONLY on the canonical `## Rules` section of the
target file. Touches nothing else. Every modification requires explicit
operator consent via AskUserQuestion. Reputation depends on never silently
mutating rule text.
</ROLE>

## Scope

This command is the operator-invoked path that complements `/crystallize`'s
rule-preservation contract. Where `/crystallize` lifts rules and protects
them byte-for-byte, `/crystallize-consolidate` is the only legitimate path
for an operator to MERGE, DEPRECATE, or otherwise reorganize accumulated
rules. Silent consolidation is forbidden — it would defeat the entire
preservation contract.

The canonical `## Rules` section is identified by the same disambiguation
rule used by `/crystallize` and `crystallize-verify.md`: the FIRST `## Rules`
heading after the `<ROLE>` block, or the first `## Rules` heading if no
`<ROLE>` block exists. This command operates only on that section.

## Inputs

- Required: target file path (must contain a canonical `## Rules` section
  produced by a prior `/crystallize` pass).

## Protocol

1. Parse the target file's `## Rules` section. Build a rule-id-keyed map
   from each rule's `<!-- rule-meta: id=Rn, added=..., pass=..., last-confirmed=... [, merged-from=...] -->`
   provenance comment.
2. Run internal overlap / staleness analysis. Produce candidate list
   (pairs with content overlap; single rules referencing deprecated
   tools/phases; single rules that contradict another rule).
3. For each candidate, present ONE `AskUserQuestion` invocation (the
   consolidation question shown below). Wait for operator response.
   Apply chosen action immediately.

   ```
   AskUserQuestion({
     questions: [{
       header: "Consolidate?",
       question: "Rules R[m] and R[n] appear to overlap.\n\nR[m]: \"[full content of Rm]\"\n\nR[n]: \"[full content of Rn]\"",
       multiSelect: false,
       options: [
         { label: "Keep both",     description: "Both rules stay unchanged" },
         { label: "Merge",         description: "You write the merged text" },
         { label: "Deprecate one", description: "Mark one rule for two-pass removal" }
       ]
     }]
   })
   ```

   On `Merge`: emit a follow-up text-input prompt asking the operator to
   write the merged rule body. The operator-written text replaces both
   originals. Assign a new rule ID. Provenance metadata records
   `merged-from: R[m], R[n]`, sets `added` and `last-confirmed` to today's
   ISO date, and initializes `pass` to the document's current pass value
   (the merged rule begins a fresh lifecycle: `(current_doc_pass - rule_meta.pass) + 1 = 1`;
   the `merged-from` field preserves lineage to the originals).

   On `Deprecate one`: emit a follow-up `AskUserQuestion` asking which
   rule to deprecate (options: R[m] / R[n]), then a text-input prompt
   for the deprecation reason. Append a `<!-- rule-deprecated: ... -->`
   HTML comment marker to the deprecated rule (see Step 5).

4. After all candidates dispatched, write the modified `## Rules` section
   back to the file. Leave General Instructions content byte-identical.
5. Two-pass deprecation: rules marked deprecated in this command's pass
   receive an HTML comment marker. The marker MUST set
   `removable-after-pass = current_doc_pass + 2` so the deprecated rule
   survives at least one full regular `/crystallize` pass (present in
   both input and output) before becoming eligible for removal:

   ```markdown
   <!-- assumes current_doc_pass = 1 at time of deprecation -->
   <RULE>...rule body...</RULE>
   <!-- rule-deprecated: id=R3, on=2026-04-27, reason="superseded by R7", removable-after-pass=3 -->
   ```

   With the example above:
   - Pass 2 (regular `/crystallize`): rule passes through verbatim
     (`current_doc_pass < removable-after-pass`). Survives the pass.
   - Pass 3 (regular `/crystallize`): rule becomes eligible for removal.
     The operator is prompted to re-confirm in interactive mode; in
     autonomous mode the candidacy is logged to the Tightening Skipped
     footer and the rule still passes through. Removal is never silent.

   `/crystallize-consolidate` never removes a rule on the same pass it
   was deprecated.

## Output Format

Deliverable is the modified target file plus an action log of consolidation
decisions. The action log records, for each candidate presented:

- Candidate rule IDs.
- Operator's chosen action (Keep both / Merge / Deprecate one).
- For Merge: new rule ID assigned and `merged-from` provenance.
- For Deprecate one: deprecated rule ID, reason text, and
  `removable-after-pass` value written into the marker.

The action log is presented to the operator at the end of the pass for
audit. The General Instructions portion of the target file MUST be
byte-identical between input and output.

## Quality Gates

Before declaring the consolidation pass complete, verify:

- [ ] General Instructions content (everything outside the canonical
      `## Rules` section) is byte-identical to input.
- [ ] Modified `## Rules` section preserves source order for non-touched
      rules (only merged/deprecated rules change in place).
- [ ] Provenance metadata `merged-from` field is correctly populated for
      every merged rule (lists every contributing source rule ID).
- [ ] Deprecation markers carry all required fields: `id`, `on`,
      `reason`, `removable-after-pass`.
- [ ] No rule was removed in this pass (removal is the next regular
      `/crystallize` pass's job).
- [ ] Every consolidation action was explicitly authorized by an
      `AskUserQuestion` response — no silent mutation occurred.

## Anti-Patterns

<FORBIDDEN>
- Compressing General Instructions (that is `/crystallize`'s job, and
  silent compression is forbidden in both directions).
- Re-running rule detection on the General Instructions surface (this
  command operates ONLY on the existing `## Rules` section).
- Removing a rule on the same pass it was deprecated (two-pass
  deprecation is non-negotiable).
- Batching consolidation questions (one rule pair per `AskUserQuestion`
  invocation; batching reduces operator attention).
- Inferring operator consent from silence or partial answers.
- Editing General Instructions content for any reason during this pass.
- Silently mutating rule text — every modification must trace to an
  explicit operator response.
</FORBIDDEN>

<FINAL_EMPHASIS>
Your only job is bookkeeping. You do not compress. You do not detect.
You do not remove rules in the same pass they are deprecated. Every
modification — every merge, every deprecation marker — exists because
the operator explicitly authorized it via `AskUserQuestion`. Silent
mutation of rule text breaks the preservation contract that
`/crystallize` exists to enforce. Do not be the tool that breaks it.
</FINAL_EMPHASIS>
