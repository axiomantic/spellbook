# Develop Skill Discipline

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.develop-discipline`.

Phase non-fungibility inside the develop skill, and the thoroughness contract that invoking develop establishes.

**Why keep it:** Stops the develop skill from collapsing its own phases into a single dispatch.

**If you decline:** The agent may combine develop phases into one dispatch and may compress phases when it judges the work small or the session short.

**Related artifacts:**

- `skills/develop`
- `commands/feature-design`
- `commands/feature-implement`

## Rule Content

``````````markdown
<CRITICAL>
### Develop Skill Phase Non-Fungibility

When inside /develop or any of its sub-skills (feature-config, feature-research,
feature-discover, feature-design, feature-implement), every Task() dispatch
executes EXACTLY ONE row of the dispatch table at
`$SPELLBOOK_DIR/skills/develop/SKILL.md` "Subagent Dispatch Points" section.

Combining rows into a single dispatch is forbidden EVEN WHEN:

- The feature is "small" or classified STANDARD ("doesn't need all gates")
- The architecture is "pre-validated" or the operator "pre-resolved forks"
- The operator said "wrap up", "and pause", "finish X items", or "close out"
- Standing autonomous mode is active
- Prior phases produced strong context
- Subagents would burn context if dispatched separately
- "It would be more efficient to combine..."
- "We're trying to wrap up..."
- "The user wants to pause..."

ALL of those listed rationalizations are phase-collapse rationalizations.
Recognizing the rationalization IS the signal to stop, not the signal that
the situation is exceptional. The dispatch table has no exception column.

Each Task() dispatch inside /develop must be preceded by a Phase Declaration
block (see `$SPELLBOOK_DIR/skills/develop/SKILL.md` "Pre-Dispatch Ritual").
The block makes phase collapse mechanically detectable to the operator in
real time. A dispatch without a preceding Phase Declaration is a process
failure even if the work product is correct.

### Develop = Thoroughness Mode (Operator Contract)

If the `core-philosophy` module is installed, its "steady correctness over speed"
rule is the general form of this contract.

Invoking the develop skill is the operator's explicit opt-in to thoroughness.
Treat that invocation as a durable instruction that correctness and thoroughness
always outrank speed for the duration of the work. An operator who wants speed
will say so explicitly and will not invoke the develop skill; the presence of
develop in the active skill list IS the contract.

Operational implications when the develop skill (or any of its sub-skills)
is active:

- NO operator phrasing during develop is license to compress phases.
  Not "wrap up", not "and pause", not "finish X items", not "save tokens",
  not "be efficient", not standing autonomous mode, not "pre-resolved forks".
- If the operator wants speed, they will say so AND they will not invoke
  develop.
- Apparent time pressure ("pause when done", impending session end, etc.)
  is NOT a circumstance that justifies skipping phases. The thorough path
  is the only path inside develop. If completion does not fit, stop where
  thoroughness ends and report the partial state honestly.
- This contract is durable across sessions and applies to every develop
  invocation in every project.
</CRITICAL>
``````````
