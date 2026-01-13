# Command Schema

Canonical structure for all commands in `commands/*.md`.

## Invariant Principles

1. **Commands are user-invocable** - Triggered by `/command-name`, not programmatic invocation
2. **Simpler than skills** - Commands are typically single-purpose, less orchestration
3. **Same quality standards** - Research-backed elements still apply
4. **Self-documenting** - Description must explain when to use

## Required Elements

### 1. YAML Frontmatter

```yaml
---
description: |
  Brief description of what command does.
  When user should invoke it.
---
```

Note: Commands use `description` only (no `name` - derived from filename).

### 2. Mission Statement

One sentence explaining the command's purpose.

```markdown
# MISSION
[Single sentence describing what this command accomplishes]
```

Or as header:

```markdown
# Command Name

[Purpose statement]
```

### 3. Invariant Principles

3-5 numbered principles. Same as skills.

```markdown
## Invariant Principles

1. **Principle** - Explanation
2. **Principle** - Explanation
3. **Principle** - Explanation
```

### 4. Role (EmotionPrompt)

Professional identity with stakes.

```markdown
<ROLE>
[Professional identity]. [Stakes statement].
</ROLE>
```

### 5. Reasoning Schema

Required for non-trivial commands.

```markdown
<analysis>
Before executing:
- [Question]
- [Question]
</analysis>

<reflection>
After executing:
- [Verification]
- [Verification]
</reflection>
```

### 6. Protocol/Steps

Clear execution flow.

```markdown
## Protocol

1. [Step]
2. [Step]
3. [Step]
```

Or workflow format for multi-phase commands.

### 7. Anti-Patterns (NegativePrompt)

```markdown
<FORBIDDEN>
- [Never do this]
- [Never do this]
</FORBIDDEN>
```

### 8. Self-Check (for complex commands)

```markdown
## Self-Check

Before completing:
- [ ] [Verification]
- [ ] [Verification]
```

## Optional Elements

### Inputs

If command takes arguments:

```markdown
## Inputs

| Argument | Required | Description |
|----------|----------|-------------|
| `path` | Yes | File to process |
```

### Outputs

If command produces artifacts:

```markdown
## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `report` | File | Generated report |
```

### Example Usage

```markdown
## Example

```
/command-name arg1 arg2
```
```

## Validation Rules

1. MUST have YAML frontmatter with `description`
2. MUST have mission/purpose statement
3. MUST have "Invariant Principles" or equivalent section (3-5 items)
4. SHOULD have `<analysis>` and `<reflection>` tags
5. SHOULD have `<ROLE>` or `<FORBIDDEN>` tag
6. SHOULD have clear protocol/steps

## Token Budget

Target: <800 tokens. Commands should be leaner than skills.

## Example Compliant Command

```markdown
---
description: Transform verbose instructions into compressed agentic prompts
---

# MISSION
Convert SOPs to high-performance prompts via principled compression.

<ROLE>
Prompt Engineer. Quality measured by token reduction without capability loss.
</ROLE>

## Invariant Principles

1. **Abstraction** - Declarative principles > imperative steps
2. **Evidence** - Claims require proof. "Done" without data = failure
3. **Compression** - Telegraphic language. Target <1000 tokens

<analysis>
Before transforming:
- What are the underlying principles?
- What's essential vs verbose?
</analysis>

<reflection>
After transforming:
- Did I extract WHY not WHAT?
- Is language telegraphic?
- Are reasoning tags present?
</reflection>

## Protocol

1. Extract invariant principles (3-5)
2. Design reasoning schema
3. Compress to telegraphic language
4. Add self-check block

<FORBIDDEN>
- Rephrasing steps without extracting principles
- Removing essential content for token count
- Omitting reasoning tags
</FORBIDDEN>
```
