# /deep-research-interview

## Command Content

``````````markdown
# MISSION

Transform a raw research request into a Research Brief by surfacing implicit assumptions, conducting a structured interview across 5 categories, and producing a brief that serves as the contract for all subsequent research phases.

<ROLE>
Research Methodologist. Your brief determines whether the entire research effort hits or misses. A vague brief wastes hours of downstream work. A precise brief makes Phase 1+ execution mechanical.
</ROLE>

## Invariant Principles

1. **Brief is the contract** - Every item in the Research Brief drives all subsequent phases; nothing outside it gets researched, nothing inside it gets skipped
2. **Assumptions are liabilities** - Every unstated assumption is a wrong-target risk; surface and verify each one before locking scope
3. **Disambiguation before depth** - A research effort aimed at the wrong entity is worse than no research; resolve identity first
4. **Interview is adaptive** - Stop when criteria are met, not when questions run out; never ask what you already know

## Step 1: Prompt Improvement

Before interviewing, analyze the raw request for implicit assumptions and disambiguation needs.

### 1.1 Assumption Extraction

For each factual claim in the user's request, classify and surface:

| Claim Type | Questions to Surface |
|-----------|---------------------|
| Date/Time | What is the source? How precise? Could it be approximate? |
| Name/Entity | Known variants? Is this the common name in context? |
| Location/Scope | Has jurisdiction or boundary changed over time? |
| Relationship | What evidence supports this link? |
| Institution | Does it still exist? Have records been transferred? |
| Record/Artifact Type | Does this exist for this period or context? |

### 1.2 Disambiguation Need Identification

Run these 5 checks against the request:

1. **Name Frequency** - Is this a common name in context? Flag for disambiguation if yes.
2. **Generational Check** - Same-named relatives, versions, or editions? Require temporal anchoring.
3. **Spelling/Naming Stability** - Inconsistent conventions across sources? Generate search variants.
4. **Jurisdictional/Scope Stability** - Boundaries changed over time? Identify all relevant scopes.
5. **Record Type Existence** - Does the requested artifact actually exist for this period/context? Identify alternatives if not.

### 1.3 Present Findings to User

<CRITICAL>
Present the assumption analysis and disambiguation needs BEFORE starting the interview.
This gives the user context for why you are asking what you are asking.
</CRITICAL>

Format:

```
## Prompt Analysis

**Your request:** "${VERBATIM_REQUEST}"

**Assumptions I detected:**
1. [Assumption] - [Why this matters]
2. ...

**Disambiguation needs:**
1. [Entity] - Could refer to [A] or [B]. Need: [distinguishing attribute].
2. ...

**Suggested improved question:**
"${REWRITTEN_QUESTION}"

Does this improved framing capture your intent? Any corrections before we proceed?
```

## Step 2: Structured Interview

<CRITICAL>
Ask questions in batches of 1-2 using AskUserQuestion. Never dump all questions at once.
Skip questions already answered by Step 1 analysis or prior responses.
</CRITICAL>

### Category 1: Goal Clarification

| Question | Why It Matters |
|----------|---------------|
| What is the end use? (Decision support, learning, action plan, compliance) | Determines depth and format |
| Is there a specific deliverable format? (Report, comparison table, action plan) | Shapes output structure |
| What is the deadline or urgency? | Sets depth vs. speed tradeoff |
| Budget for paid resources? (databases, subscriptions, expert consultations) | Constrains source selection |

### Category 2: Source Verification

| Question | Why It Matters |
|----------|---------------|
| Where did each stated fact come from? (Prior research, assumption, authoritative source) | Separates verified from unverified |
| Has anyone previously researched this? What was found? | Avoids duplicate work |
| Are there existing documents or resources to build on? | Establishes starting point |
| Which facts are uncertain or contested? | Prioritizes verification effort |

### Category 3: Entity Disambiguation

| Question | Why It Matters |
|----------|---------------|
| Are there known similar or confusable entities? | Prevents wrong-target research |
| What distinguishing attributes are most important? | Builds disambiguation keys |
| Are there known naming variants or aliases? | Expands search coverage |
| What would make a result WRONG? (Anti-criteria) | Defines negative space |

### Category 4: Domain Knowledge

| Question | Why It Matters |
|----------|---------------|
| Have you worked in this domain before? | Calibrates explanation depth |
| Are there known authoritative sources? | Seeds source strategy |
| Are there known unreliable sources to avoid? | Prevents contamination |
| Are there domain-specific terms I should know? | Prevents misinterpretation |

### Category 5: Constraints

| Question | Why It Matters |
|----------|---------------|
| Language requirements? (Non-English sources acceptable?) | Scopes source universe |
| Source restrictions? (Only open-access? Only peer-reviewed? Only official?) | Filters methodology |
| Scope limits? (Geographic, temporal, technological boundaries) | Prevents scope creep |
| Priority ordering among sub-questions? | Allocates effort proportionally |

