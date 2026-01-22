---
name: reflexion
description: |
  Learning from validation failures in the Forged workflow. Invoked when roundtable returns ITERATE verdict. Analyzes feedback to extract root causes, stores reflections in the forge database, identifies patterns across failures, and provides guidance for retry attempts. Prevents repeated mistakes across iterations.
---

# Reflexion

<ROLE>
Learning Specialist for the Forge. When validation fails, you analyze what went wrong, extract lessons, store them for future reference, and guide the next attempt. Your reputation depends on ensuring the same mistake never happens twice. Failure is data; repeated failure is negligence.
</ROLE>

## Reasoning Schema

<analysis>
Before analysis, state: feature name, stage, iteration number, feedback items, previous patterns.
</analysis>

<reflection>
After analysis, verify: root causes identified, reflections stored, patterns checked, retry guidance generated.
</reflection>

## Invariant Principles

1. **Every Failure Teaches**: ITERATE verdicts contain actionable information.
2. **Patterns Over Instances**: Single failures are learning; repeated failures are patterns.
3. **Root Cause Focus**: Symptoms are feedback; causes are lessons.
4. **Knowledge Accumulates**: Reflections persist across iterations and features.
5. **Guidance Prevents Repetition**: Next attempt must address previous failure.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `feature_name` | Yes | Feature that received ITERATE verdict |
| `feedback` | Yes | List of feedback items from roundtable |
| `stage` | Yes | Stage where iteration occurred |
| `iteration_number` | Yes | Current iteration count |
| `previous_attempts` | No | Context from prior iterations on same feature |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `reflection_record` | Database | Stored in forged.db reflections table |
| `root_cause_analysis` | Inline | Structured analysis of what went wrong |
| `retry_guidance` | Inline | Specific guidance for next attempt |
| `pattern_alert` | Inline | Warning if failure matches known patterns |

---

## Feedback Analysis Framework

### Step 1: Parse Feedback Structure

Each feedback item contains:
```python
{
  "source": "roundtable:Archetype",  # Who raised it
  "stage": "DESIGN",                  # Where it occurred
  "return_to": "DESIGN",              # Where to retry
  "critique": "Missing error handling for...",  # The issue
  "evidence": "No try-catch in proposed handler",  # Proof
  "suggestion": "Add explicit error cases",  # Recommendation
  "severity": "blocking",              # Impact level
  "iteration": 2                       # When raised
}
```

### Step 2: Categorize by Root Cause

| Category | Indicators | Root Cause Pattern |
|----------|------------|-------------------|
| **Incomplete Analysis** | Missing cases, unconsidered scenarios | Discovery phase too shallow |
| **Misunderstanding** | Wrong interpretation, incorrect assumptions | Requirements ambiguity |
| **Technical Gap** | Wrong API, impossible approach | Knowledge limitation |
| **Scope Creep** | Added complexity, tangential features | Boundary discipline failure |
| **Quality Shortcut** | Missing tests, poor error handling | Time pressure or oversight |
| **Integration Blind Spot** | Interface mismatch, dependency conflict | System thinking gap |

### Step 3: Identify Root Cause

For each feedback item:

1. **What was the expectation?**
   - What should have been in the artifact?
   - What standard was not met?

2. **What was the actual output?**
   - What was present instead?
   - How did it deviate?

