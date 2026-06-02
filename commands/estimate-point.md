---
description: Phases 4-5 of estimating-tickets. Multi-agent consensus pointing per ticket + AI productivity multiplier.
---

# Estimate Point (Phases 4-5)

<ROLE>
Calibration Lead. Single-estimator bias is the failure mode you exist to defeat. One engineer's "5 points" is another's "13"; the only defense is parallel, independent persona pointing followed by reconciliation. Your reputation rests on consensus that survives challenge.
</ROLE>

<CRITICAL>
Personas MUST be dispatched in parallel via separate Task calls in a single batch. Sequential persona dispatch defeats the entire point of multi-agent consensus — the second persona will anchor on the first's number. Parallel dispatch is non-negotiable.
</CRITICAL>

<RULE>Personas MUST be dispatched in parallel, never sequentially.</RULE>

<analysis>
Before dispatching: Which personas surface the risks THIS ticket set carries (does `has_frontend` force a Frontend Engineer)? Are all N tickets * P personas batched into a single parallel call so no persona anchors on another's number? Sequential dispatch silently destroys the independence the consensus depends on.
</analysis>

<reflection>
After pointing: For each ticket, is disagreement within 1 Fibonacci step (or reconciled if not)? Did any consensus value land at 34 (forcing a halt and loop back to scope)? Was M_AI applied with the conservative higher complexity when personas disagreed? Consensus without a reconciliation pass on >1-step splits is a lie agreed upon.
</reflection>

## Invariant Principles

1. **Parallel dispatch protects independence**: All personas point each ticket in one batched call; sequential dispatch lets later personas anchor on earlier numbers and collapses multi-agent consensus.
2. **Disagreement triggers reconciliation**: Splits greater than 1 Fibonacci step mean someone is missing context — re-dispatch with cross-visible reasoning; on persistent disagreement take the higher value and flag it.
3. **34 halts, never estimates**: A consensus value of 34 stops the pipeline and loops back to scope for splitting before any multiplier or buffering runs.
4. **Conservative on ambiguity**: When personas disagree on complexity, take the HIGHER classification; never apply M_AI < 1.0 to High-complexity work to flatter AI tooling.
5. **Consensus is synthesis, not voting**: The output is the reconciled median of independent expert reasoning, never one persona's number with the others discarded as "wrong".

---

### Step 1: Persona Selection

Default trio: **Backend Engineer**, **QA Engineer**, **Data Architect**.

If `has_frontend = true` from `estimate-scope`: auto-add **Frontend Engineer**.

Offer override via AskUserQuestion:

```
Header: "Estimator personas"
Question: "Default personas for this estimation are: [list]. Override?"
Options:
- Use defaults (Recommended)
- Add personas (you will describe)
- Replace personas (you will describe)
```

Personas matter because each surfaces different risks. Backend sees data flow and transactions; QA sees test surface and flakiness; Data Architect sees migration cost; Frontend sees state, accessibility, and integration with backend contracts.

### Step 2: Parallel Persona Pointing (Per Ticket)

For each ticket in the scoped list, dispatch ONE subagent per persona, ALL in a single batched parallel call.

For N tickets and P personas, that is N*P parallel dispatches in one batch.

Per-persona prompt template:

```
Task:
  description: "Point [ticket id] as [persona]"
  prompt: |
    First, READ the pointing rubric at:
    $SPELLBOOK_DIR/skills/estimating-tickets/pointing-rubric.md

    You are a [persona name] estimating story points for this ticket.
    Use ReAct-style reasoning: thought, action, observation.

    TICKET:
      id: [id]
      summary: [summary]
      repo: [repo]
      touches: [file list]
      integration_points: [list]
      constraints: [list]

    REPO MAP CONTEXT:
      [paste the relevant repo map JSON for this ticket's repo]

    Procedure:
    1. THOUGHT: From your persona's perspective, what is the riskiest part of this ticket?
    2. ACTION: Map the work to the rubric (3 / 5 / 8 / 13 / 21 / 34).
    3. OBSERVATION: Cross-check against your THOUGHT. Does the point value account for the risk?
    4. Classify complexity as Low or High per the heuristics in ai-multipliers.md:
       $SPELLBOOK_DIR/skills/estimating-tickets/ai-multipliers.md

    Return strict JSON:
    {
      "ticket_id": "[id]",
      "persona": "[name]",
      "points": 3 | 5 | 8 | 13 | 21 | 34,
      "complexity": "Low" | "High",
      "reasoning": "1-3 sentence justification with persona-specific risks named",
      "risk_signal": "any specific risk that would expand P in PERT (e.g. 'webhook ordering', 'undocumented legacy invariant'); empty string if none"
    }

    Return summary MUST include:
      ARTIFACTS_WRITTEN: n/a (inline JSON)
      SKILL_INVOCATION: n/a (rubric files read directly)
      COMPILE_STATUS: n/a
      TEST_STATUS: n/a
```

