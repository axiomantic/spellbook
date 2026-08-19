# Develop Gate Ledger: Writes and CLI Reference

Canonical reference for the `develop_gate_ledger` state shape, the merge
contract every write obeys, and the `scripts/develop_gate_ledger.py` CLI
surface — including every refusal the CLI raises and the remedy each one
names. `skills/develop/SKILL.md` and the commands that write the ledger
(`/feature-config`, `/feature-implement`, `/feature-implement-execute`)
resolve field names, subcommand spellings, and refusal semantics here
rather than restating them.

## Ledger Writes (workflow_state — accountability + compaction recovery)

<CRITICAL>
develop records its own phase/gate progress in a persistent state file so the work
survives context compaction and a resumed session can re-assert the remaining
gates instead of declaring "done" prematurely. This is design §5 (C4).

**MERGE-ONLY, NEVER overwrite.** develop writes via deep-merge and MUST NEVER
use full overwrite. The hooks (`_handle_pre_compact`) write `compaction_flag` and
`stint_stack` into the SAME state row; an overwrite from develop would clobber
them, and vice versa. `_deep_merge` preserves sibling keys, so disjoint-key writes
never lose a field (design §5.2/§5.5). An overwrite here is a Risk §13 regression
— do not do it.
</CRITICAL>

**The ledger shape (`develop_gate_ledger`, design §5.3):**