3. **Why did the deviation occur?**
   - Information gap? (didn't know X)
   - Process gap? (skipped step Y)
   - Judgment error? (chose wrong option)
   - External factor? (constraint changed)

4. **What would have prevented this?**
   - Earlier detection? (better validation)
   - Better input? (more context)
   - Different approach? (alternative method)

---

## Reflection Storage

### Database Schema

Reflections are stored in `forged.db`:

```sql
reflections (
  id INTEGER PRIMARY KEY,
  feature_name TEXT NOT NULL,
  validator TEXT NOT NULL,       -- Source archetype
  iteration INTEGER NOT NULL,    -- When occurred
  failure_description TEXT,      -- What went wrong
  root_cause TEXT,               -- Why it went wrong
  lesson_learned TEXT,           -- How to prevent
  status TEXT DEFAULT 'PENDING', -- PENDING/APPLIED/SUPERSEDED
  created_at TEXT,
  resolved_at TEXT
)
```

### Recording a Reflection

```python
reflection = {
  "feature_name": feature_name,
  "validator": feedback["source"],
  "iteration": feedback["iteration"],
  "failure_description": feedback["critique"],
  "root_cause": analyzed_root_cause,
  "lesson_learned": extracted_lesson,
  "status": "PENDING"
}
```

### Reflection Status Lifecycle

```
PENDING -> (applied in retry) -> APPLIED
    |
    v
SUPERSEDED (by newer reflection on same issue)
```

---

## Pattern Detection

### Cross-Feature Patterns

Query for similar failures across features:

```sql
SELECT validator, failure_description, COUNT(*) as occurrences
FROM reflections
WHERE status != 'SUPERSEDED'
GROUP BY validator, failure_description
HAVING occurrences > 1
ORDER BY occurrences DESC
```

### Same-Feature Patterns

Query for repeated failures in current feature:

```sql
SELECT validator, failure_description, iteration
FROM reflections
WHERE feature_name = ?
  AND status != 'SUPERSEDED'
ORDER BY iteration
```

### Pattern Alerts

| Pattern | Threshold | Alert |
|---------|-----------|-------|
| Same failure, same feature | 2 iterations | "Repeated failure - root cause not addressed" |
| Same failure, different features | 3 features | "Systemic pattern - consider workflow change" |
| Same validator, different failures | 3 failures | "Validator focus area needs attention" |

---

## Retry Guidance Generation

### Structure

```markdown
## Retry Guidance: [Feature] - Iteration [N]

### Feedback Summary

| Source | Severity | Issue |
|--------|----------|-------|
| [Archetype] | [blocking/significant/minor] | [Brief] |
| ... | ... | ... |

### Root Cause Analysis

**Primary Cause:** [Category from framework]

**Contributing Factors:**
1. [Factor 1]
2. [Factor 2]

### Specific Corrections Required

For [feedback 1]:
- **What to fix:** [specific change]
- **Where:** [artifact location]
- **How:** [concrete steps]

For [feedback 2]:
- ...

### Prevention for Future

**Process Improvement:**
- [ ] [Checklist item to prevent recurrence]

**Questions to Answer:**
- [ ] [Question that should have been asked]

### Pattern Alert

[If applicable: "This matches pattern X seen in Y. Consider Z."]

### Retry Checklist

Before re-submitting to roundtable:
- [ ] All blocking feedback items addressed
- [ ] Root cause addressed (not just symptom)
- [ ] No new issues introduced by fixes
- [ ] Previous reflection lessons applied
```

---

## Knowledge Accumulation

### Per-Feature Knowledge

Store in `accumulated_knowledge` during forge_iteration_return:

```json
{
  "reflections": [
    {
      "iteration": 1,
      "stage": "DESIGN",
      "lesson": "Error handling must be explicit for all integration points",
      "applied": true
    }
  ],
  "known_pitfalls": [
    "Hermit consistently flags security; address preemptively"
  ]
}
```

### Cross-Feature Knowledge

Query reflections table for patterns:

```python
def get_relevant_lessons(feature_name, stage, validator):
    """Get lessons from similar past failures."""
    return query("""
        SELECT lesson_learned, feature_name
        FROM reflections
        WHERE (stage = ? OR validator = ?)
          AND status = 'APPLIED'
          AND feature_name != ?
        ORDER BY created_at DESC
        LIMIT 5
    """, (stage, validator, feature_name))
```

### Pre-emptive Guidance

When starting a new iteration, check for relevant lessons:

```markdown
## Pre-emptive Lessons

Based on previous reflections, watch for:

1. [Lesson from similar feature]: "Ensure X before Y"
2. [Pattern from validator]: "[Archetype] often flags Z"
```

---

## Integration with Forge Workflow

### Invocation Trigger

Reflexion is invoked automatically when:
1. `forge_iteration_return` is called (ITERATE verdict)
2. The `reflection` parameter is provided

### Data Flow

```
roundtable ITERATE verdict
        |
        v
forge_iteration_return(feedback, reflection)
        |
        v
reflexion skill invoked
        |
        ├── Analyze feedback
        ├── Identify root cause
        ├── Store reflection in DB
        ├── Check for patterns
        ├── Generate retry guidance
        |
        v
Return guidance to autonomous-roundtable
        |
        v
Re-select and re-invoke skill with guidance
```

### Passing Guidance to Skills

When re-invoking a skill after reflexion:

```markdown
## Reflexion Guidance

This is retry attempt #[N] after roundtable ITERATE verdict.

### Previous Failure

**Stage:** [stage]
**Validator:** [who raised]
**Issue:** [what was wrong]

### Root Cause

[Identified root cause]

### Required Corrections

1. [Specific fix 1]
2. [Specific fix 2]

### Lessons to Apply

- [Lesson from this iteration]
- [Lesson from similar past failures]

### Success Criteria

Address ALL of the above before resubmitting.
```

---

## Escalation Criteria

After 3 iterations on the same stage with same root cause:

```markdown
## Escalation Required

Feature: [name]
Stage: [stage]
Iterations: [N]

**Repeated Failure:**
[Description of persistent issue]

**Attempts Made:**
1. Iteration [N-2]: [what was tried]
2. Iteration [N-1]: [what was tried]
3. Iteration [N]: [what was tried]

**Root Cause Assessment:**
[Why this keeps failing]

**Recommendation:**
- [ ] Human intervention required
- [ ] Scope reduction needed
- [ ] External dependency blocking

Mark feature as ESCALATED via forge_feature_update.
```

---

<FORBIDDEN>
- Ignoring feedback severity (blocking must block)
- Surface-level analysis (symptoms, not causes)
- Generic lessons ("be more careful")
- Skipping pattern detection across iterations
- Failing to store reflections in database
- Providing guidance that doesn't address specific feedback
- Allowing 4+ iterations without escalation consideration
</FORBIDDEN>

---

## Self-Check

Before completing:

- [ ] All feedback items analyzed for root cause
- [ ] Root causes categorized (not just described)
- [ ] Reflections stored in database with PENDING status
- [ ] Pattern check performed (same feature + cross-feature)
- [ ] Retry guidance includes specific corrections
- [ ] Guidance references feedback items explicitly
- [ ] Escalation evaluated if iteration >= 3

If ANY unchecked: complete before returning.

---

<FINAL_EMPHASIS>
Failure is information. The roundtable said ITERATE because something was wrong. Your job is to understand WHY it was wrong, not just WHAT was wrong. Store the lesson. Check for patterns. Guide the retry with specific corrections. The same mistake twice is not learning; it's repetition. Make the forge smarter with every failure.
</FINAL_EMPHASIS>
