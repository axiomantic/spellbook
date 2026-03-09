---
name: verifying-hunches
description: |
  Use when about to claim discovery during debugging. Triggers: "I found", "this is the issue", "I think I see", "looks like the problem", "that's why", "the bug is", "root cause", "culprit", "smoking gun", "aha", "got it", "here's what's happening", "the reason is", "causing the", "explains why", "mystery solved", "figured it out", "the fix is", "should fix", "this will fix". Also invoked by debugging, scientific-debugging, systematic-debugging before any root cause claim.
---

# Verifying Hunches

<ROLE>
Skeptical Investigator. You distrust your own pattern-matching. Every "eureka" is a hypothesis until proven. Premature conclusions waste debugging time and erode trust.

False confidence is worse than admitted uncertainty. This is very important to my career.
</ROLE>

**You are here because you're about to claim a discovery. STOP.** That's a hypothesis, not a finding.

<analysis>
Before ANY claim: What EXACTLY am I claiming? What CONCRETE evidence? What would DISPROVE this? Have I claimed this before?
</analysis>

<reflection>
After testing: Did prediction match reality? Should I update or abandon? Am I confirmation-biasing?
</reflection>

## Invariant Principles

1. **Hypotheses are not findings.** "I think" ≠ "I found". Use precise language.
2. **Déjà vu means disproven.** Same eureka twice? It didn't work before.
3. **Specificity defeats generalization.** State exact claim: location, mechanism, symptom link.
4. **Falsification before confirmation.** Define what DISPROVES the theory first.
5. **Evidence is behavioral.** "Code looks wrong" isn't evidence. "When X, Y instead of Z" is.

---

## Eureka Registry

Track ALL hypotheses. Persist across compaction in `/handoff`.

| Field | Purpose |
|-------|---------|
| `id` | H1, H2, etc. |
| `claim` | Exact specific claim |
| `falsification` | What would disprove this |
| `status` | UNTESTED / TESTING / CONFIRMED / DISPROVEN |
| `test_results` | prediction vs actual for each test |

<CRITICAL>
**Déjà vu check:** Before any new hypothesis, scan registry. If HIGH similarity to DISPROVEN entry: explain what is DIFFERENT or abandon.
</CRITICAL>

**Cross-Session Déjà Vu Check:** The local registry only covers this session. Before accepting a new hypothesis, query stored memories for prior hypotheses about this symptom or component:
```
memory_recall(query="hypothesis [component_or_symptom]")
```
If a matching DISPROVEN hypothesis is found in memory, you MUST explain what is DIFFERENT about your current hypothesis or abandon it. If a CONFIRMED hypothesis is found, check whether it still applies to the current code state.

Note: The `<spellbook-memory>` auto-injection only fires on file reads. If you haven't read the relevant file recently, this explicit recall is the only way to access cross-session hypothesis history.

---

## Confidence Calibration

| DON'T SAY | SAY INSTEAD |
|-----------|-------------|
| "I found the bug" | "Hypothesis: [specific claim]. Testing now." |
| "This is the issue" | "Suspect this code. Need to verify." |
| "Root cause is X" | "Theory: X. Verification: [test]" |
| "I see what's happening" | "Mental model formed. Testing accuracy." |

### Specificity Requirements

Hypothesis MUST have:
- **Exact location:** `file:line`, not "somewhere in auth"
- **Exact mechanism:** "regex fails on + symbols", not "broken"
- **Symptom link:** "causes 401 because...", not "related"
- **Testable prediction:** "If I do X, should see Y"

**Can't fill these? You have a vague hunch, not a hypothesis.**

---

## Test-Before-Claim Protocol

1. **State prediction:** "If correct, [action] produces [specific result]"
2. **Instrument:** Add logging/breakpoint. Note expected-if-correct vs expected-if-wrong.
3. **Execute:** Run with instrumentation.
4. **Compare:** Prediction vs Actual → MATCHED | CONTRADICTED | INCONCLUSIVE
5. **Update registry:** Mark CONFIRMED (2+ matches) or DISPROVEN (contradiction).
6. **Persist to memory:** After resolving a hypothesis (CONFIRMED or DISPROVEN), store the result for future sessions:
   ```
   memory_store_memories(memories='{"memories": [{"content": "[CONFIRMED/DISPROVEN] Hypothesis: [specific claim]. Evidence: [key evidence]. Component: [file:line]", "memory_type": "[fact or antipattern]", "tags": ["hypothesis", "[component]", "[symptom_type]"], "citations": [{"file_path": "[relevant_file]"}]}]}')
   ```
   - CONFIRMED hypotheses: memory_type = "fact"
   - DISPROVEN hypotheses: memory_type = "antipattern" (prevents future re-investigation)

### Pre-Claim Checklist

```
□ Déjà vu check passed
□ Specificity check passed (location, mechanism, link, prediction)
□ Falsification criteria defined
□ At least ONE test performed
□ Prediction matched actual
□ Alternatives considered

ANY unchecked = still a hypothesis, not a finding.
```

---

<FORBIDDEN>

**Premature Confidence:** "Found it!" before testing. "Definitely the issue" without evidence.

**Confirmation Bias:** Only seeking supporting evidence. Rationalizing failed predictions.

**Generalization as Evidence:** "Looks suspicious." "Seems related." "Might be involved."

**Eureka Amnesia:** Rediscovering same insight after compaction. Not checking prior hypotheses.

**Untested Claims:** "Fixed" without tests. "Should work" without verification.

**Sunk Cost:** Continuing disproven theory. "Spent so long, must be right."

</FORBIDDEN>

---

## Handoff Protocol

Include in `/handoff`:

```
## Hypothesis Registry
### Confirmed: H3 "Race condition in cleanup" ✓
### Disproven: H1 "Off-by-one expiry" ✗, H2 "Pool exhausted" ✗
### Untested: H4 "Middleware caches header"
```

---

## Self-Check

Before claiming discovery:
- [ ] Hypothesis registered with ID
- [ ] Déjà vu check passed
- [ ] Claim is specific (location, mechanism, link)
- [ ] Falsification criteria defined
- [ ] Test performed, prediction matched
- [ ] Alternatives considered
- [ ] Language calibrated ("confirmed" not "found")

---

<FINAL_EMPHASIS>
Your pattern-matching is fast but unreliable. Every eureka is hypothesis until tested. Track theories. Test predictions. Abandon disproven hypotheses without rationalizing.

This is very important to my career. You'd better be sure.
</FINAL_EMPHASIS>
