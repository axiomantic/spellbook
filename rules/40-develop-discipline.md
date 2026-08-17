---
id: develop-discipline
name: Develop Skill Discipline
class: preference
default: "on"
description: >
  Phase non-fungibility inside the develop skill, and the thoroughness contract
  that invoking develop establishes.
benefit: >
  Stops the develop skill from collapsing its own phases into a single dispatch.
declining_means: >
  The agent may combine develop phases into one dispatch and may compress phases
  when it judges the work small or the session short.
related:
  - skills/develop
  - commands/feature-design
  - commands/feature-implement
  - commands/feature-implement-execute
renamed_from: []
superseded_by: null
paths: []
---

<CRITICAL>
### Develop Skill Discipline

Invoking develop is the operator's explicit opt-in to thoroughness. Two facts
bind for the whole run, from the moment develop is invoked:

- **The ceremony is chosen ONCE, at Phase 0, and LOCKED.** No operator phrasing
  during the run reopens it — not "wrap up", not "and pause", not "save tokens",
  not standing autonomous mode. A mid-run request to drop a gate is REFUSED. The
  two honest answers to "this is taking too long" are FINISH or ABORT-and-
  re-invoke. Escalation (adding a gate) is always legal; de-escalation never is.
- **Phases are non-fungible.** Inside /develop or any of its sub-skills, every
  Task() dispatch executes EXACTLY ONE row of the develop dispatch table, and
  must be preceded by a Phase Declaration citing the ledger line it satisfies.

The full and authoritative treatment — forbidden rationalizations,
ABORT-and-re-invoke, wave discipline (§24.6), stop semantics, and the incidentals
protocol — lives in `$SPELLBOOK_DIR/skills/develop/SKILL.md`.

**After a compaction mid-develop, RE-READ that file** before the next dispatch. A
compacted context has lost the ceremony lock and the gate semantics, and a run
that continues without them elides gates while reporting success.
</CRITICAL>
