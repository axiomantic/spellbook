# Example SOP — Already Crystallized

This document is the output of a prior `/crystallize` pass. Re-running
`/crystallize` over it must preserve every rule in the canonical Rules
section verbatim, only advancing the `last-confirmed` provenance field on
rules that are unchanged.

## Mission

Demonstrate re-crystallization byte-fidelity for an already-crystallized
input.

## Rules

<RULE>NEVER call `/sharpen-improve` from inside a `develop` subagent.</RULE>
<!-- rule-meta: id=R1, added=2026-04-20, pass=1, last-confirmed=2026-04-20 -->

<RULE>ALWAYS verify the worker's manifest hash before accepting the result.</RULE>
<!-- rule-meta: id=R2, added=2026-04-20, pass=1, last-confirmed=2026-04-20 -->

<RULE>The operator MUST run `/crystallize-verify` on the output of every Phase 1 crystallize pass before merging.</RULE>
<!-- rule-meta: id=R3, added=2026-04-20, pass=1, last-confirmed=2026-04-20 -->

## Phase 1

General guidance for Phase 1 lives here. This content is residual prose,
subject to compression on the new pass. None of it is a rule; the rules are
all already lifted above.
