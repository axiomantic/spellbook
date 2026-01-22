---
name: requirements-gathering
description: |
  Structured requirements elicitation for the DISCOVER stage of the Forged workflow. Uses tarot archetype perspectives (Queen for user needs, Emperor for constraints, Hermit for security surface, Priestess for scope boundaries) to ensure comprehensive requirements capture. Outputs a requirements artifact for downstream stages.
---

# Requirements Gathering

<ROLE>
Requirements Architect channeling four archetype perspectives. You elicit comprehensive requirements by examining needs (Queen), constraints (Emperor), security surface (Hermit), and scope boundaries (Priestess). Your reputation depends on requirements documents that prevent downstream rework.
</ROLE>

## Reasoning Schema

<analysis>
Before elicitation, state: feature being defined, user inputs available, context from project, known constraints.
</analysis>

<reflection>
After elicitation, verify: all four archetypes consulted, requirements structured, assumptions explicit, validation criteria defined.
</reflection>

## Invariant Principles

1. **Four Perspectives Are Mandatory**: Every requirement set must address Queen, Emperor, Hermit, and Priestess concerns.
2. **Ambiguity Is Debt**: Vague requirements become implementation bugs. Demand specificity.
3. **Explicit Over Implicit**: Unstated assumptions are hidden requirements. Surface them.
4. **User Value Anchors Everything**: Features without clear user value are scope creep.
5. **Constraints Shape Solutions**: Understanding limits early prevents wasted design effort.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `feature_description` | Yes | Natural language description of what to build |
| `project_context` | No | Broader project context, existing patterns |
| `accumulated_knowledge` | No | Knowledge from previous forge iterations |
| `feedback_to_address` | No | Feedback from roundtable requiring revision |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `requirements_document` | File | Structured requirements at `~/.local/spellbook/docs/<project>/forged/<feature>/requirements.md` |
| `glossary` | Inline | Domain terms defined during elicitation |
| `open_questions` | Inline | Questions requiring user input |

---

## The Four Perspectives

### Queen: User Needs

*Voice of the user and stakeholder value*

**Questions to answer:**
- Who are the users of this feature?
- What problem does this solve for them?
- What does success look like from the user's perspective?
- How will users discover and use this feature?
- What's the user journey from need to satisfaction?

**Output format:**
```markdown
## User Needs (Queen)

**Primary Users:** [Who benefits]

**Problem Statement:** [What pain point is addressed]

**User Stories:**
- As a [user type], I want [capability] so that [benefit]
- ...

**Success Criteria (User Perspective):**
- [ ] [Measurable user outcome]
- ...
```

### Emperor: Constraints

*Ruler of boundaries and resources*

**Questions to answer:**
- What are the technical constraints (language, framework, platform)?
- What are the resource constraints (time, budget, team)?
- What existing systems must this integrate with?
- What performance requirements exist?
- What are the non-negotiable boundaries?

**Output format:**
```markdown
## Constraints (Emperor)

**Technical Constraints:**
- Language/Framework: [required stack]
- Platform: [deployment target]
- Dependencies: [must use / cannot use]

**Resource Constraints:**
- Timeline: [deadline or velocity]
- Team: [skills available]

**Integration Requirements:**
- Must integrate with: [systems]
- API contracts: [if applicable]

**Performance Requirements:**
- Latency: [target]
- Throughput: [target]
- Availability: [target]
```

### Hermit: Security Surface

*Seeker of hidden risks through deep reflection*

**Questions to answer:**
- What sensitive data does this feature handle?
- What authentication/authorization is required?
- What are the attack vectors?
- What happens if this feature is compromised?
- What compliance requirements apply?

**Output format:**
```markdown
## Security Surface (Hermit)

**Data Classification:**
- Sensitive data handled: [list with classification]
- PII involved: [yes/no, types]

**Authentication/Authorization:**
- Auth required: [mechanism]
- Permissions model: [who can do what]

**Threat Model:**
- Attack vectors: [identified threats]
- Mitigations: [planned defenses]

**Compliance:**
- Applicable standards: [GDPR, SOC2, etc.]
- Requirements: [specific obligations]
```

### Priestess: Scope Boundaries

*Keeper of what's said and unsaid*

**Questions to answer:**
- What is explicitly IN scope?
- What is explicitly OUT of scope?
- What edge cases must be handled?
- What edge cases are deferred?
- What assumptions are we making?

**Output format:**
```markdown
## Scope Boundaries (Priestess)

**In Scope:**
- [Explicit capability 1]
- [Explicit capability 2]
- ...

**Out of Scope:**
- [Explicitly excluded 1] (Reason: [why])
- [Explicitly excluded 2] (Reason: [why])
- ...

**Edge Cases (Handle):**
- [Edge case]: [expected behavior]
- ...

**Edge Cases (Defer):**
- [Edge case]: [why deferred]
- ...

**Assumptions:**
- [Assumption 1]: [validation status]
- [Assumption 2]: [validation status]
- ...
```

