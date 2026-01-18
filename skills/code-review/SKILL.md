---
name: code-review
description: "Unified code review skill with modes: --self (default), --feedback, --give <target>, --audit"
---

# Code Review

<ROLE>
Code Review Specialist. Reputation depends on catching real issues while respecting developer time.
</ROLE>

<analysis>
Code review serves different purposes depending on context:
- Self-review: Pre-PR cleanup, catch obvious issues before external eyes
- Feedback processing: Turn received feedback into actionable fixes
- Giving review: Help others by spotting issues they missed
- Audit: Comprehensive multi-pass security/quality deep-dive

A unified skill with mode routing reduces cognitive load while preserving specialized behavior.
</analysis>

## Invariant Principles

1. **Evidence Over Assertion** - Every finding requires file:line reference and reproduction path
2. **Severity Honesty** - Critical = data loss/security; Important = correctness/architecture; Minor = style/polish
3. **Context Awareness** - Same code in different contexts warrants different severity
4. **Feedback Loops** - Self-review before external; process feedback immediately; audit periodically
5. **Respect Developer Time** - False positives erode trust; prioritize signal over noise

## Inputs

| Input | Required | Source | Description |
|-------|----------|--------|-------------|
| `args` | Yes | Skill invocation | Mode flags and targets |
| `git diff` | Auto | Git | Changed files for self/give modes |
| `PR data` | Conditional | GitHub API | Required for --pr or --give with PR target |
| `feedback` | Conditional | User/PR comments | Required for --feedback mode |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `findings` | List[Finding] | Issues with severity, file:line, description |
| `summary` | String | Executive summary of review |
| `action_items` | List | Prioritized fixes |
| `approval` | Boolean | Pass/fail for --self and --audit modes |

## Mode Router

Parse the `args` parameter to determine mode:

| Flag | Mode | Handler |
|------|------|---------|
| `--self` or no flags | Self-review | Pre-PR self-review |
| `--feedback` | Feedback | Process received feedback |
| `--give <target>` | Give | Review someone else's code |
| `--audit [scope]` | Audit | Multi-pass comprehensive review |

**Modifier flags:**
- `--tarot`: Enable tarot roundtable dialogue
- `--pr <num>`: Specify remote PR as diff source

**Argument Parsing:**
```
PARSE args:
  self = args contains '--self' OR args contains '-s' OR no mode flags present
  feedback = args contains '--feedback' OR args contains '-f'
  give = extract target after '--give' (PR number, URL, or branch)
  audit = args contains '--audit' (optional scope after flag)
  tarot = args contains '--tarot' OR args contains '-t'
  pr = extract number after '--pr'

IF multiple mode flags (self, feedback, give, audit):
  ERROR: "Choose one mode: --self, --feedback, --give, or --audit"

IF --give without target:
  ERROR: "--give requires a target (PR number, URL, or branch)"
```

---

## Self Mode (`--self`)

Pre-PR self-review to catch issues before external review.

<reflection>
Self-review is about finding what you missed, not validating your work.
Assume bugs exist. Hunt them.
</reflection>

### Workflow

**1. Gather diff:**
```bash
# Get changes since branch point
git diff $(git merge-base origin/main HEAD)..HEAD
```

**2. Multi-pass review:**

| Pass | Focus | Questions |
|------|-------|-----------|
| 1 | Logic | Does code do what it claims? Edge cases handled? |
| 2 | Integration | Breaks existing behavior? Missing tests? |
| 3 | Security | User input validated? Secrets exposed? |
| 4 | Style | Consistent patterns? Clear naming? |

**3. Generate findings:**
For each issue, produce Finding with:
- severity: critical/important/minor
- file: absolute path
- line: line number (or range)
- description: what's wrong and why
- suggestion: how to fix (optional)

**4. Decision gate:**
- Any Critical findings: FAIL, must fix
- Any Important findings: WARN, should fix before PR
- Only Minor findings: PASS with notes

### Output Format

```markdown
## Self-Review Results

**Status:** PASS | WARN | FAIL
**Files reviewed:** N
**Findings:** X critical, Y important, Z minor

### Critical Issues
[List or "None"]

### Important Issues
[List or "None"]

### Minor Issues
[List or "None"]

### Summary
[1-2 sentence executive summary]
```

---

## Feedback Mode (`--feedback`)

Process received code review feedback systematically.

### Workflow

**1. Gather feedback:**
- If `--pr N` provided: Fetch PR comments via `gh pr view N --comments`
- Otherwise: User provides feedback inline or via paste

**2. Parse feedback items:**
For each piece of feedback, extract:
- file/line reference (if provided)
- category: bug, style, question, suggestion, nit
- urgency: blocking, non-blocking
- content: the actual feedback

**3. Triage and categorize:**

| Category | Action |
|----------|--------|
| Bug report | Verify, fix if valid, respond if invalid |
| Style/nit | Apply if sensible, explain if not |
| Question | Answer clearly |
| Suggestion | Evaluate merit, adopt or explain why not |

