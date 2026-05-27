# Structural Template Headings — Convention-Driven Slot Floor

This file is the **canonical home** for the bucket-key allowlist that
short-circuits structural-template pairs to `KEEP-placement` BEFORE the
per-pair classifier sees them. SKILL.md, `dedupe-setup`, and
`dedupe-analyze` reference this file by path and MUST NOT restate its
contents inline (per M6 anti-irony, design §16).

## Why this floor exists

Spellbook's skill- and command-authoring conventions
(`skills/writing-skills`, `skills/instruction-engineering`,
`skills/writing-commands`, `skills/crystallize`, `commands/ie-template`)
prescribe a canonical heading skeleton that every well-formed skill or
command instantiates. Two files that both contain a `## Invariant
Principles` section are not *duplicating content* — each is filling a
*structural slot* required by the author template. The blocks under
that heading carry the file's own per-skill principles, which are by
construction parameterized to that skill.

Bucketing by heading text alone (per `segmentation-protocol.md` §3)
therefore guarantees false-positive pairs for every template heading
shared across files. This floor is the orthogonal fix: pairs in
template-heading buckets short-circuit to `KEEP-placement` with
`source=structural_template`, with no classifier dispatch.

## Application rule

> **Orchestrator applies this allowlist in `/dedupe-analyze` Stage 5.5
> (Structural template floor), AFTER pair-list assembly (Stage 5) and
> BEFORE the mechanical safety floor (Stage 6). For every surviving
> pair, if BOTH blocks' `bucket_key` matches an entry in the allowlist
> below (exact, case-sensitive after normalization), short-circuit the
> pair to verdict `KEEP-placement`, `source=structural_template`,
> `inline_mandatory` carried from the manifest.**

The template-heading floor is **bucket-level**, not block-level: it
fires when the *bucket key* matches, not when any block content matches.
This is because the heading itself is the structural signal; the body
of a structural slot is by definition specialized.

Interaction with other floors:

- **Safety floor (Stage 6) still applies.** If either block in a
  template-heading pair carries `inline_mandatory_mechanical=true`, the
  Stage 6 short-circuit overrides this Stage 5.5 short-circuit. The
  resulting verdict family stays KEEP; only the `source` field changes
  to `mechanical_floor` and `inline_mandatory=true` is set.
- **Drift detection is NOT bypassed.** RECONCILE-drifted findings can
  still emerge from these buckets via Stage 4 LLM-triage cross-bucket
  pairs (e.g., a `## Invariant Principles` block paired with a body
  block from a different bucket whose content has drifted). Stage 5.5
  only short-circuits *intra-bucket* template-heading pairs.

## Allowlist (canonical, case-sensitive after bucket-key normalization)

These are the canonical normalized `bucket_key` values that trigger the
floor. The normalization rules are inherited from
`segmentation-protocol.md` §3 (lowercase, whitespace collapsed,
trailing punctuation stripped, leading `#` markers stripped).

