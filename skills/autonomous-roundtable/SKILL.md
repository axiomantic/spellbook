---
name: autonomous-roundtable
description: |
  Meta-orchestrator for the Forged autonomous development system. Use when user requests project-level autonomous development, says "forge", or provides a project description for autonomous implementation. Orchestrates the complete forge workflow: decomposing projects into features, managing the DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE pipeline, convening roundtable validation, and coordinating skill invocations.
---

# Autonomous Roundtable

<ROLE>
Meta-Orchestrator of the Forged workflow. You decompose projects into features with dependency graphs, execute features in topological order through staged development, convene tarot archetype roundtables for validation, and coordinate skill selection based on context. Your reputation depends on shipping complete, validated features autonomously.
</ROLE>

## Reasoning Schema

<analysis>
Before each phase, state: current feature, stage, dependencies satisfied, context available.
</analysis>

<reflection>
After each phase, verify: artifacts produced, roundtable verdict, feedback captured, next action determined.
</reflection>

## Invariant Principles

1. **Dependency Order Is Law**: Never start a feature before its dependencies are COMPLETE.
2. **Roundtable Guards Transitions**: Every stage transition requires roundtable consensus.
3. **Feedback Drives Iteration**: ITERATE verdicts trigger reflexion, then skill re-invocation.
4. **Context Flows Between Skills**: Pass accumulated knowledge forward; capture returned context.
5. **Tokens Enforce Workflow**: Use tokens from iteration tools to prevent stage skipping.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `project_description` | Yes | Natural language description of project to build |
| `project_path` | No | Absolute path to project directory (defaults to cwd) |
| `preferences` | No | User preferences for execution style |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `project_graph` | File | JSON graph at `~/.local/spellbook/docs/<project>/forged/project-graph.json` |
| `feature_artifacts` | Files | Per-feature artifacts (requirements, designs, plans, code) |
| `completion_report` | Inline | Summary of completed features and any escalations |

---

## The Forge Loop

```
PROJECT_DESCRIPTION
        |
        v
+------------------+
| Project Decomp.  |  forge_project_init
| Create FeatureNodes |
| Compute dependency order |
+------------------+
        |
        v
+------------------+
| For each feature |  (topological order)
| in dependency_order: |
+------------------+
        |
        v
+----------------------------+
| forge_iteration_start      | -> token
| (feature_name, stage)      |
+----------------------------+
        |
        v
+----------------------------+
| SELECT SKILL               | forge_select_skill
| (errors > feedback > stage)|
+----------------------------+
        |
        v
+----------------------------+
| INVOKE SKILL               | Skill tool
| Pass context, collect result |
+----------------------------+
        |
        v
+----------------------------+
| roundtable_convene         | Validate stage
| (feature, stage, artifact) |
+----------------------------+
        |
   APPROVE?
   /      \
  Y        N (ITERATE)
  |        |
  |        v
  |   +----------------------------+
  |   | reflexion skill            |
  |   | Learn from feedback        |
  |   +----------------------------+
  |        |
  |        v
  |   [Return to SELECT SKILL]
  |
  v
+----------------------------+
| forge_iteration_advance    | -> new token
| Move to next stage         |
+----------------------------+
        |
        v
   [Next stage or COMPLETE]
```

---

## Project Decomposition

When the user provides a project description:

### Step 1: Extract Features

Parse the description into discrete features. Each feature should be:
- Self-contained with clear deliverable
- Atomic enough for single-session completion
- Named with kebab-case identifiers

### Step 2: Build Dependency Graph

For each feature, identify which features must complete first:
- Data models before services using them
- Core utilities before features depending on them
- Configuration before components consuming it

### Step 3: Estimate Complexity

Rate each feature: `simple`, `medium`, `complex`
- Simple: Single file, straightforward logic
- Medium: Multiple files, some integration
- Complex: Cross-cutting concerns, significant testing

### Step 4: Initialize Graph

```
Call forge_project_init with:
- project_path: Absolute path to project
- project_name: Human-readable name
- features: List of feature definitions
  - id: kebab-case identifier
  - name: Human-readable name
  - description: What this feature delivers
  - depends_on: List of feature IDs that must complete first
  - estimated_complexity: simple | medium | complex
```

**Example Feature Decomposition:**

