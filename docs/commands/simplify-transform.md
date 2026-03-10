# /simplify-transform

## Workflow Diagram

# Diagram: simplify-transform

## Overview

```mermaid
flowchart TD
    ENTRY([Entry:<br/>After /simplify-verify]) --> S5[Step 5:<br/>Presentation]
    S5 --> S6[Step 6:<br/>Application Phase]
    S5 -->|Report-Only mode| EXIT_REPORT([Exit:<br/>No Changes])
    S6 --> DONE([Complete:<br/>Final Summary])
    S5 -->|Error| ERR[Error Handling]
    S6 -->|Error| ERR
    ERR --> EXIT_ERR([Exit:<br/>Error])

    subgraph Legend
        L1[Process Step]
        L2{Decision Point}
        L3([Terminal])
        L4[/User Prompt/]
    end

    style ENTRY fill:#4a9eff,color:#fff
    style EXIT_REPORT fill:#51cf66,color:#fff
    style DONE fill:#51cf66,color:#fff
    style EXIT_ERR fill:#ff6b6b,color:#fff
    style ERR fill:#ff6b6b,color:#fff
```

## Step 5: Presentation

```mermaid
flowchart TD
    S5([Entry: Step 5]) --> GEN_REPORT[5.1: Generate<br/>Simplification Report]
    GEN_REPORT --> MODE{Select Mode}

    MODE -->|Automated| AUTO_PRESENT[5.2: Show Full<br/>Report + Summary]
    MODE -->|Wizard| WIZ_PRESENT[5.3: Present First<br/>Simplification]
    MODE -->|Report-Only| RPT_PRESENT[5.4: Display<br/>Complete Report]

    AUTO_PRESENT --> AUTO_ASK{/User: How<br/>to proceed?/}
    AUTO_ASK -->|Apply all| TO_STEP6([To Step 6:<br/>Application])
    AUTO_ASK -->|Review individually| WIZ_PRESENT
    AUTO_ASK -->|Export report| SAVE_REPORT[5.5: Save Report]
    SAVE_REPORT --> EXIT_NO_CHANGE([Exit:<br/>No Changes])

    WIZ_PRESENT --> WIZ_SHOW[Show Before/After,<br/>Verification Status]
    WIZ_SHOW --> WIZ_ASK{/User: Apply this<br/>simplification?/}
    WIZ_ASK -->|Yes| WIZ_APPLY[Apply Transform,<br/>Show Confirmation]
    WIZ_ASK -->|No| WIZ_SKIP[Skip This One]
    WIZ_ASK -->|Show more context| WIZ_CTX[Show +/-20 Lines]
    WIZ_CTX --> WIZ_ASK
    WIZ_ASK -->|Apply all remaining| TO_STEP6
    WIZ_ASK -->|Stop wizard| WIZ_EXIT([Exit:<br/>Summary of Applied])
    WIZ_APPLY --> WIZ_MORE{More<br/>Remaining?}
    WIZ_SKIP --> WIZ_MORE
    WIZ_MORE -->|Yes| WIZ_PRESENT
    WIZ_MORE -->|No| TO_STEP6

    RPT_PRESENT --> RPT_SAVE{--save-report<br/>specified?}
    RPT_SAVE -->|Yes| SAVE_RPT_FILE[Save to File]
    RPT_SAVE -->|No| EXIT_RPT([Exit:<br/>No Changes])
    SAVE_RPT_FILE --> RPT_JSON{--json flag?}
    RPT_JSON -->|Yes| SAVE_JSON[Save as JSON]
    RPT_JSON -->|No| SAVE_MD[Save as Markdown]
    SAVE_JSON --> EXIT_RPT
    SAVE_MD --> EXIT_RPT

    style S5 fill:#4a9eff,color:#fff
    style TO_STEP6 fill:#4a9eff,color:#fff
    style EXIT_NO_CHANGE fill:#51cf66,color:#fff
    style EXIT_RPT fill:#51cf66,color:#fff
    style WIZ_EXIT fill:#51cf66,color:#fff
    style AUTO_ASK fill:#e8daef
    style WIZ_ASK fill:#e8daef
    classDef decision fill:#ff6b6b,color:#fff
    class MODE,RPT_SAVE,RPT_JSON,WIZ_MORE decision
```

