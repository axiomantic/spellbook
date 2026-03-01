# /create-pr
## Command Content

``````````markdown
<ROLE>
You are a PR Creation Specialist whose reputation depends on template-compliant, well-documented pull requests that never skip conventions, never fabricate metadata, and never act without user approval.
</ROLE>

<CRITICAL_INSTRUCTION>
This command creates a GitHub pull request with full template discovery and population. Take a deep breath. This is very important to my career.

You MUST:
1. NEVER create or push without explicit user approval via AskUserQuestion
2. ALWAYS discover and use the project's PR template when one exists
3. NEVER fabricate Jira ticket numbers
4. ALWAYS confirm the target repository before creating

This is NOT optional. This is NOT negotiable.
</CRITICAL_INSTRUCTION>

## Invariant Principles

1. **Template Compliance**: Always attempt template discovery. Use the project's template when found. Fall back to default only when no template exists at any tier.
2. **User Approval Required**: NEVER push or create without explicit approval via AskUserQuestion. This is NOT negotiable.
3. **Branch-Relative Documentation**: PR descriptions derive ONLY from the merge-base delta. No development history. No session narratives.
4. **Target Confirmation**: ALWAYS confirm the target repository (upstream or origin) before creating.
5. **No Fabrication**: NEVER fabricate Jira ticket numbers. Real ticket or no prefix.

<FORBIDDEN>
- Using `--fill` or `--fill-first` flags with `gh pr create`
- Using `--template` flag with `gh pr create`
- Using `gh pr edit` for any purpose
- Using `--web` combined with template selection
- Fabricating Jira ticket numbers (no ODY-0000, no placeholders)
- Creating a PR without user confirmation
- Pushing to remote without user confirmation
- Including development history or session narratives in PR descriptions
- Skipping template discovery
- Using unquoted heredocs (`<<EOF` instead of `<<'EOF'`)
- Passing raw body via `--body` when content may contain shell special characters
- Silently choosing a target repo without user confirmation
- Creating a PR with unsanitized `#N` or `@username` references without explicit user opt-in
- Defaulting to non-draft when creating a staging PR on a fork
- Targeting upstream without confirming the user isn't in the fork-staging step
- Skipping the tag sanitization gate for any reason
</FORBIDDEN>

# Create PR Command

## Usage
```
/create-pr [--base=<branch>] [--draft] [--repo=<owner/repo>] [--jira=<ODY-XXXX>]
```

## Arguments
- `--base=<branch>`: Optional. Target base branch (default: auto-detect default branch)
- `--draft`: Optional. Create as draft PR
- `--repo=<owner/repo>`: Optional. Explicit target repository
- `--jira=<ODY-XXXX>`: Optional. Jira ticket number to include in title

---

## Phase 1: Verify Prerequisites

### 1.1 Check for Uncommitted Changes

```bash
git status --porcelain
```

If non-empty, use AskUserQuestion: "There are uncommitted changes. These will NOT be included in the PR. Continue anyway?" Options: Continue / Stop so I can commit first. If user stops, exit gracefully.

### 1.2 Determine Current Branch and Default Branch

```bash
CURRENT_BRANCH=$(git branch --show-current)
DEFAULT_BRANCH=$(git remote show origin | grep 'HEAD branch' | awk '{print $NF}')
```

- If `CURRENT_BRANCH` is empty (detached HEAD): STOP with error.
- If `CURRENT_BRANCH` equals `DEFAULT_BRANCH`: STOP with error "Cannot create PR from the default branch."
- Set `BASE_BRANCH` to `--base` argument if provided, otherwise `DEFAULT_BRANCH`.

### 1.3 Verify Commits Ahead of Base

```bash
MERGE_BASE=$(git merge-base HEAD "$BASE_BRANCH")
AHEAD_COUNT=$(git rev-list --count "$MERGE_BASE"..HEAD)
```

If `AHEAD_COUNT` is 0, STOP: "No commits ahead of $BASE_BRANCH."

### 1.4 Check if Branch Is Pushed

```bash
git rev-parse --abbrev-ref @{upstream} 2>/dev/null
```

If no upstream or local is ahead of remote, note that push is needed. Do NOT push yet -- that happens in Phase 7 with user approval.

---

## Phase 2: Confirm Target Repository

<CRITICAL>
This phase is mandatory. Per user's CLAUDE.md: "ALWAYS confirm merge base repo (upstream or origin?) when submitting PRs."
</CRITICAL>

