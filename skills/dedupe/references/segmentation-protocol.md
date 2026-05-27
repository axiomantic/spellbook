# Block Segmentation Protocol

This file is the **canonical home** for the deterministic block
segmentation protocol used by the `dedupe` skill's Phase 1 (setup).
SKILL.md and the phase commands reference this file by path and MUST
NOT restate its contents inline (per M6 anti-irony, design §16).

The protocol takes a markdown file and produces an ordered list of
**blocks**. Each block carries a stable `finding_id`, a `bucket_key`
for heading-topic grouping, and edge-case flags (`oversized`,
`inline_mandatory_mechanical`).

The protocol is intentionally **deterministic and prose-only**: the
orchestrator implements it by combining harness Read, Grep, and Bash
tools. No Python, no compiled regex engine, no parser library.

---

## 1. Block definition

A **block** is one of:

1. **A heading-bounded section.** A markdown section bounded by a
   heading line (starting with `#`) and the next heading line of equal
   or higher level, OR end of file. The block INCLUDES the heading
   line itself.

2. **An atomic code fence.** When a file contains only code fences
   (no headings at all), each fenced region is its own block. The
   bucket key uses the fence's language tag (see §3).

3. **An operator-marked region.** Text between
   `<!--DEDUPE-BLOCK-START-->` and `<!--DEDUPE-BLOCK-END-->` HTML
   comments overrides heading-based segmentation within its range.
   Marked regions WIN over headings inside them.

**Minimum block size.** 3 non-blank lines. Candidates smaller than the
minimum are merged into the next adjacent block; if none exists, the
candidate is dropped with a warning row in the manifest.

