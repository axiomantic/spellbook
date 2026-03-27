---
name: writing-skills
description: "Use when creating new skills, editing existing skills, or verifying skills work before deployment. Triggers: 'write a skill', 'new skill', 'create a skill', 'skill doesn't work', 'skill isn't firing', 'edit skill', 'skill quality'. NOT for: general prompt improvement (use instruction-engineering) or command creation (use writing-commands)."
---

# Writing Skills

<ROLE>
Skill Architect + TDD Practitioner. Your reputation depends on skills that actually change agent behavior under pressure, not documentation that gets ignored. A skill that agents skip or rationalize around is a failure, regardless of how well-written it appears.
</ROLE>

<analysis>
Skill creation = TDD for documentation. Baseline failure reveals what agents actually need. Writing skills without testing is like writing code without running it.
</analysis>

<reflection>
After verification: Verify that the skill actually changes agent behavior in the GREEN phase.
</reflection>

## Invariant Principles

1. **No Skill Without Failing Test**: Run scenario WITHOUT skill first. Document baseline failures verbatim. Same as code TDD.
2. **Description Triggers, Not Summarizes**: Description = when to load, never workflow summary. Workflow in description causes agents to skip body.
3. **One Excellent Example Beats Many**: Single complete, runnable example in relevant language.
4. **Keywords Enable Discovery**: Error messages, symptoms, synonyms throughout. Future Claude must FIND this.
5. **Close Every Loophole Explicitly**: Agents rationalize under pressure. Each excuse needs explicit counter.
6. **Model Versioning Strategy**: Prefer general model aliases (e.g. `sonnet`, `flash`, `pro`) over hardcoded version numbers (e.g. `claude-3-5-sonnet`, `gemini-2.5-flash`). Hardcoded versions are permitted ONLY when a specific behavior is required that differs between versions.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Skill purpose | Yes | What behavior the skill should instill or technique it should teach |
| Failing scenario | Yes | Documented agent behavior WITHOUT the skill (RED phase) |
| Target location | No | `skills/<name>/SKILL.md` path; defaults to inferring from purpose |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| SKILL.md | File | Schema-compliant skill at target location |
| Baseline documentation | Inline | Record of agent behavior before skill (RED phase) |
| Verification result | Inline | Confirmation skill changes behavior (GREEN phase) |

## Skill Types

| Type | Purpose | Test Approach | Examples |
|------|---------|---------------|----------|
| Discipline | Enforces rules/requirements | Pressure scenarios, rationalizations | TDD, verify command |
| Technique | Concrete steps to follow | Application + edge cases | condition-based-waiting, root-cause-tracing |
| Pattern | Mental model for problems | Recognition + counter-examples | flatten-with-flags |
| Reference | API docs, guides | Retrieval + gap testing | office docs, library guides |

## SKILL.md Schema

```
skills/<name>/
  SKILL.md              # Required. Main content inline
  supporting-file.*     # Only for heavy reference (100+ lines) or reusable tools
```

**Frontmatter (YAML only):**
```yaml
---
name: skill-name-with-hyphens   # letters, numbers, hyphens only
description: Use when [triggering conditions and symptoms only, NEVER workflow]
---
```

**Required sections:**
```markdown
# Skill Name

## Overview
What is this? Core principle in 1-2 sentences.

## When to Use
- Bullet list with SYMPTOMS and use cases
- When NOT to use
[Small inline flowchart IF decision non-obvious]

## Core Pattern (for techniques/patterns)
Before/after code comparison

## Quick Reference
Table or bullets for scanning common operations

## Implementation
Inline code for simple patterns
Link to file for heavy reference

## Common Mistakes
What goes wrong + fixes
```

## Naming Conventions

| Asset | Pattern | Examples |
|-------|---------|----------|
| Skill | Gerund (-ing) or noun-phrase | debugging, test-driven-development, develop |
| Command | Imperative verb(-noun) | execute-plan, verify, handoff, audit-green-mirage |
| Agent | Noun-role | code-reviewer, fact-checker |

Name by what you DO, not generic category: `root-cause-tracing` > `debugging-techniques`, `using-skills` not `skill-usage`.

## Writing Effective Skill Descriptions

The `description` field is the most important line in your skill. At startup, only the name and description from every skill are pre-loaded into the system prompt. The skill body is NOT loaded until the agent decides it's relevant. That decision is made entirely from the description.

This makes the description an instruction engineering problem, not just a search optimization problem. You are writing a micro-prompt that tells the agent: "when you see these conditions, load me." Every token in the description competes with 100+ other skill descriptions for the agent's attention. A vague description drowns in the noise. A precise one acts as a reliable classifier.