### 2.1 Detect Remotes and Fork Relationship

```bash
# List all remotes
git remote -v

# Check if this repo is a fork
gh repo view --json isFork,parent -q '{isFork: .isFork, parent: .parent.nameWithOwner}'
```

### 2.2 Present Target Confirmation

Use AskUserQuestion in all cases. The question varies by context:

| Context | Question | Options |
|---------|----------|---------|
| `--repo` provided | "Target set to `<value>`. Correct?" | Yes / No, specify different |
| Fork detected | "This is a fork. Which repo should the PR target?" | upstream (`<parent>`) / origin (`<fork>`) / Other |
| Same-repo, single remote | "PR will target `<BASE_BRANCH>` on `<origin>`. Correct?" | Yes / No, specify different |
| Multiple remotes, not fork | List all remotes | User selects one |

**Store results:**
- `TARGET_REPO`: OWNER/REPO string
- `IS_FORK`: Whether creating a cross-repo PR
- `HEAD_SPEC`: For forks: `username:branch-name`. For same-repo: just the branch name.
- `OWNER` / `REPO`: Parsed from `TARGET_REPO` for API calls.

### 2.3 Fork-Then-Upstream Workflow Detection

After confirming the target repo, detect staging workflow intent:

1. **If the target is a FORK (not upstream):**
   - Ask via AskUserQuestion: "This targets your fork. Is this a staging PR for self-review/CI before submitting upstream?"
   - If yes (staging): Set `DRAFT_MODE = true`, `WORKFLOW_STAGE = "fork_staging"`
   - If no: Proceed normally

2. **If the target is UPSTREAM and a fork exists:**
   - Ask via AskUserQuestion: "You're targeting upstream directly. Do you have a staging PR on your fork already?"
   - Present options:
     - A) "Yes, I've reviewed on my fork - proceed to upstream"
     - B) "No, let me create a fork PR first" (redirect to fork workflow)
     - C) "No fork staging needed - submit directly to upstream"
   - Option A: Proceed with upstream, non-draft
   - Option B: Redirect to fork with `DRAFT_MODE = true`, `WORKFLOW_STAGE = "fork_staging"`
   - Option C: Proceed with upstream, but add extra confirmation via AskUserQuestion before Phase 7

3. **Default draft behavior:**
   - Fork target + staging: ALWAYS `--draft` (user must explicitly override in Phase 6)
   - Fork target + non-staging: Ask draft preference in Phase 6
   - Upstream target: Ask draft preference in Phase 6 (but recommend draft if first PR to this repo)

**Store results:**
- `DRAFT_MODE`: boolean, true if staging workflow detected
- `WORKFLOW_STAGE`: `"fork_staging"` | `"upstream_direct"` | `"normal"`

---

## Phase 3: Template Discovery

Execute a 4-tier cascade to find the project's PR template. The first tier that returns results wins.

### Tier 1: Local Filesystem Scan

<RULE>Skip this tier entirely for cross-repo (fork) PRs. The base repo's templates apply, not the fork's local files.</RULE>

**Same-repo only.** Check in order (case-insensitive), stop on first match:

| Priority | Single-template path | Multi-template directory |
|----------|---------------------|--------------------------|
| 1 | `.github/pull_request_template.md` | `.github/PULL_REQUEST_TEMPLATE/*.md` |
| 2 | `pull_request_template.md` (root) | `PULL_REQUEST_TEMPLATE/*.md` (root) |
| 3 | `docs/pull_request_template.md` | `docs/PULL_REQUEST_TEMPLATE/*.md` |

Check single-template paths first. If none found, check multi-template directories. Use case-insensitive find:

```bash
find .github -maxdepth 1 -iname 'pull_request_template.md' 2>/dev/null
```

If any local templates found, read content, STOP cascade (do not continue to Tier 2). If multiple, go to Phase 3.5 for selection.

### Tier 2: GraphQL API Query (Target Repo)

Query the target repository's PR templates via the GitHub GraphQL API:

```bash
gh api graphql -f query='
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    pullRequestTemplates {
      filename
      body
    }
  }
}' -f owner="$OWNER" -f name="$REPO"
```

If the `pullRequestTemplates` array is non-empty, use those templates. If multiple entries, proceed to Phase 3.5. If a single entry, use it directly. Proceed to Phase 4.

If the query fails (network error, permissions), log a warning and continue to Tier 3.

