---
name: dedupe-setup
description: "Phase 1 of the dedupe skill family. Resolves seed paths, applies the block-segmentation protocol, and emits the blocks manifest. Run before /dedupe-analyze."
---

# MISSION

Phase 1 of the `dedupe` skill: turn an operator-supplied seed (file paths or
directories of markdown) into a deterministic, reviewable blocks manifest
that downstream phases consume.

This command is orchestrator-only. No subagents are dispatched here. All
work is local filesystem inspection, segmentation, and manifest emission.

**Part of the dedupe-* command family.** Run before `/dedupe-analyze`.

## Invariant Principles

1. **Refuse on bad input** — every seed path must exist. A missing path
   aborts the run with an explicit error and emits no manifest.
2. **Resolve canonically** — symlinks and relative paths are reduced to
   their canonical absolute form before deduplication.
3. **Respect `.gitignore` by default** — gitignored files are excluded
   unless the operator passes `--include-gitignored`.
4. **Segmentation is delegated** — block boundaries and the bucket key /
   `finding_id` derivation are defined in
   `skills/dedupe/references/segmentation-protocol.md`. This command
   applies that protocol; it does not restate it.
5. **Mechanical safety floor is applied at setup time** — the pattern
   table in `skills/dedupe/references/safety-markers.md` is matched
   against every block body, and matching blocks are force-marked
   `inline_mandatory_mechanical=true` before any later phase runs.
6. **No Python, no shell scripts** — POSIX utilities only (`grep`, `awk`,
   `sed`, `shasum`, `printf`, `find`, `git ls-files`), invoked via the
   harness Bash tool.

**Safety-floor invariant:** The mechanical safety floor runs as part of
setup. Blocks flagged by the safety-marker predicate carry that flag
forward through every later phase. The LLM safety screen in analyze
may only ADD INLINE-MANDATORY status to a block, never remove
mechanically-assigned status.

---

## Invocation

```
/dedupe-setup <seed-path-or-comma-list> [--include-gitignored]
```

- `<seed-path-or-comma-list>` — one or more paths separated by commas.
  Each entry may be a single markdown file or a directory. Directories
  are walked recursively for `*.md` files.
- `--include-gitignored` — opt-in flag; when set, `.gitignored` files
  under the seed are included in the manifest.

Examples:

```
/dedupe-setup skills/finding-dead-code
/dedupe-setup skills/finding-dead-code,skills/simplify
/dedupe-setup commands/dead-code-setup.md,commands/dead-code-analyze.md
```

---

## Phase 1.1 — Parse and validate the seed

1. Split the seed argument on commas. Trim whitespace from each entry.
   Reject an empty seed argument with an explicit error.
2. For each entry, resolve it to a canonical absolute path via the
   harness Bash tool. The portable form is the subshell idiom
   `(cd "$(dirname "$path")" && printf '%s/%s\n' "$(pwd -P)" "$(basename "$path")")`
   — the outer parentheses run the `cd` in a subshell so the working
   directory of the invoking shell is preserved. Where available,
   `realpath` is also acceptable (note: macOS without GNU coreutils
   does not ship `readlink -f`, so avoid that form). Do NOT shell out
   to interpreter languages for path resolution; the skill is
   harness-agnostic and must rely only on POSIX shell tools.
3. If any resolved path does not exist on disk, HALT with the explicit
   error message:

   ```
   dedupe-setup: seed path does not exist: <path>
   no manifest written.
   ```

4. Deduplicate the resolved-path list. Two seed entries that resolve to
   the same canonical path are collapsed to a single entry.

---

## Phase 1.2 — Enumerate target markdown files

1. For each resolved seed entry:
   - If the entry is a file ending in `.md`, add it to the candidate
     file list.
   - If the entry is a directory, walk it for `*.md` files
     (`find <dir> -type f -name '*.md'`).
   - If the entry is a file but not `.md`, emit a single-line warning
     and skip:

     ```
     dedupe-setup: skipping non-markdown file: <path>
     ```

2. Unless `--include-gitignored` is set, filter out gitignored files via
   `git check-ignore` (invoked from the repository root). Any path
   reported by `git check-ignore` is removed from the candidate list.
3. The resulting list is the **target file list** for segmentation.

---

## Phase 1.3 — Apply the segmentation protocol

For every file in the target list, apply the protocol defined in
`skills/dedupe/references/segmentation-protocol.md`. The protocol
specifies block boundaries, the bucket key derivation, the
`finding_id` computation, oversized-block handling, code-fences-only
files, operator-marked regions, and the edge cases. **Do not restate
those rules here.** Read the reference file and apply it.

For each file the protocol produces a list of block records. Each
record carries at minimum:

- the source file path (resolved canonical absolute);
- the heading chain leading to the block (or the file-stem fallback per
  the protocol's edge-case table);
- the first three normalized lines of the block body;
- the block line count;
- the bucket key (derived per the protocol);
- the `finding_id` (derived per the protocol via `shasum -a 256`, then
  truncated to 12 hex chars);
- an `oversized` flag (true if the block exceeds the protocol's max
  line cap and the protocol could not chunk it at a sub-heading).

`shasum -a 256` is invoked via the harness Bash tool. No Python.

---

## Phase 1.4 — Mechanical safety-marker pre-flagging

For every block produced in Phase 1.3:

1. Read the block body verbatim from its source file.
2. Apply the pattern table from
   `skills/dedupe/references/safety-markers.md` mechanically. The
   reference file is the canonical home for the pattern set; this
   command does not restate any pattern.
3. If the block body matches any pattern, force the block's
   `inline_mandatory_mechanical` field to `true`. Otherwise the field
   is `false`.

The reference file declares the mechanical-floor application rule
(LLM screen may only ADD INLINE-MANDATORY status, never remove
mechanically-assigned status). That rule is enforced downstream in
analyze; setup only records the flag.

---

## Phase 1.5 — Compute the artifact path and the seed slug

The blocks manifest lives in the project-encoded artifact directory.
"Project-encoded" means the spellbook repository absolute path with the
leading `/` stripped and remaining `/` characters replaced by `-`. The
project-encoded path is computed with `printf` + `sed` via the harness
Bash tool — no Python:

```sh
PROJECT_ENCODED="$(printf '%s' "$REPO_ROOT" | sed 's|^/||; s|/|-|g')"
```

The seed slug is derived from the seed argument: lowercase, replace any
character outside `[a-z0-9]` with `-`, collapse adjacent dashes,
truncate at 40 characters, strip leading/trailing dashes. If the seed
expands to multiple entries, slugify the first entry and append
`-and-N-more` where N is the count of remaining seed entries.

Slug derivation is done with `printf` + `sed` + `tr` via the harness
Bash tool.

The artifact path is:

```
~/.local/spellbook/docs/<project-encoded>/dedupe-manifest-YYYY-MM-DD-<seed-slug>.md
```

- `YYYY-MM-DD` is today's date in UTC, obtained via `date -u +%Y-%m-%d`.
- The parent directory is created with `mkdir -p` if it does not exist.

---

## Phase 1.6 — Cost-ceiling gate

Estimate the worst-case pair count for the manifest as the sum over all
buckets of `C(n, 2)` where `n` is the bucket population. (This is the
upper bound on intra-bucket pairs before any cross-bucket triage.)

The default cost ceiling for pair count is **50**.

If the estimated pair count exceeds the default, drive `AskUserQuestion`
with the following options:

| Option | Effect |
|---|---|
| `proceed` | Emit the manifest as-is; analyze will surface the same gate again at its own step. |
| `narrow` | Re-prompt the operator for a tighter seed (typically a subset of the directories supplied) and re-run setup from Phase 1.1. |
| `abort` | Emit no manifest; exit cleanly. |

If the estimated pair count is at or below the default, no prompt is
shown.

---

## Phase 1.7 — Emit the blocks manifest

Write a single markdown document to the artifact path computed in
Phase 1.5. The document contains:

### Header

- Run timestamp (ISO 8601 UTC).
- Resolved seed paths (one per line).
- `--include-gitignored` flag state.
- Target file count.
- Block count.
- Estimated worst-case pair count.

### Blocks table

A markdown table with one row per block. Columns:

| `finding_id` | `file` | `heading_chain` | `first_3_lines` | `line_count` | `bucket` | `inline_mandatory_mechanical` | `oversized` |

Long fields (heading chain, first 3 lines) are wrapped in backticks so
the table stays parseable.

### Skipped files

A bullet list of any non-markdown or gitignored files that were
filtered. One bullet per skipped file with the reason.

### Footer

A single line:

```
Review manifest; proceed to /dedupe-analyze?
```

This line is the gate before Phase 2. The operator inspects the
manifest, edits source files if segmentation drifted, and invokes
`/dedupe-analyze <manifest-path>` when satisfied.

---

## Output

This command produces exactly one artifact:

```
~/.local/spellbook/docs/<project-encoded>/dedupe-manifest-YYYY-MM-DD-<seed-slug>.md
```

**Next:** Operator reviews the manifest. When ready, runs
`/dedupe-analyze <manifest-path>`.

---

## References

- Block segmentation, the bucket key derivation, `finding_id` recipe, and
  edge-case handling: `skills/dedupe/references/segmentation-protocol.md`.
- Mechanical safety-marker pattern table and application rule:
  `skills/dedupe/references/safety-markers.md`.