**The mental model:** Think of descriptions as `if` conditions in the agent's routing logic. The agent scans all descriptions on every user message and asks "does this apply right now?" Your description must answer that question unambiguously in one pass.

<CRITICAL>
Description = WHEN to load, NEVER what it does. Workflow in description causes agents to follow the description instead of reading the skill body. If the agent can extract a plan of action from the description alone, it will skip loading the skill entirely.
</CRITICAL>

### Description Anatomy

1. **Situation** (1 sentence): When this skill applies
2. **Trigger phrases** (3-10 phrases): Natural language that users actually say
3. **Anti-triggers** (optional): When NOT to use this skill, to disambiguate from overlapping skills
4. **Invocation note** (optional): If primarily invoked by other skills, say so

### The Golden Rule: User Phrasings, Not Abstract Situations

<CRITICAL>
Descriptions must contain the words users actually say, not abstract descriptions of situations. Users say "this is broken" far more often than "I need to debug." Write for the words they use, not the situation you observe.
</CRITICAL>

### Keyword Coverage

Spread discoverable terms across the description to maximize match surface:
- **Error messages**: "Hook timed out", "ENOTEMPTY", "race condition"
- **Symptoms**: "flaky", "hanging", "zombie", "pollution"
- **Synonyms**: "timeout/hang/freeze", "cleanup/teardown/afterEach"
- **Tools**: Actual commands, library names, file types

### Checklist for Every Description

- [ ] **Contains 3-10 trigger phrases** in quotes that match how users actually talk
- [ ] **Leads with user intent**, not implementation details or internal workflow jargon
- [ ] **Disambiguates from overlapping skills** with "NOT for" or "For X instead, use Y"
- [ ] **Notes invocation path** if primarily called by other skills ("Also invoked by X")
- [ ] **Avoids being too broad** ("Use when writing code" matches everything) or too narrow ("Use only during Phase 2.1 of the develop workflow")
- [ ] **No internal jargon** that only spellbook developers would know
- [ ] **No workflow leakage**: description contains zero information about what the skill does internally

### BAD vs. GOOD: Real Examples

**Workflow leakage (agent skips body because description contains the plan):**
```yaml
# BAD: Leaks internal structure. Agent reads "5-phase process: strategic planning,
# context analysis, deep review, verification, report generation" and executes
# that plan directly without loading the skill.
description: >
  Use when performing thorough multi-phase code review. 5-phase process:
  strategic planning, context analysis, deep review, verification, report
  generation. More heavyweight than code-review.

# GOOD: Triggers only. Agent knows WHEN to load but must read body to learn HOW.
description: >
  Use when performing thorough code review with historical context tracking.
  Triggers: 'thorough review', 'deep review', 'review this branch in detail',
  'full code review with report'. More heavyweight than code-review; for quick
  review, use code-review instead.
```

**Abstract situation vs. user phrasings:**
```yaml
# BAD: No trigger phrases. Matches "debug" but misses "this is broken",
# "getting an error", "why isn't this working" - what users actually say.
description: Use when debugging bugs or unexpected behavior

# GOOD: Packed with the exact words users type.
description: >
  Use when debugging bugs, test failures, or unexpected behavior. Triggers:
  'why isn't this working', 'this doesn't work', 'X is broken', 'getting an
  error', 'stopped working', 'regression', 'crash', 'flaky test', or when
  user pastes a stack trace. NOT for: test quality issues (use fixing-tests),
  adding new behavior (use develop).
```

**Too thin (no trigger surface):**
```yaml
# BAD: Only matches if user literally says "execute implementation plan."
# Misses "run the plan", "start building", "implement the tasks", "next step."
description: Use when you have a written implementation plan to execute

# GOOD: Covers the ways this situation actually arises.
description: >
  Use when you have an implementation plan ready to execute. Triggers: 'run
  the plan', 'start building from the plan', 'execute tasks', 'implement
  the steps', 'next task'. Also invoked by develop after planning phase.
```

**Pure workflow summary with zero triggers:**
```yaml
# BAD: Describes what the skill does internally. Zero user-facing phrases.
# An agent will never match this to a user saying "how are my skills performing?"
description: >
  Analyze session transcripts to extract skill invocation patterns, score
  invocations, and produce comparative metrics for skill improvement decisions.

# GOOD: Leads with when/why, includes what users actually ask.
description: >
  Use when evaluating skill effectiveness or comparing skill versions.
  Triggers: 'how are skills performing', 'skill metrics', 'which skills fire
  correctly', 'skill invocation analysis', 'compare skill versions'.
```

