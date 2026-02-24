---
name: creating-issues-and-pull-requests
description: "Use when creating GitHub pull requests or issues with template compliance. Triggers: 'create a PR', 'open a pull request', 'file an issue', 'create issue', or invoked as delegate from finishing-a-development-branch Option 2. Discovers project templates, populates them from branch context, and creates via reliable gh CLI patterns."
---

# Creating Issues and Pull Requests

<ROLE>
GitHub Integration Specialist. Your reputation depends on every PR and issue respecting the project's templates, naming conventions, and workflow constraints. A PR that ignores the project's template is a public failure. A fabricated Jira ticket number is unforgivable.
</ROLE>

**Announce:** "Using creating-issues-and-pull-requests skill to handle GitHub creation."

## Invariant Principles

1. **Template Discovery Before Creation** - Always attempt template discovery before falling back to a default body. Never skip it.
2. **Read Templates Yourself, Pass via `--body-file`** - Never rely on `--template` or `--fill`. Read the template content, populate it, write to a temp file, pass via `--body-file`.
3. **User Confirms All Side Effects** - Never push, create a PR, or create an issue without explicit user approval.
4. **Target Repository is Never Assumed** - Always confirm the merge base repo with the user (upstream or origin?).
5. **Branch-Relative Documentation Only** - PR descriptions derive from the merge-base delta. No development history, no session narratives.
6. **Jira Tickets are Real or Absent** - If no Jira ticket is evident from the branch name or user input, omit the prefix entirely. Never fabricate ticket numbers.
7. **Base Repo Templates for Fork PRs** - When creating a PR from a fork, templates come from the upstream (base) repo, not the fork.

---

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `mode` | No | auto-detect | `"pr"` or `"issue"` |
| `branch` | No | current branch | Feature branch name |
| `base` | No | auto-detect | Base/target branch for PRs |
| `target_repo` | No | auto-detect | `OWNER/REPO` for the target |
| `jira_ticket` | No | detect from branch | Jira ticket number (e.g., `ODY-1234`) |
| `diff_summary` | No | compute | Pre-computed merge-base diff summary |
| `draft` | No | false | Create as draft PR |
| `labels` | No | none | Labels to apply |
| `reviewers` | No | none | Reviewers to request |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `url` | string | Created PR or issue URL |
| `number` | int | PR or issue number |
| `type` | string | `"pr"` or `"issue"` |
| `target_repo` | string | `OWNER/REPO` where it was created |

---

## Integration Contract

### Called By

- **`finishing-a-development-branch`** (Option 2: Push and Create PR) - Delegates PR creation with branch context.
- **`executing-plans`** - Indirectly, through `finishing-a-development-branch` at the end of implementation.
- **User directly** - Via `/creating-issues-and-pull-requests`, or the shorthand commands `/create-pr` and `/create-issue`.

### Context Passed by Callers

When invoked as a delegate from `finishing-a-development-branch`:

```
mode: "pr"
branch: <feature-branch>
base: <base-branch>
diff_summary: <pre-computed merge-base diff summary>
```

The skill handles everything from push confirmation through PR creation and URL reporting.

### Direct Invocation

| Invocation | Behavior |
|------------|----------|
| `/creating-issues-and-pull-requests` | Mode detection, asks PR or issue |
| `/creating-issues-and-pull-requests --pr` | Dispatches directly to `/create-pr` |
| `/creating-issues-and-pull-requests --issue` | Dispatches directly to `/create-issue` |
| `/create-pr` | Invokes PR command directly (bypasses orchestrator) |
| `/create-issue` | Invokes issue command directly |

---

## The Process

### Phase 0: Mode Detection

<analysis>
Determine what the user wants to create:
- Examine the invocation arguments and user message
- Check for caller-provided mode
- If ambiguous, ask the user
</analysis>

| Signal | Detected Mode |
|--------|---------------|
| "create a PR", "open PR", caller passes `mode: "pr"` | PR |
| "create an issue", "file a bug", "open issue", caller passes `mode: "issue"` | Issue |
| No clear signal | Ask user: "Would you like to create a PR or an issue?" |

### Phase 1: Gather Context

Before dispatching, collect the context that commands need:

1. **Current branch:** `git branch --show-current`
2. **Remote configuration:** `git remote -v`
3. **Fork detection:** `gh repo view --json isFork,parent`
4. **Jira ticket detection:** Scan the branch name for patterns like `ODY-XXXX` or `elijahr/ODY-XXXX`

Pass all gathered context to the appropriate command.

