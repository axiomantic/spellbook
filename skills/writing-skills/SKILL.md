---
name: writing-skills
description: Use when creating new skills, editing existing skills, or verifying skills work before deployment
---

# Writing Skills

<ROLE>
Skill Architect + TDD Practitioner. Reputation depends on skills that actually change agent behavior under pressure, not documentation that gets ignored.
</ROLE>

<analysis>
Skill creation = TDD for documentation. Test failure reveals what agents actually need.
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

| Type | Purpose | Examples |
|------|---------|----------|
| Technique | Concrete steps | condition-based-waiting, root-cause-tracing |
| Pattern | Mental model | flatten-with-flags, test-invariants |
| Reference | API docs, guides | office docs, library guides |

## Structure

```
skills/<name>/
  SKILL.md              # Required. Inline if <100 lines
  supporting-file.*     # Only for heavy reference (100+ lines) or reusable tools
```

**Frontmatter (YAML only):**
- `name`: letters, numbers, hyphens only
- `description`: Start "Use when...", third person, triggers only, <500 chars
  - NEVER summarize workflow (causes agents to skip body)

## RED-GREEN-REFACTOR

<reflection>
Same cycle as code TDD. Baseline reveals natural agent behavior before intervention.
</reflection>

**RED:** Run pressure scenario WITHOUT skill. Document:
- Choices made
- Rationalizations used (verbatim quotes)
- Which pressures triggered violations

**GREEN:** Write minimal skill addressing those specific failures. Re-run. Verify compliance.

**REFACTOR:** New rationalization? Add counter. Build table. Re-test until bulletproof.

## Testing by Skill Type

| Type | Test Approach | Success Criteria |
|------|---------------|------------------|
| Discipline | Academic + pressure scenarios | Follows rule under max pressure |
| Technique | Application + edge cases | Applies correctly to new scenario |
| Pattern | Recognition + counter-examples | Knows when/when not to apply |
| Reference | Retrieval + gap testing | Finds and applies info correctly |

## Naming Conventions

| Asset | Pattern | Examples |
|-------|---------|----------|
| Skill | Gerund (-ing) or noun-phrase | debugging, test-driven-development |
| Command | Imperative verb | execute-plan, verify, handoff |
| Agent | Noun-role | code-reviewer, fact-checker |

## Token Efficiency

Target: <500 words. Getting-started skills: <150 words.

- Reference --help instead of documenting all flags
- Cross-reference other skills instead of repeating
- One example, not multi-language

## CSO (Claude Search Optimization)

```yaml
# BAD: Workflow summary - agents skip body
description: Use when executing plans - dispatches subagent per task with code review

# GOOD: Triggers only
description: Use when executing implementation plans with independent tasks
```

Include: error messages, symptoms ("flaky", "hanging"), synonyms, tool names.

## Bulletproofing Discipline Skills

Build rationalization table from testing:

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |

Add red flags list. Add explicit counters. Test under combined pressures (time + sunk cost + authority).

<FORBIDDEN>
- Writing skill without documenting baseline failure first (RED phase skipped)
- Summarizing workflow in description (causes agents to skip body)
- Multiple examples when one excellent example suffices
- Deploying without verification run (GREEN phase skipped)
- Ignoring new rationalizations discovered during testing
</FORBIDDEN>

## Iron Law

```
NO SKILL WITHOUT FAILING TEST FIRST
```

Applies to new skills AND edits. Write before testing? Delete. Start over. No exceptions.

## Self-Check

Before completing:
- [ ] RED phase documented: baseline agent behavior without skill captured
- [ ] GREEN phase verified: skill changes behavior in re-run
- [ ] Description starts "Use when..." and contains only triggers
- [ ] YAML frontmatter has `name` and `description`
- [ ] Schema compliance: ROLE, Inputs, Outputs, FORBIDDEN, Self-Check present
- [ ] Token budget: <500 words for core instructions

If ANY unchecked: STOP and fix.

## Checklist

**RED:** Create pressure scenarios, run WITHOUT skill, document baseline
**GREEN:** YAML frontmatter, "Use when..." description, address baseline failures, run WITH skill
**REFACTOR:** Add counters for new rationalizations, build tables, re-test
**Deploy:** Commit, push, consider PR if broadly useful

**REQUIRED BACKGROUND:** Understand test-driven-development skill first.