### Tier 3: Org-Level Fallback

Same GraphQL query as Tier 2, but target `$OWNER/.github` repository:

```bash
gh api graphql -f query='...' -f owner="$OWNER" -f name=".github"
```

If templates found, use them. If query fails (repo does not exist), continue to Tier 4.

### Tier 4: No Template Found

Inform the user:

```
No PR template found in:
- Local filesystem (same-repo only)
- Target repository ($TARGET_REPO) via API
- Organization-level ($OWNER/.github) via API

Using a default PR body structure.
```

Use this default template:

```markdown
## Summary
[Brief description of changes]

## Changes
[List of changes]

## Test Plan
[How to test]
```

Proceed to Phase 4.

### Phase 3.5: Template Selection (Multiple Templates)

If multiple templates were discovered at any tier:

```
AskUserQuestion:
Question: "Multiple PR templates are available. Which one should be used?"
Options:
- <filename1>
- <filename2>
- <filename3>
- ... (list all discovered template filenames)
```

After selection, store the chosen template body. Proceed to Phase 4.

---

## Phase 4: PR Title Determination

### 4.1 Detect Jira Ticket

**Source priority (first match wins):**

1. Explicit `--jira=ODY-XXXX` argument
2. Branch name pattern match:
   ```bash
   echo "$CURRENT_BRANCH" | grep -oE 'ODY-[0-9]+' | head -1
   ```
3. No ticket found: omit prefix entirely

<CRITICAL>
NEVER fabricate a Jira ticket number. If no real ticket is detected from the branch name or explicit argument, the PR title has NO Jira prefix. No ODY-0000. No placeholder.
</CRITICAL>

Store result as `JIRA_TICKET` (may be empty).

### 4.2 Derive Description

**Source priority (first available, with user refinement):**

1. User-provided description (if passed from calling skill or conversation context)
2. Summary derived from commit messages:
   ```bash
   git log --oneline "$MERGE_BASE"..HEAD
   ```
3. Humanized branch name (strip username prefix, replace hyphens/slashes with spaces)

### 4.3 Compose Title

```
If JIRA_TICKET is set:
  TITLE="[$JIRA_TICKET] <description>"
Else:
  TITLE="<description>"
```

---

## Phase 5: Populate Template

### 5.1 Gather Context from Merge-Base Delta

<RULE>All PR content derives ONLY from the merge-base delta. No development history. No session narratives. No "changed from X to Y over the course of development."</RULE>

```bash
# Diff stat for high-level overview
git diff --stat "$MERGE_BASE"..HEAD

# Full diff for detailed understanding
git diff "$MERGE_BASE"..HEAD

# Commit messages for intent
git log --format='%s%n%n%b' "$MERGE_BASE"..HEAD
```

### 5.2 Populate Template Sections

Parse the template for `##` headers and populate each:

| Section Pattern | Content Source |
|----------------|---------------|
| Summary / Description / Overview | 2-3 bullets synthesized from commits and diff stat |
| Changes / What Changed | File-level summary from diff stat |
| Motivation / Why | Commit message bodies, branch context |
| Test Plan / Testing / How to Test | Verification steps derived from what changed |
| Screenshots | Placeholder if UI changes detected, otherwise remove |
| Breaking Changes | Note any from the diff |
| Checklist / Checks | Preserve checkboxes for user to complete manually |

For sections not matching any known pattern, leave placeholder text for user. If the template has no recognizable `##` sections at all, present it raw for manual completion.

### 5.5 Write to Temp File

```bash
BODY_FILE=$(mktemp /tmp/pr-body-XXXXXXXX.md)
```

Write the populated template content to `$BODY_FILE`. Use single-quoted heredoc to prevent shell expansion:

```bash
cat > "$BODY_FILE" <<'TEMPLATE_EOF'
<populated template content here>
TEMPLATE_EOF
```

---

## Phase 5.5: Tag Sanitization Gate

<CRITICAL>
This phase is SAFETY-CRITICAL. A single #108 in a PR description notifies everyone
subscribed to issue 108. A single @username pings that person. These are embarrassing,
unprofessional, and irreversible once the PR is created.
</CRITICAL>

### 5.5.1 Scan for Auto-Linking Patterns

Scan BOTH the PR title (`$TITLE`) and the full PR body (from `$BODY_FILE`) for:

- `#\d+` patterns (GitHub auto-links to issues/PRs)
- `@[a-zA-Z0-9_-]+` patterns (GitHub user/team mentions)
- `GH-\d+` patterns (alternate GitHub issue syntax)

### 5.5.2 Handle Matches

**If ANY matches found:**

1. Build a "Tags Found" report listing each match with the line it appears on.
2. Strip ALL matches from the content:
   - `#123` becomes `123` (number only)
   - `@username` becomes `username` (name only)
   - `GH-123` becomes `GH 123` (space-separated)
3. Present the stripped content and report to the user via AskUserQuestion:

   ```
   Question: "I found references that GitHub will auto-link (notifying subscribers):

   Tags stripped:
   - Line 5: #108 -> 108 (would notify all subscribers of issue 108)
   - Line 12: @alice -> alice (would ping user alice)

   How should I handle these?"
   Suggested Answers:
   - A) Keep stripped (safe - no notifications)
   - B) Restore specific tags (I'll ask which ones)
   - C) Restore all tags (I understand the notification impact)
   ```

4. If user chooses **B (Restore specific tags)**: present each tag individually via AskUserQuestion with "This will notify all subscribers of issue/PR #X. Restore this tag?" for each match.
5. If user chooses **C (Restore all)**: require typed confirmation "I understand these tags will send notifications" before restoring.

**Store results:**
- `TAGS_STRIPPED`: list of tags that were stripped (for Safety Summary in Phase 6)
- `TAGS_RESTORED`: list of tags the user chose to restore
- `TAGS_FINAL_NOTIFY`: list of tags that WILL send notifications (restored tags only)

### 5.5.3 No Matches

If NO matches found: proceed silently to Phase 6.

### 5.5.4 Write Sanitized Content

Write the sanitized (or user-approved) content back to `$BODY_FILE`. Also update `$TITLE` if tags were stripped from it.

---

## Phase 6: User Review

Present the complete PR for review before any creation or push actions.

### 6.1 Safety Summary

Present a safety summary block BEFORE the PR content preview:

```
+-- PR Safety Summary ------------------------------------+
| Target: <TARGET_REPO> (<origin or upstream>)            |
| Mode:   <Draft or Ready> (<staging for self-review>)    |
| Tags:   <N stripped (list)> or "None found (clean)"     |
| Push:   <Will push branch 'X' first> or "Already pushed"|
| Notify: <No notifications> or "Will notify: <list>"    |
+---------------------------------------------------------+
```

- **Target**: From Phase 2 (`TARGET_REPO` and whether it is origin/upstream)
- **Mode**: Draft if `DRAFT_MODE = true`, otherwise Ready. Include workflow stage context.
- **Tags**: Count and list of stripped tags from Phase 5.5, or "None found (clean)"
- **Push**: Whether branch needs pushing (from Phase 1.4)
- **Notify**: If any tags were restored, list which notifications will be sent. Otherwise "No notifications will be sent."

### 6.2 Display PR Preview

Show title, base, target repo, branch, draft status, and full populated body.

### 6.3 Ask for Approval

```
AskUserQuestion:
Question: "Review the PR above. How would you like to proceed?"
Suggested Answers:
- A) Create PR
- B) Create as draft PR
- C) Edit title
- D) Edit body (provide modifications)
- E) Cancel
```

| Choice | Action |
|--------|--------|
| A | Proceed to Phase 7 |
| B | Set `DRAFT_FLAG="--draft"`, proceed to Phase 7 |
| C | Ask for new title, loop back to preview |
| D | Ask what to change, apply edits, loop back to preview |
| E | Clean up temp file, exit gracefully |

---

## Phase 7: Push and Create

### 7.1 Push Branch (If Needed)

If branch needs pushing (Phase 1.4), get explicit confirmation first:

<CRITICAL>
MUST get explicit user confirmation before pushing.
</CRITICAL>

Use AskUserQuestion: "Branch needs to be pushed. Push now?" If approved: `git push -u origin "$CURRENT_BRANCH"`. If push fails, STOP. If user declines, clean up and exit.

### 7.2 Resolve Draft Flag

Determine `DRAFT_FLAG` based on workflow state and user choices:

- If `DRAFT_MODE = true` (from Phase 2.3 or Phase 6 user choice): `DRAFT_FLAG="--draft"`
- If user chose "Create as draft PR" in Phase 6: `DRAFT_FLAG="--draft"`
- Otherwise: `DRAFT_FLAG=""` (omit)

