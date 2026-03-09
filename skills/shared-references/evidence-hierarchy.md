# Evidence Hierarchy

Shared reference for verification skills: fact-checking, dehallucination, and devil's advocate.

## Evidence Tier Table

| Tier | Source | May Support Verdict Alone? |
|------|--------|---------------------------|
| 1 | Code trace (actual code read via tools) | Yes |
| 2 | Test execution output | Yes |
| 3 | Project documentation (AGENTS.md, README, ADRs) | Yes, for documentation claims |
| 4 | External authoritative source (fetched via web, RFCs, OWASP) | Yes, for external reference claims |
| 5 | Git history (actual commits/diffs read) | Yes, for historical claims |
| 6 | LLM parametric knowledge | NEVER |

<RULE>LLM parametric knowledge (things "known" from training) is NOT evidence. It may generate hypotheses to investigate, but a verdict based solely on "I know that X is true" without a Tier 1-5 citation is FORBIDDEN.</RULE>

## Depth Escalation Protocol

| Depth | Activities | When to Use |
|-------|-----------|-------------|
| **Shallow** | Pattern matching, import checks, quick lookups, file/function existence | Initial pass, low-risk claims |
| **Medium** | Code tracing, dependency analysis, test reading, usage pattern analysis | Default for most claims |
| **Deep** | Test execution, profiling, runtime analysis, benchmark execution | High-risk claims, behavior verification |

### Escalation Rules

1. **Refuted at Shallow**: MUST re-verify at Medium depth before finalizing the verdict.
2. **Refuted at Medium**: Escalate to Deep depth if feasible (tests can be run, benchmarks can be executed).
3. **Inconclusive at any depth**: Does not require escalation, but document what would be needed to resolve.
4. **UNVALIDATED assumptions**: Must have attempted at least Medium depth verification before inclusion in any report.

## Mandatory Inconclusive/Unvalidated Conditions

The verdict MUST be Inconclusive (or the finding MUST be marked Unvalidated) when ANY of these conditions hold:

1. **No runtime evidence for behavior claims**: The claim is about runtime behavior (performance, concurrency, timing) and no tests were executed.
2. **Contradicting evidence unresolved**: The verification found contradicting evidence but cannot determine which is correct.
3. **Verification relies solely on Tier 6**: The only supporting evidence is LLM parametric knowledge.
4. **Temporal/version ambiguity**: The claim references a time period, version, or state that cannot be confirmed as current.
5. **Project-specific convention uncertainty**: The claim depends on a project convention not documented in AGENTS.md or equivalent.
6. **Assumption chain broken**: The claim depends on a prior claim that is itself unverified (broken dependency chain).

<RULE>When uncertain between a definitive verdict and Inconclusive, always choose Inconclusive. A wrong definitive verdict causes more harm than an honest Inconclusive.</RULE>

## Skill Integration Notes

### Fact-Checking

The fact-checking skill uses this hierarchy directly in its Evidence Hierarchy (Mandatory) section and Mandatory Inconclusive Conditions. Verification agents must cite evidence tiers in every verdict. The depth escalation protocol governs when claims must be re-verified at higher depth.

Reference: `skills/fact-checking/SKILL.md`, `commands/fact-check-verify.md`

### Dehallucination

Map dehallucination confidence levels to evidence tiers:

| Confidence Level | Evidence Tier Required |
|-----------------|----------------------|
| VERIFIED | Tier 1-2 (code trace, test execution) |
| HIGH | Tier 1-3 (code trace, tests, project docs) |
| MEDIUM | Tier 3-4 (project docs, external sources) |
| LOW | Tier 5 only (git history) |
| UNVERIFIED | Tier 6 only (insufficient, requires escalation) |
| HALLUCINATION | Contradicted by Tier 1-2 evidence |

Claims about API capabilities, library features, or external service behavior MUST be verified against actual code or documentation (Tier 1-4), never from LLM memory alone.

Reference: `skills/dehallucination/SKILL.md`

### Devil's Advocate

Challenges must cite evidence tiers. When flagging an assumption as UNVALIDATED or IMPLICIT, the reviewer must have attempted at least Medium depth verification before inclusion. Recommendations must themselves be validated against evidence before being proposed.

Reference: `skills/devils-advocate/SKILL.md`