### Phase 2: Dispatch

**For PR creation:**

Dispatch subagent with command: `/create-pr`

Provide context: branch name, base branch, target repo (if known), jira ticket (if detected), diff summary (if pre-computed), draft flag, labels, reviewers.

**For issue creation:**

Dispatch subagent with command: `/create-issue`

Provide context: target repo (if known), labels.

### Phase 3: Report Result

Report the created URL back to the user and to any calling skill.

---

## Template Discovery Overview

Both commands implement a 4-tier template discovery cascade. This section provides the high-level algorithm; commands contain the full implementation details.

### PR Template Discovery

| Tier | Source | Method | Applies When |
|------|--------|--------|-------------|
| 1 | Local filesystem | Scan `.github/`, root, `docs/` for `pull_request_template.md` and `PULL_REQUEST_TEMPLATE/` directories | Same-repo PRs only |
| 2 | Remote (target repo) | GraphQL `repository.pullRequestTemplates` | Always (primary source for fork PRs) |
| 3 | Org-level `.github` repo | GraphQL against `ORG/.github` | Fallback when target repo has no templates |
| 4 | No template found | Use sensible default body structure | Final fallback |

<RULE>
For fork PRs, skip Tier 1 entirely. Templates come from the upstream (base) repo via Tier 2 or 3.
</RULE>

### Issue Template Discovery

| Tier | Source | Method |
|------|--------|--------|
| 1 | Local filesystem | Scan `.github/ISSUE_TEMPLATE/` for `.md` and `.yml` files, parse `config.yml` |
| 2 | Remote (target repo) | GraphQL `repository.issueTemplates` |
| 3 | Org-level `.github` repo | GraphQL against `ORG/.github` |
| 4 | Legacy / No template | Check root `issue_template.md`; if nothing found, use blank issue (if allowed) |

### Multiple Templates

When multiple templates are discovered at any tier, present a chooser listing filenames and descriptions. Let the user select.

### All-or-Nothing Override

If the target repo has ANY template of a given type (PR or issue), ALL org-level templates of that type are blocked. There is no merging or layering between repo-level and org-level templates.

---

## Naming Conventions

| Condition | PR Title | Branch Name |
|-----------|----------|-------------|
| Jira ticket exists | `[ODY-XXXX] <description>` | `elijahr/ODY-XXXX` |
| No Jira ticket | `<description>` (plain, no prefix) | `elijahr/<descriptive-slug>` |

<CRITICAL>
Never fabricate a Jira ticket number. No `ODY-0000`, no placeholder tickets. If the branch name does not contain an `ODY-XXXX` pattern and the user has not provided a ticket number, omit the prefix entirely.
</CRITICAL>

---

## Post-Creation Operations

Since `gh pr edit` is broken (GitHub Projects Classic deprecation), use the REST API for any post-creation modifications:

```bash
# Update PR title or body
gh api repos/OWNER/REPO/pulls/NUMBER --method PATCH \
  -f title="New title" -f body="New body"

# Add labels
gh api repos/OWNER/REPO/issues/NUMBER/labels --method POST \
  -f 'labels[]=label1'

# Request reviewers
gh api repos/OWNER/REPO/pulls/NUMBER/requested_reviewers --method POST \
  -f 'reviewers[]=username'
```

---

<FORBIDDEN>
- Using `--fill` flag with `gh pr create` (skips templates entirely)
- Using `--template` flag with `gh pr create` or `gh issue create` (inconsistent behavior)
- Using `gh pr edit` for any purpose (broken by GitHub Projects Classic deprecation)
- Fabricating Jira ticket numbers (`ODY-0000`, placeholder tickets)
- Creating a PR or issue without user confirmation
- Pushing to remote without user confirmation
- Including development history or session narratives in PR descriptions
- Skipping template discovery (always attempt all tiers)
- Using unquoted heredocs (`<<EOF` instead of `<<'EOF'`) for body content
- Passing raw body via `--body` when content may contain shell special characters
- Silently choosing a target repo without user confirmation
- Using local templates for fork PRs (templates come from upstream)
</FORBIDDEN>

---

## Self-Check

<reflection>
Before completing:
- [ ] Mode (PR or issue) correctly identified from user intent or caller context
- [ ] Context gathered (branch, remotes, fork status, Jira ticket)
- [ ] Appropriate command dispatched with full context
- [ ] Command completed successfully
- [ ] Result URL reported to user and calling skill

IF ANY unchecked: STOP and fix.
</reflection>
