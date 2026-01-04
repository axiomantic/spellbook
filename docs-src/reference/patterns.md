# Patterns

Shared patterns used across skills and commands.

## Adaptive Response Handler (ARH)

A reusable pattern for processing AskUserQuestion responses in skills that need to handle user choices.

### Location

`patterns/adaptive-response-handler.md`

### Usage

Skills that use AskUserQuestion to gather preferences can reference this pattern for consistent response handling:

```markdown
Include the Adaptive Response Handler pattern for processing responses.
```

### Pattern Content

The ARH provides:

1. **Response parsing** - Extract user selections from AskUserQuestion responses
2. **Multi-select handling** - Process multiple selections correctly
3. **Custom input handling** - Handle "Other" responses with custom text
4. **Validation** - Verify responses match expected options

## Skill Invocation Pattern

Standard pattern for invoking skills from within other skills:

```
Use the Skill tool to invoke `<skill-name>` for [purpose].
```

## Subagent Delegation Pattern

Pattern for delegating work to subagents:

```
Launch a Task agent with:
- subagent_type: "general-purpose" (or specialized type)
- prompt: Detailed instructions with full context
- description: Brief summary for tracking
```

### Key Principles

1. **Full context** - Subagents don't see conversation history
2. **Explicit instructions** - Include everything needed
3. **Clear boundaries** - Define scope and exit criteria
4. **Output format** - Specify expected response format

## TodoWrite Integration

Skills should integrate with TodoWrite for progress tracking:

```python
# At skill start
TodoWrite([
    {"content": "Step 1", "status": "in_progress", "activeForm": "Doing step 1"},
    {"content": "Step 2", "status": "pending", "activeForm": "Doing step 2"},
])

# After completing each step
TodoWrite([
    {"content": "Step 1", "status": "completed", "activeForm": "Doing step 1"},
    {"content": "Step 2", "status": "in_progress", "activeForm": "Doing step 2"},
])
```

## Verification Pattern

Before claiming completion, verify with evidence:

```
1. Run verification commands
2. Capture output
3. Only claim success with passing evidence
4. Document any failures
```

See the `verification-before-completion` skill for the full pattern.
