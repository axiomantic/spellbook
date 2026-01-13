# Skill Schema

Canonical structure for all skills in `skills/*/SKILL.md`.

## Invariant Principles

1. **Structure enables validation** - Consistent format allows automated compliance checking
2. **Research-backed elements improve performance** - EmotionPrompt, NegativePrompt, Self-Check have empirical support
3. **Interoperability requires contracts** - Skills that call each other need explicit input/output definitions
4. **Compression preserves density** - Telegraphic language maximizes signal per token

## Required Elements

### 1. YAML Frontmatter

```yaml
---
name: skill-name
description: |
  Single paragraph. When to use this skill. Trigger phrases.
  Include examples if helpful for matching.
version: 1.0.0  # Optional but recommended
depends_on: []  # Optional: skills this skill invokes
---
```

### 2. Invariant Principles

3-5 numbered principles answering "WHY" not "WHAT". Declarative, not imperative.

```markdown
## Invariant Principles

1. **Principle Name** - Explanation of why this matters
2. **Principle Name** - Explanation of why this matters
3. **Principle Name** - Explanation of why this matters
```

### 3. Role (EmotionPrompt)

Professional identity with stakes. Research shows 8-115% improvement.

```markdown
<ROLE>
[Professional identity]. Reputation depends on [quality outcome].
</ROLE>
```

**Examples:**
- `Senior Security Auditor. Reputation depends on finding real vulnerabilities, not false positives.`
- `Scientific Skeptic + ISO 9001 Auditor. Claims are hypotheses. Verdicts require data.`

### 4. Reasoning Schema

Required XML tags that force deliberate thinking.

```markdown
## Reasoning Schema

<analysis>
Before [action], determine:
- [Question 1]
- [Question 2]
- [Question 3]
</analysis>

<reflection>
After [action], verify:
- [Verification 1]
- [Verification 2]
IF NO to ANY: [consequence]
</reflection>
```

### 5. Inputs

What context/data this skill expects when invoked.

```markdown
## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `context.feature_request` | Yes | User's feature description |
| `context.codebase_patterns` | No | Existing patterns from research |
```

### 6. Outputs

What this skill produces for downstream consumers.

```markdown
## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `design_document` | File | Design doc at specified path |
| `decision_log` | Inline | Key decisions made with rationale |
```

### 7. Workflow (if multi-phase)

```markdown
## Workflow

Phase 1: [Name]
  ├─ Step description
  └─ GATE: [quality gate]
    ↓
Phase 2: [Name]
  └─ ...
```

### 8. Evidence Requirements (where applicable)

```markdown
## Evidence Requirements

| Claim | Required Evidence |
|-------|-------------------|
| "Feature complete" | All tests pass, traced through code |
| "Secure" | No OWASP top 10 violations found |
```

### 9. Anti-Patterns (NegativePrompt)

Explicit prohibitions. Research shows 12-46% improvement from "do NOT" statements.

```markdown
## Anti-Patterns

<FORBIDDEN>
- [Thing to never do]
- [Another thing to never do]
</FORBIDDEN>
```

Or as table:

```markdown
## Anti-Patterns

| Pattern | Why Forbidden |
|---------|---------------|
| [Pattern] | [Consequence] |
```

### 10. Self-Check

Final verification before output.

```markdown
## Self-Check

Before completing:
- [ ] [Verification item]
- [ ] [Verification item]
- [ ] [Verification item]

If ANY unchecked: STOP and fix.
```

## Optional Elements

### Decision Matrix

For skills with branching logic:

```markdown
## Decision Matrix

| Condition | Action |
|-----------|--------|
| A AND B | Do X |
| A AND NOT B | Do Y |
```

### Common Issues Table

For debugging/troubleshooting skills:

```markdown
## Common Issues

| Problem | Cause | Solution |
|---------|-------|----------|
```

### Interoperability Notes

When skill is frequently called by others:

```markdown
## Called By

- `implementing-features` Phase 2.1
- `writing-plans` as prerequisite
```

## Validation Rules

1. YAML frontmatter MUST have `name` and `description`
2. MUST have "Invariant Principles" section with 3-5 items
3. MUST have `<analysis>` tag somewhere in document
4. MUST have `<reflection>` tag somewhere in document
5. SHOULD have `<ROLE>` or `<FORBIDDEN>` tag (EmotionPrompt/NegativePrompt)
6. SHOULD have "Inputs" section if called by other skills
7. SHOULD have "Outputs" section if produces artifacts
8. SHOULD have "Self-Check" section

## Token Budget

Target: <1000 tokens for core instructions. Telegraphic language. No articles where meaning is clear.

## Example Compliant Skill

```markdown
---
name: example-skill
description: Use when X happens or user says "do X"
version: 1.0.0
depends_on: [other-skill]
---

# Example Skill

<ROLE>
Expert in X. Reputation depends on Y.
</ROLE>

## Invariant Principles

1. **Principle** - Explanation
2. **Principle** - Explanation
3. **Principle** - Explanation

## Reasoning Schema

<analysis>
Before action:
- Question 1?
- Question 2?
</analysis>

<reflection>
After action:
- Verified X?
- Verified Y?
IF NO: Stop, fix.
</reflection>

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `context` | Yes | Description |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `result` | File | Description |

## Workflow

Phase 1 → Phase 2 → Done

<FORBIDDEN>
- Never do X
- Never do Y
</FORBIDDEN>

## Self-Check

- [ ] Verified A
- [ ] Verified B
```
