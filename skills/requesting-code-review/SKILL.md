---
name: requesting-code-review
description: Use when completing tasks, implementing major features, or before merging
---

# Requesting Code Review

<ROLE>
Quality Gate Enforcer. Reputation depends on catching bugs before they reach production, not rubber-stamping changes.
</ROLE>

<analysis>
Fresh eyes catch blind spots. Cost of early review << cost of cascading bugs.
Review gates prevent technical debt accumulation.
</analysis>

## Invariant Principles

1. **Review Early** - Catch issues before they compound across tasks
2. **Evidence Over Claims** - Issues require file:line references, not vague assertions
3. **Severity Honesty** - Critical = data loss/security; Important = architecture/gaps; Minor = polish
4. **Pushback Valid** - Reviewer wrong sometimes; counter with code/tests, not authority

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `context.changes` | Yes | Git range (BASE_SHA..HEAD_SHA) or file list |
| `context.what_implemented` | Yes | Feature/change description |
| `context.plan_reference` | No | Link to spec, task, or plan being implemented |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `review_report` | Inline | Structured feedback with severity levels |
| `action_items` | List | Prioritized fixes: Critical > Important > Minor |
| `approval_status` | Boolean | Whether changes pass review gate |

## When to Review

| Trigger | Requirement |
|---------|-------------|
| Task completion (subagent dev) | Mandatory |
| Major feature complete | Mandatory |
| Pre-merge to main | Mandatory |
| Stuck / need perspective | Recommended |
| Pre-refactor baseline | Recommended |

## Execution Protocol

**1. Capture git range:**
```bash
BASE_SHA=$(git rev-parse origin/main)  # or HEAD~N
HEAD_SHA=$(git rev-parse HEAD)
```

**2. Dispatch code-reviewer subagent** using template `code-reviewer.md`:

| Placeholder | Value |
|-------------|-------|
| `{WHAT_WAS_IMPLEMENTED}` | Feature/change built |
| `{PLAN_OR_REQUIREMENTS}` | Spec or task reference |
| `{BASE_SHA}`, `{HEAD_SHA}` | Git range |
| `{DESCRIPTION}` | Brief summary |

**3. Act on feedback:**

<reflection>
Before dismissing reviewer feedback, verify: Do I have evidence it's wrong?
Ego resistance != technical correctness.
</reflection>

| Severity | Action |
|----------|--------|
| Critical | Fix immediately, re-review |
| Important | Fix before proceeding |
| Minor | Note for later |
| Disagree | Counter with code/tests proving correctness |

## Integration Points

- **Subagent development:** Review after EACH task
- **Plan execution:** Review after batch (3 tasks)
- **Ad-hoc work:** Review pre-merge or when stuck

## Anti-Patterns

<FORBIDDEN>
- Skip review because change is "simple"
- Ignore Critical severity issues
- Proceed with unfixed Important issues
- Dismiss valid technical feedback without evidence
- Self-approve without fresh perspective
</FORBIDDEN>

## Self-Check

Before completing review cycle:
- [ ] All Critical issues fixed and verified
- [ ] All Important issues fixed or explicitly deferred with rationale
- [ ] Re-review triggered if Critical fixes were substantial
- [ ] Feedback addressed with code/tests, not just acknowledgment

If ANY unchecked: STOP and fix.

## Handoff to Receiving Skill

When external feedback arrives after an internal review:

### Context Preservation
- Pass `review-manifest.json` path to receiving skill
- Include internal findings for cross-reference
- Note which internal findings overlap with external

### Invocation Pattern
```
When processing external PR feedback:
1. Load review-manifest.json from prior internal review (if exists)
2. Invoke receiving-code-review skill with:
   - External feedback source
   - Internal review artifacts path
   - Trust level for source
```

### Provenance Tracking
Mark each finding with source:
- `source: internal` - From code-reviewer agent
- `source: external` - From PR reviewer
- `source: merged` - External finding confirmed by internal

Template: `requesting-code-review/code-reviewer.md`
