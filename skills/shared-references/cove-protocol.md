# Chain-of-Verification (CoVe) Self-Interrogation Protocol

Shared reference for verification skills: fact-checking, dehallucination, and verifying-hunches.

Based on Dhuliawala et al. (2023), "Chain-of-Verification Reduces Hallucination in Large Language Models."

## When to Apply

Apply CoVe self-interrogation when:
- Generating factual claims about code, APIs, or system behavior
- Producing verification verdicts that will influence decisions
- Synthesizing information from multiple sources into a conclusion

Do NOT apply to:
- Direct quotes from source code (Tier 1 evidence)
- Test execution output (Tier 2 evidence)
- Verbatim content from project documentation (Tier 3 evidence)

## Three-Step Self-Interrogation

### Step 1: Generate Verification Questions

After drafting a claim or verdict, generate 2-3 targeted questions that would expose errors:

| Claim Type | Example Questions |
|---|---|
| Existence ("X exists in Y") | "Have I read the file? Did I search for the exact name?" |
| Behavior ("X does Y when Z") | "Did I trace the execution path? What evidence shows this behavior?" |
| Constraint ("X cannot/must Y") | "Where is this constraint enforced? What happens if violated?" |
| Relationship ("X depends on Y") | "Did I verify the import/call chain? Is this direct or transitive?" |

### Step 2: Answer Each Question Independently

Answer each verification question using only Tier 1-5 evidence (per evidence-hierarchy.md). Do NOT re-derive answers from the original claim. Each answer must cite a specific evidence source.

If any answer relies on Tier 6 (LLM parametric knowledge): the claim requires escalation or must be marked with reduced confidence.

### Step 3: Reconcile and Revise

Compare original claim against verification answers:

| Outcome | Action |
|---|---|
| All answers support claim | Proceed with original claim |
| Any answer contradicts claim | Revise claim to match evidence, document the correction |
| Any answer is inconclusive | Reduce confidence level, flag for deeper verification |

## Integration with Evidence Hierarchy

CoVe operates within the evidence hierarchy framework. Verification questions in Step 2 must be answered at the same or higher depth than the original claim's depth assignment. A Shallow-depth claim verified via CoVe at Medium depth gains increased confidence.

## Skill Integration Notes

### Fact-Checking

Apply during Phase 2-3 (Claim Extraction and Triage) within the `fact-check-extract` command. After extracting claims and before triage presentation, run CoVe self-interrogation on any synthesized or inferred claims (not on directly extracted verbatim text). This catches extraction errors where the extractor mischaracterizes what code actually claims.

Reference: `commands/fact-check-extract.md`

### Dehallucination

Apply between Detection Protocol steps 2 and 3 (after categorization by risk, before verification of critical claims). Run CoVe on the categorization itself: "Did I correctly identify this as [category]? Is the risk level accurate?" This prevents miscategorization from cascading through verification.

Reference: `skills/dehallucination/SKILL.md`

### Verifying Hunches

Apply after the Test-Before-Claim Protocol, before marking a hypothesis CONFIRMED. Run CoVe on the conclusion: "Does the test result actually prove my hypothesis? Could an alternative explanation produce the same result?" This guards against confirmation bias in hypothesis verification.

Reference: `skills/verifying-hunches/SKILL.md`