### Model Descriptions

**`verifying-hunches`** -- Natural speech triggers:
```
"Use when about to claim discovery during debugging. Triggers: 'I found', 'this is the issue',
'root cause', 'smoking gun', 'aha', 'got it', 'the fix is', 'should fix', 'this will fix'.
Also invoked by debugging before any root cause claim."
```
Covers excited discovery ("aha!", "got it") and confident claims ("root cause", "the fix is"). Notes auto-invocation path. Narrow enough to avoid false positives.

**`develop`** -- Scope with anti-triggers:
```
"Use when building, creating, or adding functionality. Triggers: 'implement X', 'build Y',
'add feature Z', 'Would be great to...', 'I want to...', 'We need...'.
NOT for: bug fixes, pure research, or questions about existing code."
```
Covers direct commands ("implement X") and wish-phrasing ("Would be great to..."). "NOT for" section prevents false matches on debugging or research.

**`isolated-testing`** -- Behavioral triggers:
```
"Use when testing theories during debugging, or when chaos is detected.
Triggers: 'let me try', 'maybe if I', 'quick test', rapid context switching,
multiple changes without isolation."
```
Includes behavioral patterns (rapid context switching, multiple changes without isolation) detectable in the agent's own actions, not just user text.

### Common Description Anti-Patterns

| Anti-Pattern | Example | Problem |
|-------------|---------|---------|
| **Workflow leakage** | "3-phase process: plan, execute, verify" | Agent extracts a plan from description and skips loading the skill body entirely. |
| **Abstract-only** | "Use when reviewing code" | No trigger phrases. "Review code" matches but "look at my changes" doesn't. |
| **Jargon-first** | "Use when roundtable returns ITERATE verdict" | Users never say this. Internal workflow trigger with no user-facing phrases. |
| **Too broad** | "Use when writing or modifying code" | Matches every coding task. Will fire constantly as a false positive. |
| **Too narrow** | "Use before design phase only" | Limits to one temporal moment when the skill is useful at many stages. |
| **Implementation detail** | "Modes: --self, --feedback, --give" | Users don't think in flags. They think "review my code" or "I got feedback." |
| **Missing disambiguation** | "Use for code review" | Which of the 4 review skills? No "NOT for" or "instead use" guidance. |

### System-Triggered vs. User-Triggered Skills

- **System-only** (e.g., `reflexion`): Description should state "Invoked by [system/skill], not directly by users"
- **Dual-triggered** (e.g., `tarot-mode`): Description should cover both the system trigger AND user-facing triggers
- **User-only** (e.g., `debugging`): Description should focus entirely on user phrasings

### The Overlap Problem

When multiple skills overlap, each description MUST state why THIS skill and when to use a different one instead:

Example:
- `code-review`: "For focused single-pass review. NOT for: heavy multi-phase analysis (use advanced-code-review) or PR triage (use distilling-prs)."
- `advanced-code-review`: "For thorough 5-phase analysis with historical context. NOT for: quick review (use code-review) or PR categorization (use distilling-prs)."
- `distilling-prs`: "For triaging and categorizing PR changes. NOT for: deep code analysis (use advanced-code-review)."

## Iron Law

```
NO SKILL WITHOUT FAILING TEST FIRST
```

## File Organization

| Pattern | When | Example |
|---------|------|---------|
| Self-contained | All content fits | `defense-in-depth/SKILL.md` |
| With tool | Reusable code needed | `condition-based-waiting/SKILL.md` + `example.ts` |
| Heavy reference | Reference 100+ lines | `pptx/SKILL.md` + `pptxgenjs.md` + `ooxml.md` |

## Code Examples

One excellent example beats many mediocre ones. Choose most relevant language: testing techniques (TypeScript/JavaScript), system debugging (Shell/Python), data processing (Python).

**Good example:** Complete, runnable, well-commented explaining WHY, from real scenario, ready to adapt.

**Don't:** Implement in 5+ languages, create fill-in-the-blank templates, write contrived examples.

## Flowchart Usage

**Use ONLY for:**
- Non-obvious decision points
- Process loops where you might stop too early
- "When to use A vs B" decisions

**Never use for:** Reference material (use tables), Code examples (use markdown), Linear instructions (use numbered lists).

## Anti-Patterns

| Pattern | Why Bad |
|---------|---------|
| Narrative ("In session 2025-10-03, we found...") | Too specific, not reusable |
| Multi-language dilution | Mediocre quality, maintenance burden |
| Code in flowcharts | Can't copy-paste, hard to read |
| Generic labels (helper1, step3) | Labels need semantic meaning |

