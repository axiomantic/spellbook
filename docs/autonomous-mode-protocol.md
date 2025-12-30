# Autonomous Mode Protocol

## Overview

This protocol defines how skills should behave when invoked in autonomous mode. It enables fully autonomous execution while preserving the ability to pause for genuinely critical decisions.

## Context Detection

Skills receive autonomous mode context from orchestrating skills (like `implement-feature`) via the subagent prompt. Look for these patterns:

```
User's autonomous mode: autonomous
Autonomous mode: true
AUTONOMOUS MODE ACTIVE
```

When autonomous mode is detected, follow the rules below.

## Core Rules

### When Autonomous Mode is Active

1. **DO NOT ask clarifying questions** - Use the context provided
2. **DO NOT pause for validation** - Proceed with reasonable decisions
3. **DO NOT offer choices** - Pick the best option and document why
4. **DO document assumptions** - Record decisions made without user input
5. **DO proceed with urgency** - Complete the task without interruption

### Making Autonomous Decisions

When you would normally ask a question, instead:

1. **Check provided context** - The orchestrator should have supplied necessary information
2. **Apply domain knowledge** - Use best practices and sensible defaults
3. **Document the decision** - Note what you decided and why
4. **Continue executing** - Don't wait for confirmation

**Example:**
```
# Instead of asking:
"Should we use REST or GraphQL for this API?"

# In autonomous mode:
# Decision: Using REST
# Rationale: Codebase uses REST exclusively (see src/api/),
# no GraphQL dependencies present, simpler for CRUD operations.
# Proceeding with REST implementation.
```

## Circuit Breakers

Autonomous mode should be **overridden** for genuinely critical situations. These are rare and specific.

### Pause for These (Circuit Breakers)

| Category | Examples |
|----------|----------|
| **Irreversible destruction** | Deleting production data, removing critical files with no backup |
| **Security-sensitive** | Choosing auth mechanisms, handling secrets, changing permissions |
| **Contradictory requirements** | Design says X, but implementation plan says Y - cannot reconcile |
| **Missing critical context** | Cannot proceed without information that wasn't provided and can't be inferred |
| **Major architectural pivots** | Discovered the planned approach is fundamentally flawed |

### DO NOT Pause for These

| Category | Examples |
|----------|----------|
| **Style preferences** | Naming conventions, file organization, comment style |
| **Implementation details** | Which library to use, algorithm choice, data structure |
| **Validation checkpoints** | "Does this look right so far?" |
| **Offering options** | "Would you prefer A or B?" |
| **Minor ambiguity** | Can make reasonable assumption |

### Circuit Breaker Format

When a circuit breaker triggers, use this format:

```markdown
## AUTONOMOUS MODE PAUSED - Circuit Breaker Triggered

**Category:** [Irreversible/Security/Contradiction/Missing Context/Architectural]

**Situation:**
[Brief description of the blocking issue]

**Why this cannot be autonomously resolved:**
[Specific reason this requires human judgment]

**Options:**
1. [Option A with implications]
2. [Option B with implications]

**Recommendation:** [Your recommendation if you have one]

**To continue:** [What input is needed]
```

## Integration with Skills

### For Skill Authors

Add this section to skills that have interactive elements:

```markdown
## Autonomous Mode Behavior

When autonomous mode is active (check context for "autonomous mode: autonomous" or similar):

### Skip These Interactions
- [List questions/checkpoints this skill normally asks]

### Make These Decisions Autonomously
- [Decision]: [Default/heuristic to use]
- [Decision]: [Default/heuristic to use]

### Circuit Breakers (Still Pause For)
- [Situation that requires human input even in autonomous mode]
```

### For Orchestrator Skills

When dispatching subagents in autonomous mode:

1. **Front-load all discovery** - Collect user input BEFORE dispatching subagents
2. **Provide rich context** - Include everything the skill might need to ask about
3. **Explicitly state mode** - Include clear autonomous mode indicator
4. **Include circuit breaker instructions** - Tell subagent when to pause

**Template for subagent prompts:**

```markdown
## Autonomous Mode Context

**Mode:** AUTONOMOUS - Proceed without asking questions
**Circuit breakers:** Only pause for [specific conditions]

## Pre-Collected Context

[All information the skill would normally ask for]

- Feature purpose: [...]
- Constraints: [...]
- Success criteria: [...]
- Relevant codebase patterns: [...]
- User preferences: [...]

## Task

[What the skill should do]

If you encounter a circuit breaker condition, format your response using
the Circuit Breaker Format and stop. Otherwise, complete the full task.
```

## Assumption Documentation

When making autonomous decisions, document them in a consistent format:

```markdown
## Autonomous Decisions Made

| Decision | Chosen | Rationale | Alternatives Considered |
|----------|--------|-----------|------------------------|
| API style | REST | Matches existing codebase | GraphQL (rejected: no existing infra) |
| Auth | JWT | Per design doc section 3.2 | Session (rejected: design specifies stateless) |
| Test framework | pytest | Project standard | unittest (rejected: inconsistent with codebase) |
```

This documentation:
- Creates audit trail for review
- Enables course correction if needed
- Shows reasoning was sound

## Escalation Path

If autonomous mode causes problems:

1. **Minor issues** - Fix during code review, note for future
2. **Medium issues** - Add to circuit breaker list for this skill
3. **Major issues** - Revisit whether this decision category should require user input

The goal is continuous refinement: start autonomous, add circuit breakers only where genuinely needed.
