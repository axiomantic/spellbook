# writing-skills

Use when creating new skills, editing existing skills, or verifying skills work before deployment

!!! info "Origin"
    This skill originated from [obra/superpowers](https://github.com/obra/superpowers).

## Skill Content

``````````markdown
# Writing Skills

<ROLE>
Skill Architect + TDD Practitioner. Your reputation depends on skills that actually change agent behavior under pressure, not documentation that gets ignored. A skill that agents skip or rationalize around is a failure, regardless of how well-written it appears.
</ROLE>

<analysis>
Skill creation = TDD for documentation. Baseline failure reveals what agents actually need. Writing skills without testing is like writing code without running it.
</analysis>

## Invariant Principles

1. **No Skill Without Failing Test**: Run scenario WITHOUT skill first. Document baseline failures verbatim. Same as code TDD.
2. **Description Triggers, Not Summarizes**: Description = when to load, never workflow summary. Workflow in description causes agents to skip body.
3. **One Excellent Example Beats Many**: Single complete, runnable example in relevant language. You port well.
4. **Keywords Enable Discovery**: Error messages, symptoms, synonyms throughout. Future Claude must FIND this.
5. **Close Every Loophole Explicitly**: Agents rationalize under pressure. Each excuse needs explicit counter.

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
| Skill | Gerund (-ing) or noun-phrase | debugging, test-driven-development, implementing-features |
| Command | Imperative verb(-noun) | execute-plan, verify, handoff, audit-green-mirage |
| Agent | Noun-role | code-reviewer, fact-checker |

**Principles:**
- Name by what you DO or core insight, not generic category
- `root-cause-tracing` > `debugging-techniques`
- `using-skills` not `skill-usage`

## Claude Search Optimization (CSO)

<CRITICAL>
Description = WHEN to load, NEVER what it does. Workflow in description causes agents to follow description instead of reading skill body.
</CRITICAL>

```yaml
# BAD: Workflow summary - agents skip body
description: Use when executing plans - dispatches subagent per task with code review

# GOOD: Triggers only - forces reading body
description: Use when executing implementation plans with independent tasks
```

**Keyword coverage:**
- Error messages: "Hook timed out", "ENOTEMPTY", "race condition"
- Symptoms: "flaky", "hanging", "zombie", "pollution"
- Synonyms: "timeout/hang/freeze", "cleanup/teardown/afterEach"
- Tools: Actual commands, library names, file types

## Iron Law

```
NO SKILL WITHOUT FAILING TEST FIRST
```

<reflection>
This applies to NEW skills AND EDITS to existing skills.

Write skill before testing? Delete it. Start over.
Edit skill without testing? Same violation.

**No exceptions:**
- Not for "simple additions"
- Not for "just adding a section"
- Not for "documentation updates"
- Don't keep untested changes as "reference"
- Don't "adapt" while running tests
- Delete means delete
</reflection>

## RED-GREEN-REFACTOR

**RED - Write Failing Test (Baseline):**

Run pressure scenario with subagent WITHOUT the skill. Document:
- What choices did they make?
- What rationalizations did they use (verbatim quotes)?
- Which pressures triggered violations?

This is "watch the test fail" - you must see what agents naturally do.

**GREEN - Write Minimal Skill:**

Write skill addressing those specific rationalizations. Don't add extra content for hypothetical cases. Run same scenarios WITH skill. Agent should now comply.

**REFACTOR - Close Loopholes:**

Agent found new rationalization? Add explicit counter. Re-test until bulletproof.

## Bulletproofing Discipline Skills

Build rationalization table from testing:

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Skill is obviously clear" | Clear to you ≠ clear to other agents. Test it. |
| "It's just a reference" | References can have gaps. Test retrieval. |
| "Testing is overkill" | Untested skills have issues. Always. |
| "I'm confident it's good" | Overconfidence guarantees issues. Test anyway. |
| "No time to test" | Deploying untested wastes more time fixing later. |

**Red flags list (agents self-check):**
- Code before test
- "I already manually tested it"
- "Tests after achieve the same purpose"
- "It's about spirit not ritual"
- "This is different because..."

**All of these mean: Delete code. Start over with TDD.**

## Token Efficiency

**Targets:**
- Getting-started skills: <150 words
- Frequently-loaded skills: <200 words
- Other skills: <500 words

**Techniques:**
- Reference `--help` instead of documenting all flags
- Cross-reference other skills: `**REQUIRED BACKGROUND:** test-driven-development`
- One excellent example, not multi-language
- No `@` links (force-loads files, burns context)

## File Organization

| Pattern | When | Example |
|---------|------|---------|
| Self-contained | All content fits | `defense-in-depth/SKILL.md` |
| With tool | Reusable code needed | `condition-based-waiting/SKILL.md` + `example.ts` |
| Heavy reference | Reference 100+ lines | `pptx/SKILL.md` + `pptxgenjs.md` + `ooxml.md` |

## Code Examples

**One excellent example beats many mediocre ones.**

Choose most relevant language:
- Testing techniques → TypeScript/JavaScript
- System debugging → Shell/Python
- Data processing → Python

**Good example:** Complete, runnable, well-commented explaining WHY, from real scenario, ready to adapt.

**Don't:** Implement in 5+ languages, create fill-in-the-blank templates, write contrived examples.

## Flowchart Usage

**Use ONLY for:**
- Non-obvious decision points
- Process loops where you might stop too early
- "When to use A vs B" decisions

**Never use for:** Reference material (→ tables), Code examples (→ markdown), Linear instructions (→ numbered lists).

## Anti-Patterns

| Pattern | Why Bad |
|---------|---------|
| Narrative ("In session 2025-10-03, we found...") | Too specific, not reusable |
| Multi-language dilution | Mediocre quality, maintenance burden |
| Code in flowcharts | Can't copy-paste, hard to read |
| Generic labels (helper1, step3) | Labels need semantic meaning |

## Discovery Workflow

How future Claude finds your skill:

1. Encounters problem ("tests are flaky")
2. Finds SKILL (description matches)
3. Scans overview (is this relevant?)
4. Reads patterns (quick reference table)
5. Loads example (only when implementing)

**Optimize for this flow** - searchable terms early and often.

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

## Skill Creation Checklist

**Use TodoWrite to create todos for EACH item.**

**RED Phase:**
- [ ] Create pressure scenarios (3+ combined pressures for discipline skills)
- [ ] Run scenarios WITHOUT skill - document baseline verbatim
- [ ] Identify patterns in rationalizations/failures

**GREEN Phase:**
- [ ] Name uses only letters, numbers, hyphens
- [ ] YAML frontmatter with name and description (<1024 chars)
- [ ] Description starts "Use when..." - triggers only, NO workflow
- [ ] Description in third person
- [ ] Keywords throughout (errors, symptoms, tools)
- [ ] Clear overview with core principle
- [ ] Address specific baseline failures from RED
- [ ] One excellent example (not multi-language)
- [ ] Run scenarios WITH skill - verify compliance

**REFACTOR Phase:**
- [ ] Identify NEW rationalizations from testing
- [ ] Add explicit counters (for discipline skills)
- [ ] Build rationalization table from all test iterations
- [ ] Create red flags list
- [ ] Re-test until bulletproof

**Quality Checks:**
- [ ] Quick reference table for scanning
- [ ] Common mistakes section
- [ ] Small flowchart only if decision non-obvious
- [ ] No narrative storytelling
- [ ] Supporting files only for tools or heavy reference

**Deploy:**
- [ ] Commit skill to git
- [ ] Push to fork if configured
- [ ] Consider PR if broadly useful

## Multi-Phase Skill Architecture

Skills with multiple phases face a structural decision: what belongs in the orchestrator SKILL.md versus phase commands invoked by subagents?

**When this applies:**

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

**Canonical example:** implementing-features uses 5 commands across 6+ phases. The orchestrator defines phase sequence, dispatch templates, and shared data structures. Each phase command (discover, design, execute-plan, etc.) contains its own implementation logic.

**Anti-Patterns:**

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| Orchestrator invokes Skill tool for a phase command | Loads phase logic into orchestrator context, defeating separation |
| Orchestrator embeds phase logic directly | Monolithic file; orchestrator context bloats with implementation detail |
| Subagent prompt duplicates command instructions | Drift between prompt and command; maintenance burden doubles |
| Monolithic SKILL.md exceeding 500 lines with phase implementation | Signal that phase logic should be extracted to commands |

## Self-Check

Before completing:
- [ ] RED phase documented: baseline agent behavior captured verbatim
- [ ] GREEN phase verified: skill changes behavior in re-run
- [ ] Description starts "Use when..." and contains only triggers
- [ ] YAML frontmatter has `name` and `description`
- [ ] Schema elements present: Overview, When to Use, Quick Reference, Common Mistakes
- [ ] Token budget met: <500 words core instructions
- [ ] Multi-phase architecture: 3+ phase skills separate orchestrator from phase commands
- [ ] No workflow summary in description
- [ ] Rationalization table built (for discipline skills)

If ANY unchecked: STOP and fix before declaring complete.

<FINAL_EMPHASIS>
Creating skills IS TDD for process documentation. Same Iron Law: No skill without failing test first. Same cycle: RED (baseline) → GREEN (write skill) → REFACTOR (close loopholes). If you follow TDD for code, follow it for skills. Untested skills are untested code - they will break in production.

**REQUIRED BACKGROUND:** Understand test-driven-development skill before using this skill.
</FINAL_EMPHASIS>
``````````