## Step 6: Application Phase

```mermaid
flowchart TD
    S6([Entry: Step 6]) --> APPLY_LOOP[6.1: For Each<br/>Approved Simplification]

    APPLY_LOOP --> READ[Read Current<br/>File Content]
    READ --> EDIT[Apply Transform<br/>via Edit Tool]
    EDIT --> VERIFY{Post-Apply<br/>Verification}
    VERIFY -->|Pass| KEEP[Keep Change]
    VERIFY -->|Fail| REVERT[Revert Change,<br/>Mark Failed]
    KEEP --> MORE_APPLY{More<br/>Transforms?}
    REVERT --> MORE_APPLY
    MORE_APPLY -->|Yes| APPLY_LOOP
    MORE_APPLY -->|No| FULL_TEST[6.2: Run Full<br/>Test Suite]

    FULL_TEST --> TEST_RESULT{All Tests<br/>Pass?}
    TEST_RESULT -->|Yes| METRICS[Calculate Final<br/>Complexity Metrics]
    TEST_RESULT -->|No| FIND_CAUSE[Identify Failing<br/>Transformation]
    FIND_CAUSE --> REVERT_CAUSE[Revert Causing<br/>Transformation]
    REVERT_CAUSE --> FULL_TEST

    METRICS --> GIT_ASK{/6.3: Commit<br/>Strategy?/}
    GIT_ASK -->|Atomic per file| ATOMIC[Per-File Commits]
    GIT_ASK -->|Single batch| BATCH[Single Commit]
    GIT_ASK -->|No commit| NO_COMMIT[Leave Unstaged]

    ATOMIC --> ATOM_SHOW[Show Proposed<br/>Commit Message]
    ATOM_SHOW --> ATOM_ASK{/Approve This<br/>Commit?/}
    ATOM_ASK -->|Yes| ATOM_EXEC[git add + commit]
    ATOM_ASK -->|Edit message| ATOM_EDIT[Edit Message]
    ATOM_EDIT --> ATOM_ASK
    ATOM_ASK -->|Skip| ATOM_MORE{More Files?}
    ATOM_ASK -->|Stop| SUMMARY
    ATOM_EXEC --> ATOM_MORE
    ATOM_MORE -->|Yes| ATOM_SHOW
    ATOM_MORE -->|No| SUMMARY

    BATCH --> BATCH_SHOW[Show Proposed<br/>Batch Message]
    BATCH_SHOW --> BATCH_ASK{/Approve Batch<br/>Commit?/}
    BATCH_ASK -->|Yes| BATCH_EXEC[git add all +<br/>commit]
    BATCH_ASK -->|Edit message| BATCH_EDIT[Edit Message]
    BATCH_EDIT --> BATCH_ASK
    BATCH_ASK -->|Switch to atomic| ATOMIC
    BATCH_ASK -->|No commit| NO_COMMIT
    BATCH_EXEC --> SUMMARY

    NO_COMMIT --> SUMMARY[6.4: Final Summary]
    SUMMARY --> DONE([Complete])

    style S6 fill:#4a9eff,color:#fff
    style DONE fill:#51cf66,color:#fff
    style GIT_ASK fill:#e8daef
    style ATOM_ASK fill:#e8daef
    style BATCH_ASK fill:#e8daef
    classDef decision fill:#ff6b6b,color:#fff
    class VERIFY,TEST_RESULT,MORE_APPLY,ATOM_MORE decision
```

## Error Handling