## Discovery Workflow

1. Encounters problem ("tests are flaky")
2. Finds SKILL (description matches)
3. Scans overview (is this relevant?)
4. Reads patterns (quick reference table)
5. Loads example (only when implementing)

Optimize for this flow - searchable terms early and often.

<FORBIDDEN>
- Writing skill without documenting baseline failure first (RED phase skipped)
- Summarizing workflow in description (causes agents to skip body)
- Multiple examples when one excellent example suffices
- Deploying without verification run (GREEN phase skipped)
- Ignoring new rationalizations discovered during testing
- Creating multiple skills in batch without testing each
- Keeping untested changes as "reference"
- Using `@` links that force-load and burn context
- Generic labels without semantic meaning
- Narrative storytelling about specific sessions
</FORBIDDEN>

## Multi-Phase Skill Architecture

| Phase Count | Requirement |
|-------------|-------------|
| 1 phase | Exempt. Self-contained SKILL.md is fine. |
| 2 phases | SHOULD separate into orchestrator + commands. |
| 3+ phases | MUST separate. Orchestrator dispatches, commands implement. |

**The Core Rule:** The orchestrator dispatches subagents (Task tool). Subagents invoke phase commands (Skill tool). The orchestrator NEVER invokes phase commands directly into its own context.

**Content Split:**

| Orchestrator SKILL.md | Phase Commands |
|----------------------|----------------|
| Phase sequence and transitions | All phase implementation logic |
| Dispatch templates per phase | Scoring formulas and rubrics |
| Shared data structures (referenced by 2+ phases) | Discovery wizards and prompts |
| Quality gate thresholds | Detailed checklists and protocols |
| Anti-patterns / FORBIDDEN section | Review and verification steps |

**Data structure placement:** If referenced by 2+ phases, define in orchestrator. If referenced by 1 phase only, define in that phase's command.

**Soft target:** ~300 lines for orchestrator SKILL.md. The hard rule is about content types: orchestrators contain coordination logic, never implementation logic.

**Exceptions:**
- Config/setup phases requiring direct user interaction MAY run in orchestrator context
- Error recovery MAY load phase context temporarily to diagnose failures

**Canonical example:** develop uses 5 commands across 6+ phases. The orchestrator defines phase sequence, dispatch templates, and shared data structures. Each phase command (discover, design, execute-plan, etc.) contains its own implementation logic.

**Anti-Patterns:**

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| Orchestrator invokes Skill tool for a phase command | Loads phase logic into orchestrator context, defeating separation |
| Orchestrator embeds phase logic directly | Monolithic file; orchestrator context bloats with implementation detail |
| Subagent prompt duplicates command instructions | Drift between prompt and command; maintenance burden doubles |
| Monolithic SKILL.md exceeding 500 lines with phase implementation | Signal that phase logic should be extracted to commands |

## Assessment Framework Integration

For skills producing evaluative output (verdicts, findings, scores, pass/fail):

1. Run `/design-assessment` with the target type being evaluated
2. Copy into the skill: **Dimensions table**, **Severity levels**, **Finding schema**, **Verdict logic**
3. Use vocabulary consistently throughout (CRITICAL/HIGH/MEDIUM/LOW/NIT)

**Example skills:** code-review, auditing-green-mirage, fact-checking, reviewing-design-docs

## Self-Check

Before completing:
- [ ] RED phase documented: baseline agent behavior captured verbatim
- [ ] GREEN phase verified: skill changes behavior in re-run
- [ ] Description starts "Use when..." and contains only triggers
- [ ] YAML frontmatter has `name` and `description`
- [ ] Schema elements present: Overview, When to Use, Quick Reference, Common Mistakes
- [ ] Token budget met: <500 words core instructions (<200 words for frequently-loaded skills)
- [ ] Multi-phase architecture: 3+ phase skills separate orchestrator from phase commands
- [ ] No workflow summary in description
- [ ] Rationalization table built (for discipline skills)

If ANY unchecked: STOP and fix before declaring complete.

<FINAL_EMPHASIS>
Creating skills IS TDD for process documentation. Same Iron Law: No skill without failing test first. Same cycle: RED (baseline) → GREEN (write skill) → REFACTOR (close loopholes). If you follow TDD for code, follow it for skills. Untested skills are untested code - they will break in production.

**REQUIRED BACKGROUND:** Understand test-driven-development skill before using this skill.
</FINAL_EMPHASIS>
