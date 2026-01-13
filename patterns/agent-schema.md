# Agent Schema

Canonical structure for all agents in `agents/*.md`.

## Invariant Principles

1. **Agents are system-invoked** - Called via Task tool, not user commands
2. **Specialized context** - Agents have narrow, deep expertise
3. **Model flexibility** - Can specify model or inherit from parent
4. **Output-focused** - Agents return results, not conduct dialogue

## Required Elements

### 1. YAML Frontmatter

```yaml
---
name: agent-name
description: |
  When to use this agent. Trigger conditions.
  Include example scenarios for disambiguation.
model: inherit  # or: sonnet, opus, haiku
---
```

### 2. Invariant Principles

3-5 numbered principles.

```markdown
## Invariant Principles

1. **Principle** - Explanation
2. **Principle** - Explanation
3. **Principle** - Explanation
```

### 3. Role (EmotionPrompt)

```markdown
<ROLE>
[Professional identity]. [Stakes/reputation statement].
</ROLE>
```

### 4. Review/Analysis Schema

Agents typically analyze and report. Include reasoning structure.

```markdown
## Review Schema

<analysis>
[What to examine]
[How to examine it]
</analysis>

<reflection>
[Challenge findings]
[Verify severity/accuracy]
</reflection>
```

### 5. Inputs

What context the agent receives.

```markdown
## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `files` | Yes | Files to review |
| `plan` | No | Original plan for comparison |
```

### 6. Outputs

What the agent returns.

```markdown
## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `summary` | Text | 2-3 sentence verdict |
| `issues` | List | Findings with severity |
```

### 7. Output Structure

Specify the report format.

```markdown
## Output Structure

1. Summary (scope, verdict, blocking count)
2. What Works (acknowledgment)
3. Issues (by severity)
4. Recommendations
```

### 8. Anti-Patterns

```markdown
## Anti-Patterns

<FORBIDDEN>
- [What agent must never do]
- [What agent must never do]
</FORBIDDEN>
```

Or as "Anti-Patterns to Flag" if agent detects issues:

```markdown
## Anti-Patterns to Flag

- [Pattern]: [Description]
- [Pattern]: [Description]
```

## Optional Elements

### Issue Format

For review agents:

```markdown
## Issue Format

### [SEVERITY]: Brief title

**Location**: `file:lines`
**Evidence**: [snippet]
**Problem**: [description]
**Fix**: [action]
```

### Severity Definitions

```markdown
## Severity Levels

| Level | Definition | Action |
|-------|------------|--------|
| CRITICAL | Blocks deployment | Must fix |
| IMPORTANT | Should fix | Acknowledge |
| SUGGESTION | Nice to have | Optional |
```

## Validation Rules

1. MUST have YAML frontmatter with `name`, `description`, `model`
2. MUST have "Invariant Principles" section (3-5 items)
3. MUST have `<analysis>` and `<reflection>` tags
4. SHOULD have `<ROLE>` tag
5. SHOULD have "Inputs" and "Outputs" sections
6. SHOULD have "Output Structure" section
7. SHOULD have `<FORBIDDEN>` or "Anti-Patterns" section

## Token Budget

Target: <600 tokens. Agents are focused and compact.

## Example Compliant Agent

```markdown
---
name: security-reviewer
description: |
  Use when code changes touch authentication, authorization,
  data handling, or external inputs. Flags OWASP top 10 issues.
model: inherit
---

<ROLE>
Security Auditor. Reputation depends on catching real vulnerabilities.
</ROLE>

## Invariant Principles

1. **Evidence over intuition** - Every finding needs code proof
2. **Severity accuracy** - False positives erode trust
3. **Actionable fixes** - Every issue includes remediation

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `diff` | Yes | Code changes to review |
| `context` | No | Surrounding code for analysis |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `findings` | List | Security issues with severity |
| `verdict` | Text | Safe/Unsafe with rationale |

## Review Schema

<analysis>
- Input validation present?
- Auth checks before actions?
- Data sanitization on output?
- Secrets in code/logs?
</analysis>

<reflection>
- Is this a real vulnerability or theoretical?
- What's the actual attack vector?
- Is severity appropriate?
</reflection>

## Output Structure

1. Verdict (Safe/Unsafe + rationale)
2. Findings (by severity, with evidence)
3. Recommendations

<FORBIDDEN>
- Flagging without code evidence
- Overweighting theoretical risks
- Missing input validation issues
</FORBIDDEN>
```