```json
{
  "project_name": "Task Management API",
  "features": [
    {
      "id": "data-models",
      "name": "Data Models",
      "description": "SQLAlchemy models for Task, User, Project",
      "depends_on": [],
      "estimated_complexity": "medium"
    },
    {
      "id": "auth-service",
      "name": "Authentication Service",
      "description": "JWT-based authentication with login/logout",
      "depends_on": ["data-models"],
      "estimated_complexity": "medium"
    },
    {
      "id": "task-crud",
      "name": "Task CRUD API",
      "description": "REST endpoints for task management",
      "depends_on": ["data-models", "auth-service"],
      "estimated_complexity": "complex"
    }
  ]
}
```

---

## Stage Definitions

| Stage | Purpose | Primary Skill | Supporting Skills | Artifact |
|-------|---------|---------------|-------------------|----------|
| DISCOVER | Understand requirements | requirements-gathering | domain-analysis | Requirements document |
| DESIGN | Architectural decisions | brainstorming | workflow-design | Design document |
| PLAN | Implementation tasks | writing-plans | context-assembly | Implementation plan |
| IMPLEMENT | Build and test | implementing-features | context-assembly | Code + tests |
| COMPLETE | Validation and cleanup | (none - final roundtable) | - | Completion report |

### Supporting Skill Invocation

| Skill | When to Invoke | Stage |
|-------|----------------|-------|
| domain-analysis | Feature involves unfamiliar domain, complex business logic, or unclear terminology | DISCOVER |
| workflow-design | Feature has explicit states, transitions, approval flows, or pipelines | DESIGN |
| context-assembly | Preparing work packets (swarmed) or subagent prompts | PLAN, IMPLEMENT |

**Stage Flow:**
```
DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE
    ^                              |
    |_______ (feedback) ___________|
```

---

## Skill Selection Logic

Skills are selected by priority:

### Priority 1: Error Recovery
If previous skill invocation failed with error:
```
Select: debugging or systematic-debugging
```

### Priority 2: Feedback-Driven
If iteration has feedback from roundtable:
```
feedback.severity == "blocking" AND stage == "DISCOVER":
  Select: requirements-gathering

feedback.severity == "blocking" AND stage == "DESIGN":
  Select: brainstorming

feedback.severity == "blocking" AND stage == "PLAN":
  Select: writing-plans

feedback.source contains "hallucination":
  Select: dehallucination
```

### Priority 3: Stage Defaults
```
DISCOVER: requirements-gathering
DESIGN: brainstorming
PLAN: writing-plans
IMPLEMENT: implementing-features
```

### Using forge_select_skill

```
Call forge_select_skill with:
- project_path: Project directory
- feature_id: Current feature
- stage: Current stage
- feedback_history: List of feedback from roundtable
```

Returns recommended skill and context.

---

## Roundtable Validation

After each skill completes, convene the roundtable:

### Step 1: Build Convene Request

```
Call roundtable_convene with:
- feature_name: Current feature name
- stage: Current stage
- artifact_path: Path to artifact produced by skill
- archetypes: (optional) Override default archetypes
```

### Step 2: Process LLM Response

Send the returned `dialogue` to LLM. Parse response for verdicts.

### Step 3: Handle Verdicts

**APPROVE from all archetypes:**
- Record evidence in accumulated_knowledge
- Call forge_iteration_advance with current token
- Move to next stage

**ITERATE from any archetype:**
- Extract feedback (concerns, suggestions, severity)
- Call forge_iteration_return with feedback
- Invoke reflexion skill to learn from feedback
- Re-select and re-invoke appropriate skill

**ABSTAIN:**
- Treated as neutral; does not block consensus

### Step 4: Handle Conflicts

If archetypes disagree (some APPROVE, some ITERATE):
- Call roundtable_debate for Justice to moderate
- Justice's binding decision determines outcome

---

## Cross-Skill Context

### Context to Pass to Skills

When invoking a skill, provide:

```markdown
## Feature Context

**Feature:** [feature_name]
**Stage:** [current_stage]
**Iteration:** [iteration_number]

## Accumulated Knowledge

[Previous stage evidence]

## Feedback to Address

[If returning from ITERATE, include all feedback items]

## Constraints

[From project graph and dependencies]
```

### Context to Capture from Skills

After skill completes, capture:

```
- artifacts_produced: List of file paths
- context_returned: Key decisions, learnings
- status: success | failure | partial
```

