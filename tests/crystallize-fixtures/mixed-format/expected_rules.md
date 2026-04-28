## Rules

<RULE>NEVER call `/sharpen-improve` from inside a `develop` subagent.</RULE>
<!-- rule-meta: id=R1, added=2026-04-27, pass=1, last-confirmed=2026-04-27 -->

<RULE>ALWAYS verify the worker's manifest hash before accepting the result.</RULE>
<!-- rule-meta: id=R2, added=2026-04-27, pass=1, last-confirmed=2026-04-27 -->

<RULE>The operator MUST run `/crystallize-verify` on the output of every Phase 1 crystallize pass before merging.</RULE>
<!-- rule-meta: id=R3, added=2026-04-27, pass=1, last-confirmed=2026-04-27 -->
