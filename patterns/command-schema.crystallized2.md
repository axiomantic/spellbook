# Command Schema

<CRITICAL>
Commands are the public API of spellbook. A malformed command schema breaks every author who reads it and every agent who runs it. Precision here is not optional.
</CRITICAL>

Canonical structure for all commands in `commands/*.md`.

<ROLE>
Command Schema Author. Your reputation depends on commands that behave consistently, model correct patterns, and teach by example.
</ROLE>

## Invariant Principles

1. **User-invocable** - Triggered by `/command-name`, not programmatic invocation
2. **Simpler than skills** - Single-purpose, minimal orchestration
3. **Research-backed quality** - `<ROLE>`, `<FORBIDDEN>`, reasoning tags all apply
4. **Self-documenting** - `description` frontmatter must explain when to invoke

## Required Elements

### 1. YAML Frontmatter

```yaml
---
description: |
  Brief description of what command does.
  When user should invoke it.
---
```

Note: `description` only — `name` is derived from filename.

### 2. Mission Statement

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

```markdown
<ROLE>
[Professional identity]. [Stakes statement].
</ROLE>
```

### 5. Reasoning Schema

Required for commands with branching logic, validation, or multi-step execution. Trivial single-step commands (e.g., lookup, display) may omit.

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

```markdown
## Protocol

1. [Step]
2. [Step]
3. [Step]
```

For multi-phase commands, use phase headers with numbered steps per phase.

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

<FORBIDDEN>
- Omitting `<ROLE>` from a non-trivial command
- Omitting `<FORBIDDEN>` from a non-trivial command
- Omitting reasoning tags from commands with branching logic, validation, or multi-step execution
- Treating the <800 token budget as a ceiling that forces removal of essential content
- Omitting the "If command takes arguments:" / "If command produces artifacts:" framing from Optional Elements
</FORBIDDEN>

<FINAL_EMPHASIS>
Every command in this codebase is read by both humans and agents. A schema that omits emotional anchors, negative constraints, or reasoning structure produces commands that fail silently. Model the full schema. Require the full schema.
</FINAL_EMPHASIS>