**4. Generate response plan:**
```markdown
## Feedback Response Plan

### Will Address
- [feedback item]: [planned fix]

### Needs Clarification
- [feedback item]: [question for reviewer]

### Respectfully Disagree
- [feedback item]: [evidence-based counter]
```

**5. Execute fixes:**
Apply planned fixes, then re-run self-review on changed code.

---

## Give Mode (`--give <target>`)

Review someone else's code with helpful, specific feedback.

### Target Resolution

| Target Format | Resolution |
|---------------|------------|
| `123` | PR #123 in current repo |
| `owner/repo#123` | PR #123 in specified repo |
| `https://github.com/...` | Parse repo and PR from URL |
| `branch-name` | Compare branch to main |

### Workflow

**1. Fetch diff:**
```bash
# For PR
gh pr diff <number>

# For branch
git diff origin/main...<branch>
```

**2. Understand context:**
- Read PR description/commit messages
- Identify what the change is trying to accomplish
- Note any linked issues or specs

**3. Multi-pass review (same as self-review passes)**

**4. Compose feedback:**

Guidelines for helpful feedback:
- Lead with what's good (genuine, not performative)
- Be specific: file:line references always
- Explain why, not just what
- Suggest fixes, not just problems
- Distinguish blocking vs non-blocking
- Ask questions when unsure

**5. Output format:**

```markdown
## Code Review: [PR title or branch]

### Summary
[1-2 sentence overall impression]

### Blocking Issues
[Must fix before merge]

### Suggestions
[Would improve but not blocking]

### Questions
[Clarifications needed]

### Praise
[What was done well]

**Recommendation:** APPROVE | REQUEST_CHANGES | COMMENT
```

---

## Audit Mode (`--audit [scope]`)

Comprehensive multi-pass deep-dive for critical code.

### Scope Resolution

| Scope | Coverage |
|-------|----------|
| (none) | Current branch changes |
| `file.py` | Single file |
| `src/module/` | Directory |
| `security` | Security-focused full repo scan |
| `all` | Full codebase (expensive) |

### Audit Passes

| Pass | Duration | Focus |
|------|----------|-------|
| 1. Correctness | Fast | Logic bugs, off-by-one, null checks |
| 2. Security | Medium | Injection, auth, data exposure |
| 3. Performance | Medium | N+1 queries, memory leaks, blocking I/O |
| 4. Maintainability | Fast | Complexity, coupling, documentation |
| 5. Edge Cases | Slow | Boundary conditions, error paths |

### Per-Pass Protocol

For each pass:
1. State focus area explicitly
2. Walk through code systematically
3. Document findings with severity
4. Note areas needing follow-up

### Output Format

```markdown
## Code Audit Report

**Scope:** [what was audited]
**Passes completed:** 5/5
**Duration:** [time taken]

### Executive Summary
[2-3 sentences on overall quality and risk]

### Critical Findings
[Immediate action required]

### Security Findings
[Security-specific issues]

### Performance Findings
[Performance issues]

### Maintainability Findings
[Tech debt and complexity issues]

### Recommendations
[Prioritized action items]

**Overall Risk Assessment:** LOW | MEDIUM | HIGH | CRITICAL
```

---

## Tarot Integration (`--tarot`)

When `--tarot` flag is present, engage tarot roundtable dialogue.

### Archetypes for Review

| Archetype | Perspective | Focus |
|-----------|-------------|-------|
| The Hermit | Solitary wisdom | Deep technical correctness |
| Justice | Balance and fairness | Objective severity assessment |
| The Magician | Practical transformation | Actionable suggestions |
| The Fool | Fresh perspective | Question assumptions |

### Roundtable Format

Each archetype speaks in turn, contributing their perspective. Final synthesis integrates all viewpoints.

```markdown
**Hermit:** [technical deep-dive]
**Justice:** [severity calibration]
**Magician:** [practical fixes]
**Fool:** [naive questions that reveal assumptions]

**Synthesis:** [integrated recommendation]
```

---

## Anti-Patterns

<FORBIDDEN>
- Skip self-review because "change is small"
- Ignore Critical findings
- Dismiss feedback without technical counter-evidence
- Give vague feedback without file:line references
- Approve to avoid conflict
- Review without understanding the goal
- Apply fixes without re-validating
- Rate severity based on effort to fix rather than impact
</FORBIDDEN>

---

## Self-Check

Before completing any review:
- [ ] Correct mode identified from args
- [ ] All findings have file:line references
- [ ] Severity levels correctly assigned (impact-based, not effort-based)
- [ ] Output format matches mode specification
- [ ] For --feedback: response plan created before fixes applied
- [ ] For --audit: all passes completed and documented
- [ ] If --tarot: all archetypes contributed

If ANY unchecked: STOP and complete.
