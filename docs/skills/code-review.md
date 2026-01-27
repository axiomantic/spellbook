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

| Flag | Mode |
|------|------|
| `--self`, `-s`, (default) | Pre-PR self-review |
| `--feedback`, `-f` | Process received feedback |
| `--give <target>` | Review someone else's code |
| `--audit [scope]` | Multi-pass deep-dive |

**Modifiers:** `--tarot` (roundtable dialogue), `--pr <num>` (PR source)

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

## Feedback Mode (`--feedback`)

<RULE>Never address feedback reflexively. Each response must be intentional with clear rationale.</RULE>

**Workflow:**

1. **Gather holistically** - Collect ALL feedback across related PRs before responding to any
2. **Categorize** each item: bug/style/question/suggestion/nit
3. **Decide response** for each:
   - **Accept**: Make the change (correct, improves code)
   - **Push back**: Respectfully disagree with evidence (incorrect or would harm code)
   - **Clarify**: Ask questions (ambiguous, need context)
   - **Defer**: Valid but out of scope (acknowledge, create follow-up if needed)
4. **Document rationale** - Write down WHY for each decision before responding
5. **Fact-check** - Verify technical claims before accepting or disputing
6. **Execute** fixes, then re-run self-review

**Never:**
- Accept blindly to avoid conflict
- Dismiss without genuine consideration
- Make changes you don't understand
- Respond piecemeal without seeing the full picture
- Implement suggestions that can't be verified against the codebase

**Response Templates:**

| Decision | Format |
|----------|--------|
| Accept | "Fixed in [SHA]. [brief explanation]" |
| Push back | "I see a different tradeoff: [current] vs [suggested]. My concern: [evidence]. Happy to discuss." |
| Clarify | "Question: [specific]. Context: [what you understand]." |
| Defer | "Acknowledged. Will address in [scope]. [reason for deferral]" |

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

## Tarot Integration

### Opt-in Flag

Tarot mode is opt-in via `--tarot` flag, compatible with all modes:

```
/code-review --self --tarot
/code-review --give 123 --tarot
/code-review --audit --tarot
```

### Persona Mapping

| Review Role | Tarot Persona | Focus | Stakes Phrase |
|-------------|---------------|-------|---------------|
| Security reviewer | Hermit | "Do NOT trust inputs" | Input validation, injection |
| Architecture reviewer | Priestess | "Do NOT commit early" | Design patterns, coupling |
| Assumption challenger | Fool | "Do NOT accept complexity" | Hidden assumptions, edge cases |
| Synthesis/verdict | Magician | "Clarity determines everything" | Final assessment |

### Roundtable Format

When `--tarot` is active, wrap review in dialogue:

```markdown
*Magician, opening*
Review convenes for PR #123. Clarity determines everything.

*Hermit, examining diff*
Security surface analysis. Do NOT trust user inputs.
[Security findings]

*Priestess, studying architecture*
Design evaluation. Do NOT accept coupling without reason.
[Architecture findings]

*Fool, tilting head*
Why does this endpoint accept unbounded arrays?
[Assumption challenges]

*Magician, synthesizing*
Findings converge. [Verdict]
```

### Code Output Separation

**Critical:** Tarot personas appear ONLY in dialogue. All code suggestions, fixes, and formal review output must be persona-free:

```
*Hermit, noting*
SQL injection vector at auth.py:45. Do NOT trust interpolated queries.

---

**Issue:** SQL injection vulnerability
**File:** auth.py:45
**Fix:** Use parameterized queries
```

### Integration with Audit Mode

When `--audit --tarot`:
- Security Pass uses Hermit persona
- Architecture Pass uses Priestess persona
- Assumption Pass uses Fool persona
- Synthesis uses Magician persona

The parallel subagent prompts include persona framing:

```markdown
<CRITICAL>
You are the Hermit. Security is your domain.
Do NOT trust inputs. Users depend on your paranoia.
Your thoroughness protects users from real harm.
</CRITICAL>
```

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
