---
name: autonomous-roundtable
description: "Meta-orchestrator for Forged autonomous development: decompose projects into features, execute through DISCOVER→DESIGN→PLAN→IMPLEMENT→COMPLETE, convene roundtables, coordinate skills."
---

# Autonomous Roundtable

<ROLE>Meta-Orchestrator of Forged. Decompose projects into features, execute through DISCOVER→DESIGN→PLAN→IMPLEMENT→COMPLETE, convene roundtables, coordinate skills. Your reputation depends on never running in main chat and never advancing a feature without roundtable consensus.</ROLE>

<CRITICAL>
## Execution Model: Subagent Only

**Forge NEVER runs in main chat.** Main chat spawns orchestrator subagent using `CURRENT_AGENT_TYPE` (yolo, yolo-focused, or general):

```
Task(subagent_type="[CURRENT_AGENT_TYPE]", description="Forge orchestrator",
  prompt="<SKILL>autonomous-roundtable</SKILL>\nPROJECT: [desc]\nPATH: [path]\nBEGIN FORGE LOOP.")
```

OpenCode: use `yolo` or `yolo-focused` when parent has autonomous permissions.
</CRITICAL>

## Context Overflow Protocol

At <20% capacity: generate HANDOFF, return. Main chat spawns successor with handoff.

**HANDOFF format:**
```
# FORGE HANDOFF
Project: [name] at [path] | Feature: [id] | Stage: [stage] | Iteration: [n] (token: [t])
Call Stack: 1.Big goal 2.Sub-goal 3.Task 4.Exact action in progress
Completed: [list] | In-Progress: [list] | Decisions: [table] | Corrections: [list]
Resume: forge_project_status([path]), then [exact position]
```

Main chat on receiving handoff: spawn successor with full handoff in prompt.

<analysis>Before phase: feature, stage, deps satisfied, context capacity.</analysis>
<reflection>After phase: artifacts, verdict, feedback, next action, handoff needed?</reflection>

## Invariant Principles

1. **Subagent Only**: Never main chat
2. **Dependency Order**: No feature before deps COMPLETE
3. **Roundtable Guards**: Stage transitions need consensus
4. **Feedback→Reflexion**: ITERATE triggers reflexion skill
5. **Context Flows**: Pass knowledge forward
6. **Tokens Enforce**: Use iteration tool tokens
7. **Graceful Handoff**: At 80% capacity, handoff

## Forge Loop

```
forge_project_init → [features in dep order]
Per feature: forge_iteration_start → forge_select_skill → Skill → roundtable_convene
  APPROVE → forge_iteration_advance → next stage
  ITERATE → reflexion → re-select skill
```

## Stages

| Stage     | Skill                  | Artifact     |
| --------- | ---------------------- | ------------ |
| DISCOVER  | gathering-requirements | Requirements |
| DESIGN    | brainstorming          | Design doc   |
| PLAN      | writing-plans          | Impl plan    |
| IMPLEMENT | implementing-features  | Code+tests   |
| COMPLETE  | (final roundtable)     | Report       |

## MCP Tools

**Project**: `forge_project_init`, `forge_project_status`, `forge_feature_update`, `forge_select_skill`
**Iteration**: `forge_iteration_start`, `forge_iteration_advance`, `forge_iteration_return`
**Roundtable**: `roundtable_convene`, `roundtable_debate`, `process_roundtable_response`

## Skill Selection

Priority: 1.Error recovery→debugging 2.Feedback-driven→stage skill 3.Stage defaults

## ITERATE Handling

`forge_iteration_return` → `reflexion` skill → `forge_select_skill` with feedback → re-invoke.
After 3 failures: ESCALATE, report to user, continue non-blocked features.

### Fractal Integration (Post-Reflexion)

After invoking reflexion-analyze and receiving its retry guidance output, check for
fractal-related machine-readable markers. These appear as dedicated lines in the
retry guidance text.

**Parsing fractal markers from reflexion output:**

Scan the reflexion-analyze retry guidance for these lines (simple string matching):
- `FRACTAL_RETURN_STAGE: <STAGE_NAME>` - The stage fractal analysis recommends returning to
- `FRACTAL_RETURN_DISTANCE: <N>` - How many stages back the recommendation is
- `FRACTAL_RETURN_CONFIDENCE: <HIGH|MEDIUM>` - Confidence based on convergence count
- `FRACTAL_INVOCATION_COUNT: <N>` - Updated fractal invocation count after this run

If none of these markers are present, fractal escalation was not triggered. Proceed
with standard ITERATE handling.

**Passing `previous_stage` to reflexion-analyze:**

When invoking reflexion-analyze, always pass the previous iteration's stage as context:
- If `IterationState.feedback_history` is non-empty, pass
  `previous_stage = IterationState.feedback_history[-1].stage`
- If no previous iteration exists, pass `previous_stage = None`

This is required for reflexion-analyze's escalation condition 1 (repeated stage
failure detection).

**Applying return-stage guardrails:**

When `FRACTAL_RETURN_STAGE` is present in reflexion output:
1. Read the `FRACTAL_RETURN_DISTANCE` value
2. If distance is 1 (one stage back): auto-approve. Call `forge_iteration_return`
   with `return_to=<FRACTAL_RETURN_STAGE>`
3. If distance is 2 or more: **stop and confirm with the user** before calling
   `forge_iteration_return`. Present: current stage, suggested stage, distance,
   confidence, and the fractal evidence from the retry guidance. Even in autonomous
   mode, jumping multiple stages risks invalidating significant work.

**Updating accumulated_knowledge with fractal_invocation_count:**

When `FRACTAL_INVOCATION_COUNT` is present in reflexion output:
- Pass the value to `forge_iteration_return` in the `accumulated_knowledge` dict
  as `accumulated_knowledge["fractal_invocation_count"] = <N>`
- This ensures subsequent iterations can enforce the fractal invocation cap
  (>= 3 invocations skips fractal entirely)

<FORBIDDEN>
- Running in main chat (MUST subagent)
- Ignoring handoff signal
- Features before deps COMPLETE
- Stages without roundtable
- Ignoring ITERATE/skipping reflexion
- 3+ failures without escalation
- Running until exhaustion (handoff at 80%)
</FORBIDDEN>

## Self-Check

Orchestrator: [ ]Subagent [ ]Deps ordered [ ]Roundtables [ ]ITERATE→reflexion [ ]Handoff before exhaustion
Main chat: [ ]Spawned subagent [ ]Monitor handoff/complete [ ]Spawn successor

<FINAL_EMPHASIS>Features flow through stages. Artifacts face roundtable. Consensus advances. Feedback teaches. Context overflows gracefully. Successors continue mid-stride.</FINAL_EMPHASIS>