| bucket_key (normalized) | Source convention | Slot purpose |
|---|---|---|
| `invariant principles` | writing-skills, writing-commands, instruction-engineering | The skill's 3-5 numbered non-negotiable constraints — per-skill content. |
| `inputs` | writing-skills | Input parameter table. Per-skill schema. |
| `outputs` | writing-skills | Output artifact table. Per-skill schema. |
| `self-check` | writing-skills, writing-commands | Pre-completion checklist. Per-skill items. |
| `overview` | writing-skills | One- or two-sentence skill summary. Per-skill content. |
| `when to use` | writing-skills | Trigger conditions and anti-triggers. Per-skill content. |
| `quick reference` | writing-skills | Table or bullets for common operations. Per-skill content. |
| `anti-patterns` | writing-skills, writing-commands | Known failure modes. Per-skill content. |
| `common mistakes` | writing-skills | What goes wrong + fixes. Per-skill content. |
| `quality gates` | writing-skills | Validation thresholds. Per-skill content. |
| `quality checklist` | writing-commands | Detailed evaluation items. Per-command content. |
| `reasoning schema` | writing-skills, instruction-engineering | Pre- and post-action deliberation prompts. Per-skill content. |
| `phase overview` | writing-skills | Orchestrator-skill phase summary. Per-skill content. |
| `phases` | writing-skills | Phase list for multi-phase skills. Per-skill content. |
| `mission` | writing-commands | H1 command-purpose statement. Per-command content. |
| `output` | writing-commands | Concrete output format. Per-command content. |
| `prerequisite verification` | develop family, writing-commands | Pre-phase artifact checks. Per-command content. |
| `prerequisites` | writing-commands | Pre-execution requirements. Per-command content. |
| `invocation` | writing-commands | How to invoke. Per-command syntax. |
| `core pattern` | writing-skills | Before/after code comparison. Per-skill content. |
| `implementation` | writing-skills | Inline code or links. Per-skill content. |
| `constraints` | writing-skills | Resource limits, boundary rules. Per-skill content. |
| `context` | writing-skills | Supporting information. Per-skill content. |
| `token budget` | writing-skills, instruction-engineering | Target line counts. Per-skill content. |
| `skill types` | writing-skills | Classification table (meta-skills). |
| `behavior decision table` | writing-commands | Branching logic. Per-command content. |
| `execution flow` | writing-commands | High-level flow. Per-command content. |
| `protocol` | writing-commands | Named protocol. Per-command content. |
| `mode router` | writing-commands | Decision branching for invocation modes. Per-command content. |
| `mcp tools` | writing-commands | Tool/system integration. Per-command content. |
| `integration points` | writing-commands | Same family as mcp tools. Per-command content. |
| `references` | writing-skills | Cross-reference list. Per-skill content. |
| `cross-references` | writing-skills | Same family as references. Per-skill content. |

The list is intentionally a **fixed table**, not operator-tunable per
invocation. Operator tunability is a v2 concern; v1 calibration happens
by editing this file and re-running the skill.

## Phase-name patterns (regex floor)

In addition to the exact-match allowlist above, bucket keys that match
the following regex patterns are also short-circuited. These cover the
spellbook convention of numbered phase headings in command files, which
are per-command structural slots even though each phase's name varies.

| Regex (case-insensitive, anchored) | Matches | Rationale |
|---|---|---|
| `^phase \d+(\.\d+)*` | `phase 1`, `phase 0.5`, `phase 1.5.2` | Numbered phase header — per-command slot. |
| `^phase \d+(\.\d+)* (complete\|done\|gate)$` | `phase 0 complete`, `phase 4 done` | Phase-end gate marker — per-command slot. |
| `^step \d+:` | `step 1: parse recovery context` | Numbered step inside a phase — per-command slot. |
| `^\d+\.\d+` | `0.1 detect escape hatches`, `1.5.4 synthesize` | Decimal-prefixed phase section — per-command slot. |
| `^═+$` | `═══════════════════════════════════════════════════════════════════` | Box-drawing banner used as section divider in develop family. |

A bucket whose key matches **either** the exact-match allowlist or any
pattern above is short-circuited.

## What this floor does NOT do

- **Does not suppress cross-file drift findings.** A template-heading
  block in file A that *contradicts* a template-heading block in file B
  is still surfaceable via Stage 4 cross-bucket triage. Triage receives
  the heading-only manifest, including these structural buckets, and
  may pair their blocks against blocks in *other* buckets where the
  drift becomes visible.
- **Does not suppress same-file duplicate-heading findings.** The
  `segmentation-protocol.md` §3 ordinal-suffix rule
  (`Overview#1`, `Overview#2`) is upstream of this allowlist; intra-file
  duplicate-heading pairs are surfaced as their own bucket keys and
  bypass this floor.
- **Does not modify the manifest.** The floor is applied at analyze
  time, not at setup. The manifest's `bucket_key` column is unchanged.

## Cross-references

- Block segmentation that produces the bucket keys this allowlist
  matches: `segmentation-protocol.md`.
- Mechanical safety-marker floor that takes precedence over this floor
  when either block carries `inline_mandatory_mechanical=true`:
  `safety-markers.md`.
- Verdict catalog (where `KEEP-placement` is defined):
  `verdict-taxonomy.md`.
- The analyze-stage insertion point that applies this floor:
  `commands/dedupe-analyze.md` Stage 5.5.
- Authoring conventions that prescribe these headings:
  `skills/writing-skills/SKILL.md`,
  `skills/writing-commands/SKILL.md`,
  `skills/instruction-engineering/SKILL.md`,
  `skills/crystallize/SKILL.md`,
  `commands/ie-template.md`.
