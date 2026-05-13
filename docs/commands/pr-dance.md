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
4. **Never merge automatically**: Report merge-ready status. User decides when to merge. This rule is absolute and is NOT overridden by any session-level autonomy directive — including but not limited to "do the PR dance autonomously", "yolo", "just land it", "pick it up where we left off", "stop asking", "go go go", or any equivalent phrasing. "Autonomous" scopes commit / push / comment / iterate / re-request-review. It does not scope merge, tag-push, branch deletion, or any other destructive or visible-to-others action listed in the global git-safety rules. If the user wants you to merge, they will say "merge it" (or equivalent imperative) AFTER you report merge-ready status. Until then: stop at Step 5.
5. **Version bump before first cycle**: If the project uses semver (pyproject.toml, package.json), ensure version bump + CHANGELOG entry exist before the first review cycle. This prevents wasting a cycle on a finding the bot will always flag.
6. **One PR at a time, never wrapped in `/loop`**: This command already polls internally (Step 3 watches CI, Step 4 polls for bot feedback). Wrapping it in `/loop` creates a watcher around a watcher and re-fires the full polling cycle on the loop's timer even after merge-ready. Running it concurrently on multiple PRs multiplies GraphQL load by N. Today's GitHub GraphQL quota is 5000/hour — a single misconfigured run can exhaust it in under an hour.

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

Every `gh pr checks` invocation (with `--watch` or `--json`) is a GraphQL query, so polling cadence directly drives GraphQL quota burn. Use a long interval — CI runs are minutes-long, sub-minute polling is theater.

#### Step 3 pre-flight: GraphQL rate-limit check

Before entering `--watch` or each manual poll, check remaining GraphQL budget. If below threshold, sleep until reset rather than letting the loop crash mid-cycle:

```bash
remaining=$(gh api rate_limit --jq '.resources.graphql.remaining')
reset=$(gh api rate_limit --jq '.resources.graphql.reset')
if [ "$remaining" -lt 200 ]; then
  now=$(date +%s)
  echo "GraphQL low ($remaining); sleeping until reset..."
  sleep $((reset - now + 5))
fi
```

#### Poll for terminal state

```bash
gh pr checks "$PR_NUMBER" --watch --interval 60
```

If `--watch` is unavailable or times out, poll manually with the same cadence — never tighter than 30s:

```bash
gh pr checks "$PR_NUMBER" --json name,state,conclusion
sleep 60
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

<CRITICAL>
This stop point is non-negotiable. Even if the user said "do the PR dance autonomously", "yolo", "just land it", or anything similar at the start of the session, you stop here. Those phrases authorize the iteration loop (commit / push / comment / re-request-review). They do NOT authorize merge.

If you find yourself constructing an argument that "the user clearly wants this merged" or "they said autonomous" or "the dance includes the merge" — STOP. That is the rationalization the global git-safety rule warns about. The user will type "merge it" when they are ready. Until then, the answer is always "ready when you are".

Tag-push (`git push origin vX.Y.Z`) and branch deletion are also out of scope until explicitly requested.
</CRITICAL>

**If either condition not met:** Return to the appropriate step (Step 3 for CI, Step 4 for bot).

## Output

```
PR Dance complete.
- Cycles: N
- PR: <url>
- Status: Merge-ready (CI green, bot review clean)
```

<FORBIDDEN>
- Merging the PR (user decides when to merge — no session-level autonomy directive overrides this)
- Pushing tags (`git push origin vX.Y.Z`) or creating GitHub releases without explicit request
- Deleting the feature branch after merge without explicit request
- Treating "do the PR dance autonomously" / "yolo" / "just land it" as merge authorization
- Hardcoding or assuming a bot name without reading config
- Pushing without addressing ALL bot findings in the current cycle
- Skipping `act` for reproducible CI failures and going straight to blind push
- Re-requesting review without pushing fixes first
- Declaring merge-ready when CI is failing or bot findings are unaddressed
- Using `gh pr edit` for any purpose
- Using `requested_reviewers` API to request bot re-review
- Adding AI attribution or co-authored-by trailers to commits
- Referencing GitHub issue numbers in commit messages
- Invoking this command under `/loop` — it already polls internally; `/loop` creates a watcher around a watcher and re-fires the full cycle on the loop's timer even after merge-ready, exhausting the GitHub GraphQL quota
- Running this command on more than one PR concurrently — serialize across PRs to keep GraphQL spend bounded
- Polling CI checks tighter than 30s (use `--interval 60` with `--watch`, or `sleep 60` between manual polls) — sub-minute polling burns GraphQL quota with no UX benefit, since CI runs are minutes-long
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
</reflection>

### Cycle budget (hard cap)

Track a cycle counter. After **4 cycles** without reaching merge-ready, STOP and surface to the user:

```
PR Dance paused after 4 cycles without converging.
- Last CI state: <green|failing|pending>
- Last bot review: <clean|N findings>
- Suggested causes: flaky test, bot disagreement on a contested change, repeated push without addressing root cause.

How would you like to proceed? (a) continue another N cycles, (b) hand back for manual review, (c) abandon.
```

This is a hard cap, not advice. After 4 cycles, do NOT start a 5th without explicit user confirmation. Repeated cycling without convergence is almost always a signal of a structural problem (flaky test, contested finding, missing context) that more polling will not fix.
``````````