```mermaid
flowchart TD
    ERR([Error Encountered]) --> ERR_TYPE{Error Type}

    ERR_TYPE -->|No functions found| NO_FUNC[Report: No<br/>Opportunities Found]
    NO_FUNC --> SUGGEST_LOWER[Suggest: Lower<br/>--min-complexity]
    SUGGEST_LOWER --> EXIT_ERR([Exit])

    ERR_TYPE -->|Parse error| PARSE[Report: Syntax<br/>Error in File]
    PARSE --> EXIT_ERR

    ERR_TYPE -->|Test failure<br/>during verify| TEST_FAIL[Report: Transform<br/>Would Break Tests]
    TEST_FAIL --> SKIP_ASK{/Continue with<br/>remaining?/}
    SKIP_ASK -->|Yes| CONTINUE([Continue])
    SKIP_ASK -->|No| EXIT_ERR

    ERR_TYPE -->|Missing test command| NO_CMD[Report: Test<br/>Command Not Found]
    NO_CMD --> CMD_OPTS[Options: Configure,<br/>--dry-run, --allow-uncovered]
    CMD_OPTS --> EXIT_ERR

    ERR_TYPE -->|Git repo issues| GIT_ERR{Specific Issue}
    GIT_ERR -->|Not in repo| NOT_REPO[Suggest: Use<br/>Explicit Path]
    GIT_ERR -->|Base not found| NO_BASE[Suggest:<br/>--base=branch]
    NOT_REPO --> EXIT_ERR
    NO_BASE --> EXIT_ERR

    ERR_TYPE -->|Unsupported language| LANG[Report: Language<br/>Not Supported]
    LANG --> LANG_NOTE[Note: Generic<br/>Simplifications Available]
    LANG_NOTE --> EXIT_ERR

    style ERR fill:#ff6b6b,color:#fff
    style EXIT_ERR fill:#ff6b6b,color:#fff
    style CONTINUE fill:#51cf66,color:#fff
    style SKIP_ASK fill:#e8daef
    classDef decision fill:#ff6b6b,color:#fff
    class ERR_TYPE,GIT_ERR decision
```

## Cross-Reference

| Overview Node | Detail Section | Source |
|---|---|---|
| Step 5: Presentation | Step 5: Presentation | `commands/simplify-transform.md:37-252` |
| Step 6: Application Phase | Step 6: Application Phase | `commands/simplify-transform.md:296-457` |
| Error Handling | Error Handling | `commands/simplify-transform.md:461-543` |

## Legend

```mermaid
flowchart LR
    L1[Process Step]
    L2{Decision Point}
    L3([Terminal])
    L4[/User Prompt/]
    style L1 fill:#4a9eff,color:#fff
    style L2 fill:#ff6b6b,color:#fff
    style L3 fill:#51cf66,color:#fff
    style L4 fill:#e8daef
```

## Command Content

``````````markdown
# /simplify-transform

<ROLE>
Simplification Applier. Your reputation depends on applying ONLY verified transformations with explicit user approval, reverting on any verification failure. Unauthorized commits or unverified changes are failures, regardless of apparent correctness.
</ROLE>

**Runs after `/simplify-verify`.** Applies changes in Automated, Wizard, or Report-Only mode.

## Invariant Principles

1. **Behavior preservation is mandatory** - Every transformation must pass verification; no changes without proof of equivalence
2. **Never commit without approval** - All git operations require explicit user consent via AskUserQuestion
3. **Post-application verification** - Re-verify after applying changes; revert on failure
4. **Atomic or batch commits** - User chooses commit granularity; provide clear messages with complexity deltas

<CRITICAL>
This command NEVER commits changes without explicit user approval via AskUserQuestion.
All transformations go through post-application verification.
</CRITICAL>

<FORBIDDEN>
- Committing changes without explicit user approval
- Skipping post-application verification after applying a transformation
- Adding AI attribution (Co-Authored-By, "Generated with Claude Code", bot signatures) to commits, PRs, issues, or comments
- Tagging GitHub issues in commit messages
- Applying transformations that failed verification
- Proceeding after a test failure without user confirmation
- Executing a commit without first displaying the exact commit message to the user for review
</FORBIDDEN>

---

## Step 5: Presentation

Present verified simplifications based on selected mode.

### 5.1 Generate Report

Create comprehensive simplification report:

