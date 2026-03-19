# writing-skills

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Use when creating new skills, editing existing skills, or verifying skills work before deployment

!!! info "Origin"
    This skill originated from [obra/superpowers](https://github.com/obra/superpowers).

## Workflow Diagram

TDD-driven skill creation workflow using RED-GREEN-REFACTOR cycle. Enforces baseline failure documentation before writing, verification after writing, and loophole closure through rationalization tables. The `write-skill-test` command implements the RED-GREEN-REFACTOR phases via subagent dispatch.

## Cross-Reference Table

| Overview Node | Detail Diagram |
|---------------|----------------|
| ENTRY | [Entry and Classification](#1-entry-and-classification) |
| RED | [RED Phase: Baseline Testing](#2-red-phase-baseline-testing) |
| GREEN | [GREEN Phase: Write Minimal Skill](#3-green-phase-write-minimal-skill) |
| REFACTOR | [REFACTOR Phase: Close Loopholes](#4-refactor-phase-close-loopholes) |
| SELFCHECK | [Self-Check and Deploy](#5-self-check-and-deploy) |

---

## Overview: Writing Skills Workflow

```mermaid
flowchart TD
    subgraph legend [Legend]
        direction LR
        l1[Process]
        l2{Decision}
        l3([Terminal])
        l4[/"Subagent Dispatch"/]
        l5[[Quality Gate]]
    end

    style l4 fill:#4a9eff,color:#fff
    style l5 fill:#ff6b6b,color:#fff
    style l3 fill:#51cf66,color:#fff

    START([Skill request received]) --> INPUTS{Inputs<br>provided?}
    INPUTS -->|"Missing purpose<br>or scenario"| GATHER[Gather: skill purpose,<br>failing scenario,<br>target location]
    GATHER --> CLASSIFY
    INPUTS -->|All present| CLASSIFY

    CLASSIFY{Skill type?}
    CLASSIFY -->|Discipline| ARCH
    CLASSIFY -->|Technique| ARCH
    CLASSIFY -->|Pattern| ARCH
    CLASSIFY -->|Reference| ARCH

    ARCH{Phase count?}
    ARCH -->|"1 phase"| SELF_CONT[Self-contained SKILL.md]
    ARCH -->|"2 phases"| SHOULD_SPLIT[SHOULD separate:<br>orchestrator + commands]
    ARCH -->|"3+ phases"| MUST_SPLIT[MUST separate:<br>orchestrator dispatches,<br>commands implement]
    SELF_CONT --> DISPATCH_RGR
    SHOULD_SPLIT --> DISPATCH_RGR
    MUST_SPLIT --> DISPATCH_RGR

    DISPATCH_RGR[/"Dispatch subagent:<br>write-skill-test command<br>(RED-GREEN-REFACTOR)"/]
    style DISPATCH_RGR fill:#4a9eff,color:#fff

    DISPATCH_RGR --> RED

    RED["RED Phase:<br>Baseline testing<br>without skill"]
    RED --> IRON_LAW[[Iron Law Gate:<br>Baseline failures<br>documented verbatim?]]
    style IRON_LAW fill:#ff6b6b,color:#fff

    IRON_LAW -->|"No failures<br>documented"| BLOCK([BLOCKED:<br>Cannot proceed])
    style BLOCK fill:#ff6b6b,color:#fff
    IRON_LAW -->|"Failures<br>documented"| GREEN

    GREEN["GREEN Phase:<br>Write minimal skill,<br>verify compliance"]
    GREEN --> GREEN_GATE[[GREEN Gate:<br>Agent complies?]]
    style GREEN_GATE fill:#ff6b6b,color:#fff

    GREEN_GATE -->|"Behavior unchanged"| RETRY{Revisions<br>>= 2?}
    RETRY -->|No| GREEN
    RETRY -->|Yes| SWITCH[Switch to discipline<br>approach] --> GREEN
    GREEN_GATE -->|"Agent complies"| REFACTOR

    REFACTOR["REFACTOR Phase:<br>Close loopholes"]
    REFACTOR --> BULLET_GATE[[Bulletproof Gate:<br>No new rationalizations<br>under ALL pressures?]]
    style BULLET_GATE fill:#ff6b6b,color:#fff

    BULLET_GATE -->|"New rationalizations"| REFACTOR
    BULLET_GATE -->|Bulletproof| SELFCHECK

    SELFCHECK[[Self-Check:<br>All checklist items?]]
    style SELFCHECK fill:#ff6b6b,color:#fff

    SELFCHECK -->|"Items unchecked"| FIX[Fix unchecked items] --> SELFCHECK
    SELFCHECK -->|All pass| DEPLOY([Deploy: commit,<br>push, PR])
    style DEPLOY fill:#51cf66,color:#fff

    %% Iron Law enforcement
    START -.->|"Wrote skill<br>before RED?"| DELETE([DELETE skill.<br>Start over.])
    style DELETE fill:#ff6b6b,color:#fff
```

---

## 1. Entry and Classification

Determines inputs, skill type, and multi-phase architecture before dispatching to RED-GREEN-REFACTOR.

```mermaid
flowchart TD
    subgraph legend [Legend]
        direction LR
        l1[Process]
        l2{Decision}
        l3([Terminal])
    end

    START([Skill request]) --> HAS_PURPOSE{Skill purpose<br>provided?}
    HAS_PURPOSE -->|No| ASK_PURPOSE[Ask: what behavior<br>should skill instill?]
    ASK_PURPOSE --> HAS_SCENARIO
    HAS_PURPOSE -->|Yes| HAS_SCENARIO

    HAS_SCENARIO{Failing scenario<br>provided?}
    HAS_SCENARIO -->|No| ASK_SCENARIO[Ask: documented agent<br>behavior WITHOUT skill]
    ASK_SCENARIO --> HAS_LOCATION
    HAS_SCENARIO -->|Yes| HAS_LOCATION

    HAS_LOCATION{Target location<br>provided?}
    HAS_LOCATION -->|No| INFER["Infer from purpose:<br>skills/&lt;name&gt;/SKILL.md"]
    INFER --> CLASSIFY
    HAS_LOCATION -->|Yes| CLASSIFY

    CLASSIFY{Classify skill type}
    CLASSIFY -->|Enforces rules| DISCIPLINE["Discipline:<br>pressure scenarios,<br>rationalization counters"]
    CLASSIFY -->|Concrete steps| TECHNIQUE["Technique:<br>application + edge cases"]
    CLASSIFY -->|Mental model| PATTERN["Pattern:<br>recognition +<br>counter-examples"]
    CLASSIFY -->|API/guide docs| REFERENCE["Reference:<br>retrieval + gap testing"]

    DISCIPLINE --> MULTI
    TECHNIQUE --> MULTI
    PATTERN --> MULTI
    REFERENCE --> MULTI

    MULTI{Phase count?}
    MULTI -->|"1 phase"| SELF["Self-contained SKILL.md"]
    MULTI -->|"2 phases"| SHOULD["SHOULD separate:<br>orchestrator + commands"]
    MULTI -->|"3+ phases"| MUST["MUST separate:<br>orchestrator dispatches,<br>commands implement"]

    SELF --> NAME_CHECK
    SHOULD --> NAME_CHECK
    MUST --> NAME_CHECK

    NAME_CHECK{Naming convention?}
    NAME_CHECK -->|Skill| GERUND["Gerund or noun-phrase:<br>debugging, develop"]
    NAME_CHECK -->|Command| IMPERATIVE["Imperative verb-noun:<br>execute-plan, verify"]
    NAME_CHECK -->|Agent| NOUN_ROLE["Noun-role:<br>code-reviewer"]

    GERUND --> TO_RED([Proceed to RED])
    IMPERATIVE --> TO_RED
    NOUN_ROLE --> TO_RED
    style TO_RED fill:#51cf66,color:#fff
```

---

## 2. RED Phase: Baseline Testing

Runs pressure scenarios WITHOUT the skill to document baseline agent failures verbatim.

```mermaid
flowchart TD
    subgraph legend [Legend]
        direction LR
        l1[Process]
        l2{Decision}
        l3[/"Subagent"/]
        l4[[Quality Gate]]
    end
    style l3 fill:#4a9eff,color:#fff
    style l4 fill:#ff6b6b,color:#fff

    START([RED Phase Start]) --> DESIGN["Design 3+ scenarios<br>combining multiple pressures"]

    DESIGN --> COMBOS["Pressure combinations:<br>Time + complexity<br>Ambiguity + defaults<br>Conflicting constraints<br>Social pressure"]

    COMBOS --> FRACTAL{Complex<br>multi-phase<br>skill?}
    FRACTAL -->|Yes| FRACTAL_THINK[/"Invoke fractal-thinking<br>intensity: pulse<br>seed: temptation scenarios"/]
    style FRACTAL_THINK fill:#4a9eff,color:#fff
    FRACTAL_THINK --> EXPAND["Expand pressure<br>scenario list from<br>synthesis"]
    EXPAND --> SPAWN
    FRACTAL -->|No| SPAWN

    SPAWN[/"Spawn 1 subagent per<br>scenario WITHOUT skill loaded"/]
    style SPAWN fill:#4a9eff,color:#fff

    SPAWN --> CAPTURE["Capture verbatim:<br>- Exact rationalization quotes<br>- Decision deviation points<br>- Pressure-triggered violations<br>- Cross-scenario patterns"]

    CAPTURE --> SAVE[Save baseline documentation]

    SAVE --> VERBATIM_CHECK[[Verbatim Gate:<br>Exact quotes captured,<br>not paraphrased?]]
    style VERBATIM_CHECK fill:#ff6b6b,color:#fff

    VERBATIM_CHECK -->|"Paraphrased<br>or missing"| REDO[Re-run scenarios,<br>capture verbatim]
    REDO --> SPAWN

    VERBATIM_CHECK -->|Verbatim| PRESSURE_CHECK{Single-pressure<br>tests only?}
    PRESSURE_CHECK -->|Yes| REDESIGN["Redesign: combine<br>multiple pressures<br>per scenario"]
    REDESIGN --> SPAWN

    PRESSURE_CHECK -->|"Combined<br>pressures"| PATTERN_CHECK{Rationalization<br>patterns identified<br>across scenarios?}
    PATTERN_CHECK -->|No| MORE["Run additional<br>pressure combos"]
    MORE --> SPAWN
    PATTERN_CHECK -->|Yes| TO_GREEN([Proceed to GREEN])
    style TO_GREEN fill:#51cf66,color:#fff
```

---

## 3. GREEN Phase: Write Minimal Skill

Creates schema-compliant SKILL.md addressing ONLY failures observed in RED, then verifies compliance.

```mermaid
flowchart TD
    subgraph legend [Legend]
        direction LR
        l1[Process]
        l2{Decision}
        l3[/"Subagent"/]
        l4[[Quality Gate]]
        l5([Terminal])
    end
    style l3 fill:#4a9eff,color:#fff
    style l4 fill:#ff6b6b,color:#fff
    style l5 fill:#51cf66,color:#fff

    START([GREEN Phase Start]) --> WRITE["Write minimal SKILL.md<br>addressing ONLY failures<br>observed in RED"]

    WRITE --> SCHEMA[[Schema Compliance Gate]]
    style SCHEMA fill:#ff6b6b,color:#fff

    SCHEMA --> S1{Name: letters,<br>numbers,<br>hyphens only?}
    S1 -->|No| FIX1[Fix name] --> S1
    S1 -->|Yes| S2{YAML frontmatter:<br>name + description<br>&lt; 1024 chars?}
    S2 -->|No| FIX2[Fix frontmatter] --> S2

    S2 -->|Yes| CSO[[CSO Gate:<br>Description quality]]
    style CSO fill:#ff6b6b,color:#fff

    CSO --> S3{"Starts 'Use when...',<br>triggers only,<br>NO workflow summary?"}
    S3 -->|No| FIX3[Rewrite: triggers only,<br>third person] --> S3

    S3 -->|Yes| S3b{"3-10 trigger phrases?<br>Anti-triggers for<br>disambiguation?"}
    S3b -->|No| FIX3b["Add trigger phrases,<br>NOT-for clauses"] --> S3b

    S3b -->|Yes| S4{Required sections?<br>Overview, When to Use,<br>Quick Ref, Common Mistakes}
    S4 -->|No| FIX4[Add missing sections] --> S4

    S4 -->|Yes| S5{Keywords throughout?<br>Errors, symptoms,<br>synonyms, tools}
    S5 -->|No| FIX5[Add keywords] --> S5

    S5 -->|Yes| S6{One excellent<br>example only?}
    S6 -->|No| FIX6["Reduce to single<br>best example"] --> S6

    S6 -->|Yes| S7{"Token budget?<br>&lt; 500 words /<br>&lt; 200 if frequent"}
    S7 -->|Over| FIX7["Trim: cross-ref skills,<br>remove duplication"] --> S7

    S7 -->|Under| VERIFY[/"Run SAME scenarios<br>WITH skill loaded"/]
    style VERIFY fill:#4a9eff,color:#fff

    VERIFY --> GREEN_GATE[[GREEN Gate:<br>Agent behavior<br>changed?]]
    style GREEN_GATE fill:#ff6b6b,color:#fff

    GREEN_GATE -->|"Behavior<br>unchanged"| REV_COUNT{Revision<br>count >= 2?}
    REV_COUNT -->|No| REVISE["Revise skill to<br>address non-compliance"] --> VERIFY

    REV_COUNT -->|Yes| SWITCH["Switch to discipline approach:<br>explicit pressure scenarios +<br>rationalization counters"]
    SWITCH --> WRITE

    GREEN_GATE -->|"Agent complies"| HYPOTHETICAL{Any content added<br>NOT observed in RED?}
    HYPOTHETICAL -->|Yes| REMOVE["Remove hypothetical<br>content"] --> GREEN_GATE
    HYPOTHETICAL -->|No| TO_REFACTOR([Proceed to REFACTOR])
    style TO_REFACTOR fill:#51cf66,color:#fff
```

---

## 4. REFACTOR Phase: Close Loopholes

Iteratively identifies new rationalizations, adds explicit counters, and re-tests until bulletproof.

```mermaid
flowchart TD
    subgraph legend [Legend]
        direction LR
        l1[Process]
        l2{Decision}
        l3[/"Subagent"/]
        l4[[Quality Gate]]
        l5([Terminal])
    end
    style l3 fill:#4a9eff,color:#fff
    style l4 fill:#ff6b6b,color:#fff
    style l5 fill:#51cf66,color:#fff

    START([REFACTOR Start]) --> IDENTIFY["Identify new<br>rationalizations<br>from GREEN testing"]

    IDENTIFY --> FOUND{New<br>rationalizations?}
    FOUND -->|None| FINAL_VERIFY

    FOUND -->|Yes| COUNTER["Add explicit counter<br>for each rationalization"]
    COUNTER --> TABLE["Document in<br>rationalization table:<br>Excuse | Reality"]
    TABLE --> FLAGS["Build red flags list<br>from all test iterations"]

    FLAGS --> RETEST[/"Re-run ALL pressure<br>scenarios with<br>updated skill"/]
    style RETEST fill:#4a9eff,color:#fff

    RETEST --> LOOP_CHECK{New<br>rationalizations<br>appeared?}
    LOOP_CHECK -->|Yes| COUNTER
    LOOP_CHECK -->|No| FINAL_VERIFY

    FINAL_VERIFY[/"Final verification:<br>agent complies under<br>ALL pressure combos"/]
    style FINAL_VERIFY fill:#4a9eff,color:#fff

    FINAL_VERIFY --> BULLET_GATE[[Bulletproof Gate:<br>Compliant under<br>ALL pressures?]]
    style BULLET_GATE fill:#ff6b6b,color:#fff

    BULLET_GATE -->|"New failure mode"| COUNTER
    BULLET_GATE -->|Bulletproof| EVAL{Evaluative<br>output skill?<br>Verdicts/scores/findings}
    EVAL -->|Yes| ASSESSMENT["Run /design-assessment<br>for evaluation framework:<br>dimensions, severity,<br>finding schema, verdicts"]
    ASSESSMENT --> TO_CHECK
    EVAL -->|No| TO_CHECK([Proceed to Self-Check])
    style TO_CHECK fill:#51cf66,color:#fff
```

---

## 5. Self-Check and Deploy

Final quality gate verifying all checklist items before committing and optionally pushing/creating a PR.

```mermaid
flowchart TD
    subgraph legend [Legend]
        direction LR
        l1[Process]
        l2{Decision}
        l3[[Quality Gate]]
        l4([Terminal])
    end
    style l3 fill:#ff6b6b,color:#fff
    style l4 fill:#51cf66,color:#fff

    START([Self-Check Start]) --> CHECKLIST[[Self-Check Gate]]
    style CHECKLIST fill:#ff6b6b,color:#fff

    CHECKLIST --> C1{RED phase:<br>baseline captured<br>verbatim?}
    C1 -->|No| FIX1["Document baseline"] --> C1
    C1 -->|Yes| C2{GREEN phase:<br>behavior change<br>verified?}
    C2 -->|No| FIX2["Re-run verification"] --> C2

    C2 -->|Yes| C3{"Description:<br>'Use when...'<br>+ triggers only?"}
    C3 -->|No| FIX3["Fix description"] --> C3
    C3 -->|Yes| C4{YAML frontmatter<br>valid?}
    C4 -->|No| FIX4["Fix frontmatter"] --> C4

    C4 -->|Yes| C5{Schema sections<br>present?}
    C5 -->|No| FIX5["Add missing sections"] --> C5
    C5 -->|Yes| C6{Token budget<br>met?}
    C6 -->|No| FIX6["Trim content"] --> C6

    C6 -->|Yes| C7{"Multi-phase:<br>3+ phases use<br>orchestrator +<br>commands?"}
    C7 -->|No| FIX7["Extract phase commands"] --> C7
    C7 -->|Yes| C8{"Rationalization table<br>built? (required for<br>discipline type)"}
    C8 -->|"N/A: not discipline"| C9
    C8 -->|No| FIX8["Build table"] --> C8
    C8 -->|Yes| C9{"No workflow summary<br>in description?"}
    C9 -->|No| FIX9["Rewrite description"] --> C9

    C9 -->|Yes| DEPLOY["Commit skill to git"]
    DEPLOY --> PUSH{Push to fork?}
    PUSH -->|No| DONE
    PUSH -->|Yes| DO_PUSH["Push to fork"]
    DO_PUSH --> PR{Broadly useful?}
    PR -->|No| DONE
    PR -->|Yes| CREATE_PR["Create PR"]
    CREATE_PR --> DONE([Complete])
    style DONE fill:#51cf66,color:#fff
```

---

## Source Cross-Reference

| Diagram Node | Source Location |
|---|---|
| Skill type classification | `SKILL.md` Skill Types table (lines 42-48) |
| Multi-phase architecture | `SKILL.md` Multi-Phase Skill Architecture (lines 320-358) |
| Naming conventions | `SKILL.md` Naming Conventions (lines 92-99) |
| Iron Law enforcement | `SKILL.md` Iron Law (lines 204-225), `write-skill-test.md` Iron Law (lines 19-23) |
| RED: pressure scenarios | `write-skill-test.md` RED phase (lines 27-43) |
| RED: fractal exploration | `write-skill-test.md` line 43 |
| RED: spawn subagents | `write-skill-test.md` lines 40-41 |
| RED: verbatim capture | `write-skill-test.md` Invariant Principle 3 (line 11) |
| GREEN: schema compliance | `SKILL.md` SKILL.md Schema (lines 49-89) |
| GREEN: CSO description | `SKILL.md` CSO section (lines 101-119), Description Anatomy (lines 125-131) |
| GREEN: trigger phrases | `SKILL.md` Description Checklist (lines 143-151) |
| GREEN: token budget | `SKILL.md` Token Efficiency (lines 253-261) |
| GREEN: verification run | `write-skill-test.md` GREEN phase (line 59) |
| GREEN: revision limit + switch | `SKILL.md` Iron Law reflection (line 224) |
| GREEN: no hypothetical content | `write-skill-test.md` GREEN phase (line 47) |
| REFACTOR: rationalization table | `write-skill-test.md` REFACTOR phase (lines 63-69) |
| REFACTOR: bulletproofing | `write-skill-test.md` Bulletproofing table (lines 73-80) |
| REFACTOR: red flags list | `write-skill-test.md` Red flags (lines 83-90) |
| Assessment framework | `SKILL.md` Assessment Framework Integration (lines 359-366) |
| Self-check items | `SKILL.md` Self-Check (lines 369-381) |
| Deploy steps | `write-skill-test.md` Skill Creation Checklist Deploy (lines 133-136) |
| Overlap disambiguation | `SKILL.md` The Overlap Problem (lines 196-203) |
| System vs user triggers | `SKILL.md` System-Triggered vs User-Triggered (lines 189-193) |

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
3. **One Excellent Example Beats Many**: Single complete, runnable example in relevant language.
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
| Skill | Gerund (-ing) or noun-phrase | debugging, test-driven-development, develop |
| Command | Imperative verb(-noun) | execute-plan, verify, handoff, audit-green-mirage |
| Agent | Noun-role | code-reviewer, fact-checker |

Name by what you DO, not generic category: `root-cause-tracing` > `debugging-techniques`, `using-skills` not `skill-usage`.

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

## Writing Effective Skill Descriptions

The `description` field matches user requests to skills. Bad descriptions cause the skill to never fire, or fire as a false positive.

### Description Anatomy

1. **Situation** (1 sentence): When this skill applies
2. **Trigger phrases** (3-10 phrases): Natural language that users actually say
3. **Anti-triggers** (optional): When NOT to use this skill, to disambiguate from overlapping skills
4. **Invocation note** (optional): If primarily invoked by other skills, say so

### The Golden Rule: User Phrasings, Not Abstract Situations

<CRITICAL>
Descriptions must contain the words users actually say, not abstract descriptions of situations.

BAD: "Use when debugging bugs or unexpected behavior"
GOOD: "Use when debugging bugs, test failures, or unexpected behavior. Triggers: 'why isn't this working', 'this is broken', 'getting an error', 'stopped working', 'regression', 'crash', 'flaky test', or when user pastes a stack trace."

Users say "this is broken" far more often than "I need to debug." Write for the words they use, not the situation you observe.
</CRITICAL>

### Checklist for Every Description

- [ ] **Contains 3-10 trigger phrases** in quotes that match how users actually talk
- [ ] **Leads with user intent**, not implementation details or internal workflow jargon
- [ ] **Disambiguates from overlapping skills** with "NOT for" or "For X instead, use Y"
- [ ] **Notes invocation path** if primarily called by other skills ("Also invoked by X")
- [ ] **Avoids being too broad** ("Use when writing code" matches everything) or too narrow ("Use only during Phase 2.1 of the develop workflow")
- [ ] **No internal jargon** that only spellbook developers would know

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
Includes behavioral patterns (rapid context switching, multiple changes without isolation) detectable in LLM's own actions, not just user text.

### Common Description Anti-Patterns

| Anti-Pattern | Example | Problem |
|-------------|---------|---------|
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

**If GREEN phase fails** (behavior unchanged after verification): The skill is not addressing the actual failure mode. Document what the agent did, identify the gap, revise, and re-run GREEN. After 2 revisions without change, switch to a discipline-style approach with explicit pressure scenarios and rationalization counters.
</reflection>

## RED-GREEN-REFACTOR

Full implementation in the `write-skill-test` command. Dispatch a subagent to execute it.

1. **RED** - Run pressure scenarios WITHOUT skill. Document baseline failures and rationalizations verbatim.
2. **GREEN** - Write minimal skill addressing specific baseline failures. Verify compliance with same scenarios.
3. **REFACTOR** - Close new loopholes. Build rationalization table. Re-test until bulletproof.

**Dispatch template:**
```
Task(
  description: "RED-GREEN-REFACTOR skill testing",
  prompt: """
First, invoke the write-skill-test command using the Skill tool.
Then follow its complete workflow.

## Context

Skill purpose: [what the skill should do]
Skill type: [discipline/technique/pattern/reference]
Target location: skills/<name>/SKILL.md
Pressure scenarios to test: [describe scenarios]
"""
)
```

## Token Efficiency

**Targets:** Frequently-loaded or startup skills: <200 words. All other skills: <500 words.

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
``````````
