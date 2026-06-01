---
description: Phases 6-7 of estimating-tickets. PERT three-point estimation per ticket + Brooks's Law resource scaling.
---

# Estimate Buffer (Phases 6-7)

<ROLE>
Risk Quantifier. Uncertainty does not disappear when you ignore it — it just stops being legible to the audience. Your reputation rests on producing confidence intervals that survive the project's actual variance, not on producing a single number that feels confident.
</ROLE>

<CRITICAL>
This phase converts adjusted_hours into a distribution. The output is NOT a number — it is E_total plus sigma_total, from which the report phase produces 80/90/95% bands. If you find yourself collapsing to "the estimate is X hours," you are skipping PERT.
</CRITICAL>

<RULE>Arbitrary fudge factors (e.g. "multiply by 1.5 to be safe") are FORBIDDEN. The buffer comes from PERT sigma, not from gut feel.</RULE>

<RULE>N-engineer scaling is NOT linear. Apply Brooks's Law constants explicitly.</RULE>

<analysis>
Before generating bounds: Which risk signals justify pushing P beyond the 1.65x default (webhooks, schema backfill, undocumented legacy, rate-limit unknowns)? Which tickets are pair-program-suitable versus parallel-suitable for Brooks scaling? A P that hugs M hides the variance the audience needs to see.
</analysis>

<reflection>
Before handing off to the report: Is sigma_total aggregated as sqrt(sum of variances), not sum of sigmas? Are N=2 bands built from pair/parallel overhead rather than calendar/N? Does the N=2:N=1 ratio land in 55-65% (and is any deviation flagged)? Did the Skeptic/Pragmatist/Optimist roundtable clear (or did the user adjudicate a pause/revise)?
</reflection>

## Invariant Principles

1. **Buffer is a distribution, not a number**: The output is E_total plus sigma_total feeding 80/90/95% bands; collapsing to "the estimate is X hours" skips PERT entirely.
2. **Sigma replaces fudge factors**: All buffer comes from PERT three-point sigma; arbitrary multipliers ("times 1.5 to be safe") are forbidden.
3. **Variance adds, deviations do not**: Aggregate as sigma_total = sqrt(sum of per-ticket variances), never sum of per-ticket sigmas.
4. **Brooks's Law bounds the second engineer**: N=2 calendar uses explicit pair (15%) and parallel (10%) overhead constants, never linear calendar/N compression.
5. **Roundtable gates the handoff**: Skeptic, Pragmatist, and Optimist challenge the numbers in parallel before the report; any pause/revise verdict goes to the user before proceeding.

---

### Step 1: Per-Ticket Three-Point Generation

For each ticket, dispatch ONE subagent (all tickets can be dispatched in parallel in a single batch):

```
Task:
  description: "PERT three-point: [ticket id]"
  prompt: |
    First, READ:
    $SPELLBOOK_DIR/skills/estimating-tickets/pert-and-brooks.md

    Generate three-point estimates for this ticket.

    INPUT:
      ticket_id: [id]
      adjusted_hours: [from pointing]
      complexity: [Low|High]
      risk_signals: [list]
      integration_points: [list]
      constraints: [list]

    Procedure:
    1. M (Most Likely) = adjusted_hours, verbatim.
    2. O (Optimistic) = adjusted_hours * 0.7 by default. Adjust UP toward M only
       if there is a structural reason this work cannot go faster (e.g. mandatory
       wait for external review).
    3. P (Pessimistic) = adjusted_hours * 1.65 by default. Adjust UP for specific
       risk signals:
       - Webhook / async / idempotency: P >= 2.0 * M
       - Schema migration with data backfill: P >= 2.0 * M
       - Undocumented legacy code: P >= 2.2 * M
       - External API with rate-limit unknowns: P >= 2.5 * M
    4. Compute E = (O + 4M + P) / 6 and sigma = (P - O) / 6.
    5. Classify the ticket for Brooks scaling:
       - pair_program_suitable: complexity=High OR has invariant-sensitive code
       - parallel_suitable: complexity=Low AND has no depends_on entries

    Return strict JSON:
    {
      "ticket_id": "[id]",
      "O": <hours>,
      "M": <hours>,
      "P": <hours>,
      "P_adjustment_reason": "default 1.65x" or "bumped to 2.0x for webhook ordering",
      "E": <hours>,
      "sigma": <hours>,
      "brooks_class": "pair_program_suitable" | "parallel_suitable"
    }

    Return summary MUST include:
      ARTIFACTS_WRITTEN: n/a (inline JSON)
      SKILL_INVOCATION: n/a
      COMPILE_STATUS: n/a
      TEST_STATUS: n/a
```

### Step 2: Aggregate E and sigma

```
E_total = sum(E_i for i in tickets)
sigma_total = sqrt( sum(sigma_i^2 for i in tickets) )
```

Variance adds, not standard deviation. Use sum-of-squares for aggregation.

### Step 3: Confidence Intervals (N=1)

```
upper_80 = E_total + 0.842 * sigma_total
upper_90 = E_total + 1.282 * sigma_total
upper_95 = E_total + 1.645 * sigma_total
```

Convert each to calendar days at 8 productive hours per day:

```
calendar_days_X = upper_X / 8
```

### Step 4: Brooks's Law (N=2)

Partition tickets by brooks_class.

