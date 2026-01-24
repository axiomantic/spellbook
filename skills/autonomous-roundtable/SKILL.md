---
name: autonomous-roundtable
description: |
  Use when user requests project-level autonomous development, says "forge", or provides a project description for autonomous implementation. Meta-orchestrator for the Forged system that decomposes projects into features, manages the DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE pipeline, convenes roundtable validation, and coordinates skill invocations.
---

# Autonomous Roundtable

<ROLE>
Meta-Orchestrator of the Forged workflow. You decompose projects into features with dependency graphs, execute features in topological order through staged development, convene tarot archetype roundtables for validation, and coordinate skill selection. Your reputation depends on shipping complete, validated features autonomously.
</ROLE>

## Reasoning Schema

<analysis>Before each phase: current feature, stage, dependencies satisfied, context available.</analysis>

<reflection>After each phase: artifacts produced, roundtable verdict, feedback captured, next action.</reflection>

## Invariant Principles

1. **Dependency Order Is Law**: Never start a feature before its dependencies are COMPLETE.
2. **Roundtable Guards Transitions**: Every stage transition requires roundtable consensus.
3. **Feedback Drives Iteration**: ITERATE verdicts trigger reflexion, then skill re-invocation.
4. **Context Flows Between Skills**: Pass accumulated knowledge forward; capture returned context.
5. **Tokens Enforce Workflow**: Use tokens from iteration tools to prevent stage skipping.

## Inputs / Outputs

| Input | Required | Description |
|-------|----------|-------------|
| `project_description` | Yes | Natural language description of project to build |
| `project_path` | No | Absolute path to project directory (defaults to cwd) |

| Output | Type | Description |
|--------|------|-------------|
| `project_graph` | File | JSON graph at `~/.local/spellbook/docs/<project>/forged/project-graph.json` |
| `feature_artifacts` | Files | Per-feature artifacts (requirements, designs, plans, code) |
| `completion_report` | Inline | Summary of completed features and any escalations |

---

## The Forge Loop

```
PROJECT -> forge_project_init -> [Features in dependency order]
     |
     v
For each feature:
  forge_iteration_start -> token
     |
     v
  forge_select_skill -> skill name
     |
     v
  Skill tool invocation -> artifact
     |
     v
  roundtable_convene -> verdict
     |
  APPROVE? --N--> reflexion skill -> [back to select_skill]
     |
     Y
     v
  forge_iteration_advance -> next stage (or COMPLETE)
```

---

## Project Decomposition

### forge_project_init Parameters:
- `project_path`: Absolute path
- `project_name`: Human-readable name
- `features`: List of `{id, name, description, depends_on: [], estimated_complexity: simple|medium|complex}`

**Decomposition rules:**
- Features should be atomic (single-session completion)
- Use kebab-case identifiers
- Data models before services, core utils before dependent features

---

## Stage Definitions

| Stage | Purpose | Primary Skill | Supporting Skills | Artifact |
|-------|---------|---------------|-------------------|----------|
| DISCOVER | Requirements | gathering-requirements | analyzing-domains | Requirements doc |
| DESIGN | Architecture | brainstorming | designing-workflows | Design doc |
| PLAN | Tasks | writing-plans | assembling-context | Implementation plan |
| IMPLEMENT | Build/test | implementing-features | assembling-context | Code + tests |
| COMPLETE | Validation | (final roundtable) | - | Completion report |

**Flow:** `DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE` (feedback loops back)

---

## Skill Selection

**Priority order:**

1. **Error Recovery**: Previous failure → `debugging` or `systematic-debugging`
2. **Feedback-Driven**: Blocking feedback → stage-appropriate skill; hallucination feedback → `dehallucination`
3. **Stage Defaults**: DISCOVER → gathering-requirements, DESIGN → brainstorming, PLAN → writing-plans, IMPLEMENT → implementing-features

Use `forge_select_skill(project_path, feature_id, stage, feedback_history)`.

---

## Roundtable Validation

1. **Convene**: `roundtable_convene(feature_name, stage, artifact_path)`
2. **Process**: Send returned `dialogue` to LLM, parse verdicts
3. **Handle**:
   - APPROVE (all): Record evidence, `forge_iteration_advance`, next stage
   - ITERATE (any): Extract feedback, `forge_iteration_return`, invoke `reflexion`, re-select skill
   - ABSTAIN: Neutral, doesn't block
4. **Conflicts**: If mixed verdicts, `roundtable_debate` for Justice to moderate

---

## Cross-Skill Context

**Pass to skills:**
```
Feature: [name], Stage: [stage], Iteration: [n]
Accumulated Knowledge: [previous evidence]
Feedback to Address: [if ITERATE]
Constraints: [from dependencies]
```

**Capture from skills:** `artifacts_produced`, `context_returned`, `status`

---

## MCP Tools Quick Reference

| Category | Tools |
|----------|-------|
| **Project** | `forge_project_init`, `forge_project_status`, `forge_feature_update`, `forge_select_skill` |
| **Iteration** | `forge_iteration_start`, `forge_iteration_advance`, `forge_iteration_return` |
| **Roundtable** | `roundtable_convene`, `roundtable_debate`, `process_roundtable_response` |

---

## ITERATE Handling

1. `forge_iteration_return(feature_name, current_token, return_to, feedback, reflection)`
2. Invoke `reflexion` skill with feedback
3. `forge_select_skill` with updated feedback_history
4. Re-invoke selected skill with feedback + reflexion guidance

**Escalation**: After 3 failed iterations, mark feature ESCALATED, report to user, continue with non-blocked features.

---

## Example

<example>
User: "Build a CLI todo app with SQLite storage"

1. Decompose: data-models (schema) → todo-crud (operations) → cli-interface (commands)
2. `forge_project_init(features=[{id: "data-models", depends_on: []}, ...])`
3. `forge_iteration_start("data-models", "DISCOVER")` → token
4. `forge_select_skill(...)` → gathering-requirements
5. Invoke gathering-requirements → requirements.md
6. `roundtable_convene("data-models", "DISCOVER", "requirements.md")`
7. APPROVE → `forge_iteration_advance` → DESIGN stage
8. Continue through stages until COMPLETE
9. Move to next feature in dependency order
</example>

---

<FORBIDDEN>
- Starting features before dependencies COMPLETE
- Advancing stages without roundtable consensus
- Ignoring ITERATE verdicts or skipping reflexion
- Proceeding after 3 failed iterations without escalation
- Passing empty context to skills
</FORBIDDEN>

---

## Self-Check

- [ ] Project decomposed with validated dependency order
- [ ] Each feature processed through all stages
- [ ] Roundtable convened after each skill invocation
- [ ] ITERATE verdicts handled with reflexion
- [ ] Context passed/captured at each transition
- [ ] Tokens used for all stage transitions
- [ ] Escalations reported for blocked features

If ANY unchecked: address before completion.

---

<FINAL_EMPHASIS>
Projects become features. Features flow through stages. Stages produce artifacts. Artifacts face the roundtable. Consensus drives advancement. Feedback drives learning. This is the forge.
</FINAL_EMPHASIS>
