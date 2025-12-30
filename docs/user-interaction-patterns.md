# User Interaction Patterns

## Overview

This document defines how skills should handle user interaction. Consistent patterns improve user experience and enable autonomous mode to work correctly.

## The AskUserQuestion Tool

**ALWAYS use the AskUserQuestion tool** when a skill needs user input. Never use plain text questions that require the user to type free-form responses when structured options are possible.

### Why AskUserQuestion?

1. **Multiple choice is faster** - Users can click instead of typing
2. **Options guide decisions** - Good options educate users about trade-offs
3. **Recommendations show expertise** - Mark the best option to help users decide
4. **Structured responses enable automation** - Easier to process in autonomous mode

## When to Use AskUserQuestion

| Situation | Use AskUserQuestion? |
|-----------|---------------------|
| Binary choice (yes/no, proceed/cancel) | YES - provide 2 options |
| Multiple approach options | YES - provide 2-4 options |
| Configuration preferences | YES - provide common choices |
| Approval gate (review before continuing) | YES - "Approve" / "Request changes" / "Skip" |
| Need specific file path or identifier | NO - ask in plain text |
| Need free-form description | NO - ask in plain text |
| Explaining what you're about to do | NO - just explain |

## Option Design Guidelines

### Always Include a Recommendation

Mark your recommended option with "(Recommended)" in the label:

```markdown
Question: "Which testing approach should we use?"
Options:
- Unit tests first (Recommended) - Faster feedback, easier to write
- Integration tests first - Tests real interactions but slower
- Both in parallel - Comprehensive but more work upfront
```

### Provide Clear Descriptions

Each option should explain:
- What it means
- Why someone might choose it
- Any trade-offs

```markdown
Question: "How should we handle the existing data?"
Options:
- Migrate in place (Recommended)
  Description: Update existing records to new schema. Faster but requires downtime.
- Copy and transform
  Description: Create new table, copy data, swap. Zero downtime but uses 2x storage.
- Start fresh
  Description: New table, archive old data. Cleanest but requires data re-entry.
```

### Limit Options to 2-4

More than 4 options overwhelms users. If you have more:
- Group related options into categories
- Ask a higher-level question first, then drill down
- Use hierarchical questions

### Always Allow "Other"

The AskUserQuestion tool automatically includes "Other" for custom input. Don't add your own "Other" option.

## Question Design Guidelines

### Be Specific

```markdown
// BAD - Too vague
Question: "What would you like to do?"

// GOOD - Specific context
Question: "The design has 3 minor issues. How should we proceed?"
```

### Include Context

```markdown
// BAD - Missing context
Question: "Which database?"

// GOOD - Context included
Question: "Research found two databases in use: PostgreSQL (main app) and Redis (caching). Which should this feature use?"
```

### Make Questions Actionable

```markdown
// BAD - Not actionable
Question: "Is this approach acceptable?"

// GOOD - Actionable
Question: "Approve this design and proceed to implementation planning?"
Options:
- Approve and continue
- Request specific changes (I'll ask what)
- Reject and start over
```

## Batching Questions

Use the `questions` array to ask up to 4 related questions at once:

```javascript
AskUserQuestion({
  questions: [
    {
      question: "Which authentication method?",
      header: "Auth",
      options: [
        { label: "JWT (Recommended)", description: "Stateless, scalable" },
        { label: "Session-based", description: "Simpler but requires session store" }
      ],
      multiSelect: false
    },
    {
      question: "Which user data to store?",
      header: "User Data",
      options: [
        { label: "Email only", description: "Minimal, privacy-focused" },
        { label: "Email + profile", description: "Richer experience" }
      ],
      multiSelect: false
    }
  ]
})
```

### When to Batch vs. Sequential

| Batch (multiple questions at once) | Sequential (one at a time) |
|-----------------------------------|---------------------------|
| Questions are independent | Later questions depend on earlier answers |
| All are simple choices | Some need discussion |
| User has context for all | User needs explanation between questions |

## Integration with Autonomous Mode

### Design for Both Modes

When writing skills, design questions so they can be:
1. Asked interactively when user wants involvement
2. Answered automatically when autonomous mode provides defaults

### Provide Default Behaviors

Document what happens if the question isn't asked (autonomous mode):

```markdown
## Autonomous Mode Behavior

When autonomous mode is active:

### Skip These Questions
- "Which approach?" - Use the recommended approach
- "Approve design?" - Auto-approve if no critical issues

### Still Ask These Questions (Circuit Breakers)
- "Delete existing data?" - Never auto-approve destructive operations
- "Security-critical choice?" - Always require explicit approval
```

## Examples

### Good: Scope Selection

```javascript
AskUserQuestion({
  questions: [{
    question: "What scope should we analyze?",
    header: "Scope",
    options: [
      { label: "Branch changes (Recommended)", description: "All changes since branching from main" },
      { label: "Uncommitted only", description: "Just staged and unstaged changes" },
      { label: "Full repository", description: "Entire codebase - slower but comprehensive" }
    ],
    multiSelect: false
  }]
})
```

### Good: Approval Gate

```javascript
AskUserQuestion({
  questions: [{
    question: "Design review complete. 2 minor issues found. Proceed?",
    header: "Approval",
    options: [
      { label: "Approve and continue", description: "Accept design, move to implementation planning" },
      { label: "Fix minor issues first", description: "Address the 2 issues before proceeding" },
      { label: "Request major changes", description: "Significant rework needed - I'll explain" }
    ],
    multiSelect: false
  }]
})
```

### Good: Configuration Wizard (Batched)

```javascript
AskUserQuestion({
  questions: [
    {
      question: "How much autonomy should agents have?",
      header: "Autonomy",
      options: [
        { label: "Fully autonomous (Recommended)", description: "Agents proceed without asking, except for critical decisions" },
        { label: "Semi-autonomous", description: "Agents ask for approval at major checkpoints" },
        { label: "Interactive", description: "Agents ask at every decision point" }
      ],
      multiSelect: false
    },
    {
      question: "How should we organize worktrees?",
      header: "Worktrees",
      options: [
        { label: "Single worktree", description: "One isolated workspace for all work" },
        { label: "Per parallel track", description: "Separate worktree for each parallel work stream" },
        { label: "No worktree", description: "Work in current directory" }
      ],
      multiSelect: false
    }
  ]
})
```

## Anti-Patterns to Avoid

### Don't Ask Without Options When Options Exist

```markdown
// BAD
"Should we proceed with option A or option B?"

// GOOD
Use AskUserQuestion with options for A and B
```

### Don't Forget Recommendations

```markdown
// BAD - No guidance
Options: [A, B, C]

// GOOD - Clear recommendation
Options: [A (Recommended), B, C]
```

### Don't Overload With Options

```markdown
// BAD - Too many options
Options: [A, B, C, D, E, F, G]

// GOOD - Grouped or tiered
First question: "Category?" Options: [Development, Testing, Deployment]
Follow-up based on answer with specific options
```

### Don't Ask Unnecessary Questions

```markdown
// BAD - Could be inferred or has obvious answer
"Should I read the file before analyzing it?"

// GOOD - Just do it
[Read file and analyze without asking]
```

## Checklist for Skill Authors

Before finalizing a skill, verify:

- [ ] Every user decision point uses AskUserQuestion (when options exist)
- [ ] All questions have 2-4 well-designed options
- [ ] One option is marked "(Recommended)" with clear reasoning
- [ ] Options have descriptions explaining trade-offs
- [ ] Questions include context needed to decide
- [ ] Autonomous mode behavior is documented
- [ ] Circuit breakers are identified (questions that must always be asked)