```markdown
# Simplification Analysis: <branch-name or scope>

**Scope:** <X functions in Y files>
**Base:** merge-base with <main|master|devel> @ <commit> (if changeset mode)
**Mode:** <Automated|Wizard|Report>
**Date:** <YYYY-MM-DD HH:MM:SS>

## Summary

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total Cognitive Complexity | <sum_before> | <sum_after> | <delta> (<percent>%) |
| Max Function Complexity | <max_before> | <max_after> | <delta> |
| Functions Above Threshold | <count_before> | <count_after> | <delta> |
| Functions Analyzed | <total> | - | - |
| Simplifications Proposed | <count> | - | - |

## Changes by File

### <file_path>

#### `<function_name>()` - Complexity: <before> -> <after>

**Patterns Applied:**
1. <Pattern name> (<category>)
2. <Pattern name> (<category>)

**Before:**
\`\`\`<language>
<original code with line numbers>
\`\`\`

**After:**
\`\`\`<language>
<transformed code with line numbers>
\`\`\`

**Verification:**
- [x] Syntax valid
- [x] Type check passed
- [x] <N> tests passed
- [x] Complexity reduced by <delta> (<percent>%)

---

## Skipped (No Coverage)

| Function | File | Complexity | Reason |
|----------|------|------------|--------|
| `<function>` | <file> | <score> | 0% test coverage |

Use `--allow-uncovered` to include these functions (higher risk).

## Skipped (Category Disabled)

| Function | File | Pattern | Flag |
|----------|------|---------|------|
| `<function>` | <file> | <pattern> | --no-<category> |

## Skipped (Verification Failed)

| Function | File | Reason |
|----------|------|--------|
| `<function>` | <file> | Parse error: <details> |
| `<function>` | <file> | Type error: <details> |
| `<function>` | <file> | Tests failed: <details> |

## Action Plan

### High Priority (>5 complexity reduction, tested)
- [ ] Apply <N> simplifications in <file>

### Medium Priority (2-5 complexity reduction, tested)
- [ ] Apply <N> simplifications in <file>

### Review Recommended
- [ ] Review <N> flagged dead code blocks
- [ ] Consider adding tests for <N> uncovered functions
```

### 5.2 Automated Mode Presentation

**Present complete batch report:**

1. Show full report with all proposed changes
2. Display summary statistics
3. Ask for batch approval:

```
AskUserQuestion:
Question: "Review complete. Found <N> simplification opportunities. How would you like to proceed?"
Options:
- Apply all simplifications (will verify each before applying)
- Let me review each one individually (wizard mode)
- Export report and exit (no changes)
```

**If "Apply all":**
- Proceed to application phase (Step 6)
- Apply each verified change
- Re-verify after each application

**If "Review individually":**
- Switch to wizard mode
- Proceed to wizard flow

**If "Export report":**
- Save report to specified path or default location
- Exit without changes

### 5.3 Wizard Mode Presentation

**Present one simplification at a time:**

For each simplification in priority order:

```
===============================================================
Simplification <n> of <total>
Priority: <High|Medium>
===============================================================

File: <file_path>
Function: `<function_name>()`
Complexity: <before> -> <after> (-<delta>, -<percent>%)

Pattern: <Pattern name> (<Category>)
Risk: <Low|Medium|High>

BEFORE:
---------------------------------------------------------------
<original code with highlighting>
---------------------------------------------------------------

AFTER:
---------------------------------------------------------------
<transformed code with highlighting>
---------------------------------------------------------------

Verification:
[ok] Syntax valid
[ok] Type check passed
[ok] <N> tests passed
[ok] Complexity reduced

===============================================================
```

```
AskUserQuestion:
Question: "Apply this simplification?"
Options:
- Yes, apply this change
- No, skip this one
- Show more context (+/-20 lines)
- Apply all remaining (switch to automated)
- Stop wizard (exit)
```

**If "Yes":** Apply the transformation, show confirmation, continue to next.

**If "No":** Skip and continue to next.

**If "Show more context":** Display wider code window, re-present the same question.

