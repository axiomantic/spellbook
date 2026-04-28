# Example SOP — Mixed Rule Forms

This SOP demonstrates the three rule input forms `/crystallize` must lift into
the canonical Rules section: an inline `<RULE>` tag, a MUST/NEVER prose line
with named scope, and a pre-existing `## Rules` heading from a prior pass.

## Mission

Run a small task that exercises all three rule-detection signals.

## Rules

<RULE>NEVER call `/sharpen-improve` from inside a `develop` subagent.</RULE>
<!-- rule-meta: id=R1, added=2026-04-27, pass=1, last-confirmed=2026-04-27 -->

## Phase 1

Some narrative about Phase 1. The orchestrator dispatches a worker, the worker
returns a result, the orchestrator validates the result. There is no rule in
this paragraph; it is descriptive prose.

<RULE>ALWAYS verify the worker's manifest hash before accepting the result.</RULE>

## Phase 2

The operator MUST run `/crystallize-verify` on the output of every Phase 1
crystallize pass before merging. This is a named-scope imperative directive
and must be lifted into the Rules section.

More narrative below the rule. This paragraph is not a rule; it is general
guidance about why verification matters.