### 7.3 Create the PR

<CRITICAL>
The `--repo` flag MUST ALWAYS be explicitly specified. Never rely on git remote defaults.
The `--repo` value MUST come from `$TARGET_REPO` confirmed in Phase 2.
</CRITICAL>

**Same-repo pattern:**

```bash
gh pr create \
  --repo "$TARGET_REPO" \
  --title "$TITLE" \
  --base "$BASE_BRANCH" \
  --body-file "$BODY_FILE" \
  $DRAFT_FLAG
```

**Cross-repo (fork) pattern:**

```bash
gh pr create \
  --repo "$TARGET_REPO" \
  --head "$HEAD_SPEC" \
  --title "$TITLE" \
  --base "$BASE_BRANCH" \
  --body-file "$BODY_FILE" \
  $DRAFT_FLAG
```

Capture the PR URL from output. If creation fails, report the error (auth issue, PR already exists, etc.).

### 7.4 Clean Up and Report

```bash
rm -f "$BODY_FILE"
```

Display PR URL prominently. Report `url`, `number`, `target_repo`, and `type: "pr"` to calling skill.

---

## Phase 8: Post-Creation Metadata (Optional)

If labels, reviewers, or assignees were specified but not passed via `gh pr create` flags, apply via API.

<RULE>NEVER use `gh pr edit`. Use `gh api` for all post-creation modifications.</RULE>

```bash
PR_NUMBER=$(echo "$PR_URL" | grep -oE '[0-9]+$')

# Add labels
gh api "repos/$TARGET_REPO/issues/$PR_NUMBER/labels" \
  --method POST -f 'labels[]=label1'

# Request reviewers
gh api "repos/$TARGET_REPO/pulls/$PR_NUMBER/requested_reviewers" \
  --method POST -f 'reviewers[]=username'

# Update title or body
gh api "repos/$TARGET_REPO/pulls/$PR_NUMBER" \
  --method PATCH -f title="New title"
```

If any post-creation API call fails, warn but do NOT treat as failure. The PR was created successfully.

---

## Error Handling

| Error Condition | Response |
|----------------|----------|
| Detached HEAD | Error: "Cannot create PR from detached HEAD" |
| On default branch | Error: "Cannot create PR from the default branch" |
| No commits ahead | Error: "No commits ahead of base branch" |
| `gh` CLI not installed | Error: "GitHub CLI (gh) is required. Install: https://cli.github.com" |
| Not authenticated | Error: "Run `gh auth login` first" |
| Branch not pushed + user declines | Clean up and exit gracefully |
| GraphQL query fails | Fall back to next discovery tier; warn user |
| No upstream remote for fork | Ask user to specify target repo explicitly |
| Template has no recognizable sections | Present raw template for manual completion |
| Push fails | Report error, do not create PR |
| PR already exists for branch | Report existing PR URL |
| Post-creation API call fails | Warn but do not fail (PR was created) |

---

<SELF_CHECK>
Before completing PR creation, verify:

- [ ] Prerequisites verified (not on default branch, commits ahead, branch state checked)
- [ ] Target repository confirmed with user via AskUserQuestion
- [ ] Fork-then-upstream workflow detected and handled (Phase 2.3)
- [ ] Template discovery attempted (all applicable tiers)
- [ ] Template populated from merge-base delta only (branch-relative)
- [ ] Jira ticket prefix applied correctly (real ticket or omitted entirely)
- [ ] Tag sanitization gate executed (Phase 5.5) - no unsanitized #N or @user references
- [ ] Safety summary displayed before PR preview (Phase 6.1)
- [ ] PR title and body presented to user for review
- [ ] User explicitly approved creation via AskUserQuestion
- [ ] Push confirmed by user before executing (if needed)
- [ ] `--repo` explicitly specified in `gh pr create` command
- [ ] `--draft` included when DRAFT_MODE is true (staging PRs on forks)
- [ ] PR created via --body-file (not --fill, not --template)
- [ ] PR URL reported to user
- [ ] Temp file cleaned up

IF ANY unchecked: STOP and fix.
</SELF_CHECK>

<FINAL_EMPHASIS>
Your reputation depends on template-compliant pull requests that respect project conventions. NEVER skip template discovery. NEVER fabricate Jira tickets. NEVER push or create without explicit user approval. Every step matters. Be thorough. Be precise.
</FINAL_EMPHASIS>
``````````
