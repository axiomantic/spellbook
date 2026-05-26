---
name: dispatching-sub-orchestrators
description: |
  DEPRECATED: The sub-orchestrator (CEO/Manager) execution mode has been removed.
  Spellbook now supports single-orchestrator dispatch only (direct / delegated).
  Nested subagent dispatch proved unreliable because dispatched subagents do not
  reliably have the Task tool, so a "Manager" sub-orchestrator could not dispatch
  its own gate sub-subagents. Use develop's single-orchestrator delegated mode
  instead; for very large efforts, checkpoint the `develop_gate_ledger` and
  hand off to a fresh session. The original body is preserved in ARCHIVE.md.
---

# Dispatching Sub-Orchestrators (Deprecated)

<CRITICAL>
This skill is deprecated. The `sub_orchestrators` execution mode (the CEO/Manager
nested-dispatch pattern) and the related `work_items` separate-session
decomposition mode have been removed from `develop` / `feature-implement`.

**Why it was removed:** the pattern depended on a "Manager" subagent dispatching
its own per-gate sub-subagents via the Task tool. In practice, dispatched
subagents do not reliably have the Task tool wired through, so Managers silently
degraded to inline execution and the intended per-gate context isolation was
lost. The single-orchestrator model is the only reliable dispatch topology.

**Migration:**
- Use `develop`'s single-orchestrator **delegated** execution mode: one
  orchestrator dispatches gate subagents directly.
- For very large features, do NOT nest orchestrators. Instead, checkpoint the
  `develop_gate_ledger` and hand off to a fresh `develop` session when the
  orchestrator's context approaches its limit.
- End-of-phase quality gates (comprehensive audit, full test suite, green-mirage
  audit, comprehensive fact-check, pre-PR claim validation) still run at the
  single orchestrator level.

**Provenance:** the original ~500-line skill body (CEO loop, Manager Dispatch
Template, gotchas) is preserved verbatim in
[`ARCHIVE.md`](./ARCHIVE.md) for historical reference. It is NOT live guidance.
</CRITICAL>

## Invariant Principles

1. **Deprecated** - Do not use this skill or the `sub_orchestrators` / `work_items`
   execution modes. Use `develop`'s single-orchestrator delegated mode instead.

<analysis>This skill is deprecated. Nested sub-orchestrator dispatch is unsupported because dispatched subagents lack a reliable Task tool. The original body lives in ARCHIVE.md.</analysis>
<reflection>If invoked, redirect the user to develop's single-orchestrator delegated mode, and point to the `develop_gate_ledger` checkpoint mechanism for very large efforts.</reflection>
