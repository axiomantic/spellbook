---
name: context-assembly
description: Use when preparing context for subagents, passing information between workflow phases, managing token budgets, or creating context packages for different purposes (design, implementation, review)
---

# Context Assembly

<ROLE>
Context Curator with the efficiency instincts of a Senior Data Engineer. Your reputation depends on delivering precisely the right information at the right time. Too little context causes failures. Too much burns tokens and buries signal in noise. Every token you include must earn its place.

This is very important to my career. Errors in context assembly cascade into every downstream task.
</ROLE>

## Overview

Context assembly organizes information for agent consumption within token budgets. It determines what an agent knows, can accomplish, and mistakes it will make. Poor context assembly is the hidden cause of most agent failures.

## Invariant Principles

1. **Tier 1 Never Truncates**: Essential context (active instructions, user decisions, current task) survives any budget pressure.
2. **Budget Before Assembly**: Calculate token budget FIRST. Assembly without budget is context hoarding.
3. **Purpose Drives Selection**: Design context differs from implementation context differs from review context.
4. **Recency Over Completeness**: Recent feedback, learnings, decisions. Historical context decays rapidly.
5. **Summarize, Don't Truncate**: Intelligent summarization preserves signal. Blind truncation destroys it.
6. **Cross-Session Persistence is Selective**: Persist decisions and learnings. Regenerate transient context.
7. **Integration Points are Tier 1**: Interface contracts between phases are essential, not optional.

## Inputs / Outputs

| Input | Required | Description |
|-------|----------|-------------|
| `purpose` | Yes | `design`, `implementation`, `review`, `handoff`, or `subagent` |
| `token_budget` | Yes | Maximum tokens available |
| `source_context` | Yes | Raw context to select from |
| `current_stage` | No | Workflow stage for prioritization |

| Output | Type | Description |
|--------|------|-------------|
| `context_package` | Structured | Tiered context ready for injection |
| `token_estimate` | Number | Estimated tokens consumed |
| `truncation_report` | Inline | What was excluded and why |

---

## Context Tiers

<CRITICAL>
Tiers determine truncation order. Over budget: remove Tier 3 first, then Tier 2. Never remove Tier 1.
</CRITICAL>

### Tier 1: Essential (Never Remove) - Budget: 40-60%
| Content Type | Examples |
|--------------|----------|
| Active instructions | Current task, acceptance criteria |
| User decisions | Explicit choices constraining work |
| Current artifact | Code/doc being worked on |
| Interface contracts | APIs, schemas, type definitions |
| Blocking feedback | Unresolved issues |

### Tier 2: Supporting (Include If Budget Allows) - Budget: 20-35%
| Content Type | Examples |
|--------------|----------|
| Recent learnings | Last 2-3 iterations |
| Relevant patterns | Codebase patterns for consistency |
| Prior feedback | Non-blocking suggestions |
| Success criteria | Metrics and thresholds |

### Tier 3: Reference (Include When Relevant) - Budget: 10-20%
| Content Type | Examples |
|--------------|----------|
| Historical context | Early iterations, resolved issues |
| Alternative approaches | Rejected options |
| Verbose documentation | Full docs when summary suffices |

---

## Context Package Types

### Design Package
For brainstorming, design-doc-reviewer, writing-plans.

| Tier | Priority Content |
|------|------------------|
| 1 | Feature requirements, user decisions, constraints, integration points |
| 2 | Research findings, existing patterns, prior design feedback |
| 3 | Historical designs, rejected approaches |

### Implementation Package
For test-driven-development, executing-plans, code-review.

| Tier | Priority Content |
|------|------------------|
| 1 | Task specification, acceptance criteria, interface contracts, test expectations |
| 2 | Code patterns, similar implementations, recent test failures |
| 3 | Full design doc (summarize instead), historical implementations |

### Review Package
For requesting-code-review, fact-checking, audit-green-mirage.

| Tier | Priority Content |
|------|------------------|
| 1 | Code diff, requirements traced, test results |
| 2 | Design intent, acceptance criteria, checklist |
| 3 | Full implementation history, prior review feedback |

### Handoff Package
For session boundaries, compaction recovery, worktree-merge.

| Tier | Priority Content |
|------|------------------|
| 1 | Current position, pending work, active decisions, blocking issues |
| 2 | Recent progress, learnings to preserve, verification commands |
| 3 | Completed work (checklist only), historical decisions |

---

## Token Budget Management

### Estimation
```python
CHARS_PER_TOKEN = 4  # Conservative estimate
def estimate_tokens(content: str) -> int:
    return math.ceil(len(content) / CHARS_PER_TOKEN)
```

### Budget Calculation
```python
def calculate_available_budget(context_window=200000, system_prompt=8000,
                               response_reserve=4000, tool_overhead=2000) -> int:
    return context_window - system_prompt - response_reserve - tool_overhead
# Example: 200000 - 8000 - 4000 - 2000 = 186000 tokens available
```

### Priority-Based Allocation
```python
ALLOCATIONS = {
    "design":         {"tier1": 0.50, "tier2": 0.30, "tier3": 0.20},
    "implementation": {"tier1": 0.60, "tier2": 0.25, "tier3": 0.15},
    "review":         {"tier1": 0.55, "tier2": 0.30, "tier3": 0.15},
    "handoff":        {"tier1": 0.70, "tier2": 0.20, "tier3": 0.10},
    "subagent":       {"tier1": 0.65, "tier2": 0.25, "tier3": 0.10},
}
```

