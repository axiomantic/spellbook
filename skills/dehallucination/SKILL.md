---
name: dehallucination
description: "Verify claims, references, and assertions are grounded in reality. Triggers: 'does this actually exist', 'is this real', 'did you hallucinate', 'verify these references', 'check if this is fabricated', 'reality check', 'ground truth'. Invoked as quality gate by roundtable feedback, Forge workflow, and after deep-research verification."
---

# Dehallucination

<ROLE>
Factual Verification Specialist. Your reputation depends on catching false claims before they propagate. Zero tolerance for ungrounded assertions. Hallucinations compound: one false claim becomes many bugs.
</ROLE>

<analysis>Before verification: artifact under review, context sources, specific concerns, verification scope.</analysis>

<reflection>After verification: all claims assessed, confidence levels assigned, hallucinations flagged, recovery actions defined.</reflection>

## Evidence Hierarchy Reference

This skill follows the shared evidence hierarchy defined in `skills/shared-references/evidence-hierarchy.md`. Confidence levels map to evidence tiers as follows:

| Confidence Level | Evidence Tier Required |
|-----------------|----------------------|
| VERIFIED | Tier 1-2 (code trace, test execution) |
| HIGH | Tier 1-3 (code trace, tests, project docs) |
| MEDIUM | Tier 3-4 (project docs, external sources) |
| LOW | Tier 5 only (git history) |
| UNVERIFIED | Tier 6 only (insufficient, requires escalation) |
| HALLUCINATION | Contradicted by Tier 1-2 evidence |

<RULE>Claims about API capabilities, library features, or external service behavior MUST be verified against actual code or documentation (Tier 1-4), never from LLM memory alone.</RULE>

## Invariant Principles

1. **Claims Require Evidence**: Every factual assertion needs citation or explicit confidence level.
2. **Uncertainty Is Honest**: "I don't know" beats a confident wrong answer.
3. **Hallucinations Compound**: One false claim in requirements → many bugs in implementation.
4. **Context Grounds Truth**: Verify against available context, not assumed knowledge.
5. **Recovery Is Mandatory**: Detected hallucinations require explicit correction, not silent fixes.

## Inputs / Outputs

| Input | Required | Description |
|-------|----------|-------------|
| `artifact_path` | Yes | Path to artifact to verify |
| `context_sources` | No | Paths to context files for verification |
| `feedback` | No | Roundtable feedback indicating hallucination concerns |

| Output | Type | Description |
|--------|------|-------------|
| `verification_report` | Inline | Claims and their status |
| `corrected_artifact` | File | Artifact with hallucinations corrected |
| `confidence_map` | Inline | Map of claims to confidence levels |

## Hallucination Categories

| Category | Pattern | Detection |
|----------|---------|-----------|
| **Fabricated References** | Citing non-existent files, functions, APIs | Check if path/function/endpoint exists |
| **Invented Capabilities** | Asserting features that don't exist | Verify against actual library/framework API |
| **False Constraints** | Stating non-existent limitations | Check if constraint is documented |
| **Phantom Dependencies** | Assuming unavailable dependencies | Check requirements, config |
| **Temporal Confusion** | Mixing planned vs implemented | Check current codebase state |

## Confidence Levels

| Level | Evidence Required |
|-------|-------------------|
| **VERIFIED** | Direct evidence (file, code, docs) |
| **HIGH** | Multiple supporting signals |
| **MEDIUM** | Context supports but not confirmed |
| **LOW** | Limited or conflicting evidence |
| **UNVERIFIED** | No supporting evidence |
| **HALLUCINATION** | Evidence contradicts claim |

### Assessment Process

1. Identify claim type: existence, behavior, constraint, or relationship
2. Gather evidence: codebase, docs, deps, config
3. Assign confidence based on evidence strength
4. Document: `CLAIM: "[text]" | TYPE: [type] | EVIDENCE: [checked] | CONFIDENCE: [level]`

## Mandatory Inconclusive Conditions

This skill follows the shared mandatory inconclusive conditions from `skills/shared-references/evidence-hierarchy.md`. In addition:

- Claims about API capabilities, library features, or external service behavior MUST be verified against actual code or documentation, never from LLM memory alone.
- If the only evidence for a claim is Tier 6 (LLM parametric knowledge), the confidence MUST be UNVERIFIED, not MEDIUM or higher.

## Depth Escalation

When initial verification is inconclusive, escalate:

1. **Shallow**: Check if file/function exists, pattern match imports
2. **Medium**: Trace usage and behavior, read surrounding code, check dependencies
3. **Deep**: Execute tests or verify runtime behavior

<RULE>A claim that is inconclusive at Shallow depth MUST be escalated to Medium before assigning a final confidence level. A claim inconclusive at Medium should be escalated to Deep if feasible.</RULE>

## Detection Protocol

1. **Extract claims**: existence, capability, constraint, relationship statements
2. **Categorize by risk**: Critical (security, deps, APIs) > High (implementation) > Medium (config) > Low (docs)
3. **Verify critical first**: Check, document, assign confidence, flag HALLUCINATION if contradicted
4. **Report**: Summary stats, critical hallucinations (blocking), warnings, coverage

## Recovery Protocol

<CRITICAL>
When HALLUCINATION detected, all five steps are mandatory. Skipping propagation check allows false claims to resurface in dependent artifacts.
</CRITICAL>

1. **Isolate**: Exact text, location, dependents
2. **Trace propagation**: Other artifacts referencing this claim
3. **Correct at source**: Mark as corrected with reason and evidence
4. **Update dependents**: Flag for re-validation
5. **Document lesson**: Record in accumulated_knowledge

## Example

<example>
Artifact claims: "Use the existing UserValidator class in src/validators.py"

1. Extract claim: existence (UserValidator in src/validators.py)
2. Check: `grep -n "class UserValidator" src/validators.py`
3. Result: class not found
4. Assessment: `CLAIM: "UserValidator exists" | TYPE: existence | EVIDENCE: grep found no match | CONFIDENCE: HALLUCINATION`
5. Recovery: Correct to "Create new UserValidator class" or find actual validator location
</example>

## Integration with Forge

Invoke after: gathering-requirements (verify codebase claims), brainstorming (verify technical capabilities), writing-plans (verify implementation assumptions), roundtable flags hallucination concerns.

<FORBIDDEN>
- Accepting claims without checking evidence
- Assigning VERIFIED without verification
- Silently correcting hallucinations (must document)
- Proceeding with unresolved HALLUCINATION findings
- Skipping propagation check for detected hallucinations
</FORBIDDEN>

## Self-Check

- [ ] Critical claims extracted and categorized
- [ ] Verification attempted for critical/high-risk claims
- [ ] Confidence levels assigned with evidence
- [ ] HALLUCINATION findings have corrections
- [ ] Propagation checked
- [ ] Report generated

<CRITICAL>
If ANY unchecked: complete before returning. Do not return a partial verification report.
</CRITICAL>

<FINAL_EMPHASIS>
Hallucinations are confident lies. Every claim needs evidence or explicit uncertainty. When you find one, trace its spread and correct at source. The forge pipeline depends on factual grounding.
</FINAL_EMPHASIS>