### Step 3: Reconciliation

For each ticket, collect the per-persona point values. Measure disagreement on the Fibonacci scale [3, 5, 8, 13, 21, 34]:

- 0 steps apart = consensus
- 1 step apart (e.g. 5 vs 8) = acceptable; take the median or the higher value (conservative)
- >1 step apart (e.g. 5 vs 13) = REQUIRES RECONCILIATION

For tickets requiring reconciliation, dispatch a SECOND parallel batch where each persona sees the OTHER personas' reasoning and revotes. Reconciliation prompt:

```
Task:
  description: "Reconcile [ticket id] as [persona]"
  prompt: |
    First, RE-READ:
    $SPELLBOOK_DIR/skills/estimating-tickets/pointing-rubric.md

    You previously pointed ticket [id] at [your prior points].
    The other personas pointed it as follows:
      [persona A]: [points] - [reasoning]
      [persona B]: [points] - [reasoning]
      [persona C]: [points] - [reasoning]

    The disagreement is more than 1 step on the Fibonacci scale, which means at
    least one persona is missing context the others have. Re-evaluate.

    You may keep your original number, move toward consensus, or move further
    away if you see a risk the others missed. Justify either way.

    Return strict JSON:
    {
      "ticket_id": "[id]",
      "persona": "[name]",
      "points": 3 | 5 | 8 | 13 | 21 | 34,
      "complexity": "Low" | "High",
      "reasoning": "what changed (or why you kept your number)",
      "risk_signal": "..."
    }
```

After reconciliation, take the median of the reconciled values as the consensus point. If disagreement persists at >1 step, take the HIGHER value (conservative) and flag the persistent disagreement in the assumptions log for the report.

### Step 4: 34-Point Auto-Split Halt

<RULE>If ANY ticket's consensus value is 34, HALT the pipeline and loop back to `estimate-scope`.</RULE>

Surface to user via AskUserQuestion:

```
Header: "Ticket too large to estimate"
Question: "Ticket [id] consensus-pointed at 34 (>2 weeks). The rubric requires splitting before estimation can continue. How should I split it?"
Options:
- I will describe how to split it
- Suggest splits (you draft 2-3 sub-tickets based on the repo map and integration points)
```

After splitting, re-run `estimate-point` on the new sub-tickets. Do NOT proceed to AI multiplier classification or buffering until no ticket is at 34.

### Step 5: AI Productivity Multiplier (M_AI)

For each ticket, take the consensus complexity classification (Low or High — if personas disagreed, take the HIGHER complexity).

Apply M_AI from `$SPELLBOOK_DIR/skills/estimating-tickets/ai-multipliers.md`:

- Low complexity: M_AI = 0.7
- High complexity: M_AI = 1.25

Compute:

```
base_hours = lookup from pointing-rubric.md by consensus_points
adjusted_hours = base_hours * M_AI
```

Per-ticket output:

```
{
  "ticket_id": "...",
  "consensus_points": 5,
  "base_hours": 8,
  "complexity": "High",
  "M_AI": 1.25,
  "adjusted_hours": 10.0,
  "risk_signals": ["webhook ordering", ...],
  "reconciled": true | false,
  "persistent_disagreement": true | false
}
```

<FORBIDDEN>
- Running personas sequentially when they can be parallel (anchor bias)
- Accepting consensus without a reconciliation pass when disagreement exceeds 1 step
- Skipping the 34-point halt because "it's actually only a bit over"
- Applying M_AI < 1.0 to High-complexity work to "be optimistic about AI tooling"
- Picking a single persona's number and discarding the others as "wrong"
</FORBIDDEN>

## Phase Complete

Before invoking `estimate-buffer`, verify:

- [ ] Persona set finalized (defaults or override)
- [ ] First-round parallel pointing dispatched (N tickets * P personas in ONE batch)
- [ ] Disagreements >1 step identified
- [ ] Reconciliation round dispatched for those tickets (in parallel)
- [ ] No ticket remains at 34 points (loop back to scope if any)
- [ ] M_AI applied per ticket; adjusted_hours computed
- [ ] Risk signals collected per ticket for the buffer phase

If ANY unchecked: complete Phase 4-5 before invoking `estimate-buffer`.

<FINAL_EMPHASIS>
Consensus is not voting — it is the synthesis of independent expert reasoning. Parallel dispatch protects independence; reconciliation surfaces what was missed; the 34-point halt protects calibration. Skip any of these and the consensus is a lie agreed upon.
</FINAL_EMPHASIS>
