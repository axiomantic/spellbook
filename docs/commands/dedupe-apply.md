# /dedupe-apply
## Command Content

``````````markdown
# MISSION

Execute the approved consolidations as atomic, resumable, reversible
replace-with-reference edits, then re-detect to confirm each landed.

**Part of the dedupe-* command family.** Run last, after `/dedupe-report`.

## Invariant Principles

1. **Clean tree required** — refuse to run against a dirty git working tree;
   instruct the operator to commit or stash first.
2. **Home before deletion** — never delete a duplicate occurrence before its
   canonical home is written and verified readable. Replace-with-reference,
   never raw delete.
3. **Journaled, resumable, reversible** — every edit is recorded incrementally in
   a journal so the run can be resumed if interrupted and rolled back per finding.
4. **Safety blocks barred from Read-on-demand** — INLINE-MANDATORY content is
   never routed to a referenced-but-unread home.

<analysis>
Before applying, confirm:
- The git tree is clean.
- Each approved consolidation has a routing home that respects the
  INLINE-MANDATORY bar (no Read-on-demand for safety blocks).
- Edits within one file are ordered to avoid offset drift.
- The journal is being written incrementally, not only at the end.
</analysis>

## Phase 0: Preconditions

<RULE>Require a clean git working tree. If `git status --porcelain` is non-empty,
REFUSE to run and instruct the operator to commit or stash first (design §8).</RULE>

## Phase 1: Apply Order (design §5.3, strict)

Execute approved EXTRACTs in this exact order:

1. **Create all new reference files** for the batch (prefer
   `skills/shared-references/<topic>.md`).
2. **Verify each reference file** is readable AND contains the canonical block.
3. **Edit source files**: replace each occurrence with a pointer (e.g. "Load
   `<topic>` from `skills/shared-references/<topic>.md`" or a markdown link).
   NEVER delete content before its canonical home is written.
   - Multiple edits in one file are applied in **descending `start_line` order**
     (bottom-up) so not-yet-applied ranges stay valid.
   - **Overlapping** `[start_line, end_line]` ranges are **skipped and flagged**
     (`status: pending`, `overlap` note) for human resolution — never merged
     blindly.
4. **Write/update the apply journal incrementally** as each step lands.
5. **Post-apply verify** (see Phase 3).

## Phase 2: Journal (design §5.3.1)

Write the journal to:

```
~/.local/spellbook/docs/<project-encoded>/dedupe-journal-YYYY-MM-DD-HHMM.json
```

One entry per cluster/finding with a status enum (`pending`, `refs_created`,
`sources_edited`, `verified`, `rolled_back`), the `reference_files[]`, and per
edit: `file`, verbatim `original_text` (the rollback source of truth),
`replacement_text`, `start_line`, `end_line`, and `content_hash` (sha256 of
`original_text`, the per-edit idempotency key). Update it incrementally so an
interrupted run leaves an accurate record.

## Phase 3: Verify, Rollback, Resume

- **Verify:** run `python3 $SPELLBOOK_DIR/skills/dedupe/scripts/dedupe.py verify
  --journal <path> --corpus <corpus>`. Per finding it asserts BOTH (1) the
  original duplicate is absent AND (2) the pointer line is present and the
  reference file exists, readable, and contains the consolidated block.
- **Rollback on FAIL:** a finding that FAILs verify triggers journal-based
  per-finding rollback (restore source files first in descending `start_line`
  order, then delete reference files only when their refcount reaches 0).
- **Resume:** `--resume <journal>` branches per finding on `status`, using
  `content_hash` to skip already-landed edits and never re-create existing
  reference files or double-apply edits.

## Phase 4: Routing Constraints (design §5.5)

- `skills/shared-references/<topic>.md` is the **preferred** home.
- `CLAUDE.md` (always-on) is used ONLY for INLINE-MANDATORY content and is
  **human-flagged, never auto-applied**.
- INLINE-MANDATORY blocks (per the predicate in
  `skills/dedupe/references/verdict-taxonomy.md`) are **barred** from
  Read-on-demand homes.

## Output

The applied (or skipped/flagged) findings, the journal path, and the per-finding
verify PASS/FAIL results.

<reflection>
- [ ] Was the git tree clean before applying?
- [ ] Did every reference home get written and verified before any source edit?
- [ ] Were multi-edit files applied bottom-up, with overlaps skipped + flagged?
- [ ] Was the journal written incrementally (resumable + reversible)?
- [ ] Were INLINE-MANDATORY blocks kept out of Read-on-demand homes?
- [ ] Did post-apply verify pass per finding, with rollback on any FAIL?
</reflection>
``````````