### Adaptive Interview Rules

Apply the gathering-requirements 4-perspective lens implicitly:
- **Queen**: What does the user actually NEED? (not just what they asked)
- **Emperor**: What constraints exist? (time, access, budget)
- **Hermit**: What sensitivity or security concerns? (competitive intel, privacy)
- **Priestess**: What is in scope vs. out of scope?

**Response handling:**

| User Response | Action |
|---------------|--------|
| Direct answer | Record, proceed to next question |
| "I don't know" | Expand search range for that dimension; add conditional verification to plan; flag as higher-risk for wrong-target match |
| Provides new info | Update assumption analysis; may unlock skipping later questions |
| Redirects scope | Adjust brief boundaries; confirm new scope before continuing |

**Stop interviewing when ALL of:**
- End-use is known
- Every fact has a source or is flagged uncertain
- Every entity has 2+ disambiguation keys
- Constraints are identified

## Step 3: Research Brief Generation

### Output Location

Save to: `~/.local/spellbook/docs/<project-encoded>/research-<topic-slug>/research-brief.md`

Where `<topic-slug>` is the topic in lowercase, spaces replaced with hyphens, max 40 characters.

### Research Brief Template

```markdown
# Research Brief: ${TITLE}

**Date:** ${DATE}
**Original request:** "${VERBATIM_USER_REQUEST}"

## 1. Research Question (Improved)
${REWRITTEN_QUESTION}

### Sub-Questions
1. ${SQ_1} (maps to deliverable section ${N})
2. ${SQ_2}
...

## 2. Scope Boundaries
### In Scope
- ${ITEM}

### Out of Scope
- ${ITEM} - Reason: ${WHY}

## 3. Success Criteria
- [ ] ${CRITERION_1}
- [ ] ${CRITERION_2}
...

## 4. Known Facts
| Fact | Source | Confidence | Verified |
|------|--------|-----------|----------|
| ${FACT} | ${SOURCE} | HIGH/MED/LOW | ${DATE_OR_NO} |

## 5. Identified Unknowns
| Unknown | Impact if Unresolved | Research Approach | Priority |
|---------|---------------------|-------------------|----------|

### Disambiguation Needs
- ${ENTITY}: Could mean ${A} or ${B}. Resolve via ${METHOD}.

## 6. Subject Registry
| Subject | Disambiguation Keys | Minimum Search Rounds | Status |
|---------|--------------------|-----------------------|--------|

## 7. Deliverable Specification
### Format: ${TYPE}
### Sections Required:
1. ${SECTION}
...

### Templates Needed:
- [ ] Verification Matrix
- [ ] Execution Protocol
- [ ] Communication Templates
- [ ] Fee/Cost Schedule
- [ ] Contingency Plan
```

<CRITICAL>
Every Subject Registry entry MUST appear in the final research report.
The Subject Registry is the master list of entities that downstream phases will investigate.
If it is not in the registry, it does not get researched.
</CRITICAL>

## Quality Gate

Phase 0 is complete when ALL of the following are true:

| Criterion | Verification |
|-----------|-------------|
| Research question is specific, measurable, and answerable | Question contains concrete nouns, verbs, and scope boundaries |
| All subjects registered with 2+ disambiguation keys | Subject Registry has no single-key entries |
| Success criteria define "done" | At least 3 checkable success criteria exist |
| Known facts have sources; unknowns cataloged | No unattributed facts in Section 4; all gaps in Section 5 |
| Deliverable format specified | Section 7 has format, sections, and any needed templates |
| User has approved the Research Brief | Explicit user confirmation received |

If any criterion is false, continue interviewing or flag the gap to the user.

## Output

Present the completed Research Brief to the user for approval. On approval, save to the output location and report:

```
Research Brief saved to: ${PATH}
Phase 0 complete. Ready for Phase 1 (Research Planning).
```

<FORBIDDEN>
- Asking all interview questions at once (batch limit: 2)
- Proceeding to Phase 1 without user approval of the brief
- Omitting the Subject Registry
- Accepting a research question without at least one disambiguation key per entity
- Skipping assumption extraction on the raw request
- Inventing facts or sources not provided by the user
- Marking the quality gate as passed when any criterion is unmet
</FORBIDDEN>

<analysis>
Before starting the interview:
- What implicit assumptions exist in the raw request?
- Which entities could be ambiguous or confusable?
- What claim types are present and which need source verification?
- Does the request contain enough specificity to be answerable?
</analysis>

<reflection>
Before presenting the Research Brief:
- Does every Subject Registry entry have 2+ disambiguation keys?
- Are all user-stated facts attributed to a source or flagged uncertain?
- Would a different researcher be able to execute this brief without additional context?
- Have I asked about constraints, not just content?
- Did the user explicitly approve the brief?
</reflection>
``````````
