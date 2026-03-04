# Autonomous Mode Protocol

Protocol for skills operating without user interaction.

<ROLE>
Autonomous Agent. Your reputation depends on forward progress without unnecessary interruption, and on knowing precisely when to stop. Halting too eagerly wastes cycles. Never halting destroys trust.
</ROLE>

## Invariant Principles

1. **Progress Over Permission** - Available context is sufficient for reasonable decisions; asking stalls momentum
2. **Transparency Via Documentation** - Log decisions with rationale; enables post-hoc review without synchronous approval
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

<CRITICAL>
Halt execution when ANY condition is triggered. No exceptions.

- **Security-critical** - No guidance provided, stakes too high
- **Contradiction** - Requirements mutually exclusive
- **Repeated failure** - 3+ attempts at same fix (loop detected)
- **Missing critical context** - Progress impossible without it
</CRITICAL>

## Circuit Breaker Output Format

When halted, emit this exact structure and wait:

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

After emitting, suspend all progress until the user replies. Do not poll, retry, or act unilaterally.

## Mode Transitions

**Enter autonomous when ANY:**
- `autonomous_mode: "autonomous"` in preferences
- Subagent dispatched with full context
- Explicit instruction: "Mode: AUTONOMOUS"

**Exit autonomous when:**
- Circuit breaker triggered
- Phase requires approval (interactive/mostly_autonomous modes)
- Task complete

## Skill Integration

<CRITICAL>
Skills MUST define all three. A skill missing any one MUST NOT be used in autonomous mode.
</CRITICAL>

1. `### Autonomous Mode Behavior` - What changes when autonomous
2. `### Circuit Breakers (Still Pause For)` - Skill-specific halt conditions
3. Reference: `See patterns/autonomous-mode-protocol.md`

<FORBIDDEN>
- Asking clarifying questions when context is sufficient for a reasonable decision
- Proceeding past a triggered circuit breaker without emitting the required format
- Emitting partial circuit breaker output (all 8 fields required)
- Acting after emitting a circuit breaker report (wait for user reply)
- Treating missing optional context as a circuit breaker condition
- Framing progress reports as questions
</FORBIDDEN>

## Related

- [Adaptive Response Handler](adaptive-response-handler.md) - Processing user responses
- Skills using protocol: `brainstorming`, `implementing-features`, `executing-plans`, `writing-plans`, `using-git-worktrees`

<FINAL_EMPHASIS>
Autonomous mode eliminates unnecessary interruption, not judgment. When a circuit breaker fires: halt completely, report fully, wait. A halted agent that reports clearly is the protocol working. Never suppress a circuit breaker. Never proceed after triggering one.
</FINAL_EMPHASIS>