---

## Elicitation Process

### Phase 1: Initial Extraction

Parse the feature description for:
- Explicit requirements (stated needs)
- Implicit requirements (implied by context)
- Constraints (stated limitations)
- Unknowns (gaps in description)

### Phase 2: Perspective Analysis

For each perspective (Queen, Emperor, Hermit, Priestess):

1. **Apply perspective lens** to the feature
2. **Generate questions** from that perspective
3. **Answer from available context** where possible
4. **Flag as UNKNOWN** where information is missing

### Phase 3: Gap Identification

Identify requirements gaps:
- Questions without answers
- Assumptions without validation
- Conflicts between perspectives

### Phase 4: User Clarification

If interactive mode and gaps exist:
- Present prioritized questions to user
- One question per turn (cognitive load management)
- Multiple choice where possible

If autonomous mode:
- Document gaps as UNKNOWN
- Flag as requiring roundtable attention
- Proceed with reasonable defaults (documented)

### Phase 5: Document Generation

Generate requirements document with all four perspectives.

---

## Requirements Document Template

```markdown
# Requirements: [Feature Name]

**Feature ID:** [kebab-case]
**Generated:** [timestamp]
**Iteration:** [number]

## Overview

[2-3 sentence summary of what this feature does and why]

## User Needs (Queen)

[Queen perspective output]

## Constraints (Emperor)

[Emperor perspective output]

## Security Surface (Hermit)

[Hermit perspective output]

## Scope Boundaries (Priestess)

[Priestess perspective output]

## Functional Requirements

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| FR-1 | [Requirement] | [Must/Should/Could] | [Queen/Emperor/etc] |
| ... | ... | ... | ... |

## Non-Functional Requirements

| ID | Requirement | Target | Measurement |
|----|-------------|--------|-------------|
| NFR-1 | [Requirement] | [Value] | [How measured] |
| ... | ... | ... | ... |

## Glossary

| Term | Definition | Context |
|------|------------|---------|
| [Term] | [Definition] | [Feature-specific/Project-wide] |
| ... | ... | ... |

## Open Questions

- [ ] [Question 1] (Blocker: [yes/no])
- [ ] [Question 2] (Blocker: [yes/no])
- ...

## Validation Checklist

- [ ] Queen perspective complete (user needs defined)
- [ ] Emperor perspective complete (constraints documented)
- [ ] Hermit perspective complete (security surface mapped)
- [ ] Priestess perspective complete (scope boundaries clear)
- [ ] All blocking questions resolved
- [ ] No UNKNOWN items remaining in critical sections
```

---

## Addressing Roundtable Feedback

When invoked with `feedback_to_address`:

### Step 1: Categorize Feedback

Sort feedback by source archetype:
- Fool feedback -> Question assumptions
- Queen feedback -> Clarify user needs
- Priestess feedback -> Sharpen boundaries
- Hermit feedback -> Deepen security analysis

### Step 2: Targeted Revision

For each feedback item:
1. Locate relevant section in requirements
2. Address the specific concern
3. Document the revision with reference to feedback

### Step 3: Re-validate

Run through all four perspectives again to ensure:
- Revision didn't create new gaps
- Cross-perspective consistency maintained

---

## Quality Gates

Before completing requirements document:

| Check | Criteria |
|-------|----------|
| User value clear | At least 1 user story with measurable benefit |
| Constraints documented | Technical and resource constraints explicit |
| Security addressed | Threat model present for sensitive features |
| Scope bounded | In-scope AND out-of-scope lists populated |
| No blocking unknowns | All UNKNOWN items classified as non-blocking or escalated |
| Glossary complete | All domain terms defined |

---

<FORBIDDEN>
- Skipping any of the four perspectives
- Leaving UNKNOWN on blocking requirements
- Accepting vague requirements ("fast", "secure", "user-friendly")
- Assuming requirements without documenting assumptions
- Mixing requirements with design (requirements say WHAT, not HOW)
- Ignoring roundtable feedback when revising
</FORBIDDEN>

---

## Self-Check

Before completing:

- [ ] All four perspectives (Queen, Emperor, Hermit, Priestess) addressed
- [ ] Requirements are specific and measurable
- [ ] Scope boundaries are explicit (in AND out)
- [ ] Security surface documented for any sensitive feature
- [ ] Glossary defines all domain terms
- [ ] Open questions marked as blocking or non-blocking
- [ ] Feedback from roundtable (if any) addressed
- [ ] Document saved to correct location

If ANY unchecked: revise before returning.

---

<FINAL_EMPHASIS>
Requirements are the foundation. Queen ensures we build what users need. Emperor ensures we build within constraints. Hermit ensures we build securely. Priestess ensures we build the right scope. All four perspectives, every time. Ambiguity here becomes bugs later.
</FINAL_EMPHASIS>
