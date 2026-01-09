# Structured Output Contract Pattern

## Purpose
Define explicit output schemas to reduce LLM verbosity and ensure consistent, parseable responses.

## Benefits

| Benefit | Impact |
|---------|--------|
| Reduces output tokens | LLM doesn't explain what it's returning |
| Enables automation | Downstream tools can parse output |
| Improves consistency | Same format every time |
| Clarifies expectations | LLM knows exactly what to produce |

## Contract Format

In skill SKILL.md, add an Output Contract section:

```markdown
## Output Contract

Return ONLY the following JSON structure. No explanation, no preamble.

```json
{
  "status": "success" | "failure" | "partial",
  "result": {
    // Specific fields for this skill
  },
  "metadata": {
    "tokens_used": number,
    "duration_ms": number
  }
}
```

### Field Definitions
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| status | enum | yes | Outcome status |
| result | object | yes | Skill-specific payload |
```

## Contract Types

### Report Contract
For skills that produce reports:
```json
{
  "title": "string",
  "summary": "string (max 100 words)",
  "findings": [{"severity": "high|medium|low", "item": "string", "recommendation": "string"}],
  "metrics": {"key": "value"}
}
```

### Analysis Contract
For skills that analyze code/content:
```json
{
  "files_analyzed": ["path"],
  "issues": [{"file": "path", "line": number, "issue": "string", "fix": "string"}],
  "summary": {"total_issues": number, "by_severity": {"high": n, "medium": n, "low": n}}
}
```

### Action Contract
For skills that perform actions:
```json
{
  "actions_taken": [{"action": "string", "target": "string", "result": "success|failed"}],
  "rollback_possible": boolean,
  "next_steps": ["string"]
}
```

## Enforcement

Add to skill:
```markdown
## Output Rules
1. Return ONLY the JSON structure defined above
2. No markdown formatting around JSON
3. No explanatory text before or after
4. If unable to complete, return with status: "failure" and error in result
```

## Usage in Skills

```markdown
## Output Contract
See patterns/structured-output-contract.md for format guidelines.

This skill returns:
```json
{
  "status": "success" | "failure",
  "optimizations": [{...}],
  "total_savings": number
}
```
```

## When NOT to Use

- Interactive skills (user dialogue)
- Creative output (writing, personas)
- Exploratory tasks (research, investigation)

Use for: audits, analysis, transformations, validations.
