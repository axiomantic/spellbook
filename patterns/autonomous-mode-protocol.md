# Autonomous Mode Protocol

Protocol for skills operating without user interaction.

## Invariant Principles

1. **Progress Over Permission** - Available context sufficient for reasonable decisions; asking wastes cycles
2. **Transparency Via Documentation** - Decisions logged with rationale enable post-hoc review without synchronous approval
3. **Circuit Breakers Protect Against Runaway** - Specific conditions halt execution; prevents compounding errors
4. **Report, Never Ask** - When paused, state problem + options + recommendation; user decides, agent waits

## Reasoning Schema

```
<analysis>
- Current state: [what attempting]
- Context available: [relevant info]
- Decision space: [options with tradeoffs]
</analysis>

<reflection>
- Circuit breaker check: [pass/fail + why]
- Confidence: [high/medium/low]
- Action: [proceed/pause]
</reflection>
```

## Default Behaviors

| Situation | Action | Rationale |
|-----------|--------|-----------|
| Ambiguous requirements | Choose simplest, document alternatives | Reversible; keeps momentum |
| Multiple valid approaches | Follow existing codebase patterns | Consistency over novelty |
| Minor test failures | Log, proceed unless 3+ consecutive | Flaky tests common; repeated = real |
| Missing optional context | Sensible defaults | Optional means dispensable |

## Universal Circuit Breakers

Halt execution when ANY triggered:

- **Security-critical** - No guidance, stakes high
- **Contradiction** - Requirements mutually exclusive
- **Repeated failure** - 3+ attempts same fix (loop detected)
- **Missing critical context** - Progress impossible

## Circuit Breaker Output Format

```markdown
## Circuit Breaker Triggered

**Type:** [Security | Contradiction | Repeated Failure | Missing Context]
**Skill:** [skill-name]
**Phase:** [current phase/step]

**Condition:** [what triggered]

**Context:** [evidence that led here]

**Options:**
A) [option + tradeoff]
B) [option + tradeoff]
C) [option + tradeoff]

**Recommended:** [letter] - [rationale]

**Awaiting:** User decision
```

## Mode Transitions

**Enter autonomous when:**
- `autonomous_mode: "autonomous"` in preferences
- Subagent dispatched with full context
- Explicit instruction: "Mode: AUTONOMOUS"

**Exit autonomous when:**
- Circuit breaker triggered
- Phase requires approval (interactive/mostly_autonomous modes)
- Task complete

## Skill Integration

Skills supporting autonomous mode MUST define:

1. `### Autonomous Mode Behavior` - What changes when autonomous
2. `### Circuit Breakers (Still Pause For)` - Skill-specific halt conditions
3. Reference: `See patterns/autonomous-mode-protocol.md`

## Related

- [Adaptive Response Handler](adaptive-response-handler.md) - Processing user responses
- Skills using protocol: `brainstorming`, `implementing-features`, `executing-plans`, `writing-plans`, `using-git-worktrees`
