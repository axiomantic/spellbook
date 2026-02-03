# code-review

Use when reviewing code (self-review, processing feedback, reviewing others, or auditing). Modes: --self (default), --feedback, --give <target>, --audit

## Skill Content

``````````markdown
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

| Flag | Mode | Command File |
|------|------|-------------|
| `--self`, `-s`, (default) | Pre-PR self-review | (inline below) |
| `--feedback`, `-f` | Process received feedback | `code-review-feedback` |
| `--give <target>` | Review someone else's code | `code-review-give` |
| `--audit [scope]` | Multi-pass deep-dive | (inline below) |

**Modifiers:** `--tarot` (roundtable dialogue via `code-review-tarot`), `--pr <num>` (PR source)

---

## MCP Tool Integration

### Available Tools

| Tool | Purpose | Used In |
|------|---------|---------|
| `pr_fetch` | Fetch PR metadata and diff | --self (with --pr), --give, --audit |
| `pr_diff` | Parse unified diff into FileDiff objects | All modes with PR source |
| `pr_match_patterns` | Heuristic pre-filtering of changes | --give, --audit |
| `pr_files` | Extract file list from pr_fetch result | All modes with PR source |

### Tool Layering Principle

- **MCP tools for read/analyze:** Deterministic, structured data
- **gh CLI for write operations:** User-visible side effects

### Usage Patterns

**Fetching PR Data:**
```python
# By number (uses current repo context)
pr_data = pr_fetch("123")

# By URL (explicit repo)
pr_data = pr_fetch("https://github.com/owner/repo/pull/123")
```

**Parsing Diff:**
```python
diff_result = pr_diff(pr_data["diff"])
# Returns: {"files": [FileDiff, ...], "warnings": [...]}
```

**Pattern Matching:**
```python
match_result = pr_match_patterns(
    files=diff_result["files"],
    project_root=PROJECT_ROOT
)
# Returns: {"matched": {...}, "unmatched": [...], "patterns_checked": N}
```

### Fallback Behavior

| Failure | Fallback | User Message |
|---------|----------|--------------|
| MCP unavailable | gh CLI | "Using gh CLI (MCP unavailable)" |
| PR not found | Local diff | "PR not found. Reviewing local changes." |
| Auth failure | Manual paste | "Auth failed. Paste PR diff manually." |

### gh CLI Integration

For write operations (posting reviews, replies):

```bash
# Post review with verdict
gh pr review <num> --approve --body "review content"
gh pr review <num> --request-changes --body "review content"
gh pr review <num> --comment --body "review content"

# Reply to comment thread
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies \
  -f body="Fixed. [description]"
```

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

## Audit Mode (`--audit [scope]`)

Scopes: (none)=branch changes, file.py, dir/, security, all

**Passes:** Correctness > Security > Performance > Maintainability > Edge Cases

Output: Executive Summary, findings by category, Risk Assessment (LOW/MEDIUM/HIGH/CRITICAL)

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
``````````
