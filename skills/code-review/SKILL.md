---
name: code-review
description: "Use when reviewing code (self-review, processing feedback, reviewing others, or auditing). Modes: --self (default), --feedback, --give <target>, --audit"
---

# Code Review

<ROLE>
Code Review Specialist. Catch real issues. Respect developer time.
</ROLE>

<analysis>
Unified skill routes to specialized handlers via mode flags.
Self-review catches issues early. Feedback mode processes received comments. Give mode provides helpful reviews. Audit mode does deep security/quality passes.
</analysis>

## Invariant Principles

1. **Evidence Over Assertion** - Every finding needs file:line reference
2. **Severity Honesty** - Critical=security/data loss; Important=correctness; Minor=style
3. **Context Awareness** - Same code may warrant different severity in different contexts
4. **Respect Time** - False positives erode trust; prioritize signal

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `args` | Yes | Mode flags and targets |
| `git diff` | Auto | Changed files |
| `PR data` | If --pr | PR metadata via GitHub |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `findings` | List | Issues with severity, file:line |
| `status` | Enum | PASS/WARN/FAIL or APPROVE/REQUEST_CHANGES |

## Mode Router

| Flag | Mode |
|------|------|
| `--self`, `-s`, (default) | Pre-PR self-review |
| `--feedback`, `-f` | Process received feedback |
| `--give <target>` | Review someone else's code |
| `--audit [scope]` | Multi-pass deep-dive |

**Modifiers:** `--tarot` (roundtable dialogue), `--pr <num>` (PR source)

---

## Self Mode (`--self`)

<reflection>
Self-review finds what you missed. Assume bugs exist. Hunt them.
</reflection>

**Workflow:**
1. Get diff: `git diff $(git merge-base origin/main HEAD)..HEAD`
2. Multi-pass: Logic > Integration > Security > Style
3. Generate findings with severity, file:line, description
4. Gate: Critical=FAIL, Important=WARN, Minor only=PASS

---

## Feedback Mode (`--feedback`)

**Workflow:**
1. Gather feedback (from --pr or user input)
2. Categorize: bug/style/question/suggestion/nit
3. Triage: Will Address | Needs Clarification | Respectfully Disagree
4. Execute fixes, then re-run self-review

---

## Give Mode (`--give <target>`)

Target formats: `123` (PR#), `owner/repo#123`, URL, branch-name

**Workflow:**
1. Fetch diff via `gh pr diff` or `git diff`
2. Understand goal from PR description
3. Multi-pass review
4. Output: Summary, Blocking Issues, Suggestions, Questions
5. Recommendation: APPROVE | REQUEST_CHANGES | COMMENT

---

## Audit Mode (`--audit [scope]`)

Scopes: (none)=branch changes, file.py, dir/, security, all

**Passes:** Correctness > Security > Performance > Maintainability > Edge Cases

Output: Executive Summary, findings by category, Risk Assessment (LOW/MEDIUM/HIGH/CRITICAL)

---

## Tarot Integration (`--tarot`)

Four archetypes contribute perspectives:
- **Hermit**: Deep technical correctness
- **Justice**: Severity calibration
- **Magician**: Actionable suggestions
- **Fool**: Question assumptions

Synthesis integrates all viewpoints.

---

<FORBIDDEN>
- Skip self-review for "small" changes
- Ignore Critical findings
- Dismiss feedback without evidence
- Give vague feedback without file:line
- Approve to avoid conflict
- Rate severity by effort instead of impact
</FORBIDDEN>

## Self-Check

- [ ] Correct mode identified
- [ ] All findings have file:line
- [ ] Severity based on impact, not effort
- [ ] Output matches mode spec
