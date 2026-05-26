---
name: autonomous-roundtable
description: |
  DEPRECATED: This skill has been absorbed into the develop skill. Use develop instead.
  The capabilities of autonomous-roundtable (project decomposition, roundtable gating,
  reflexion on ITERATE) are now available through develop's dialectic_mode and
  token_enforcement preferences. Set dialectic_mode to "roundtable" in Phase 0.4
  for equivalent behavior.
---

# Autonomous Roundtable (Deprecated)

<CRITICAL>
This skill is deprecated. Its functionality has been absorbed into the `develop` skill.

**Migration:**
- Project decomposition: develop no longer auto-decomposes into separate work items; use develop's single-orchestrator delegated execution and, for very large efforts, checkpoint the `develop_gate_ledger` and hand off to a fresh session
- Roundtable validation: Set `dialectic_mode: "roundtable"` in Phase 0.4 preferences
- Token enforcement: Set `token_enforcement: "gate_level"` or `"every_step"` in Phase 0.4
- Reflexion on ITERATE: Still invoked automatically by develop when roundtable returns ITERATE

**To use:** Invoke the `develop` skill instead. Configure dialectic preferences in Phase 0.4.
</CRITICAL>

## Invariant Principles

1. **Deprecated** - Do not use this skill. Use `develop` instead.

<analysis>This skill is deprecated. Redirect to develop skill.</analysis>
<reflection>If invoked, redirect user to the develop skill with dialectic_mode: "roundtable".</reflection>