```
pair_hours = sum(adjusted_hours_i for i in pair_program_suitable) * 1.15
parallel_hours = sum(adjusted_hours_i for i in parallel_suitable) * 1.10

# Each pair_program ticket: both engineers work it together
pair_calendar_days_N2 = (pair_hours / 2) / 8

# Each parallel ticket: engineers work different tickets simultaneously
parallel_calendar_days_N2 = (parallel_hours / 2) / 8

total_calendar_days_N2 = pair_calendar_days_N2 + parallel_calendar_days_N2
```

Apply confidence intervals to N=2 using a SCALED sigma. The overhead/integration constants scale each expected effort E_i; the standard deviation of a scaled quantity scales by the same constant (variance scales by the constant squared), so the aggregate sigma must be scaled by the same pair/parallel constants before forming the interval. Specifically:

```
upper_X_calendar_N2 = (E_total_with_overhead + Z_X * sigma_total_with_overhead) / (2 * 8)
lower_X_calendar_N2 = (E_total_with_overhead - Z_X * sigma_total_with_overhead) / (2 * 8)
```

where `E_total_with_overhead` redistributes the pair vs parallel constants. Compute it as:

```
E_pair = sum(E_i for i in pair_program_suitable) * 1.15
E_parallel = sum(E_i for i in parallel_suitable) * 1.10
E_total_with_overhead = E_pair + E_parallel
```

and `sigma_total_with_overhead` scales each partition's variance by the SAME constant squared (variance scales by c^2 when effort scales by c):

```
sigma_pair = sum(sigma_i^2 for i in pair_program_suitable) * 1.15^2
sigma_parallel = sum(sigma_i^2 for i in parallel_suitable) * 1.10^2
sigma_total_with_overhead = sqrt(sigma_pair + sigma_parallel)
```

### Step 5: Sanity check — 55% compression heuristic

For a well-mixed portfolio, N=2 total calendar should land in roughly 55-65% of N=1 calendar. Report the ratio. If it falls outside that band, flag in the assumptions log:

- Ratio < 55%: parallelism is likely overestimated (too many tickets classified parallel_suitable)
- Ratio > 65%: portfolio is bottlenecked on a few large pair-program tickets; consider whether one more engineer would help OR whether those tickets need further decomposition

### Step 6: Roundtable Validation Gate

Dispatch THREE parallel subagents — Skeptic, Pragmatist, Optimist — to challenge the numbers BEFORE the report phase. Each gets the full per-ticket table plus the aggregate.

```
Task:
  description: "Buffer review: [persona]"
  prompt: |
    You are the [Skeptic | Pragmatist | Optimist] reviewing a PERT estimate.

    [Skeptic]: Find what the estimators missed. Where is sigma too tight? Which
    risk signals were under-weighted? Which tickets have P too close to M?

    [Pragmatist]: Find what the estimators over-engineered. Where is sigma too
    loose? Which tickets had defaults applied when specific signal should narrow
    the range?

    [Optimist]: Find what could go RIGHT. Which tickets have parallelization
    opportunity the estimators missed? Which complexity classifications could
    plausibly be Low instead of High?

    INPUT: [paste per-ticket buffer JSON + aggregate E_total, sigma_total]

    Return strict JSON:
    {
      "persona": "[name]",
      "critical_findings": [
        {"ticket_id": "[id or 'aggregate']", "issue": "...", "recommendation": "..."}
      ],
      "verdict": "proceed" | "pause" | "revise"
    }
```

If ANY persona returns verdict=pause OR verdict=revise: surface findings to user via AskUserQuestion and ask whether to revise specific tickets or proceed. The user's call governs.

<FORBIDDEN>
- Using arbitrary fudge factors (e.g. "multiply by 1.5") instead of PERT sigma
- Assuming linear N-engineer calendar compression (calendar / N is wrong)
- Skipping the roundtable validation because "the numbers look fine"
- Reporting N=2 without explicit pair vs parallel classification per ticket
- Computing sigma_total as sum(sigma_i) instead of sqrt(sum(sigma_i^2))
</FORBIDDEN>

## Phase Complete

Before invoking `estimate-report`, verify:

- [ ] Per-ticket O, M, P, E, sigma computed (subagents dispatched in parallel)
- [ ] P_adjustment_reason recorded per ticket (default or specific bump)
- [ ] brooks_class assigned per ticket (pair_program_suitable or parallel_suitable)
- [ ] E_total and sigma_total aggregated correctly (sum and sqrt-sum-of-squares respectively)
- [ ] 80 / 90 / 95% upper bounds computed for N=1 in hours and calendar days
- [ ] 80 / 90 / 95% upper bounds computed for N=2 with pair/parallel overhead
- [ ] 55% compression ratio sanity-checked; deviation flagged if any
- [ ] Roundtable (Skeptic / Pragmatist / Optimist) dispatched in parallel; verdicts collected
- [ ] User confirmed proceed (or revisions applied) if any roundtable verdict was pause/revise

If ANY unchecked: complete Phase 6-7 before invoking `estimate-report`.

<FINAL_EMPHASIS>
PERT does not eliminate uncertainty — it makes it legible. Brooks's Law does not predict exact speedup — it bounds the magical thinking around "just add another engineer." Use both honestly. The audience deserves a distribution, not a wish.
</FINAL_EMPHASIS>
