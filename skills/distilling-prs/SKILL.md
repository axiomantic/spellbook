---
name: distilling-prs
description: "Use when reviewing PRs to triage, categorize, or summarize changes requiring human attention. Triggers: 'summarize this PR', 'what changed in PR #X', 'triage PR', 'which files need review', 'PR overview', 'categorize changes', or pasting a PR URL. NOT for: deep code analysis (use advanced-code-review) or quick review (use code-review)."
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

## MCP Tools

| Tool | Purpose |
|------|---------|
| `pr_fetch` | Fetch PR metadata and diff from GitHub |
| `pr_diff` | Parse unified diff into FileDiff objects |
| `pr_files` | Extract file list from pr_fetch result |
| `pr_match_patterns` | Match heuristic patterns against file diffs |
| `pr_bless_pattern` | Bless a pattern for elevated precedence |
| `pr_list_patterns` | List all available patterns (builtin and blessed) |

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

```python
pr_data = pr_fetch("<pr-identifier>")    # Fetch PR data
diff_result = pr_diff(pr_data["diff"])   # Parse the diff
match_result = pr_match_patterns(
    files=diff_result["files"],
    project_root="/path/to/project"
)
```

Produces:
- `match_result["matched"]`: Files with pattern matches (categorized)
- `match_result["unmatched"]`: Files requiring AI analysis

**On MCP tool failure**: If `pr_fetch` or `pr_match_patterns` fails, halt and surface the error to the user. Do not proceed with partial data.

### Phase 2: AI Analysis (if needed)

For unmatched files, analyze each to determine:
- **review_required**: Significant logic, API, or behavior changes
- **safe_to_skip**: Formatting, comments, trivial refactors
- **uncertain**: When confidence is low, surface for human decision

### Phase 3: Generate Report

Produce a markdown report with:
1. Summary of changes by category (review_required, safe_to_skip, uncertain)
2. Full diffs for review_required items
3. Pattern matches with confidence levels
4. Discovered patterns with bless commands

<reflection>
After completion, verify:
- All files categorized (no files missing from report)
- REVIEW_REQUIRED items have full diffs
- Pattern summary table is accurate
- Discovered patterns listed with bless commands
</reflection>

### Examples

```python
# Analyze PR by number (uses current repo context)
pr_data = pr_fetch("123")

# Analyze PR by URL
pr_data = pr_fetch("https://github.com/owner/repo/pull/123")

# Parse and match
diff_result = pr_diff(pr_data["diff"])
match_result = pr_match_patterns(
    files=diff_result["files"],
    project_root="/Users/alice/project"
)

# Bless a discovered pattern
pr_bless_pattern("/Users/alice/project", "query-count-json")

# List all patterns
patterns = pr_list_patterns("/Users/alice/project")
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

15 builtin patterns across three confidence levels. Use `pr_list_patterns()` to see all with IDs and descriptions.

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
