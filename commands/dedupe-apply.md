---
name: dedupe-apply
description: "Phase 4 of the dedupe skill family. Applies operator-approved EXTRACT findings with HTML-comment-fenced JSON journaling and supports deterministic rollback. Run after /dedupe-report."
---

# MISSION

Phase 4 of the `dedupe` skill: consume the report artifact produced by
`/dedupe-report`, apply every EXTRACT finding marked `apply` after one
final pre-edit checkpoint, and journal each edit in a deterministic,
rollback-ready format.

**Part of the dedupe-* command family.** Run after `/dedupe-report`.

## Invariant Principles

1. **Clean working tree is a hard gate** — `git status --porcelain` must
   be empty. There is no override flag. The operator commits / stashes /
   discards before this command will touch the filesystem.
2. **Every edit is journaled** — the journal is the rollback source of
   truth. If an edit is not journaled, it did not happen.
3. **Per-finding final checkpoint** — every EXTRACT finding marked
   `apply` in the report receives one `AskUserQuestion` prompt
   immediately before its edit. There is no "apply all" affordance.
4. **Rollback is byte-exact** — restoring an original block requires the
   `new_path` content to match what the journal recorded as the
   post-apply state. Mismatch means the canonical home was edited
   externally; warn and skip rather than overwrite the operator's work.
5. **No Python, no shell scripts** — base64 encode/decode runs via the
   `base64` CLI through the harness Bash tool. Journal parsing uses
   POSIX text utilities plus `jq` (preinstalled via brew on the dev
   machine).

**Clean-tree-gate invariant:** The clean-tree gate has no override.
Every applied edit is journaled; the only way rollback remains
trustworthy is if the working tree before apply is a known git state.
Suppressing the gate would silently break rollback's correctness
invariant.

**Prohibited operations:**

- Editing any file before the clean-tree gate passes.
- Editing any file before the per-finding `AskUserQuestion` checkpoint
  for that finding has returned `apply`.
- Writing a journal entry whose `original_text_*_b64` field does not
  round-trip back to the exact bytes read from the source file.
- Rolling back a finding whose `new_path` content does not match the
  recorded `new_text_b64` (warn and skip instead).
- Implementing base64 encode/decode in Python.

---

## Invocation

```
/dedupe-apply <report-path>
/dedupe-apply --rollback <journal-path>
```

- `<report-path>` — the artifact produced by `/dedupe-report`. Required
  in apply mode.
- `--rollback <journal-path>` — switches to rollback mode. The journal
  is the artifact produced by an earlier successful or partial apply
  run.

The two modes are mutually exclusive.

---

## Mode A — Apply

### Phase 4.1 — Clean-tree hard gate

The very first action is:

```sh
git status --porcelain
```

run via the harness Bash tool from the repository root. If the output
is non-empty, HALT with the explicit error message:

```
dedupe-apply: working tree is not clean.
The following files have uncommitted changes:
<list of files>

Commit, stash, or discard them and re-invoke /dedupe-apply.
There is no override flag.
```

No journal entry is written. No file is edited.

### Phase 4.2 — Parse the report

Read the report at `<report-path>`. Identify every EXTRACT subsection
whose `Disposition` line records `apply`. Skip every other disposition
(`skip-this`, `defer-to-drift`, `mark-keep`) silently.

For each `apply` finding, extract:

- the pair `finding_id`;
- the two source file paths and heading chains for blocks A and B;
- the proposed canonical home path under `skills/shared-references/`;
- the rationale and counterfactual-loss prose (echoed into the journal
  narrative).

### Phase 4.3 — Compute the journal artifact path

```
~/.local/spellbook/docs/<project-encoded>/dedupe-journal-YYYY-MM-DD-<seed-slug>.md
```

The project-encoded prefix and seed slug are inherited from the report
header. `YYYY-MM-DD` is today's date in UTC, obtained via
`date -u +%Y-%m-%d`. Create the parent directory with `mkdir -p` if it
does not exist.

If a journal file already exists at that path (resume scenario), append
new entries to it rather than truncating. Read the existing journal to
identify which `finding_id`s have already been applied (entries with
`status=applied`); skip those on the second pass to keep the run
idempotent.

### Phase 4.4 — Per-finding apply loop

For each `apply` finding, in the order they appear in the report:

1. **Final pre-edit checkpoint.** Drive `AskUserQuestion` with the
   options:

   | Option | Effect |
   |---|---|
   | `apply` | Proceed with the edit for this finding. |
   | `skip-this` | Skip this finding; do not edit, do not journal. |
   | `abort-remaining` | Skip this and every remaining finding; finish the run. |

   This is the final safety checkpoint. There is no "apply all"
   affordance. If 50 prompts are operationally excessive, the operator
   should have narrowed the cost ceiling at `/dedupe-analyze`.

2. **Read the original block bodies.** For each of block A and block B,
   read the verbatim bytes from the source file. Hold them in memory
   for the journal entry.

3. **Base64-encode the originals** via the `base64` CLI through the
   harness Bash tool, e.g.:

   ```sh
   ORIG_A_B64="$(printf '%s' "$ORIG_A" | base64 | tr -d '\n')"
   ```

   The `printf '%s'` form avoids `echo`'s trailing newline. The
   `| tr -d '\n'` strips GNU `base64`'s default 76-column line wraps so
   the resulting string survives embedding in a single-line JSON value.
   Decoded round-trip is verified before writing the journal entry: if
   `printf '%s' "$ORIG_A_B64" | base64 --decode` does not produce
   byte-exact `$ORIG_A`, HALT with a journal-encode-failure error.
   Use `base64 --decode` (not `-d`) for portability across GNU and
   BSD/macOS implementations.

