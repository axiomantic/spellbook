---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Context:** This should be run in a dedicated worktree (created by brainstorming skill).

**Save plans to:** `~/.local/spellbook/docs/<project-encoded>/plans/YYYY-MM-DD-<feature-name>.md`
- Create the directory if it doesn't exist: `mkdir -p ~/.local/spellbook/docs/<project-encoded>/plans`
- Generate project encoded path:
  ```bash
  # Encode full project path: /Users/alice/Development/myproject → Users-alice-Development-myproject
  PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
  PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')
  ```

---

## Autonomous Mode Behavior

Check your context for autonomous mode indicators:
- "Mode: AUTONOMOUS" or "autonomous mode"
- "DO NOT ask questions"
- Design document path already provided in context

When autonomous mode is active:

### Skip These Interactions
- "Ask the user for the path to the design document" (should be in context)
- Execution handoff choice (proceed based on context or skip handoff entirely)

### Make These Decisions Autonomously
- Design doc path: Use path from context, or find most recent design doc in plans directory
- Plan structure: Use standard structure, don't ask for preferences

### Circuit Breakers (Still Pause For)
- No design document exists and no requirements provided (cannot plan without spec)
- Design document has critical gaps that make planning impossible

---

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Source Design Document

**In interactive mode:** Ask the user for the path to the design document before writing the plan.

**In autonomous mode:** Use the design document path from context. If not provided, search for the most recent design doc in `~/.local/spellbook/docs/<project-encoded>/plans/`.

Record the path in the header so reviewers and executing agents can reference the original design decisions.

If no design document exists and none can be found, note that explicitly (or trigger circuit breaker if requirements are insufficient).

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** [One sentence describing what this builds]

**Source Design Doc:** [path/to/design-doc.md or "None - requirements provided directly"]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## Task Structure

```markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
```

## Remember
- Exact file paths always
- Complete code in plan (not "add validation")
- Exact commands with expected output
- Reference relevant skills with @ syntax
- DRY, YAGNI, TDD, frequent commits

## Execution Handoff

**In interactive mode:**

After saving the plan, offer execution choice:

**"Plan complete and saved to `~/.local/spellbook/docs/<project-encoded>/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?"**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use subagent-driven-development
- Stay in this session
- Fresh subagent per task + code review

**If Parallel Session chosen:**
- Guide them to open new session in worktree
- **REQUIRED SUB-SKILL:** New session uses executing-plans

---

**In autonomous mode:**

Skip the execution choice. Just save the plan and report completion:

**"Plan complete and saved to `~/.local/spellbook/docs/<project-encoded>/plans/<filename>.md`."**

The orchestrating skill (e.g., implementing-features) will handle execution dispatch.
