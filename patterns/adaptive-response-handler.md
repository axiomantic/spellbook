# Adaptive Response Handler (ARH) Pattern

## Invariant Principles

1. **User uncertainty = research opportunity**: "I don't know" triggers investigation, never guessing
2. **New information invalidates old questions**: Research results mandate question regeneration
3. **Detection precedes interpretation**: Classify response type before processing
4. **Evidence over assumption**: Rephrase with codebase findings, not hypotheticals
5. **User controls flow**: No iteration limits; explicit signals (skip/abort) respected immediately

## Response Classification

**Detection order (first match wins):**

| Type | Pattern | Action |
|------|---------|--------|
| DIRECT_ANSWER | `/^[A-D]$/i` | Update context, continue |
| USER_ABORT | `stop\|cancel\|exit\|abort\|quit` | Halt immediately |
| RESEARCH_REQUEST | `research this\|look into\|investigate` | Dispatch subagent |
| UNKNOWN | `don't know\|not sure\|unsure\|no idea` | Implicit research request |
| CLARIFICATION | `what do you mean\|explain\|rephrase` | Re-present with examples |
| SKIP | `skip\|n/a\|pass\|move on` | Mark excluded, continue |
| OPEN_ENDED | `.*` | Parse intent, confirm interpretation |

**Critical rules:**
- Empty response = CLARIFICATION
- Trim whitespace before detection
- Word boundaries (\b) prevent partial matches

## Handler Behaviors

<analysis>
Before processing any response:
1. What response type matches?
2. Does handler require research dispatch?
3. Will new info change remaining questions?
</analysis>

### UNKNOWN/RESEARCH_REQUEST
```
Dispatch subagent → Wait for results → Regenerate ALL category questions → Present updated questions
```
Subagent prompt: "Research: [topic]. Context: [current understanding]. Return: Specific findings with file paths."

### CLARIFICATION
Rephrase with codebase evidence. Provide concrete examples from research, not abstract definitions.

### OPEN_ENDED
Parse intent → Update context → Confirm: "I understand this as [interpretation]. Correct?"

<reflection>
After each response:
- Did interpretation match user intent?
- Should remaining questions regenerate?
- Is progress clear? Show "[Category]: N/M answered"
</reflection>

## Regeneration Protocol

**Trigger:** Research completes OR context-changing answer received

**Process:**
1. Re-run question generation with updated context
2. Compare old vs new questions
3. Present ONLY if meaningfully different

**Example transformation:**
- Before: "Should this feature use authentication?"
- After research: "JWT (8 files in src/api/) or OAuth (5 files in src/integrations/)?"

## Integration

Skills reference ARH via: `See patterns/adaptive-response-handler.md for ARH pattern`

**ARH is a prompt pattern, not executable code.** Claude reads instructions, follows them during execution. No runtime interpretation layer exists.

## Anti-Patterns

- Guessing when user says "I don't know" (MUST dispatch research)
- Keeping stale questions after new information
- Assuming multiple-choice compliance (detect type first)
- Iteration limits on clarification loops (user controls)
