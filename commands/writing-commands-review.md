---
description: "Review and test a command against the quality checklist. Use when writing-commands skill dispatches Phase 2, or when user says 'review command', 'check command quality'."
---

# MISSION

Evaluate a command against the full quality checklist, identify anti-patterns, and run the testing protocol. Produce a scored review report with actionable fixes.

<ROLE>
Command Quality Auditor. A command that passes your review and still confuses agents is your failure. Be thorough, specific, and constructive.
</ROLE>

## Invariant Principles

1. **Structure enables scanning**: Agents under pressure skim. Sections, tables, and code blocks catch the eye.
2. **FORBIDDEN closes loopholes**: Every command needs explicit negative constraints. Each rationalization needs a counter.
3. **Reasoning tags force deliberation**: `<analysis>` before action, `<reflection>` after. Without these, agents skip to output.

## Quality Checklist

Run every item. No shortcuts.

### Structure (required elements)

- [ ] YAML frontmatter with `description` field
- [ ] `# MISSION` section with clear single-paragraph purpose
- [ ] `<ROLE>` tag with domain expert persona and stakes
- [ ] `## Invariant Principles` with 3-5 numbered rules
- [ ] Execution sections with clear steps (numbered, not prose)
- [ ] `## Output` section defining what agent produces
- [ ] `<FORBIDDEN>` section with explicit prohibitions
- [ ] `<analysis>` tag (pre-action reasoning)
- [ ] `<reflection>` tag (post-action verification)

### Content quality

- [ ] Steps are imperative ("Run X", "Check Y"), not suggestive ("Consider X", "You might Y")
- [ ] Tables used for structured data, not prose paragraphs
- [ ] Code blocks for every shell command and code snippet
- [ ] Every conditional has both branches specified (if X, do Y; if not X, do Z)
- [ ] No undefined failure modes (what happens when things go wrong?)
- [ ] Cross-references use correct paths (verify targets exist)
- [ ] Dev-only guards specified where applicable

### Behavioral

- [ ] Agent knows exactly what to do at every step (no ambiguity)
- [ ] Invariant principles are testable, not aspirational
- [ ] FORBIDDEN section addresses likely shortcuts the agent would take
- [ ] Reflection tag asks specific verification questions, not generic "did I do well?"
- [ ] Output section has a concrete format (not "display results")

### Anti-patterns avoided

- [ ] No workflow summary in description (triggers only)
- [ ] No "consider" or "you might" language (use imperatives)
- [ ] No undefined abbreviations or jargon without context
- [ ] No assumptions about project structure without detection steps
- [ ] No external dependencies not already in the project

## Common Anti-Patterns

| Anti-Pattern | Why It Fails | Fix |
|-------------|-------------|-----|
| Prose-heavy execution steps | Agents skim under pressure, miss details | Use numbered steps, tables, code blocks |
| Missing failure paths | Agent encounters error, has no guidance | Add "If X fails:" after every step that can fail |
| Vague FORBIDDEN section | "Don't do bad things" closes no loopholes | Each prohibition must name a specific action |
| Generic reflection | "Did I do a good job?" prompts rubber-stamping | Ask specific: "Did I check X? Is Y present in Z?" |
| Hardcoded project assumptions | Breaks on different project structures | Add detection/discovery steps before implementation |
| Missing output format | Agent produces unstructured dump | Define exact output template with fields |
| Orphaned paired commands | Create command exists but remove command doesn't | Always create paired commands together |
| Description summarizes workflow | Agent reads description, skips body | Description states WHEN to use, not HOW it works |

## Review Protocol

When reviewing an existing command:

1. **Read the full command** (not a summary)
2. **Run the Quality Checklist** above, marking each item
3. **Score**: Count checked items / total items
4. **Report format**:

```
Command Review: /command-name

Score: X/Y (Z%)

Passing:
  [list of passing checks]

Failing:
  [list of failing checks with specific issues and suggested fixes]

Critical Issues:
  [any issues that would cause the command to malfunction]
```

5. **If score < 80%**: Command needs revision before use
6. **If critical issues found**: Fix immediately, do not just report

## Command Testing Protocol

Before deploying a new command, verify it works:

1. **Dry run**: Load command, explain what you WOULD do (don't execute)
2. **Happy path**: Execute against a known-good scenario
3. **Error path**: Execute against a known-bad scenario
4. **Edge case**: Execute with unusual but valid input

All 4 must produce correct behavior. Document test results.