**If "Apply all remaining":** Switch to automated mode for remaining items.

**If "Stop wizard":** Exit with summary of what was applied.

### 5.4 Report-Only Mode Presentation

1. Display complete analysis report
2. Show all proposed changes
3. Save report to file if --save-report specified
4. If --json flag: output as JSON instead of markdown

**Exit without applying any changes.**

### 5.5 Save Report

**Default location:** `${SPELLBOOK_CONFIG_DIR:-~/.local/spellbook}/docs/<project-encoded>/reports/simplify-report-<YYYY-MM-DD>.md`

Generate project encoded path:
```bash
# Find outermost git repo (handles nested repos)
# Returns "NO_GIT_REPO" if not in any git repository
_outer_git_root() {
  local root=$(git rev-parse --show-toplevel 2>/dev/null)
  [ -z "$root" ] && { echo "NO_GIT_REPO"; return 1; }
  local parent
  while parent=$(git -C "$(dirname "$root")" rev-parse --show-toplevel 2>/dev/null) && [ "$parent" != "$root" ]; do
    root="$parent"
  done
  echo "$root"
}
PROJECT_ROOT=$(_outer_git_root)

# If NO_GIT_REPO: Ask user if they want to run `git init`, otherwise use _no-repo fallback
[ "$PROJECT_ROOT" = "NO_GIT_REPO" ] && { echo "Not in a git repo - ask user to init or use fallback"; exit 1; }

PROJECT_ENCODED=$(echo "$PROJECT_ROOT" | sed 's|^/||' | tr '/' '-')
```

Create directory if needed: `mkdir -p "${SPELLBOOK_CONFIG_DIR:-~/.local/spellbook}/docs/${PROJECT_ENCODED}/reports"`

**Custom location:** Use --save-report=<path> flag to override

**JSON output:** If --json flag, save as JSON:

```json
{
  "scope": "<scope>",
  "base": "<base_commit>",
  "mode": "<mode>",
  "timestamp": "<iso8601>",
  "summary": {
    "total_complexity_before": "<number>",
    "total_complexity_after": "<number>",
    "delta": "<number>",
    "delta_percent": "<number>",
    "functions_analyzed": "<number>",
    "simplifications_proposed": "<number>"
  },
  "changes": [
    {
      "file": "<path>",
      "function": "<name>",
      "complexity_before": "<number>",
      "complexity_after": "<number>",
      "patterns": ["<pattern1>", "<pattern2>"],
      "before_code": "<code>",
      "after_code": "<code>",
      "verification": {
        "parse": true,
        "type_check": true,
        "tests_passed": "<number>",
        "complexity_reduced": true
      }
    }
  ],
  "skipped": {
    "no_coverage": [],
    "category_disabled": [],
    "verification_failed": []
  }
}
```

---

## Step 6: Application Phase

Apply verified simplifications and integrate with git.

### 6.1 Apply Transformations

**For each approved simplification:**

1. Read the current file content
2. Apply the transformation using the file editing tool (`replace`, `edit`, or `write_file`)
3. Verify the change preserves behavior
4. If verification passes: keep the change
5. If verification fails: revert the change, mark as failed

<CRITICAL>
Re-verify after application even though changes were verified during analysis. Edge cases can emerge from the application context that were not present during static analysis.
</CRITICAL>

### 6.2 Post-Application Verification

**After all transformations applied:**

1. Run full test suite (not just affected tests)
2. Verify all tests pass
3. Calculate final complexity metrics
4. Generate final report

```bash
# Run project test suite
<project_test_command>

# If tests fail, identify which transformation caused the failure
# Revert that transformation
# Re-run tests until passing
```

### 6.3 Git Integration

**After successful application, ask about commit strategy:**

```
AskUserQuestion:
Question: "All simplifications applied successfully. How should I handle commits?"
Options:
- Atomic per file (one commit per file with detailed message)
- Single batch commit (all changes in one commit)
- No commit (leave as unstaged changes for you to commit manually)
```

#### Option 1: Atomic Per File

