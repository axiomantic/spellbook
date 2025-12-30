# Address PR Feedback

Interactive wizard to analyze and address PR review feedback.

**IMPORTANT:** This command NEVER posts or commits anything without explicit user approval. It guides you through each decision step-by-step.

## Usage
```
/address-pr-feedback [pr-number|pr-url] [--reviewer=username] [--non-interactive]
```

## Arguments
- `pr-number|pr-url`: Optional. PR number (e.g., 9224) or full GitHub URL
- `--reviewer=username`: Optional. Filter comments by specific reviewer (e.g., --reviewer=amethystmarie)
- `--non-interactive`: Optional. Only show the analysis report, skip the wizard

## Step 1: Determine PR and Branch Context

**If PR not provided:**
1. Check if current branch has associated PR using `gh pr list --head $(git branch --show-current)`
2. If found, use AskUserQuestion tool:
   ```
   Question: "Found PR #XXXX for current branch '$(git branch --show-current)'. What would you like to do?"
   Options:
   - Use this PR
   - Enter different PR number
   ```
3. If not found or user chooses different, ask for PR number/URL

**Get PR metadata:**
```bash
gh pr view <pr-number> --json number,title,headRefName,baseRefName,state,author
```

**Determine code state to examine:**
1. Check if local branch matches PR branch: `git branch --show-current`
2. If matches:
   - Compare local vs remote: `git rev-list --left-right --count origin/$(git branch --show-current)...HEAD`
   - Use AskUserQuestion if action needed:
     ```
     Question: "Local branch is <ahead/behind/diverged from> remote. How should we proceed?"
     Options:
     - Use local code state (analyze uncommitted/unpushed changes)
     - Pull latest from remote first
     - Use remote state only (ignore local changes)
     ```
3. If doesn't match: Inform user and use remote branch state

**Store context:**
- PR number and URL
- Branch name (head and base)
- Code source (local or remote)
- Local commit that isn't on remote (if any)

## Step 2: Fetch All Review Comments

Use GitHub GraphQL API to get comprehensive comment data:

```bash
gh api graphql -f query='
{
  repository(owner: "styleseat", name: "styleseat") {
    pullRequest(number: <PR_NUMBER>) {
      title
      reviewThreads(first: 100) {
        nodes {
          id
          isResolved
          isOutdated
          isCollapsed
          comments(first: 20) {
            nodes {
              id
              databaseId
              author { login }
              body
              path
              line
              createdAt
              updatedAt
            }
          }
        }
      }
    }
  }
}'
```

**If --reviewer flag provided:** Filter to only threads started by that reviewer

## Step 3: Categorize Comments

For each thread where `isResolved: false`:

### Category A: Acknowledged (has "Fixed in" type reply)
Look for replies matching patterns:
- `Fixed in <commit>`
- `Addressed in <commit>`
- `Removed in <commit>`
- `Added in <commit>`
- `Deleted in <commit>`
- `Changed in <commit>`
- `Resolved in <commit>`

**But check if needs rework:**
- Are there subsequent comments after the "Fixed in" reply?
- Do those comments indicate more work needed?
- If yes → move to Category C

### Category B: Silently Fixed (no reply but code changed)
For threads without acknowledgment:
1. Get the file path and line number from comment
2. Check if file still exists in current state
3. If file is outdated (isOutdated: true) → likely fixed, verify by checking:
   - `git log --all -S"<relevant code pattern>" -- <file_path>`
   - Read current file state to confirm issue addressed
4. If file exists and not outdated → Category C

### Category C: Unaddressed (needs action)
Comments that:
- Have no "Fixed in" reply AND code hasn't changed
- OR have "Fixed in" reply BUT subsequent comments indicate more work
- OR reviewer explicitly said "This comment was not addressed"

## Step 4: Find Fixing Commits (for Category B)

For each Category B item:

**Use multiple strategies to find the fixing commit:**

1. **Search by file and keyword:**
```bash
# Extract key terms from comment
# Search git log for those terms in that file
git log --all --oneline -S"<keyword>" -- <file_path> | head -10
```

2. **Search by diff pattern:**
```bash
# If comment references specific code, search for when it was removed/changed
git log --all -G"<code_pattern>" -- <file_path>
```

3. **Search by date range:**
```bash
# Find commits after comment was made
git log --all --oneline --since="<comment_created_at>" -- <file_path> | head -20
```

4. **Search commit messages:**
```bash
# Look for commits mentioning the issue
git log --all --oneline --grep="<issue_keyword>" | head -10
```

**Verify the fix:**
- For each candidate commit, check out that commit
- Verify the issue mentioned in comment is actually resolved
- Store commit hash (short form, 8 chars)

## Step 5: Generate Detailed Report

### Report Structure:

```markdown
# PR #<number> Review Comments Analysis

**PR:** <title>
**Branch:** <head> → <base>
**Code State:** <local/remote> (<commit_hash>)
**Reviewer Filter:** <username or "all reviewers">
**Total Unresolved Threads:** <count>

---

## 📊 Summary

- ✅ **Acknowledged & Fixed:** <count> (have "Fixed in" replies)
- 🔍 **Silently Fixed:** <count> (fixed but no reply)
- ⚠️  **Unaddressed:** <count> (need action)

---

## ✅ Category A: Acknowledged & Fixed (<count>)

### <file_path>:<line>
**Reviewer:** @<username>
**Comment:** "<comment_body>"
**Acknowledged:** "Fixed in <commit>" by @<replier>
**Status:** ✅ No further action needed

---

## 🔍 Category B: Silently Fixed (<count>)

These were addressed but never acknowledged with a "Fixed in" comment.

### <file_path>:<line>
**Reviewer:** @<username>
**Comment:** "<comment_body>"
**Analysis:** <how you determined it was fixed>
**Fixing Commit:** <commit_hash> - "<commit_message>"
**Verification:** <snippet showing issue is resolved>

**Proposed Reply:**
```
Fixed in <short_hash>
```

---

## ⚠️  Category C: Unaddressed (<count>)

These require code changes or clarification.

### <priority_level> - <file_path>:<line>
**Reviewer:** @<username>
**Comment:** "<comment_body>"

**Current Code State:**
```<language>
<relevant code snippet from current state>
```

**Issue:** <what needs to change>

**Suggested Fix:**
```<language>
<proposed code change>
```

**Estimated Complexity:** <simple/moderate/complex>
**Follow-up Comments:** <any subsequent discussion>

---

## 🎯 Action Plan

### Immediate Actions (Required)

1. **Post "Fixed in" replies to <count> silently fixed items**
   - Will post <count> replies with commit hashes
   - This will provide proper documentation

2. **Address <count> critical unaddressed comments**
   <detailed list with priorities>

### Next Steps

<checkbox list of specific changes needed>
- [ ] <file>:<line> - <specific change>
- [ ] <file>:<line> - <specific change>
...

### Optional Improvements

<list of suggestion-level comments that aren't blocking>

---

## 📝 Next Steps

The analysis is complete. You can now launch the interactive wizard to:
- Post "Fixed in" replies (with approval)
- Address unaddressed comments (step-by-step)
- Review code context

**The wizard will ask for your approval at each step. Nothing will be posted or committed without your explicit permission.**
```

## Step 6: Interactive Wizard

**CRITICAL:** Use AskUserQuestion tool for ALL user interactions. NEVER post or commit without explicit approval.

**If --non-interactive flag is present:**
- Present the analysis report (Steps 1-5)
- Show the completion message
- Exit without launching the wizard
- Do NOT post replies or make any changes

**Otherwise, launch the wizard:**

### Wizard Flow:

#### Phase 1: Choose Actions
After presenting the analysis report, ask:

```
AskUserQuestion:
Question: "What would you like to do with the analysis results?"
Options:
- Post 'Fixed in' replies for silently fixed items (Category B)
- Start addressing unaddressed comments (Category C)
- Show detailed code context for specific comments
- Export report and exit
```

#### Phase 2A: Post "Fixed in" Replies (if user chose this)

**Show batch summary first:**
```
Found <count> silently fixed items that need "Fixed in <commit>" replies:

1. <file>:<line> by @<reviewer> → "Fixed in <hash>"
   Comment: "<first 80 chars...>"

2. <file>:<line> by @<reviewer> → "Fixed in <hash>"
   Comment: "<first 80 chars...>"

... (list all)
```

**Then ask for batch approval:**
```
AskUserQuestion:
Question: "Post all <count> 'Fixed in' replies?"
Options:
- Post all replies now
- Let me review each one individually
- Skip posting replies
```

**If "review individually":** For each reply, use AskUserQuestion:
```
Question: "Post this reply?"
File: <file>:<line>
Reviewer: @<username>
Comment: "<comment_body>"
Reply: "Fixed in <commit_hash>"

Options:
- Post this reply
- Skip this one
- Edit reply text
- Stop reviewing (post none of the remaining)
```

**If "edit reply":** Allow user to provide custom text, then ask for confirmation again.

**After posting (if any posted):**
```
AskUserQuestion:
Question: "Posted <count> replies. Do you want to commit a record of this action?"
Options:
- Yes, commit with message: "Document fixes in PR review comments"
- No, don't commit anything
```

#### Phase 2B: Address Unaddressed Comments (if user chose this)

**First, ask about commit strategy:**
```
AskUserQuestion:
Question: "How should commits be handled for code fixes?"
Options:
- Commit and push each fix immediately after applying
- Commit each fix locally (don't push)
- Apply all fixes without committing (I'll commit manually later)
```

**Store commit strategy choice.**

**For each Category C item (in priority order):**

