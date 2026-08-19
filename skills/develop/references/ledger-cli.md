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

When the skill tells you to "write the ledger", it means call this
CLI, not write the JSON yourself. The contract is enforced in Python
because it is enforced in Python; the LLM-side discipline is just
the trigger.

**Every `ceremony` field is a newline-joined SCALAR, for the same CRIT-1 reason as
`remaining_gates`: `_deep_merge` APPENDS lists but REPLACES scalars, so a list-valued
`declined` would accumulate forever and a list-valued `selected` could never shrink.
Write each as the authoritative full scalar; the merge replaces it wholesale.**

