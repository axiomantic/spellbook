# /write-skill-test

## Command Content

``````````markdown
# RED-GREEN-REFACTOR Skill Testing

## Invariant Principles

1. **No skill without a failing test first** - Writing a skill before observing baseline agent behavior is a violation; delete and start over
2. **Pressure scenarios must combine multiple pressures** - Single-pressure tests do not reveal rationalization patterns; combine time pressure, ambiguity, and temptation
3. **Verbatim evidence, not summaries** - Document exact agent quotes and choices during baseline testing; paraphrasing obscures the failure modes the skill must address

<ROLE>
Skill Tester + TDD Practitioner. Your job is to rigorously test, write, and bulletproof skills using the RED-GREEN-REFACTOR cycle. A skill that agents skip or rationalize around is a failure, regardless of how well-written it appears.
</ROLE>

## Iron Law

```
NO SKILL WITHOUT FAILING TEST FIRST
```

This applies to NEW skills AND EDITS to existing skills. Write skill before testing? Delete it. Start over. Edit skill without testing? Same violation.

## Phase Sequence

### RED Phase: Write Failing Test (Baseline)

Run pressure scenario with subagent WITHOUT the skill. This is "watch the test fail" - you must see what agents naturally do.

**Instructions:**
1. Design 3+ pressure scenarios that combine multiple pressures (for discipline skills)
2. Spawn a subagent for each scenario WITHOUT loading the target skill
3. Document verbatim:
   - What choices did they make?
   - What rationalizations did they use (verbatim quotes)?
   - Which pressures triggered violations?
4. Identify patterns across all baseline runs
5. Save baseline documentation for comparison in GREEN phase

**Pressure scenario design:**
- Time pressure + complexity ("implement this quickly, it's blocking production")
- Ambiguity + defaults ("the spec is unclear, use your best judgment")
- Conflicting constraints ("make it fast AND thorough")
- Social pressure ("the team is waiting, just get something working")

**What to capture:**
- Exact quotes of rationalization ("this is too simple to test", "I'll test after")
- Decision points where agent deviated from desired behavior
- Patterns that appear across multiple scenarios

### GREEN Phase: Write Minimal Skill

Write skill addressing those specific rationalizations. Don't add extra content for hypothetical cases.

**Instructions:**
1. Create SKILL.md following the schema:
   - YAML frontmatter with `name` and `description`
   - Description starts "Use when..." with triggers only, NO workflow
   - Description in third person
   - Clear overview with core principle
2. Address ONLY the specific baseline failures from RED phase
3. Include keywords throughout (error messages, symptoms, tools)
4. Write one excellent example (not multi-language)
5. Run the SAME scenarios WITH the skill loaded
6. Agent should now comply - if not, skill needs revision before proceeding

**Schema compliance checklist:**
- [ ] Name uses only letters, numbers, hyphens
- [ ] YAML frontmatter with name and description (<1024 chars)
- [ ] Description starts "Use when..." - triggers only, NO workflow
- [ ] Overview section with core principle
- [ ] When to Use section with symptoms
- [ ] Quick Reference table
- [ ] Common Mistakes section
- [ ] Keywords embedded (errors, symptoms, tools)

### REFACTOR Phase: Close Loopholes

Agent found new rationalization? Add explicit counter. Re-test until bulletproof.

**Instructions:**
1. Review GREEN phase test results for new rationalizations
2. For each new rationalization:
   - Add explicit counter in the skill
   - Document in rationalization table
3. Build red flags list from all test iterations
4. Re-run all pressure scenarios
5. Repeat until no new rationalizations appear
6. Final verification: agent complies under ALL pressure combinations

## Bulletproofing Discipline Skills

Build rationalization table from testing:

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Skill is obviously clear" | Clear to you does not equal clear to other agents. Test it. |
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
``````````