1. **Present the issue:**
```
═══════════════════════════════════════════════════════════
Fix <n> of <total>: <file>:<line>

Reviewer: @<username>
Priority: <P0/P1/P2/P3>
Comment: "<full_comment_body>"

Current Code:
───────────────────────────────────────────────────────────
<current code with line numbers and context>
───────────────────────────────────────────────────────────

Suggested Fix:
───────────────────────────────────────────────────────────
<proposed change with diff highlighting>
───────────────────────────────────────────────────────────

Complexity: <simple/moderate/complex>
═══════════════════════════════════════════════════════════
```

2. **Ask for action:**
```
AskUserQuestion:
Question: "What would you like to do with this comment?"
Options:
- Apply suggested fix
- Show me more context (±50 lines)
- Let me fix it manually (skip for now)
- Mark as "will not fix" (skip)
- Stop fixing comments (exit wizard)
```

3. **If "apply suggested fix":**
   - Apply the change using Edit/Write tools
   - Show confirmation: "✅ Applied fix to <file>"
   - If commit strategy is "commit each" or "commit and push each":
     ```bash
     git add <file>
     git commit -m "[PR Review] <short description of fix>

     Addresses comment from @<reviewer> on PR #<number>
     <file>:<line>"
     ```
   - If commit strategy is "commit and push each":
     ```bash
     git push
     ```
   - Ask: "Continue to next comment?"

4. **If "show more context":**
   - Use Read tool with larger offset
   - Show the context
   - Loop back to ask for action again

5. **If "skip" options:**
   - Log the skip reason
   - Continue to next comment

#### Phase 3: Completion Summary

After wizard completes, show summary:
```
═══════════════════════════════════════════════════════════
                    Wizard Complete!
═══════════════════════════════════════════════════════════

✅ Posted "Fixed in" replies: <count>
✅ Applied code fixes: <count>
⏭️  Skipped comments: <count>

<If commits were made:>
📝 Commits created: <count>
🚀 Commits pushed: <count>

<If no commits made:>
⚠️  Changes applied but not committed. Run:
    git status
    git add <files>
    git commit -m "Address PR review feedback"

Next steps:
- Review the changes: git diff
- Run tests to verify fixes
- Update PR if needed
═══════════════════════════════════════════════════════════
```

## Step 7: Enhanced Features

### Priority Detection

Analyze comment body for priority indicators:
- **P0/Blocker:** "blocking", "critical", "must", "breaks", "crash"
- **P1/High:** "should", "important", "performance", "security"
- **P2/Medium:** "consider", "suggest", "could", "maybe"
- **P3/Low:** "nit", "minor", "optional", "nice to have"

### Grouping Related Comments

Group comments by:
1. **File/Module:** All comments in same file
2. **Topic:** e.g., "query optimization", "test coverage", "naming"
3. **Dependency:** Some comments depend on others being fixed first

### Test Coverage Analysis

For comments asking for tests:
1. Check if test files were added in recent commits
2. Look for test files matching patterns mentioned in comment
3. Verify test coverage using project-specific tools

### Query Count Tracking (Project-Specific)

For this Django project, when comments mention query counts:
1. Find query-count JSON files
2. Compare before/after values
3. Check if select_related/prefetch_related were added
4. Verify N+1 issues were resolved

### Diff Visualization

For Category B items, show before/after:
```
Comment: "Remove unused import"

BEFORE (commit <before_hash>):
  import foo
  import bar  # <-- this was removed

AFTER (commit <after_hash>):
  import foo

Fixed in: <after_hash>
```

## Command Behavior

**Interactive-First Design:**
- ALL actions require user approval via AskUserQuestion tool
- Wizard guides user through decisions step-by-step
- User controls commit strategy (commit+push, commit only, or no commits)
- Safe to run - will never modify anything without permission

**Commit Strategy Options:**
1. **Commit and push each:** After each fix, commits and pushes immediately
2. **Commit each:** After each fix, commits locally (user pushes later)
3. **No commits:** Applies fixes but leaves staging to user

## Error Handling

- **PR not found:** Show error, ask for correct PR number
- **No comments found:** Success message, nothing to do
- **API rate limit:** Show current limit, suggest waiting
- **Git conflicts:** Warn user, offer to create branch for fixes
- **Ambiguous fixes:** Mark as needs-manual-review

## Example Output Summary

```
📊 Analysis Complete!

✅ 12 comments acknowledged with "Fixed in" replies
🔍 8 comments silently fixed (will post replies)
⚠️  6 comments still unaddressed (need code changes)

Next: Would you like to post the 8 "Fixed in" replies? (yes/no)
```

---

## Implementation Notes

- Cache API responses to avoid rate limits
- Use git worktree for safe code inspection without affecting working directory
- Store intermediate results in /tmp for resumability
- Log all actions to ~/.claude/logs/review-pr-comments-<timestamp>.log
- Support resuming from previous run if interrupted
