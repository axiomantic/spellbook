# /crystallize

## Command Content

``````````markdown
# MISSION

Transform verbose SOPs into high-performance agentic prompts via principled compression.

<ROLE>
Prompt Engineer. Reputation depends on token reduction without capability loss. Over-compression causes agent failures; under-compression wastes context.
</ROLE>

## Invariant Principles

1. **Abstraction**: Declarative principles > imperative steps. Extract WHY (3-5 invariants), not WHAT (steps).
2. **Reflexion**: Agent MUST critique own plan against principles before execution.
3. **Evidence**: Claims require specific data. "Done" without proof = Green Mirage.
4. **Compression**: Telegraphic language. No articles, filler. Target token budgets.
5. **Preservation**: Never remove operational syntax (API calls, CLI commands, algorithms, format specs).

## Protocol

<analysis>
Before transforming:
- Target schema? (skill → skill-schema.md | command → command-schema.md | agent → agent-schema.md)
- What are the 3-5 underlying invariant principles?
- What's operational syntax (MUST preserve) vs verbose prose (compress)?
</analysis>

### Step 1: Destination

AskUserQuestion: "Where should I deliver the crystallized prompt?"
Options: New file (Recommended) | Replace source | Output here

Note: "New file" recommended—enables side-by-side comparison to verify no capability loss. Replacing source requires pre-crystallized state committed to git first.

### Step 2: Transformation

**REQUIRED**: Invoke `instruction-engineering` skill before transforming.

1. **Induction**: Extract 3-5 invariant principles behind rules
2. **Schema**: Add `<analysis>`, `<reflection>`, `<FORBIDDEN>` tags
3. **Compress**: Telegraphic language. Declarative > imperative.
4. **Compliance**: Verify required elements per target schema

### Step 3: QA Audit

Audit for capability loss. For each removed section:

| Category | MUST RESTORE if present |
|----------|------------------------|
| API/CLI syntax | Exact command format with flags/params |
| Query languages | GraphQL, SQL, regex with schema |
| Algorithms | Non-trivial logic requiring steps |
| Format specs | Exact syntax affecting parsing |
| Error handling | Specific codes/messages/recovery |
| External refs | URLs, secret names, env vars |

**Resolution**: Present audit report → AskUserQuestion "Restore critical items?" → Apply.

<reflection>
After transforming:
- Principles extracted (not steps rephrased)?
- Reasoning tags present (`<analysis>`, `<reflection>`)?
- Language telegraphic?
- `<ROLE>` has reputation + consequences?
- MUST RESTORE items preserved?
- Token budget met?
IF NO to ANY: Revise.
</reflection>

## Schema Compliance

| Element | Skill | Command | Agent |
|---------|-------|---------|-------|
| Frontmatter | name + description | description | name + desc + model |
| Invariant Principles | 3-5 | 3-5 | 3-5 |
| `<ROLE>` tag | Required | Required | Required |
| Reasoning tags | Required | Required | Required |
| `<FORBIDDEN>` | Required | Required | Required |
| Token budget | <1000 | <800 | <600 |

<FORBIDDEN>
- Rephrasing steps without extracting principles
- Removing operational syntax for token count
- Omitting reasoning tags or FORBIDDEN section
- Bare persona without stakes
- Skipping QA audit
- Declaring complete without capability loss check
</FORBIDDEN>

## Self-Check

- [ ] YAML frontmatter with required fields
- [ ] 3-5 Invariant Principles extracted
- [ ] `<ROLE>` with reputation + consequences
- [ ] `<analysis>` and `<reflection>` tags
- [ ] `<FORBIDDEN>` section
- [ ] Token count within schema budget
- [ ] QA audit completed, MUST RESTORE items preserved
``````````
