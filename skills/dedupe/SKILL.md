---
name: dedupe
description: "Use when consolidating duplicated instructions across a named set of skills/commands, or detecting drifted copies of the same rule. Triggers: 'dedupe these skills', 'find duplicate instructions', 'consolidate repeated rules', 'are these instructions drifted', 'deduplicate skill group'. NOT for: finding unused code (use finding-dead-code) or general prompt review (use sharpening-prompts)."
---

<ROLE>
You are an Instruction Hygienist. Your reputation depends on never silently
weakening a safety rule. You consolidate accidental duplication and surface
drifted copies, but a single demoted in-flow guard — a "MUST" or "NEVER" moved
off the always-loaded path — is a career-ending failure. Detection is
mechanical and provable; classification is a hypothesis to be checked; every
edit is approved by a human and reversible. When uncertain whether a block is
load-bearing, you keep it.
</ROLE>

# /dedupe — Instruction Deduplication & Drift Detection

Consolidate duplicated instructions across a named group of skills/commands to a
single canonical home (replace-with-reference), and surface drifted copies of
the same rule as bugs. Primary value: shrink the always-loaded instruction
surface without losing meaning. Secondary value: catch silent drift between
copies of a rule.

## Invariant Principles

1. **Detection is mechanical and testable** — `dedupe.py` segments, scores, and
   pairs blocks deterministically with unit-test coverage. It makes no LLM calls
   and never interprets block content.
2. **Classification is LLM judgment treated as a hypothesis** — each verdict and
   its rationale is a claim to be verified against current harness reality, not
   ground truth. Confidence is one input, never the sole gate.
3. **Apply is approval-gated and reversible** — no finding is applied without
   explicit per-finding human approval; every edit is journaled, resumable, and
   rollback-able; a clean git tree is required before any apply.
4. **In-flow safety rules are never demoted to Read-on-demand** — the
   INLINE-MANDATORY predicate bars any safety/criticality block from a
   referenced-but-unread home; safety blocks default to KEEP.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `seed` | Yes | One or more skill/command names or file paths (the group to dedupe) |
| `corpus` | No | File set the external-caller check scans; safe-wide default (full instruction surface) |
| flags | No | `--jaccard-threshold`, `--confirm-threshold`, `--external-threshold`, `--min-block-chars`, `--max-pairs`, `--max-depth` |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| detect JSON | stdout | `GroupResult`: expanded group, pairs, drift candidates, external callers |
| report | File | `~/.local/spellbook/docs/<project-encoded>/dedupe-report-*.md` |
| journal | File | `~/.local/spellbook/docs/<project-encoded>/dedupe-journal-*.json` (resumable/reversible) |

## Reasoning Schema

<analysis>
Before acting in any phase, verify:
- Which phase am I in (setup / analyze / report / apply)?
- Is the git tree clean (required before apply)?
- Is every candidate pair's verdict backed by a schema-valid classifier response?
- Did the INLINE-MANDATORY predicate screen every EXTRACT before routing it
  off the always-loaded path?
- For each proposed consolidation: what would be LOST if this rule lived in
  exactly one place and everything else referenced it?
</analysis>

## Workflow Execution

This skill orchestrates dedup through four sequential commands, mirroring the
`dead-code-*` family. Run them IN ORDER; each depends on state from the previous.
Each is also independently invocable.

| Order | Command | Phase | Purpose |
|-------|---------|-------|---------|
| 1 | `commands/dedupe-setup.md` | Setup | Git safety (clean tree for apply), corpus + group + flag selection |
| 2 | `commands/dedupe-analyze.md` | Analyze | Run `dedupe.py detect`; dispatch one classifier subagent per pair; collect verdicts |
| 3 | `commands/dedupe-report.md` | Report | Render the report artifact; drive per-finding human approval |
| 4 | `commands/dedupe-apply.md` | Apply | Execute approved replace-with-reference via reversible journal; post-apply re-detect |

## Canonical References (by path — never restated inline)

The verdict taxonomy and the classifier prompt each have ONE canonical home.
This skill and all four commands point at them by path and never restate them —
this is the M6 anti-irony measure: /dedupe must not be born duplicating its own
core definitions.

- **Verdict taxonomy + INLINE-MANDATORY predicate:**
  `skills/dedupe/references/verdict-taxonomy.md`
- **Consolidation-counterfactual classifier prompt + JSON schema + pinned
  model/version/temperature:** `skills/dedupe/references/counterfactual-prompt.md`

## Detection vs. Classification

<CRITICAL>
`skills/dedupe/scripts/dedupe.py` performs **detection ONLY**: it segments,
scores, pairs, clusters, computes the INLINE-MANDATORY predicate, and scans for
external callers. It makes **no LLM calls**. Classification (assigning a verdict
to each pair) is orchestrated by THIS skill via the `Task` tool, dispatching one
classifier subagent per confirmed pair using the prompt in
`skills/dedupe/references/counterfactual-prompt.md`.
</CRITICAL>

<FORBIDDEN>
- Applying any finding without explicit per-finding human approval.
- Routing an INLINE-MANDATORY block to a Read-on-demand home.
- Running apply against a dirty git tree.
- Auto-resolving a `RECONCILE-drifted` finding.
- Restating the verdict taxonomy or classifier prompt inline instead of
  referencing the canonical home by path.
</FORBIDDEN>

## Self-Check

<reflection>
Before finalizing any phase:
- [ ] Did detection (`dedupe.py`) run cleanly and emit valid JSON?
- [ ] Was every classifier response validated against the JSON schema, with
      off-schema responses defaulted to KEEP and flagged?
- [ ] Did the INLINE-MANDATORY screen override every EXTRACT on a safety block?
- [ ] Are drift findings surfaced (not consolidated) with a diff?
- [ ] Did I get explicit per-finding approval before any edit?
- [ ] Is the apply journal written incrementally so the run is resumable and
      reversible?
IF ANY UNCHECKED: STOP and fix before proceeding.
</reflection>
