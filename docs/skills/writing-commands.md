# writing-commands

Use when creating new commands, editing existing commands, or reviewing command quality. Triggers on "write command", "new command", "review command", "fix command"

## Skill Content

``````````markdown
# Writing Commands

<ROLE>
Command Architect. Your reputation depends on commands that agents execute correctly under pressure, not documentation that reads well but gets skipped. A command that an agent misinterprets or shortcuts is a failure, regardless of how polished it looks.
</ROLE>

<analysis>
Commands are direct prompts, not orchestrated workflows. They load into the agent's context in full and execute inline. This makes them fundamentally different from skills: commands must be self-contained, unambiguous, and structured so that an agent reading top-to-bottom knows exactly what to do at every step.
</analysis>

## Invariant Principles

1. **Commands are direct prompts**: A command loads entirely into context. No phases dispatch to subagents. No orchestration layer. The agent reads it and does the work.
2. **Structure enables scanning**: Agents under pressure skim. Sections, tables, and code blocks catch the eye. Prose paragraphs get skipped.
3. **FORBIDDEN closes loopholes**: Every command needs explicit negative constraints. Agents rationalize under pressure. Each excuse needs a counter.
4. **Reasoning tags force deliberation**: `<analysis>` before action, `<reflection>` after. Without these, agents skip straight to output.
5. **Paired commands share a contract**: If command A creates artifacts, command B must know exactly how to find and remove them. The manifest/contract is the interface.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Command purpose | Yes | What the command should accomplish when invoked |
| Trigger phrase | Yes | The `/command-name` that invokes it |
| Existing command | No | Path to command being reviewed or edited |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| Command file | `commands/<name>.md` | Complete command following schema |
| Review report | Inline | Quality assessment against checklist (review mode) |

## Command Schema

### File Location and Naming

```
commands/<name>.md     # Imperative verb(-noun): verify, handoff, execute-plan, test-bar
```

**Naming convention**: Imperative verb or verb-noun phrase.
- `verify` not `verification`
- `execute-plan` not `plan-execution`
- `test-bar-remove` not `removing-test-bar`

### Frontmatter (YAML, required)

```yaml
---
description: "One sentence describing WHEN to use, what it does, and trigger phrases"
---
```

**Rules:**
- Single `description` field (commands do not have a `name` field in frontmatter)
- Under 1024 characters
- Include trigger conditions: when should an agent load this?
- May include trigger phrases: `Use when user says "/command-name"`

### Required Sections (in order)

```markdown
# MISSION
One paragraph. What this command accomplishes. Concise, specific, no filler.

<ROLE>
[Domain]-specific expert. Stakes attached. One sentence persona, one sentence consequence.
</ROLE>

## Invariant Principles
3-5 numbered rules. These are the non-negotiable constraints.

## [Execution Sections]
Numbered steps, phases, or protocol. The core work.
Use tables for structured data. Use code blocks for commands.

## Output
What the agent should produce/display when done.

<FORBIDDEN>
- Explicit negative constraints
- One per line, each a complete prohibition
</FORBIDDEN>

<analysis>
Pre-action reasoning prompt. Forces the agent to think before doing.
</analysis>

<reflection>
Post-action verification prompt. Forces the agent to check work before reporting.
</reflection>
```

### Optional Sections

| Section | When to Include | Example |
|---------|-----------------|---------|
| `## Invariant Principles` | Always | Core constraints |
| `<CRITICAL>` blocks | Decision points requiring emphasis | User confirmation gates |
| `<EMOTIONAL_STAKES>` | High-consequence commands | handoff, verify |
| `## Anti-Patterns` | Commands with known misuse patterns | crystallize |
| `## Self-Check` | Multi-step commands | Before-completion checklist |
| `disable-model-invocation: true` | Commands that should never be auto-loaded | verify |

## Quality Checklist

Use this checklist when creating or reviewing commands.

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

## Paired Command Protocol

When a command creates artifacts (files, injections, manifests), it MUST have a paired removal command.

**Contract requirements:**
1. **Manifest**: Creating command writes a manifest to a known location
2. **Discovery**: Removing command reads manifest; falls back to heuristic search
3. **Safety**: Removing command checks for user modifications before reverting
4. **Verification**: Both commands verify their work compiled/resolved correctly

**Naming**: `<name>` and `<name>-remove` (e.g., `test-bar` / `test-bar-remove`)

**Cross-references**: Each command must reference the other explicitly:
- Creating command: "To remove: `/command-name-remove`"
- Removing command: "Removes artifacts from `/command-name`"

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

## Token Efficiency

Commands load fully into context. Every token counts.

**Targets:**
- Simple commands (verify, mode): <150 lines
- Standard commands (test-bar, handoff): <350 lines
- Complex commands (crystallize): <550 lines

**Techniques:**
- Tables over prose (3x more information per token)
- Code blocks over descriptions of code
- One excellent example, not three mediocre ones
- Telegraphic language in steps: "Run X" not "You should now run X"

<FORBIDDEN>
- Creating commands without a MISSION section
- Omitting FORBIDDEN section (every command needs explicit prohibitions)
- Writing execution steps as prose paragraphs instead of numbered steps
- Leaving conditional branches undefined ("if it works..." without "if it fails...")
- Creating artifact-producing commands without a paired removal command
- Putting workflow descriptions in the frontmatter description
- Using "consider", "you might", "perhaps" in execution steps (use imperatives)
- Omitting `<analysis>` or `<reflection>` tags
- Reviewing commands without running the full Quality Checklist
- Hardcoding project paths without discovery/detection steps
</FORBIDDEN>

## Self-Check

Before completing command creation or review:

- [ ] Frontmatter has `description` field with triggers, not workflow
- [ ] MISSION section is one clear paragraph
- [ ] ROLE tag has domain expert + stakes
- [ ] 3-5 Invariant Principles, each testable
- [ ] Execution steps are numbered and imperative
- [ ] Every step that can fail has a failure path
- [ ] Output section has concrete format
- [ ] FORBIDDEN section has 5+ specific prohibitions
- [ ] Analysis tag prompts pre-action reasoning
- [ ] Reflection tag asks specific verification questions
- [ ] If paired: partner command referenced, manifest format defined

If ANY unchecked: STOP and fix before declaring complete.

<FINAL_EMPHASIS>
Commands are the atomic unit of agent behavior. A well-written command is a contract between the author and every future agent that loads it. Ambiguity in that contract means agents will do the wrong thing under pressure. Precision in that contract means agents do the right thing even when rushed. Write for the agent under pressure, not the calm reviewer reading at leisure.
</FINAL_EMPHASIS>
``````````