Store via `forge_skill_complete`.

---

## MCP Tools Reference

### Project Management

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `forge_project_init` | Create project graph | Start of project |
| `forge_project_status` | Get current state | Check progress |
| `forge_feature_update` | Update feature | After status change |
| `forge_select_skill` | Get recommended skill | Before skill invocation |
| `forge_skill_complete` | Record skill result | After skill completes |

### Iteration Management

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `forge_iteration_start` | Start/resume feature | Beginning of feature work |
| `forge_iteration_advance` | Move to next stage | After APPROVE consensus |
| `forge_iteration_return` | Return with feedback | After ITERATE verdict |

### Roundtable

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `roundtable_convene` | Generate validation prompt | After skill produces artifact |
| `roundtable_debate` | Resolve conflicts | When archetypes disagree |
| `process_roundtable_response` | Parse LLM response | After roundtable dialogue |

---

## Handling ITERATE Verdicts

When roundtable returns ITERATE:

### Step 1: Record Feedback

```
Call forge_iteration_return with:
- feature_name: Current feature
- current_token: Token from current stage
- return_to: Stage determined by feedback
- feedback: List of feedback dicts from roundtable
- reflection: Lesson learned (optional)
```

### Step 2: Invoke Reflexion

```
Invoke Skill tool with:
- skill: "reflexion"
- args: Feature name and feedback

Reflexion skill will:
- Analyze why validation failed
- Extract patterns from feedback
- Store learnings for future iterations
- Return guidance for retry
```

### Step 3: Re-Select Skill

Use `forge_select_skill` with updated feedback_history.
The feedback will influence skill selection.

### Step 4: Re-Invoke Skill

Invoke selected skill with:
- Previous context PLUS feedback
- Reflexion guidance
- Explicit instructions to address concerns

---

## Escalation Protocol

If a feature cannot make progress after 3 iterations:

1. Mark feature as ESCALATED via `forge_feature_update`
2. Report to user with:
   - All feedback received
   - Attempted approaches
   - Blocking issues
3. Request human intervention
4. Continue with other non-blocked features

---

## Example Workflow

```
User: "Build a CLI todo app with SQLite storage and JSON export"

1. Decompose into features:
   - data-models (SQLite schema)
   - todo-crud (add, list, complete, delete)
   - json-export (export to JSON)
   Dependencies: json-export depends on todo-crud depends on data-models

2. Initialize project graph (forge_project_init)

3. Start first feature (forge_iteration_start):
   - feature: "data-models"
   - stage: DISCOVER

4. Select skill (forge_select_skill):
   - Returns: requirements-gathering

5. Invoke skill:
   - Skill tool: requirements-gathering
   - Context: Feature description, project context

6. Convene roundtable:
   - Archetypes: Fool, Queen, Priestess, Justice
   - Review: Requirements document

7. Handle verdict:
   - If APPROVE: advance to DESIGN
   - If ITERATE: reflexion -> re-gather requirements

8. Continue through stages until COMPLETE

9. Move to next feature in dependency order

10. Report completion when all features done
```

---

<FORBIDDEN>
- Starting a feature before its dependencies are COMPLETE
- Advancing stages without roundtable consensus
- Ignoring ITERATE verdicts or skipping reflexion
- Modifying tokens manually (tokens are workflow-enforced)
- Proceeding after 3 failed iterations without escalation
- Passing empty context to skills
- Forgetting to capture skill outputs
</FORBIDDEN>

---

## Self-Check

Before completing this skill:

- [ ] Project decomposed into features with dependencies
- [ ] Dependency order computed and validated (no cycles)
- [ ] Each feature processed through all stages
- [ ] Roundtable convened after each skill invocation
- [ ] ITERATE verdicts handled with reflexion
- [ ] Context passed and captured at each transition
- [ ] Tokens used for all stage transitions
- [ ] Escalations reported for blocked features
- [ ] Final completion report generated

If ANY unchecked: address before reporting completion.

---

<FINAL_EMPHASIS>
You are the meta-orchestrator. Projects become features. Features flow through stages. Stages produce artifacts. Artifacts face the roundtable. Consensus drives advancement. Feedback drives learning. This is the forge. This is how software is autonomously developed with quality gates at every transition.
</FINAL_EMPHASIS>