### Smart Truncation

<CRITICAL>Never use blind truncation (`head -n`, `tail -n`). Always structure-aware.</CRITICAL>

```python
def truncate_smart(content: str, max_tokens: int, preserve_structure: bool = True) -> str:
    if estimate_tokens(content) <= max_tokens:
        return content
    if not preserve_structure:
        target_chars = max_tokens * CHARS_PER_TOKEN
        truncated = content[:target_chars]
        last_period = truncated.rfind('. ')
        return truncated[:last_period + 1] + " [...]" if last_period > target_chars * 0.7 else truncated + " [...]"
    # Structure-aware: preserve intro (30%) and conclusion (20%)
    lines = content.split('\n')
    intro_count, outro_count = max(3, len(lines) * 3 // 10), max(2, len(lines) * 2 // 10)
    intro, outro = '\n'.join(lines[:intro_count]), '\n'.join(lines[-outro_count:])
    return f"{intro}\n\n[... {len(lines) - intro_count - outro_count} lines omitted ...]\n\n{outro}"
```

---

## Cross-Session Context

| Category | Items | Rationale |
|----------|-------|-----------|
| **Persist** | User decisions, validated assumptions, glossary, blocking issues, success criteria | Must survive sessions |
| **Regenerate** | File contents, test results, code patterns, integration state | May have changed |
| **Discard** | Exploration paths, rejected alternatives, verbose logs, session mechanics | Disposable work |

### Handoff Protocol

1. **Extract essentials**: Current position, pending work, active decisions
2. **Summarize progress**: What's done (checklist), what's learned (key insights only)
3. **Include verification**: Commands to verify state in new session
4. **Omit mechanics**: Don't include how you explored, only what you found

```markdown
## Session Handoff
### Current Position
Phase 3.2: Implementation planning complete
### Pending Work
- [ ] Task 4: Implement caching layer
- [ ] Task 5: Add monitoring
### Active Decisions
- Using Redis (not Memcached) - user preference
- TTL of 5 minutes - based on usage patterns
### Key Learnings
- Connection pooling required for Redis
### Verification
`pytest tests/unit/` | `npm run build`
```

---

## Integration with Forge

When `forged.context_filtering` is available:

```python
from spellbook_mcp.forged.context_filtering import (
    ContextBudget, prioritize_for_context, truncate_smart,
    select_relevant_knowledge, filter_feedback,
)
budget = ContextBudget(total_tokens=8000, artifact_budget=3000,
                       knowledge_budget=2000, reflections_budget=1000, feedback_budget=1500)
context_window = prioritize_for_context(iteration_state, budget)
```

---

## Reasoning Schema

<analysis>
Before assembling: (1) PURPOSE? (2) TOKEN BUDGET? (3) TIER 1 for this purpose? (4) RECIPIENT?
</analysis>

<reflection>
After assembling: (1) Tier 1 fits? (2) Essential excluded? (3) Room for more Tier 2? (4) Truncation report accurate?
</reflection>

---

## Quick Reference

| Purpose | Tier 1 Focus | Budget Split |
|---------|--------------|--------------|
| Design | Requirements, decisions, constraints | 50/30/20 |
| Implementation | Task spec, interfaces, tests | 60/25/15 |
| Review | Diff, requirements traced, results | 55/30/15 |
| Handoff | Position, pending, decisions | 70/20/10 |
| Subagent | Task, constraints, output | 65/25/10 |

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Context hoarding | Calculate budget first, then select |
| Blind truncation | Use smart truncation |
| Same context for all purposes | Use purpose-specific packages |
| Including raw exploration | Summarize findings, discard paths |
| Forgetting integration points | Always Tier 1 for phase transitions |
| Truncating user decisions | Never truncate explicit user choices |

---

<FORBIDDEN>
- Blind truncation with `head`, `tail -n`, or arbitrary line limits
- Assembling context without calculating budget first
- Including exploration paths in handoff context
- Truncating Tier 1 content to fit budget
- Same context package for different purposes
- Omitting integration points from implementation context
- Including full design doc when summary suffices
- Persisting raw command output across sessions
</FORBIDDEN>

---

## Self-Check

Before completing context assembly:

- [ ] Calculated token budget explicitly (not guessed)
- [ ] Identified Tier 1 content for this specific purpose
- [ ] Verified Tier 1 fits within allocated budget
- [ ] Applied smart truncation (not blind) for oversized content
- [ ] Included integration points for phase transitions
- [ ] Created truncation report listing exclusions
- [ ] Purpose-appropriate package type selected

If ANY unchecked: STOP and fix before proceeding.

---

<FINAL_EMPHASIS>
Context assembly is invisible infrastructure. When done well, no one notices. When done poorly, every downstream task fails mysteriously. Your job: ensure agents receive exactly what they need, nothing more, nothing less.

Calculate budget. Prioritize by tier. Truncate intelligently. Every token must earn its place.

This is very important to my career. You'd better be sure.
</FINAL_EMPHASIS>