For each file with changes, show proposed commit message and ask approval:

```
refactor(<scope>): simplify <function-name>

Apply: <pattern1>, <pattern2>
Cognitive complexity: <before> -> <after> (-<percent>%)

Patterns:
- <Pattern description>
- <Pattern description>

Verified: syntax ok types ok tests ok
```

```
AskUserQuestion:
Question: "Commit <file_path> with this message?"
Message:
<show full commit message>

Options:
- Yes, commit with this message
- Edit commit message
- Skip this commit
- Stop (no more commits)
```

**If approved, execute commit:**
```bash
git add <file_path>
git commit -m "<message>"
```

#### Option 2: Single Batch Commit

Show proposed batch commit message and ask approval:

```
refactor: simplify code across <N> files

Cognitive complexity: <total_before> -> <total_after> (-<percent>%)

Files changed:
- <file1>: <function1>, <function2>
- <file2>: <function3>

Patterns applied:
- Guard clauses: <count>
- Boolean simplifications: <count>
- Modern idioms: <count>

Verified: syntax ok types ok tests ok
```

```
AskUserQuestion:
Question: "Commit all changes with this message?"
Message:
<show full commit message>

Options:
- Yes, commit all changes
- Edit commit message
- Switch to atomic commits instead
- No commit (leave unstaged)
```

**If approved, execute commit:**
```bash
git add <all_changed_files>
git commit -m "<message>"
```

#### Option 3: No Commit

```
Changes applied but not committed:
- <file1> (<N> simplifications)
- <file2> (<N> simplifications)

To review: git diff
To commit: git add <files> && git commit -m "your message"
```

### 6.4 Final Summary

```
===============================================================
                 Simplification Complete!
===============================================================

[ok] Simplifications applied: <count>
[ok] Files modified: <count>
[ok] Total complexity reduction: -<delta> (-<percent>%)

Before: <total_before>
After: <total_after>

<If commits made:>
[ok] Commits created: <count>

<If no commits made:>
[!] Changes applied but not committed.

Next steps:
- Run tests: <project_test_command>
- Review changes: git diff
- Commit if needed: git add <files> && git commit
===============================================================
```

---

## Error Handling

### No Functions Found

```
No simplification opportunities found.

Scope: <scope>
Functions analyzed: <count>
Functions above threshold (complexity >= <threshold>): 0

Consider:
- Lowering --min-complexity threshold (current: <value>)
- Using --allow-uncovered to include untested functions
- Checking a different target scope
```

### Parse Errors

```
Cannot analyze <file>: syntax error

<error details>

Fix syntax errors before running simplification analysis.
```

### Test Failures During Verification

```
Verification failed for <function> in <file>

Transformation would break tests:
<test failure details>

This simplification has been skipped.
Continue with remaining simplifications? (yes/no)
```

### Missing Test Command

```
Cannot verify simplifications: test command not found.

Detected project type: <type>
Expected test command: <command>

Options:
1. Configure test command in project settings
2. Use --dry-run for analysis only
3. Use --allow-uncovered (skips test verification, higher risk)
```

### Git Repository Issues

```
Cannot determine changeset: <issue>

<If not in git repo:>
/simplify requires a git repository for changeset analysis.
Use explicit file/directory path instead.

<If base branch not found:>
Cannot find base branch (tried: main, master, devel).
Use --base=<branch> to specify base branch.
Or use explicit file/directory path.
```

### Unsupported Language

```
<file>: language not supported

Supported languages:
- Python (.py)
- TypeScript (.ts, .tsx)
- JavaScript (.js, .jsx)
- Nim (.nim)
- C (.c, .h)
- C++ (.cpp, .cc, .cxx, .hpp)

Generic simplifications (control flow, boolean logic) available for all languages.
Language-specific idioms only available for supported languages.
```

<FINAL_EMPHASIS>
Every commit is permanent. Every unverified change is a liability. Require explicit approval. Revert on failure. The value of this command is trustworthy, auditable simplification - not speed.
</FINAL_EMPHASIS>
``````````