```typescript
develop_gate_ledger: {
  current_phase: string;        // "0" | "1" | "1.5" | "2" | "3" | "4" | "fast-path"
  need_flags: { needs_research: boolean; needs_design: boolean; needs_infrastructure: boolean };
  remaining_gates: string;      // NEWLINE-JOINED SCALAR (NOT a list), e.g.
                                // "design review\ncode review\ngreen-mirage\ntest suite"
  plan_pointer: string;         // absolute path to impl plan / design doc / understanding doc
  ceremony: {                   // the ONE-TIME ceremony selection (feature-config §0.8)
    locked_at: string;          // ISO 8601. Its PRESENCE is the lock. Never rewritten.
    source: string;             // "operator_selected" | "recommendation_accepted" | "default_full"
    assessment: string;         // newline-joined "D{n} {dimension}={low|high}: {evidence}" (§0.7.5)
    core: string;               // newline-joined non-negotiable gates — never were selectable
    selected: string;           // newline-joined optional gates chosen to RUN
    declined: string;           // newline-joined optional gates chosen to SKIP (recorded, not absent)
    promotions: string;         // newline-joined "{gate} <- {reason} ({ISO ts})" escalation record
    gate_position: string;      // "per_task" | "per_group", default "per_task". "per_group" is
                                 // offered only when SESSION_PREFERENCES.task_granularity ==
                                 // "capability" (feature-config §0.7 Step 2.5) — that answer is
                                 // recorded in Phase 0, before any plan exists. Locked with the
                                 // rest of ceremony at locked_at; never changed mid-run.
  };
  ceremony_history: {            // archive of superseded `ceremony` blocks, keyed by ISO archive
                                  // timestamp. Written only on a deliberate re-invocation over an
                                  // existing ledger — the old `ceremony` block is archived here
                                  // with a reason before a new Phase 0 sets `ceremony` fresh.
    [archived_at: string]: {
      ceremony: object;          // the full superseded ceremony block, verbatim
      reason: string;            // why the operator re-invoked and re-selected
      archived_at: string;       // ISO 8601; also written INTO the entry by archive_ceremony,
                                  // duplicating the key this entry is stored under
    };
  };
  blockers: {                    // open blockers keyed by id; each row carries a type so the
                                  // orchestrator can count them at phase/wave boundaries
    [blocker_id: string]: {
      type: "decision" | "work" | "external";
      description?: string;      // omitted by record_blocker when --description is blank or absent
      opened_at: string;         // ISO 8601
      closed_at?: string;        // ISO 8601. `_deep_merge` never deletes keys, so a blocker row
                                  // is permanent once written — closure is a FIELD, never an
                                  // absence. A blocker is OPEN iff it has no `closed_at`.
    };
  };
  waves: {                      // §24.6 wave-discipline check records, keyed by wave id
    [wave_id: string]: {
      section_24_6_check: {
        status: "passed" | "failed" | "n_a";
        open_rows: string[];    // the W<n>- ids still open; written on EVERY status, empty
                                // included. `_deep_merge` replaces lists but never deletes
                                // keys, so an omitted key cannot SHRINK -- a passing
                                // re-record would inherit the prior failure's rows.
                                // status=failed is REFUSED with an empty list.
        timestamp?: string;     // ISO 8601; the develop skill writes it on each entry
        reason?: string;        // free-form context; records WHY on status=n_a
      };
    };
  };
  groups: {                     // gate_position: per_group boundary-gate check records, keyed by
                                 // group id. Without this record, "the boundary gate stack ran"
                                 // and "it never ran" are indistinguishable — the same
                                 // mechanism-vs-discipline gap §24.6 closes for waves.
    [group_id: string]: {
      gate_stack: {
        status: "passed" | "failed" | "n_a";
        gates: string[];           // the gates run at this group boundary
        open_findings: string[];   // the findings still open at this boundary
                                   // Both lists follow the `open_rows` shrink rule: written on
                                   // EVERY status, empty included, because a conditionally
                                   // written field can never shrink. A re-record that omitted
                                   // them would retain stale findings on a pass, or a coverage
                                   // claim the re-record never asserted.
                                   // status=failed is REFUSED with an empty open_findings.
        timestamp?: string;        // ISO 8601
      };
    };
  };
  dispatches: {                 // subagent dispatch records, keyed by ISO-8601 timestamp.
                                 // A MAP, not a list, for the same reason ceremony_history
                                 // is: the merge replaces lists wholesale, so a list would
                                 // lose every prior dispatch on the next sibling write --
                                 // in precisely the audit trail that proves a dispatch ran.
                                 // Collisions within one second (ordinary in parallel
                                 // waves) take a zero-padded `#NNN` suffix on the key.
                                 // The intended writer is the PostToolUse hook on the Task
                                 // tool, NOT the agent: a record authored by the party that
                                 // would have skipped the step is a checkbox with extra
                                 // steps. Every field but `recorded_at` and `skills` is
                                 // optional -- the hook records what the payload carried.
    [recorded_at: string]: {
      recorded_at: string;      // ISO 8601; duplicates the key this entry is stored under
      skills: string[];         // recognized DISPATCH_SKILLS names, sorted; always written
      subagent_type?: string;   // from the Task call; truncated to DESCRIPTION_MAX (200)
      description?: string;     // short description; truncated to DESCRIPTION_MAX
      source?: string;          // what wrote the record (default "cli"); truncated likewise
                                // The dispatch PROMPT is never stored -- it can carry file
                                // contents, credentials, and operator text. Only the skill
                                // names recognized out of it are.
    };
  };
}
```

**Defect register rows carry a `class:` tag.** The tag lives in the defect
register (plan/ledger-adjacent, not a `develop_gate_ledger` field), and the
orchestrator reads it to detect a recurring-defect shape: two open rows
sharing one `class:` tag.

**Writes go through `scripts/develop_gate_ledger.py`.** The Python
implementation is the only path that respects the merge contract --
it deep-merges, and refuses `section_24_6_check.status=failed` without
open rows. Ordinary `set` refuses to rewrite `ceremony.locked_at`; the
ONLY sanctioned path that supersedes a lock is `archive-ceremony`, which
archives the old `ceremony` block into `ceremony_history` before writing
a new one, and cannot run without a `--reason`. Hand-writing the
JSON is a full overwrite and will clobber sibling keys written by
other develop writes or by the spellbook hooks' `workflow_state` row;
do not do it. The CLI surface is intentionally narrow:

- `python3 scripts/develop_gate_ledger.py show [--field ceremony.locked_at]`
- `python3 scripts/develop_gate_ledger.py set <field> <value>` (top-level or `ceremony.*`,
  including `set ceremony.gate_position per_task|per_group` — refused once `locked_at`
  is set and a different position is already recorded; use `archive-ceremony` to reposition)
- `python3 scripts/develop_gate_ledger.py wave-discipline <wave_id> --status {passed|failed|n_a} [--open-rows W3a-2,W3a-5] [--timestamp ISO]`
- `python3 scripts/develop_gate_ledger.py archive-ceremony --reason "<text>" [--timestamp ISO]`
- `python3 scripts/develop_gate_ledger.py blocker <id> --type decision|work|external [--description "<text>"] [--close]`
- `python3 scripts/develop_gate_ledger.py group-gate <group_id> --status passed|failed|n_a [--gates ...] [--open-findings ...]` —
  writes `develop_gate_ledger.groups.<group_id>.gate_stack`; `status=failed` requires
  `--open-findings`, mirroring the wave-discipline guard.
- `python3 scripts/develop_gate_ledger.py wave-discipline <wave_id> --status n_a --reason "<text>"` —
  `n_a` without a reason records only that the check did not apply, never why, so
  the reason is what separates "the operator established this does not apply" from
  "nobody ran it".
- `python3 scripts/develop_gate_ledger.py record-dispatch [--subagent-type <text>] [--description "<text>"] [--prompt "<text>"] [--skill <skill>] [--source <text>] [--timestamp ISO]` —
  `--skill` is repeatable.
  writes `develop_gate_ledger.dispatches.<timestamp>`. `--prompt` is SCANNED for known
  skill names and then discarded; the prompt itself is never stored. Normally written
  by the `PostToolUse` hook on the `Task` tool, not by hand.
- `python3 scripts/develop_gate_ledger.py dispatches [--skill <skill>] [--since ISO]` —
  prints matching records as JSON and **exits 1 when none match**, so the invocation
  can BE a phase-verification checkbox rather than something the agent ticks itself.
  Pass `--since` for a per-task gate: without a lower bound, one dispatch recorded in
  task 1 satisfies the same query for every task after it.

When the skill tells you to "write the ledger", it means call this
CLI, not write the JSON yourself. The contract is enforced in Python
because it is enforced in Python; the LLM-side discipline is just
the trigger.

**Every `ceremony` field is a newline-joined SCALAR, for the same CRIT-1 reason as
`remaining_gates`: `_deep_merge` APPENDS lists but REPLACES scalars, so a list-valued
`declined` would accumulate forever and a list-valued `selected` could never shrink.
Write each as the authoritative full scalar; the merge replaces it wholesale.**


## Refusals

The CLI refuses rather than warns, because a warning the caller never reads
leaves the write exactly as done as no warning at all. Every refusal below
prints `error: <message>` to stderr and names the route to use instead. Each
named remedy is a real subcommand — a refusal pointing at a command argparse
rejects tells the reader to run something that cannot run.

**Exit codes.** `1` means the STORED ledger is not what the operation needs
(a `LedgerError`: corrupt file, malformed shape, a lock already set). `2` means
the CALLER asked for something the ledger does not accept (a `ValueError`:
unknown field, invalid value, a missing required argument). The split matters
when a caller branches on the result: `1` is "repair the ledger", `2` is "fix
the command".

### `set` refuses six structured fields

`set <field> <value>` writes a top-level scalar. Six top-level fields are JSON
objects that ACCUMULATE entries, and a bare `set` does not edit such an object —
it REPLACES it, discarding every entry under it at once, which is the audit
trail that exists to prove those entries were recorded. Each is refused and
routed to the recorder that owns it:

| Field | Use instead |
|-------|-------------|
| `ceremony` | `set ceremony.<field>` (or `archive-ceremony` to supersede it) |
| `ceremony_history` | the `archive-ceremony` command |
| `blockers` | the `blocker` command |
| `waves` | the `wave-discipline` command |
| `groups` | the `group-gate` command |
| `dispatches` | the `record-dispatch` command |

The refusal is UNCONDITIONAL — it does not depend on whether the ceremony is
locked. Collapsing one of these objects to a scalar is not a narrower version of
a legitimate operation; it is not one at all, and a guard that fired only after
the lock would leave the Phase-0 window wide open. Membership is exactly "has
another route": `need_flags` is an object too and is deliberately NOT refused,
because it has no dedicated recorder and refusing it would leave it unwritable
rather than write it correctly.

`set` also refuses any `field` containing `/` or `.` other than a `ceremony.*`
name, and refuses a `ceremony.<name>` that is not a known ceremony field.

### The ceremony lock

`ceremony.locked_at` is the lock, and its PRESENCE is what locks — never its
truthiness. A ledger holding `locked_at: ""` is locked; only an absent or `null`
stamp is unlocked. Testing truthiness once made a blank stamp a master key that
disengaged every guard at once.

- **A blank `locked_at` is refused on write** (exit 2). A stamp whose value is
  blank is a lock in name only: nothing can read it, and it would disengage the
  guards it is supposed to arm.
- **Rewriting `locked_at` to a different value is refused** (exit 1). The lock is
  set once and never rewritten. `archive-ceremony` is the only sanctioned path
  that supersedes it.
- **Repositioning `ceremony.gate_position` after the lock is refused** (exit 1).
  Re-asserting the SAME value is allowed, and a first write after the lock is
  allowed — the guard refuses a reposition, not the recording of the original
  selection. An invalid value (anything but `per_task`/`per_group`) is refused
  at exit 2 whether or not the ceremony is locked.

### The gate set may only escalate

After the lock, `selected`, `core` and `declined` stay writable in ONE DIRECTION
only — "the lock is a floor, not a ceiling":

- **`ceremony.selected` and `ceremony.core` may not SHRINK.** A write that drops
  an element is refused (exit 1) naming the dropped elements.
- **`ceremony.declined` may not GROW.** A write that adds an element is refused
  (exit 1) naming the added ones, because growing `declined` removes a gate from
  the run by the back door. `declined` shrinks legitimately on promotion.

The comparison is unconditional, not guarded on a truthy prior value. Locking
with NOTHING declined is the DEFAULT path (`source = "default_full"`), so a
guard that skipped an empty prior value would let a single post-lock
`set ceremony.declined <gate>` drop a gate in the most common configuration.
One element is one non-blank stripped line; order and blank lines carry no
meaning, so a reordering does not read as a change. `promotions` and the
remaining fields are unrestricted — they record history rather than the gate set.

De-escalation mid-run is not a thing. Every one of these refusals names the same
remedy: `archive-ceremony` and re-select in a fresh Phase 0.

### A malformed ledger shape is refused with a remedy, not a traceback

A ledger on disk can hold the wrong type where the shape says object or string —
an older ledger written through the `set ceremony <value>` bypass now closed, or
a hand edit, which this module's own docstring invites. This is the RECOVERY
path, and a traceback is most expensive exactly there: the reader is already
holding a broken ledger and trying to repair it.

- `ceremony` stored as a non-object → refused (exit 1) rather than raising
  `AttributeError`, naming `archive-ceremony` to move it to `ceremony_history`
  and clear it, then re-select in a fresh Phase 0.
- A ceremony field stored as a non-string where a newline-joined scalar belongs →
  refused (exit 1), naming which field is malformed, with the same remedy.
- The ledger file is not valid JSON → refused, rather than silently overwritten;
  rename the corrupt file aside and start a new ledger.
- The ledger file is valid JSON but not an object → refused.
- No home directory resolvable and the default path is needed → refused, naming
  the remedy: set `$SPELLBOOK_DEV_DIR`, or pass `--path`. It does NOT fall back
  to a directory under the cwd; that would exit 0 while reading and writing a
  ledger that is not the project's.

### False-pass guards on the recorders

A failure with nothing to fix reads exactly like a pass, so both status
recorders refuse one:

- `wave-discipline --status failed` with no `--open-rows` → refused (exit 2).
- `group-gate --status failed` with no `--open-findings` → refused (exit 2).
- Any `--status` outside `passed`/`failed`/`n_a` → refused (exit 2).

`archive-ceremony` refuses a blank or missing `--reason` (an archive with no
stated reason is exactly the unaudited supersede the lock prevents), and refuses
to run when there is no ceremony to archive.

`blocker` refuses to open without `--type` (the kind of a blocker is recorded at
open time and has no default), refuses `--close` on an id that was never opened
(closing a blocker that never opened would record a gate that never ran), and
refuses a `--type` on close that disagrees with the stored type — either the id
or the `--type` is wrong; omit `--type` to close.