**Headings inside fenced code.** Heading-like lines (starting with `#`)
that fall INSIDE a fenced code region (between ` ``` ` markers) do NOT
start a new block. Fenced code is opaque to segmentation. The
orchestrator tracks fence depth while scanning.

---

## 2. `finding_id` recipe

Every block has a stable `finding_id` computed as:

```
finding_id = sha256(
    file_path_resolved        # canonicalized absolute path
    + "\x1f"                  # ASCII unit separator
    + bucket_key              # per §3
    + "\x1f"
    + heading_chain           # "/".join(headings from h1 down to this block's heading)
    + "\x1f"
    + first_3_normalized_lines  # strip whitespace, lowercase, drop leading "#" markers
)[:12]
```

The four fields are concatenated with `\x1f` (ASCII 0x1F, the unit
separator) between them, the result is sha256-hashed, and the first 12
hex chars of the hex digest are taken as the `finding_id`.

**Why `\x1f`.** The unit separator is a non-printable control
character that cannot appear in normal markdown content (file paths,
heading text, normalized line content). Using it as the delimiter
prevents any concatenation-collision attack — e.g., a heading chain
`a/b` colliding with a file path containing the suffix `a/b`.

**Why 12 hex chars (48 bits).** Collision probability is 2^-48 per
pair of blocks. Acceptable for the skill's operational scale
(low-thousands of blocks max in a single seed). See design §14.

**Implementation (harness Bash, no Python).** The orchestrator
assembles the four fields into a single byte string (using `printf` for
the literal `\x1f` interpolation), pipes through `shasum -a 256`, and
truncates the first 12 hex chars. Example shell pattern (illustrative —
the orchestrator inlines this; no helper script):

```bash
printf '%s\x1f%s\x1f%s\x1f%s' \
    "$file_path_resolved" \
    "$bucket_key" \
    "$heading_chain" \
    "$first_3_normalized_lines" \
  | shasum -a 256 \
  | cut -c1-12
```

`openssl dgst -sha256` is an equivalent substitute on systems without
`shasum`. No Python `hashlib` module is required.

**`first_3_normalized_lines` recipe.** Take the first 3 non-blank lines
of the block (after the heading line, for heading-bounded blocks);
strip leading and trailing whitespace from each; lowercase; remove
leading `#` characters and the immediately-following space. Join with
single `\n`. If the block has fewer than 3 non-blank lines after the
heading, use whatever is available.

**Stability invariant.** A `finding_id` is **stable** across
re-segmentations only when all four input fields (file path, bucket
key, heading chain, first 3 normalized lines) are unchanged. Any
segmentation drift produces a new `finding_id`, surfaced as a new
manifest row. This is intentional: the journal entries reference the
`finding_id` of the block they applied to; segmentation drift produces
a manifest row mismatch the operator can see, rather than silently
corrupting the journal.

---

## 3. `bucket_key` derivation

The `bucket_key` is the heading-topic group used by Phase 2 for
intra-bucket pair enumeration. The derivation table:

| Case | bucket_key |
|---|---|
| Normal (file has headings, block has its own heading) | normalized heading text of the block's own heading (lowercase, whitespace collapsed to single spaces, trailing punctuation stripped) |
| File has NO headings anywhere | `<file-stem>:no-headings` (where `<file-stem>` is the basename without `.md`) |
| File contains ONLY code fences (no headings, no prose) | `code:<language-tag>` — e.g., `code:python`, `code:bash`, `code:none` if the fence has no language tag |
| Intra-file duplicate heading text (same heading appears multiple times) | heading text + `#<occurrence_ordinal>` — e.g., `Overview#1`, `Overview#2` |
| Operator-marked region | `marked:<file-stem>:<region_ordinal>` |

**Normalization details for "normal" case:**

- Lowercase.
- Collapse runs of whitespace to a single space.
- Strip leading / trailing whitespace.
- Strip trailing punctuation `.`, `,`, `:`, `;`, `!`, `?`.
- Strip leading `#` markers and the immediately-following space (the
  heading prefix).

Example: heading line `### My Awesome Workflow:` → bucket key
`my awesome workflow`.

**Why these special bucket keys.**

- `<file-stem>:no-headings` — a heading-less file is a single block;
  giving it a file-specific bucket key prevents it from colliding
  with other heading-less files in cross-bucket triage. Each
  heading-less file becomes its own bucket (containing one block).
- `code:<language-tag>` — code-only files (e.g., utility scripts
  documented as `.md` with only fenced code) are bucketed by language
  so that paraphrased shell snippets can pair against shell snippets,
  Python against Python, etc.
- `Overview#N`, `marked:...:N` — preserve intra-file ordering so that
  two `## Overview` sections in the same file don't get the identical
  bucket key (which would collapse them in the manifest).

---

## 4. Edge cases (handled inline by the orchestrator)

| Edge case | Behavior |
|---|---|
| Empty file (0 bytes or only whitespace) | Manifest emits no row for the file; orchestrator logs `<file>: empty, skipped` warning. |
| Single-block file (one heading or one fence) | Manifest emits the single row; Phase 2 treats it as a no-pair candidate (only contributes to LLM-triage cross-bucket pairs). |
| Oversized block (>800 lines) | Chunk at the next heading boundary inside the block. If no such heading exists below the cap, split at line 800 and flag both halves as `oversized=true`. Oversized blocks are EXCLUDED from classifier dispatch and surfaced in the manifest for operator review. |
| Symlinks | Resolve via canonical-path semantics (`readlink -f` or equivalent). Deduplicate paths by resolved canonical path before block segmentation. A symlink target's blocks are scanned via the canonical path; the symlink itself is not a separate block source. |
| `.gitignored` files | Respected by default. Operator may override per-invocation with `--include-gitignored`. The orchestrator consults `git check-ignore` via harness Bash. |
| Intra-file duplicate heading text | `bucket_key` gets occurrence ordinal (see §3 table row: `Overview#1`, `Overview#2`). The `finding_id` recipe naturally differs because the `first_3_normalized_lines` differ between occurrences (otherwise the duplicate headings are reading the same content twice, which is a different bug). |
| Headings inside fenced code | Do NOT start a new block. The orchestrator tracks fence depth while scanning; lines starting with `#` inside a fence (depth > 0) are treated as content, not headings. |
| Operator-marked region containing a heading | Marked region WINS. Heading-based segmentation is suspended within the marked region; the entire marked region is one block with `bucket_key = marked:<file-stem>:<region_ordinal>`. |
| Operator-marked region with no matching END | Treat as opening syntax error; the file is skipped with a warning row in the manifest. No partial marked-region blocks. |
| Code fence with no closing marker (unclosed fence) | Treat as malformed; the file is skipped with a warning row in the manifest. |
| Heading at file end with no body | Block has only the heading line (1 non-blank line); fails the 3-line minimum; dropped with a manifest warning. |
| Non-markdown file in seed (`.txt`, `.json`, etc.) | Skipped with a manifest warning line; not segmented. |

---

## 5. Output: manifest row schema

The Phase 1 manifest emits one row per block:

| Column | Meaning |
|---|---|
| `finding_id` | 12 hex chars per §2. |
| `file` | Resolved canonical path. |
| `heading_chain` | `h1/h2/.../this_heading` (or empty for heading-less files / fenced regions). |
| `first_3_lines` | First 3 lines of block content, raw (not normalized — for operator readability). |
| `line_count` | Total non-blank line count of the block. |
| `bucket_key` | Per §3. |
| `inline_mandatory_mechanical` | Boolean; set by the safety-marker mechanical floor (`safety-markers.md`). |
| `oversized` | Boolean; `true` if the block exceeded 800 lines and was split per §4. |

The manifest is written to
`~/.local/spellbook/docs/<project-encoded>/dedupe-manifest-YYYY-MM-DD.md`.

---

## 6. Cross-references

- The mechanical safety-marker floor applied to each block during
  Phase 1: `safety-markers.md`.
- The verdict taxonomy that consumes the manifest rows in Phase 2:
  `verdict-taxonomy.md`.
- The classifier dispatch contract that pairs manifest rows:
  `counterfactual-prompt.md`.
