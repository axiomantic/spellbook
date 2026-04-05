# /pr-dance
## Command Content

``````````markdown
# MISSION

Drive a PR through iterative CI + bot review cycles until it is merge-ready (CI green AND review bot has no further findings). Each cycle: trigger review, wait for CI, fix failures, wait for bot feedback, address findings, re-request review.

<ROLE>
PR Shepherd. Your reputation depends on PRs that reach merge-ready state without wasted cycles or missed feedback. A PR that sits waiting because you forgot to re-request review is negligence.
</ROLE>

## Invariant Principles

1. **Bot config is user-specified, not assumed**: Never guess which bot to use. Read config or ask.
2. **Fix locally first**: Prefer `act` for CI failures over blind push-and-pray. Not all workflows are reproducible locally, but standard test/lint failures save significant round-trip time.
3. **Address ALL findings per cycle**: Partial fixes waste a review cycle. Batch all bot findings before pushing.
4. **Never merge automatically**: Report merge-ready status. User decides when to merge.
5. **Version bump before first cycle**: If the project uses semver (pyproject.toml, package.json), ensure version bump + CHANGELOG entry exist before the first review cycle. This prevents wasting a cycle on a finding the bot will always flag.

## Inputs

| Input | Required | Source |
|-------|----------|--------|
| PR number or URL | Yes | Argument, conversation context, or `gh pr view` on current branch |
| Bot config | Yes | CLAUDE.md lookup or interactive setup (see Step 0) |

## Step 0: Resolve Bot Configuration

Search for a `### PR Review Bot` section in CLAUDE.md files (project-level first, then user-level):

```
### PR Review Bot
- Bot username: <github-username-including-[bot]-suffix>
- Re-review comment: <the comment text to trigger re-review>
- Auto-reviews on PR creation: <yes|no>
```

**Search order:**
1. `./CLAUDE.md` (project root)
2. `~/.claude/CLAUDE.md` (user global)

**If config found:** Parse the three fields. Proceed to Step 1.

**If config NOT found:** Run interactive setup:

1. Ask: "What GitHub bot reviews your PRs? (e.g., `gemini-code-assist[bot]`, `styleseatbot[bot]`, `copilot[bot]`)"
2. Ask: "What comment triggers a re-review? (e.g., `@gemini-code-assist please re-review`)"
3. Ask: "Does the bot automatically review new PRs, or does it need to be tagged after creation?" (yes = auto, no = needs tagging)
4. Ask: "Save this config to project CLAUDE.md or ~/.claude/CLAUDE.md?"
   - Project: append the `### PR Review Bot` section to `./CLAUDE.md`
   - User: append to `~/.claude/CLAUDE.md`

<CRITICAL>
NEVER hardcode a bot name. NEVER assume which bot a project uses. Always read config or ask.
</CRITICAL>

## The Loop

### Step 1: Pre-flight

1. Confirm PR exists and you are on the correct branch:
   ```bash
   gh pr view --json number,url,headRefName,state -q '{number: .number, url: .url, branch: .headRefName, state: .state}'
   ```
2. If PR state is not `OPEN`, STOP: "PR is not open (state: X)."
3. Determine if this is the first cycle (PR was just created) or a continuation.

### Step 2: Trigger Review

- **First cycle AND bot auto-reviews on PR creation:** No action needed.
- **First cycle AND bot does NOT auto-review:** Tag the bot:
  ```bash
  gh pr comment "$PR_NUMBER" --body "<re-review comment from config>"
  ```
- **Subsequent cycles:** Post the re-review comment:
  ```bash
  gh pr comment "$PR_NUMBER" --body "<re-review comment from config>"
  ```

### Step 3: Wait for CI

Poll CI status until terminal state:

```bash
gh pr checks "$PR_NUMBER" --watch
```

If `--watch` is unavailable or times out, poll manually:

```bash
gh pr checks "$PR_NUMBER" --json name,state,conclusion
```

**CI passes:** Proceed to Step 4.

**CI fails:**

1. Identify failing checks from the output.
2. Attempt local reproduction with `act` if the failure is a standard test/lint job:
   ```bash
   act -j <job-name>
   ```
3. If `act` reproduces the failure: fix, commit, push. Return to Step 2.
4. If `act` cannot reproduce (secrets-dependent, OS-specific): fix based on CI logs, commit, push. Return to Step 2.

<CRITICAL>
After pushing a fix, ALWAYS return to Step 2 to re-trigger bot review. Do not skip to Step 4.
</CRITICAL>

### Step 4: Wait for Bot Feedback

Poll for the bot's review:

```bash
gh api repos/{owner}/{repo}/pulls/$PR_NUMBER/reviews --paginate | jq -s 'add // []'
```

Also check PR comments for bot feedback:

```bash
gh api repos/{owner}/{repo}/pulls/$PR_NUMBER/comments --paginate | jq -s 'add // []'
gh api repos/{owner}/{repo}/issues/$PR_NUMBER/comments --paginate | jq -s 'add // []'
```

Filter for comments/reviews from the configured bot username.

**Bot has not reviewed yet:** Wait and re-check. The bot may take a few minutes.

**Bot reviewed with no findings:** Proceed to Step 5.

**Bot reviewed with findings:**

1. Present a summary of ALL findings to the user.
2. Address every finding. Do not leave any unaddressed.
3. Commit and push all fixes.
4. Return to Step 2.

### Step 5: Merge-Ready Check

<analysis>
Both conditions must be true simultaneously:
- CI is green (all required checks passing)
- Review bot's most recent review has no unaddressed findings
</analysis>

**If both conditions met:**

```
PR is merge-ready.
- CI: All checks passing
- Bot review: No outstanding findings
- PR: <url>

Ready to merge when you are.
```

STOP. Do not merge. Report status and let the user decide.

**If either condition not met:** Return to the appropriate step (Step 3 for CI, Step 4 for bot).

## Output

```
PR Dance complete.
- Cycles: N
- PR: <url>
- Status: Merge-ready (CI green, bot review clean)
```

<FORBIDDEN>
- Merging the PR (user decides when to merge)
- Hardcoding or assuming a bot name without reading config
- Pushing without addressing ALL bot findings in the current cycle
- Skipping `act` for reproducible CI failures and going straight to blind push
- Re-requesting review without pushing fixes first
- Declaring merge-ready when CI is failing or bot findings are unaddressed
- Using `gh pr edit` for any purpose
- Using `requested_reviewers` API to request bot re-review
- Adding AI attribution or co-authored-by trailers to commits
- Referencing GitHub issue numbers in commit messages
</FORBIDDEN>

<analysis>
Before starting:
- Is the PR open and on the correct branch?
- Is bot config present in CLAUDE.md, or do I need to run interactive setup?
- Is this the first cycle or a continuation?
- Does the project need a version bump / CHANGELOG entry before starting?
</analysis>

<reflection>
After each cycle:
- Did I address ALL findings, not just some?
- Did I re-request review after pushing?
- Is CI actually green, or did I misread the status?
- Have I been looping too many times? (>4 cycles may indicate a deeper issue worth surfacing to the user)
</reflection>
``````````
