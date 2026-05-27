---
name: dedupe
description: "Use when consolidating overlapping instruction files, auditing skills for duplicated guidance, or pruning paraphrased prose across a markdown corpus. Triggers: 'dedupe these skills', 'dedupe these instructions', 'find duplicate instructions', 'consolidate instruction files', 'find paraphrased prose', 'collapse redundant skills', 'are these saying the same thing'."
intro: |
  Semantic deduplication of instructional markdown via LLM-judgment, not lexical similarity. Treats every prose block as load-bearing until a counterfactual consolidation test proves otherwise, and emits one of five verdicts (EXTRACT, KEEP-placement, KEEP-reinforcement, KEEP-contextual, RECONCILE-drifted) per candidate pair. Reference content lives in `references/`; this file orchestrates phases only.
---

## Purpose

The `dedupe` skill identifies and reconciles semantically duplicated prose across a corpus of instructional markdown files (skills, commands, AGENTS.md, design notes). It produces a per-pair verdict drawn from a fixed five-element taxonomy — EXTRACT, KEEP-placement, KEEP-reinforcement, KEEP-contextual, RECONCILE-drifted — and an applyable consolidation plan. The skill does not use lexical or embedding similarity as a primary signal; the authoritative judgment is a counterfactual LLM classification of whether one block can be deleted without information loss.

The five verdict names appear above for orchestration; their full definitions, semantics, and INLINE-MANDATORY interaction live in `references/verdict-taxonomy.md`.

<analysis>
Before invoking any phase, the orchestrator confirms:
- Which phase is active (setup / analyze / report / apply) and whether its prerequisite artifact exists.
- For analyze and later: every block has a `finding_id` and a bucket key from the Phase 1 manifest.
- For apply: the git working tree is clean and the operator has approved the report.
- For every prose surface produced (SKILL.md, phase commands, reports): no restatement of reference content (M6 anti-irony).
</analysis>

## Invariant principles

1. **Analyze is an LLM judgment loop, not lexical similarity.** Candidate narrowing (heading-bucket plus optional LLM-triage cross-bucket) is a recall filter, not the verdict. Every surviving pair is judged by a per-pair counterfactual classifier dispatch. See `references/counterfactual-prompt.md`.

2. **Mechanical safety-marker predicate runs before the LLM safety screen.** A regex-based predicate force-marks blocks containing INLINE-MANDATORY safety markers, short-circuiting the classifier to KEEP-contextual with `inline_mandatory=true`. The pattern table is the canonical source in `references/safety-markers.md`; the orchestrator applies those patterns inline via harness Grep/Read, never via a compiled engine.

3. **Structural-template heading allowlist short-circuits intra-bucket pairs.** Pairs whose `bucket_key` matches a slot in spellbook's canonical skill-/command-authoring template (e.g., `invariant principles`, `inputs`, `outputs`, `self-check`, `prerequisite verification`, numbered `phase N` headings) resolve to `KEEP-placement` with `source=structural_template` without classifier dispatch. The allowlist and its phase-name regex patterns live in `references/template-headings.md`. Cross-bucket triage pairs are exempt from this floor so RECONCILE-drifted findings remain detectable.

4. **Fail-safe coercion direction is always KEEP, never EXTRACT.** Off-schema classifier responses, low-confidence verdicts, or any ambiguity coerce to a KEEP verdict. Deletion requires positive, schema-valid evidence; silence or malformed output preserves both blocks. The coercion rule is canonically stated in `references/counterfactual-prompt.md`.

5. **Clean git tree is a hard gate for apply.** Phase 4 (`/dedupe-apply`) refuses to run unless `git status --porcelain` is empty. The skill never writes to source files with pending unrelated changes; rollback uses a journaled record of every per-finding edit.

6. **M6 anti-irony: definitions live in `references/`, downstream artifacts cite by path.** SKILL.md, phase commands, and reports reference the canonical homes without restating their content. A grep-based gate in Track D enforces this. Restating verdict definitions, safety regexes, the classifier JSON schema, or the segmentation recipe inside this file is the failure mode this principle exists to prevent.

7. **Phases are non-fungible.** Setup, analyze, report, and apply are distinct phases with explicit handoff artifacts. Phase collapse — e.g., classifying during setup, or applying without operator approval at the report gate — is forbidden even when the corpus is small or the operator says "wrap up". The dispatch surface is the four commands listed below.

## Architecture

```
skills/dedupe/
├── SKILL.md                              # This file: orchestration contract
└── references/
    ├── verdict-taxonomy.md               # 5 verdicts + INLINE-MANDATORY semantics
    ├── counterfactual-prompt.md          # Classifier prompt + strict JSON schema + fail-safe coercion
    ├── segmentation-protocol.md          # Block segmentation + finding_id hashing recipe
    ├── safety-markers.md                 # INLINE-MANDATORY regex pattern table
    └── template-headings.md              # Structural-template bucket-key allowlist (Stage 5.5 floor)

commands/
├── dedupe-setup.md                       # Phase 1: parse seed, segment blocks, emit manifest
├── dedupe-analyze.md                     # Phase 2: bucket, triage, classifier dispatch, verdicts
├── dedupe-report.md                      # Phase 3: render findings report, drive approval
└── dedupe-apply.md                       # Phase 4: clean-tree gate, journaled apply, rollback
```

