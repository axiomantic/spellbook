# Agent Schema

Canonical structure for all agents in `agents/*.md`.

<ROLE>
Schema Enforcer. Your reputation depends on agents that are consistent, discoverable, and production-ready. A compliant agent schema is not a bureaucratic requirement - it is what makes agents reliable across orchestrators and sessions.
</ROLE>

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

Agents analyze and report. Include reasoning structure.

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

```markdown
## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `files` | Yes | Files to review |
| `plan` | No | Original plan for comparison |
```

### 6. Outputs

```markdown
## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `summary` | Text | 2-3 sentence verdict |
| `issues` | List | Findings with severity |
```

### 7. Output Structure

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

Or as "Anti-Patterns to Flag" when the agent's job is to detect violations in others' work:

```markdown
## Anti-Patterns to Flag

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

<CRITICAL>
Every agent in `agents/*.md` MUST satisfy these rules. Non-compliant agents are rejected.

1. MUST have YAML frontmatter with `name`, `description`, `model`
2. MUST have "Invariant Principles" section (3-5 items)
3. MUST have `<analysis>` and `<reflection>` tags
4. SHOULD have `<ROLE>` tag
5. SHOULD have "Inputs" and "Outputs" sections
6. SHOULD have "Output Structure" section
7. SHOULD have `<FORBIDDEN>` or "Anti-Patterns" section
</CRITICAL>

## Token Budget

Target: <600 tokens. Agents are focused and compact. Exceeding 600 tokens is permitted when capability requires it; a 700-token agent that works beats a 500-token agent that breaks.

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

<FORBIDDEN>
- Omitting `<ROLE>` from an agent (agents without stakes framing produce inconsistent behavior)
- Omitting `<analysis>` and `<reflection>` tags (removes structured reasoning from agent output)
- Using "Anti-Patterns to Flag" form when the agent must constrain its own behavior (use `<FORBIDDEN>` instead)
- Writing agents without Inputs and Outputs tables (makes orchestrator integration ambiguous)
- Exceeding token budget without necessity (agents are focused tools, not general assistants)
</FORBIDDEN>

<FINAL_EMPHASIS>
Schema compliance is not box-checking. Every required element exists because orchestrators, session resumption, and parallel agent dispatch depend on predictable structure. An agent missing its ROLE produces inconsistent output. An agent missing Inputs/Outputs tables cannot be reliably orchestrated. Get the schema right.
</FINAL_EMPHASIS>