4. **Write the canonical home.** Create or overwrite the file at the
   proposed canonical home path under `skills/shared-references/`. The
   canonical home contains the consolidated block body. Capture the
   exact bytes written and base64-encode them as `new_text_b64`.

5. **Replace block A in its source file** with the single-line
   reference plumbing:

   ```
   See [<slug>](../shared-references/<slug>.md).
   ```

   Replace block B in its source file the same way.

6. **Append a journal entry.** Each entry is one markdown subsection
   with an HTML-comment-fenced JSON block embedded in it:

   ```
   ## EXTRACT-<finding_id_pair>

   Applied EXTRACT for blocks in <file_a> and <file_b>. Canonical home
   written to <new_path>; both original blocks replaced with single-line
   references.

   <!--FINDING {
     "id": "<finding_id_pair>",
     "verdict": "EXTRACT",
     "status": "applied",
     "timestamp": "<ISO8601 UTC>",
     "original_path_a": "<resolved path>",
     "original_text_a_b64": "<base64 of block A bytes>",
     "replacement_text_a": "See [<slug>](../shared-references/<slug>.md).",
     "original_path_b": "<resolved path>",
     "original_text_b_b64": "<base64 of block B bytes>",
     "replacement_text_b": "See [<slug>](../shared-references/<slug>.md).",
     "new_path": "skills/shared-references/<slug>.md",
     "new_text_b64": "<base64 of canonical home bytes>"
   } FINDING-->
   ```

   The `<!--FINDING ... FINDING-->` fence makes the entry parseable by
   substring scan without a markdown parser and invisible in rendered
   markdown.

   If step 2, 4, or 5 fails for any reason, append the journal entry
   with `status=failed` and a `error_message` field carrying the error
   text. The apply loop continues to the next finding; idempotency
   requires that partial runs be resumable.

### Phase 4.5 — Final summary

When every approved finding has been processed, emit a single-line
summary:

```
dedupe-apply complete: A applied, S skipped, F failed (journal: <path>)
```

---

## Mode B — Rollback

### Phase 4.6 — Parse the journal

Read the journal at `<journal-path>`. Extract every `<!--FINDING ...
FINDING-->` block via substring scan; do NOT rely on a markdown
parser. The pattern is anchored: scan for the literal opening sentinel
`<!--FINDING`, then for the matching closing sentinel `FINDING-->`.
The content between them is JSON.

Pipe each JSON block through `jq` for parsing and field extraction:

```sh
echo "$JSON" | jq -r '.id, .status, .original_path_a, .original_text_a_b64, ...'
```

Discard entries whose `status` is not `applied`.

### Phase 4.7 — Per-entry restore

For each applied entry, in REVERSE order of the journal (most-recent
first), restore in three steps:

1. **Verify the canonical home content.** Read the current bytes at
   `new_path`. Compute its base64 via the `base64` CLI. Compare against
   the journal's `new_text_b64`.

   - If the bytes match byte-exactly, proceed to step 2.
   - If they differ, EMIT a single-line warning:

     ```
     dedupe-apply --rollback: skipping <new_path> — content differs from journal record.
     The operator may have edited the canonical home; reconcile manually.
     ```

     Skip steps 2 and 3 for this entry. Move to the next entry.

2. **Restore block A.** Base64-decode `original_text_a_b64` via
   `base64 --decode` through the harness Bash tool. In the source file at
   `original_path_a`, replace the current single-line reference
   plumbing with the decoded original bytes.

3. **Restore block B.** Same procedure with `original_text_b_b64` and
   `original_path_b`.

4. **Delete the canonical home.** Remove the file at `new_path`. If it
   does not exist (already deleted in a prior rollback), proceed silently.

### Phase 4.8 — Companion rollback journal

Write a companion artifact at:

```
~/.local/spellbook/docs/<project-encoded>/dedupe-rollback-YYYY-MM-DD-<seed-slug>.md
```

It records every restore action with the same HTML-comment-fenced JSON
shape, with `status` set to `rolled-back` or `skipped-content-differs`
as appropriate.

### Phase 4.9 — Rollback summary

Emit:

```
dedupe-apply --rollback complete: R restored, S skipped (companion journal: <path>)
```

Rollback does NOT require a clean working tree, but every restore step
that detected a post-apply edit (step 1 mismatch) is logged so the
operator can reconcile manually.

---

## Output

In apply mode:

```
~/.local/spellbook/docs/<project-encoded>/dedupe-journal-YYYY-MM-DD-<seed-slug>.md
```

In rollback mode:

```
~/.local/spellbook/docs/<project-encoded>/dedupe-rollback-YYYY-MM-DD-<seed-slug>.md
```

---

## References

- The classifier JSON schema (referenced for the verdict field set
  embedded in journal entries): `skills/dedupe/references/counterfactual-prompt.md`.
- Verdict catalog: `skills/dedupe/references/verdict-taxonomy.md`.

**Closing:** The clean-tree gate has no override. Every edit is
journaled. Rollback is byte-exact or it warns and skips. There are
no shortcuts on this phase; the operator's working tree is the
contract.
