# Safety Markers — Mechanical INLINE-MANDATORY Floor

This file is the **canonical home** for the mechanical regex table that
sets `inline_mandatory_mechanical=true` on instruction blocks BEFORE
the per-pair classifier sees them. SKILL.md, `dedupe-setup`, and
`dedupe-analyze` reference this file by path and MUST NOT restate its
contents inline (per M6 anti-irony, design §16).

## Application rule

> **Orchestrator applies these patterns inline before LLM safety screen.
> The LLM screen may only ADD INLINE-MANDATORY status, never SUBTRACT.**

The orchestrator scans every block's text (via harness Grep / Read; no
compiled regex engine of its own) and marks the block
`inline_mandatory_mechanical=true` if **any** pattern below matches.
Once set, this flag is sticky: the per-pair classifier's
`inline_mandatory` field may upgrade `false` to `true`, but the
orchestrator overrides any attempt to write `false` over a `true` set
by the mechanical floor (recorded as `mechanical_override=true` in the
finding row).

This grounds correctness in the mechanical predicate (falsifiable,
testable) rather than in the LLM screen (probabilistic). See design
§7 and §12 Success Criterion #2.

## Pattern table

Each row: regex (case-sensitive multiline unless noted), category,
example matched text, rationale.

| Pattern | Category | Example matched text | Rationale |
|---|---|---|---|
| `<CRITICAL>` | xml-marker | `<CRITICAL>` opening tag in `CLAUDE.md` Inviolable Rules section | XML-style safety marker used throughout spellbook to denote non-negotiable rules. |
| `<FORBIDDEN>` | xml-marker | `<FORBIDDEN>` opening tag wrapping the forbidden-actions list | Same family as `<CRITICAL>`; flags an authoritative prohibition block. |
| `<RULE>` | xml-marker | `<RULE>No any types, no blanket try-catch...` | Inline rule marker; each instance is a load-bearing prohibition. |
| `<ROLE>` | xml-marker | `<ROLE>You are a pattern-recognition engine...` | Persona / contract marker; defines authoritative role framing. |
| `<FINAL_EMPHASIS>` | xml-marker | `<FINAL_EMPHASIS>The test must fail first...` | Closing emphasis marker; load-bearing reminder at artifact end. |
| `^\s*NEVER\s` | imperative-lead-in | `NEVER push to a protected branch` at line start | Imperative-safety lead-in; per spellbook style, line-leading `NEVER` is reserved for inviolable rules. |
| `^\s*ALWAYS\s` | imperative-lead-in | `ALWAYS check git history before making claims` at line start | Same family as `NEVER`; line-leading `ALWAYS` indicates a non-negotiable affirmative requirement. |
| `^\s*MUST\s` | imperative-lead-in | `MUST adhere to these efficiency standards` at line start | Line-leading `MUST` is the standard spellbook RFC-2119-style mandate. |
| `^\s*DO NOT\s` | imperative-lead-in | `DO NOT skip phases or summarize skill workflows` at line start | Imperative prohibition; same load-bearing class as line-leading `NEVER`. |
| `Inviolable Rules?` | section-header | `## Inviolable Rules` heading | Section-header marker for the authoritative safety rules block in `CLAUDE.md` and skill files. |
| `Git Safety` | section-header | `### Git Safety` subsection heading | Section-header marker for git-side-effect safety rules; explicit operator-approval requirements live here. |
| `production[-\s]quality or nothing` | shibboleth | `Production-quality or nothing.` in `Code Quality` section (case-insensitive) | Spellbook-specific shibboleth phrase that consistently appears in load-bearing quality-bar statements. |
| `<CRITICAL>[\s\S]*?</CRITICAL>` | xml-marker | Multi-line `<CRITICAL>...content...</CRITICAL>` block | Multi-line CRITICAL block as a unit; ensures the closing tag's containing block is also caught when only one tag appears in the segmented block. |
| `^\s*STOP\s` | imperative-lead-in | `STOP and ask permission first` at line start | Imperative-halt lead-in; load-bearing prohibition against autonomous continuation. |

(A minimum of 12 data rows is required by the M6 acceptance gate; this
table currently has 14, leaving margin for future additions during
calibration. See design §17 open question #1.)

## Regex application notes

- All patterns are evaluated against the full block text (heading line
  + body), not against individual lines except where `^` is used.
- `^` anchors are evaluated in multiline mode (each line of the block
  is a candidate match site).
- The `production[-\s]quality or nothing` pattern is the only
  case-insensitive pattern. All others are case-sensitive — the
  spellbook style uses uppercase imperatives deliberately, and
  case-sensitivity prevents false positives on prose like "this would
  forbid... never doing X."
- The patterns are intentionally a **fixed table**, not operator-tunable
  per invocation. Operator tunability is a v2 concern (see design §17
  open question #1); v1 calibration happens by editing this file and
  re-running the skill.

## What this table does NOT cover

The mechanical floor is necessarily incomplete — it cannot detect
load-bearing instructions that lack any of these markers. The per-pair
LLM classifier remains responsible for catching those cases via the
`inline_mandatory` field of its strict JSON verdict. The two layers
are complementary:

- **Mechanical floor** (this file): high-precision, low-recall — it
  catches the markers spellbook uses to FLAG safety, but misses any
  block whose author neglected to use a marker.
- **LLM screen** (`counterfactual-prompt.md`): higher-recall but
  probabilistic — it reads the prose and decides whether the
  instruction reads as safety-critical.

The orchestrator combines them: a block is INLINE-MANDATORY if **either**
layer sets the flag. Once set by the mechanical layer, the flag cannot
be cleared by the LLM layer.

## Cross-references

- Verdict definitions (and the INLINE-MANDATORY orthogonal flag's
  interaction with verdicts): `verdict-taxonomy.md`.
- Classifier prompt and JSON schema (where the LLM screen's
  `inline_mandatory` field lives): `counterfactual-prompt.md`.
- Block segmentation that produces the blocks this table scans:
  `segmentation-protocol.md`.
