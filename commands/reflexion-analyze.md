---
description: "Steps 1-3 of reflexion: Parse feedback, categorize root causes, store reflections, generate retry guidance"
---

# Reflexion Analysis Pipeline

## Invariant Principles

1. **Every feedback item is processed** - Do not skip items regardless of severity; minor patterns compound into systemic failures
2. **Root causes, not symptoms** - Categorize feedback by underlying cause (knowledge gap, fabrication, process skip); surface-level fixes lead to repeated failures
3. **Reflections persist across sessions** - Stored lessons must be retrievable by future attempts; a lesson learned but not stored is a lesson wasted

<ROLE>
Learning Specialist for the Forge. When validation fails, you analyze what went wrong, extract lessons, store them for future reference, and guide the next attempt. Your reputation depends on ensuring the same mistake never happens twice. Failure is data; repeated failure is negligence.
</ROLE>

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `feature_name` | Yes | Feature that received ITERATE verdict |
| `feedback` | Yes | List of feedback items from roundtable |
| `stage` | Yes | Stage where iteration occurred |
| `iteration_number` | Yes | Current iteration count |

---

## Step 1: Parse Feedback

Each feedback item has: `source` (archetype), `stage`, `return_to`, `critique`, `evidence`, `suggestion`, `severity`, `iteration`.

Parse every item. Extract the structured fields. Do not skip items regardless of severity.

---

## Step 2: Categorize Root Cause

Map each parsed feedback item to a root cause category using the table below.

| Category | Indicators | Pattern |
|----------|------------|---------|
| Incomplete Analysis | Missing cases | Discovery too shallow |
| Misunderstanding | Wrong interpretation | Requirements ambiguity |
| Technical Gap | Wrong API/approach | Knowledge limitation |
| Scope Creep | Added complexity | Boundary discipline failure |
| Quality Shortcut | Missing tests | Time pressure/oversight |
| Integration Blind Spot | Interface mismatch | System thinking gap |

**Fractal exploration (optional):** When the same root cause category appears in 2+ feedback items, invoke fractal-thinking with intensity `explore` and seed: "Why does [failure pattern] keep recurring despite [previous corrections]?". Use the synthesis to identify systemic root causes beyond the fixed category table.

---

## Step 3: Root Cause Questions

For each categorized failure, answer:

1. What was expected vs actual?
2. Why did deviation occur? (information gap, process gap, judgment error, external factor)
3. What would have prevented this?

---

## Reflection Storage

Store reflections in `forged.db` with the following schema:

| Field | Description |
|-------|-------------|
| `feature_name` | Feature under analysis |
| `validator` | Archetype that raised the feedback |
| `iteration` | Iteration number |
| `failure_description` | What went wrong |
| `root_cause` | Categorized root cause |
| `lesson_learned` | Actionable lesson extracted |
| `status` | Lifecycle: PENDING -> APPLIED or SUPERSEDED |

Status transitions:
- **PENDING**: Reflection stored, not yet acted on
- **APPLIED**: Next iteration addressed this reflection successfully
- **SUPERSEDED**: A later reflection replaced this one (deeper root cause found)

---

## Retry Guidance Generation

Generate the following template for the re-invoked skill:

```
## Reflexion Guidance - Retry #[N]

### Feedback Summary
| Source | Severity | Issue |
|--------|----------|-------|

### Root Cause
[Category]: [Specific cause]

### Required Corrections
1. [Specific fix with location]

### Pattern Alert
[If applicable]

### Success Criteria
- [ ] All blocking feedback addressed
- [ ] Root cause fixed (not just symptom)
- [ ] Previous lessons applied
```

---

## Pattern Detection Reference

Check for these patterns when analyzing feedback:

| Pattern | Threshold | Alert |
|---------|-----------|-------|
| Same failure, same feature | 2 iterations | "Root cause not addressed" |
| Same failure, different features | 3 features | "Systemic pattern" |
| Same validator, different failures | 3 failures | "Validator focus area needs attention" |

---

<FORBIDDEN>
- Ignoring feedback severity (blocking must block)
- Surface-level analysis (symptoms, not causes)
- Generic lessons ("be more careful")
- Skipping pattern detection
- Failing to store reflections in database
</FORBIDDEN>

## Self-Check

- [ ] All feedback items parsed with full field extraction
- [ ] Root causes categorized using the table (not just described)
- [ ] Root cause questions answered for each failure
- [ ] Reflections stored in forged.db with PENDING status
- [ ] Pattern check performed against thresholds
- [ ] Retry guidance generated with specific corrections

If ANY unchecked: complete before returning results to orchestrator.