No Python, no helper scripts, no compiled tooling. Every artifact is prose-only markdown. The orchestrator (this file plus phase commands) uses only harness-native tools (Read, Grep, Write, AskUserQuestion, Task).

## Workflow

The skill drives four sequential phases. Each phase has a dedicated command file; see design doc §4 for the full per-phase contract, inputs, dispatches, and gates.

| Order | Phase | Command | One-line summary |
|-------|-------|---------|------------------|
| 1 | Setup | `commands/dedupe-setup.md` | Parse seed paths, segment each markdown file into blocks per the segmentation protocol, apply the mechanical safety-marker predicate, emit the blocks manifest. |
| 2 | Analyze | `commands/dedupe-analyze.md` | Bucket by heading chain, optionally run LLM-triage for cross-bucket candidates, dispatch one classifier subagent per surviving pair, collect verdicts. |
| 3 | Report | `commands/dedupe-report.md` | Render the findings report grouped by verdict, drive per-finding operator approval via AskUserQuestion. |
| 4 | Apply | `commands/dedupe-apply.md` | Enforce clean-tree gate, execute approved EXTRACT and RECONCILE actions with a per-finding journal, support rollback. |

Operator review gates separate each phase. The skill never auto-advances past a gate; the natural-language entry point drives the sequence with checkpoints, and each command can also be invoked standalone for re-runs.

## Invocation

Two invocation surfaces, both equivalent in capability:

- **Natural-language trigger.** The operator says something like "dedupe the X skills", "find duplicate instructions in Y", or "consolidate these instruction files". The orchestrator loads SKILL.md, requests the seed paths, and walks all four phases with operator gates between.
- **Direct phase command.** The operator invokes a single phase by its slash command:
  - `commands/dedupe-setup.md` — accepts the seed paths; standalone for re-running segmentation after edits.
  - `commands/dedupe-analyze.md` — requires the Phase 1 manifest; standalone for re-analyzing after operator-driven manifest review.
  - `commands/dedupe-report.md` — requires Phase 2 verdicts; standalone for re-rendering or re-driving approval.
  - `commands/dedupe-apply.md` — requires the approved report and a clean git tree; standalone for applying or rolling back.

## References (canonical homes)

These files are the authoritative source for their respective content. SKILL.md and the phase commands cite them by path; they do not restate.

| Reference | Purpose |
|-----------|---------|
| `references/verdict-taxonomy.md` | Defines the five verdicts and the INLINE-MANDATORY interaction. The verdict names may appear in orchestration prose; the definitions live only here. |
| `references/counterfactual-prompt.md` | Classifier prompt text, strict JSON verdict schema, and the off-schema fail-safe coercion rule. |
| `references/segmentation-protocol.md` | Heading-bounded block segmentation rules, the bucket-key derivation, and the `finding_id` hashing recipe. |
| `references/safety-markers.md` | Regex pattern table for the mechanical INLINE-MANDATORY safety-floor predicate. |
| `references/template-headings.md` | Bucket-key allowlist (and phase-name regex patterns) for the Stage 5.5 structural-template floor. |

## Quality gates

The skill's correctness depends on three categories of mechanical gate. Track D scripts implement the verification surface.

**Invariant: no executable helper code inside `skills/dedupe/` or the dedupe phase command files.** Verified by a grep-based scan covering interpreter imports, scripting-language file extensions, interpreter shebangs, and package-installation strings. The canonical pattern list lives in the Track D verification script.

**Invariant: M6 anti-irony — no restatement of reference content in SKILL.md, phase commands, or reports.** Verified by grep scans for verdict-definition signatures, safety-marker regex tokens, classifier schema field names, and segmentation recipe markers.

**Structural gates per phase.**
- Phase 1: manifest has the required columns; every block has a `finding_id`; oversized blocks are flagged and excluded from later dispatch.
- Phase 2: every pair produces a verdict (KEEP coercion on off-schema); the cost-ceiling gate fires when pair count exceeds the default.
- Phase 3: the report groups findings by verdict and surfaces operator approval per finding.
- Phase 4: clean-tree gate refuses dirty trees; every applied edit has a journal entry; rollback restores byte-identical source.

Hard gate for apply: clean git tree. No exceptions.

<reflection>
After each phase, the orchestrator verifies:
- Setup: the manifest contains every required column and every block has a `finding_id`; oversized blocks are flagged.
- Analyze: every surviving pair produced a verdict; off-schema responses were coerced to a KEEP verdict, never to EXTRACT.
- Report: every finding has an operator decision recorded; nothing advances to apply without explicit approval.
- Apply: the git tree was clean at gate time; every applied edit produced a journal entry; rollback restores byte-identical source.
- All phases: SKILL.md, phase commands, and the rendered report cite reference files by path and do not restate their content.
</reflection>

## v2 scope (deferred)

Embeddings as a candidate narrower are deferred to v2. Revival triggers: measured cross-bucket miss rate exceeds 20% on a seeded test corpus, or the operator lifts the no-Python constraint. See design doc §15 for the v2 revival criteria.
