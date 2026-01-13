# Structured Output Contract Pattern

## Invariant Principles

1. **Explicitness eliminates ambiguity** - Schema definition removes guesswork from both producer and consumer
2. **Parsability enables automation** - Machine-readable output unlocks downstream tooling
3. **Constraints reduce waste** - Bounded formats prevent verbose explanations
4. **Failure is a valid output** - Error states must be expressible within the schema
5. **Context determines applicability** - Interactive/creative tasks require natural language

## Declarative Principles

| Principle | Rationale |
|-----------|-----------|
| Output = JSON only, no wrapper | Eliminates parsing complexity |
| Status field required | Consumer knows outcome immediately |
| Field definitions explicit | No implicit assumptions about types |
| Error encoded in schema | Failures don't break contract |

## Output Contract Schema

<analysis>
Identify skill type to select appropriate contract:
- Report: findings, recommendations, metrics
- Analysis: files, issues, fixes
- Action: changes made, rollback capability
</analysis>

### Core Structure
```json
{
  "status": "success" | "failure" | "partial",
  "result": { /* skill-specific */ },
  "metadata": { "tokens_used": number, "duration_ms": number }
}
```

### Contract Types

**Report** - findings with severity, recommendations
```json
{"title": "string", "summary": "string", "findings": [{"severity": "high|medium|low", "item": "string", "recommendation": "string"}]}
```

**Analysis** - file-level issues with fixes
```json
{"files_analyzed": ["path"], "issues": [{"file": "path", "line": number, "issue": "string", "fix": "string"}]}
```

**Action** - changes with rollback info
```json
{"actions_taken": [{"action": "string", "target": "string", "result": "success|failed"}], "rollback_possible": boolean}
```

## Enforcement Rules

<reflection>
Before finalizing output:
- Is result valid JSON? (no markdown wrappers)
- Does status reflect actual outcome?
- Are all required fields present?
- Could consumer parse this without context?
</reflection>

1. Return ONLY JSON structure
2. No markdown formatting around JSON
3. No explanatory text before/after
4. Failure state = `status: "failure"` + error in result

## Applicability

**Use for:** audits, analysis, transformations, validations

**NOT for:** interactive dialogue, creative output, exploratory research
