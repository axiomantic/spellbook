---
name: pr-distill
description: Use when reviewing large PRs to surface changes requiring human attention
---

# PR Distill Skill

<ROLE>PR Review Analyst. Your reputation depends on accurately identifying which changes need human review and which are safe to skip.</ROLE>

Analyzes pull requests to categorize changes by review necessity, reducing cognitive load on large PRs.

## Invariant Principles

1. **Heuristics First, AI Second**: Always run heuristic pattern matching before invoking AI analysis. Heuristics are fast and deterministic.
2. **Confidence Requires Evidence**: Never mark a change as "safe to skip" without a pattern match or AI explanation justifying the confidence level.
3. **Surface Uncertainty**: When confidence is low, categorize as "uncertain" rather than guessing. Humans should decide ambiguous cases.
4. **Preserve Context**: The report must include enough diff context for reviewers to understand changes without switching to the PR itself.

## Execution Flow

This skill uses a **two-phase execution model** where the agent orchestrates multiple tool calls:

<analysis>
When invoked with `/pr-distill <pr>`:
1. Parse PR identifier (number or URL)
2. Run Phase 1: Fetch, parse, heuristic match
3. If unmatched files remain, process AI prompt for pattern discovery
4. Run Phase 2: Score all changes, generate report
5. Present report to user
</analysis>

### Phase 1: Fetch, Parse, Match (returns AI prompt)

```bash
node lib/pr-distill/index.js <pr-identifier>
```

This returns:

- Heuristic analysis results (pattern matches)
- An AI prompt for pattern discovery on unmatched files

### Phase 2: Complete Analysis (after AI processing)

```bash
node lib/pr-distill/index.js --continue <pr-identifier> <ai-response-file>
```

Where `<ai-response-file>` contains the JSON response from processing the AI prompt.

This returns:

- Final scored changes
- Generated markdown report

### Usage

When invoked via `/pr-distill <pr>`:

1. Run initial phase: `node lib/pr-distill/index.js <pr>`
2. If the output contains `__AI_PROMPT_START__`, extract the prompt between markers
3. Process the prompt (pattern discovery analysis)
4. Save the JSON response to a temp file
5. Run continuation: `node lib/pr-distill/index.js --continue <pr> /tmp/ai-response.json`
6. Present the generated report to the user

<reflection>
After completion, verify:
- All files categorized (no files missing from report)
- REVIEW_REQUIRED items have full diffs
- Pattern summary table is accurate
- Discovered patterns listed with bless commands
</reflection>

### Output Markers

The CLI uses markers to delineate machine-readable sections:

- `__AI_PROMPT_START__` / `__AI_PROMPT_END__`: AI prompt content
- `__REPORT_START__` / `__REPORT_END__`: Final markdown report

### Examples

```bash
# Analyze PR by number (uses current repo)
node lib/pr-distill/index.js 123

# Analyze PR by URL
node lib/pr-distill/index.js https://github.com/owner/repo/pull/123

# Continue with AI response
node lib/pr-distill/index.js --continue 123 /tmp/ai-response.json
```

## Configuration

Config file: `~/.local/spellbook/docs/<project-encoded>/pr-distill-config.json`

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

<FORBIDDEN>
- Marking changes as "safe to skip" without pattern match or AI justification
- Skipping Phase 1 heuristics and going straight to AI analysis
- Collapsing "review required" changes to save space
- Blessing patterns automatically without user confirmation
</FORBIDDEN>
