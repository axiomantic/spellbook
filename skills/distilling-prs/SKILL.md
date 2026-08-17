---
name: distilling-prs
description: "Use when triaging, categorizing, or summarizing PR changes to decide where human attention should go. Triggers: 'summarize this PR', 'what changed in PR #X', 'triage PR', 'which files need review', 'PR overview', 'categorize changes', or pasting a PR URL. NOT for: judging code quality or producing findings on a branch — unspecified-scope branch review such as 'review this branch' or 'code review' DEFAULTS to advanced-code-review, and an explicitly lightweight pass ('quick review') goes to code-review. This skill triages and summarizes; it does not review. Never bypass the review skills for a raw Explore dispatch, even when the user's concerns seem narrow or specific."
intro: |
  PR triage and categorization that extracts patterns from pull request diffs for fast review prioritization. Uses heuristic pattern matching to classify changes as safe-to-skip, needs-review, or uncertain, so human reviewers can focus their time on what matters. This core spellbook skill is useful when facing a backlog of PRs or when you need a quick summary of what changed.
---

# PR Distill Skill

<ROLE>PR Review Analyst. Your reputation depends on accurately identifying which changes need human review and which are safe to skip.</ROLE>

## Invariant Principles

1. **Heuristics First, AI Second**: Always run heuristic pattern matching before invoking AI analysis. Heuristics are fast and deterministic.
2. **Confidence Requires Evidence**: Never mark a change as "safe to skip" without a pattern match or AI explanation justifying the confidence level.
3. **Surface Uncertainty**: When confidence is low, categorize as "uncertain" rather than guessing. Humans decide ambiguous cases.
4. **Preserve Context**: Report must include enough diff context for reviewers to understand changes without switching to the PR itself.

## Tool Integration

Use `gh` CLI for PR data and `git` for local diffs. Pattern matching is done in-context by the AI against the diff output.

| Tool | Purpose |
|------|---------|
| `gh pr view` | Fetch PR metadata (number, title, files, diff) |
| `gh pr diff` | Get unified diff for the PR |
| `git diff` | Local branch diff against merge-base |

## Execution Flow

Three-phase model: heuristics → AI analysis → report.

<analysis>
When invoked with `/distilling-prs <pr>`:
1. Parse PR identifier (number or URL)
2. Run Phase 1: Fetch, parse, heuristic match
3. If unmatched files remain, use AI to analyze remaining changes
4. Run Phase 3: Generate report categorizing all changes
5. Present report to user
</analysis>

### Phase 1: Fetch, Parse, Match

```bash
# Fetch PR data and diff via gh CLI
gh pr view <PR_NUMBER> --json number,title,body,files,additions,deletions
gh pr diff <PR_NUMBER>
```

For local branches (no PR yet):
```bash
git diff $(git merge-base HEAD main)...HEAD
```

Read the diff output and apply heuristic pattern matching in-context against the known builtin patterns (see Builtin Patterns section below).

Produces:
- `matched`: Files with pattern matches (categorized as review_required / safe_to_skip / uncertain)
- `unmatched`: Files requiring AI analysis

**On tool failure**: If `gh` CLI or `git` fails, halt and surface the error to the user. Do not proceed with partial data.

### Phase 2: AI Analysis (if needed)

<CRITICAL>
Before dispatching any subagent to analyze the PR, load the `reviewing-prs`
skill and compute `review_source`. Triage runs against the fetched diff, but
the local working tree is on a different branch; a subagent that reads a
changed file locally in `DIFF_ONLY` mode categorizes the pre-PR code and
reports it as the PR's. `reviewing-prs` owns that decision and the context
block the subagent must receive.
</CRITICAL>

For unmatched files, analyze each to determine:
- **review_required**: Significant logic, API, or behavior changes
- **safe_to_skip**: Formatting, comments, trivial refactors
- **uncertain**: When confidence is low, surface for human decision

### Phase 3: Generate Report

Produce a markdown report with:
1. Summary of changes by category (review_required, safe_to_skip, uncertain)
2. Full diffs for review_required items
3. Pattern matches with confidence levels
4. Discovered patterns (can be added to config for future triage)

<reflection>
After completion, verify:
- All files categorized (no files missing from report)
- REVIEW_REQUIRED items have full diffs
- Pattern summary table is accurate
- Discovered patterns listed with config update instructions
</reflection>

### Examples

```bash
# Analyze PR by number (uses current repo context)
gh pr view 123 --json number,title,body,files,additions,deletions
gh pr diff 123

# Analyze PR by URL (extract number and use gh)
gh pr view 123 --json number,title,body,files

# For local branch analysis
MERGE_BASE=$(git merge-base HEAD main)
git diff $MERGE_BASE...HEAD

# Add a discovered pattern to config (manual)
# Edit ~/.local/spellbook/docs/<project>/distilling-prs-config.json
# and add to "blessed_patterns" array
```

## Configuration

Config file: `~/.local/spellbook/docs/<project-encoded>/distilling-prs-config.json`

```json
{
  "blessed_patterns": ["query-count-json", "import-cleanup"],
  "always_review_paths": ["**/migrations/**", "**/permissions.py"],
  "query_count_thresholds": {
    "relative_percent": 20,
    "absolute_delta": 10
  }
}
```

## Builtin Patterns

15 builtin patterns across three confidence levels. Apply these heuristically against the diff output in Phase 1.

**Always Review** (5): migration files, permission changes, model changes, signal handlers, endpoint changes

**High Confidence** (5): settings changes, query count JSON, debug print statements, import cleanup, gitignore updates

**Medium Confidence** (5): backfill commands, decorator removals, factory setup, test renames, test assertion updates

<FORBIDDEN>
- Marking changes as "safe to skip" without pattern match or AI justification
- Skipping Phase 1 heuristics and going straight to AI analysis
- Collapsing "review required" changes to save space
- Blessing patterns automatically without user confirmation
</FORBIDDEN>

<FINAL_EMPHASIS>
Heuristics before AI, always. A mis-categorized "safe to skip" sends a reviewer past a breaking change. Surface uncertainty rather than hide it.
</FINAL_EMPHASIS>
