# instruction-optimizer

"Use when instruction files (skills, prompts, CLAUDE.md) are too long or need token reduction while preserving capability"

## Skill Content

``````````markdown
# Instruction Optimizer

You optimize instruction files to reduce token count while preserving or improving their effectiveness.

## Core Principle

**SMARTER AND SMALLER, NOT DUMBER.**

Every optimization must pass this test: "Would a fresh agent following the optimized instructions produce equal or better results?"

## Trigger Conditions

- User asks to "optimize", "compress", "reduce tokens in" instructions
- User wants to "make X leaner", "tighten up", "streamline"
- After instruction-engineering, as a refinement pass
- When context window pressure is a concern

## Input

Either:
- A specific file path to optimize
- A directory of instruction files
- The current conversation's loaded skill/command

## Optimization Techniques

### 1. Semantic Deduplication
Remove content that says the same thing twice.

Before:
```
You must always verify. Never skip verification. Verification is required.
```

After:
```
Always verify.
```

### 2. Example Reduction
Keep only examples that demonstrate unique cases.

Before:
```
Example 1: User says "hello" -> Respond with greeting
Example 2: User says "hi" -> Respond with greeting
Example 3: User says "hey" -> Respond with greeting
Example 4: User says "help" -> Show help menu
```

After:
```
Examples:
- Greeting ("hello", "hi", etc.) -> Respond with greeting
- "help" -> Show help menu
```

### 3. Verbose Phrase Compression

| Verbose | Compressed |
|---------|------------|
| "In order to" | "To" |
| "It is important to note that" | [delete] |
| "Make sure to" | [delete or just state the action] |
| "You should always" | "Always" |
| "Prior to doing X" | "Before X" |
| "In the event that" | "If" |
| "Due to the fact that" | "Because" |
| "At this point in time" | "Now" |
| "For the purpose of" | "To" / "For" |

### 4. Section Collapse
Merge sections with overlapping concerns.

Before:
```
## Input Validation
Validate all inputs.

## Error Handling
Handle errors from invalid inputs.

## Edge Cases
Consider edge cases in inputs.
```

After:
```
## Input Handling
Validate inputs, handle errors, consider edge cases.
```

### 5. Implicit Context Removal
Remove statements that are obvious from context.

Before:
```
# Code Review Skill
This skill is for reviewing code. When reviewing code, you should look at the code carefully.
```

After:
```
# Code Review Skill
[just start with what to do]
```

### 6. Table Compression
Convert verbose lists to tables when appropriate.

### 7. Conditional Flattening
Simplify nested conditionals.

Before:
```
If A:
  If B:
    If C:
      Do X
```

After:
```
If A and B and C: Do X
```

### 8. Workflow Linearization
Convert complex branching workflows to linear steps with conditions.

## Process

1. **Read** the instruction file completely
2. **Estimate** current token count (words * 1.3)
3. **Identify** optimization opportunities using techniques above
4. **Draft** optimized version
5. **Verify** no capability loss:
   - All trigger conditions preserved?
   - All edge cases handled?
   - All outputs specified?
   - Clarity maintained or improved?
6. **Calculate** savings
7. **Present** diff with before/after token counts

## Output Format

```markdown
## Optimization Report: [filename]

### Summary
- Before: ~X tokens
- After: ~Y tokens
- Savings: Z tokens (N%)

### Changes Made
1. [Technique]: [Description] (-N tokens)
2. ...

### Capability Verification
- [ ] All triggers preserved
- [ ] All edge cases handled
- [ ] All outputs specified
- [ ] Clarity maintained

### Optimized Content
[full optimized file content]
```

## Constraints

- NEVER remove functionality
- NEVER make instructions ambiguous
- NEVER sacrifice clarity for brevity when clarity matters
- Preserve all edge case handling
- Keep examples that demonstrate UNIQUE behaviors
- Maintain consistent terminology (don't introduce synonyms)
- Preserve structured output formats exactly

## When NOT to Optimize

- Instructions that are already minimal
- Safety-critical sections (keep verbose for clarity)
- Sections with legal/compliance requirements
- Recently-written instructions (let them stabilize first)
``````````
