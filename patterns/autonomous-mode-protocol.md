# Autonomous Mode Protocol

Protocol for skills operating in autonomous mode without user interaction.

## Overview

When a skill operates in **autonomous mode**, it proceeds without asking questions, making reasonable decisions based on available context. This protocol defines when and how to pause (circuit breakers) and the format for reporting issues.

## Autonomous Mode Principles

1. **Proceed without asking** - Use available context to make decisions
2. **Document decisions** - Log choices made and alternatives considered
3. **Respect circuit breakers** - Only pause for critical conditions
4. **Report, don't ask** - When pausing, report the issue clearly

## Default Behaviors in Autonomous Mode

| Situation | Default Action |
|-----------|---------------|
| Ambiguous requirements | Make reasonable choice, document rationale |
| Multiple valid approaches | Choose simplest approach, document alternatives |
| Minor test failures | Log and proceed (unless repeated) |
| Style/formatting questions | Follow existing codebase patterns |
| Missing optional context | Use sensible defaults |

## Circuit Breakers

Circuit breakers are conditions that REQUIRE pausing even in autonomous mode. Skills should define their specific circuit breakers, but common ones include:

### Universal Circuit Breakers
- **Security-critical decisions** with no guidance in context
- **Contradictory requirements** that cannot be reconciled
- **Repeated failures** (3+ attempts at same fix)
- **Missing critical context** that makes progress impossible

### Skill-Specific Circuit Breakers
Each skill may define additional circuit breakers in its `### Circuit Breakers (Still Pause For)` section.

## Circuit Breaker Format

When a circuit breaker is triggered, use this exact format:

```markdown
## Circuit Breaker Triggered

**Type:** [Security | Contradiction | Repeated Failure | Missing Context | Other]

**Skill:** [skill-name]

**Phase:** [current phase/step]

**Condition:**
[Describe what triggered the circuit breaker]

**Context:**
[Relevant information that led to this state]

**Options:**
A) [Option 1 - description]
B) [Option 2 - description]
C) [Option 3 - description]

**Recommended:** [A/B/C] - [brief rationale]

**Awaiting:** User decision to proceed
```

## Example Circuit Breaker Report

```markdown
## Circuit Breaker Triggered

**Type:** Contradiction

**Skill:** implementing-features

**Phase:** Phase 2.1 - Design Document Creation

**Condition:**
Design requirements specify both "stateless authentication" and "server-side session management" which are mutually exclusive approaches.

**Context:**
- Requirement A (line 45): "Use JWT tokens for stateless auth"
- Requirement B (line 89): "Maintain user sessions in Redis"
- These approaches conflict - JWT is stateless, Redis sessions are stateful

**Options:**
A) Use hybrid approach: JWT for auth, Redis for optional session data
B) Clarify with user which requirement takes priority
C) Default to JWT (more modern) and remove session requirement

**Recommended:** B - Requirements are contradictory, need user clarification

**Awaiting:** User decision to proceed
```

## Transitioning Between Modes

### Entering Autonomous Mode
Skills enter autonomous mode when:
- User sets `autonomous_mode: "autonomous"` in preferences
- Subagent is dispatched with full context (synthesis mode)
- Explicit instruction: "Mode: AUTONOMOUS"

### Exiting Autonomous Mode
Skills exit autonomous mode when:
- Circuit breaker is triggered
- Phase requires user approval (in "interactive" or "mostly_autonomous" modes)
- Task is complete

## Integration with Skills

### Skill Authors
When creating skills that support autonomous mode:

1. Define `### Autonomous Mode Behavior` section
2. List specific circuit breakers in `### Circuit Breakers (Still Pause For)`
3. Reference this protocol: `See patterns/autonomous-mode-protocol.md`
4. Use the Circuit Breaker Format when pausing

### Example Skill Integration

```markdown
## Autonomous Mode Behavior

When `autonomous_mode == "autonomous"`:
- Skip confirmation prompts
- Make default choices for ambiguous situations
- Log decisions for later review
- Only pause for circuit breakers

### Circuit Breakers (Still Pause For)
- Critical security decisions without guidance
- Contradictory requirements
- Repeated test failures (3+ consecutive)
- Missing required dependencies

Use the Circuit Breaker Format from patterns/autonomous-mode-protocol.md if pausing.
```

## Related Patterns

- [Adaptive Response Handler](adaptive-response-handler.md) - For processing user responses
- Skills using this protocol:
  - `brainstorming`
  - `implementing-features`
  - `executing-plans`
  - `writing-plans`
  - `using-git-worktrees`
