# PERT and Brooks's Law: Formulas Cheat Sheet

Reference for `estimate-buffer`. All formulas operate on per-ticket adjusted_hours from `estimate-point`.

## PERT Three-Point Estimation

For each ticket, generate three estimates:

- **O** (Optimistic) — best-case hours, everything goes right
- **M** (Most Likely) — = adjusted_hours from pointing
- **P** (Pessimistic) — worst-case hours, with realistic risks materializing

**Expected value (per ticket):**

```
E = (O + 4M + P) / 6
```

**Standard deviation (per ticket):**

```
sigma = (P - O) / 6
```

**Aggregation across N tickets (assumes independence):**

```
E_total = sum(E_i)
sigma_total = sqrt( sum(sigma_i^2) )
```

The aggregate sigma uses sum-of-squares because per-ticket variances add (not standard deviations). This is the standard PERT aggregation and is why combining many small tickets has TIGHTER aggregate uncertainty than one large ticket of equivalent total expected value.

## Confidence Intervals (Z-scores)

For a one-sided upper bound at confidence level C:

```
upper_bound(C) = E_total + Z(C) * sigma_total
```

| Confidence | Z-score |
|------------|---------|
| 80% | 0.842 |
| 90% | 1.282 |
| 95% | 1.645 |

Always report all three bands. A single band hides the shape of the distribution from the audience.

## Default heuristics for O and P

When a pointing subagent has no specific risk signal:

- O = adjusted_hours * 0.7
- P = adjusted_hours * 1.65

These can and should be adjusted per ticket when there is specific risk signal. Example: a ticket involving Stripe webhook signature verification should bump P toward 2.5x adjusted_hours because async/mocking complexity has a fat right tail. The estimator should EXPLAIN any deviation from the defaults inline; unexplained P > 2*M is a flag worth surfacing in the report.

## Brooks's Law: Resource Scaling

Adding engineers does not linearly compress calendar time. Communication overhead scales as N(N-1)/2 — the number of pairwise communication channels.

```
C = N(N-1)/2
```

| N | Channels |
|---|----------|
| 1 | 0 |
| 2 | 1 |
| 3 | 3 |
| 4 | 6 |
| 5 | 10 |

For N=2 estimation, classify each ticket and apply the appropriate constant:

- **Pair-program suitable (high complexity):** both engineers work the same ticket together. 15% communication/coordination overhead. Effective calendar compression to ~57.5% of single-engineer hours per ticket.
- **Parallel-execution suitable (decoupled, low complexity):** engineers work different tickets in parallel. 10% integration penalty applied to aggregate hours. Calendar compression depends on dependency graph; for fully-independent tickets, near-linear compression after penalty.

## N=1 calendar conversion

Assume 8 productive hours per day. Convert hours to calendar days:

```
calendar_days(N=1) = hours / 8
```

## N=2 calendar conversion

For a ticket portfolio mixing pair-program and parallel tickets:

```
pair_hours = sum(adjusted_hours_i for i in pair-suitable) * 1.15
pair_calendar_days = (pair_hours / 2) / 8
                     # divided by 2 because both engineers work the ticket together

parallel_hours = sum(adjusted_hours_i for i in parallel-suitable) * 1.10
parallel_calendar_days = (parallel_hours / 2) / 8
                         # divided by 2 because engineers work different tickets in parallel

total_calendar_days(N=2) = pair_calendar_days + parallel_calendar_days
```

The 55% calendar-compression heuristic is a sanity check: for a well-mixed portfolio, N=2 calendar should land in the 55-65% range of N=1 calendar. Significantly higher means the portfolio is bottlenecked on a few large pair-program tickets; significantly lower means parallelism is overestimated and integration cost will likely correct it.

## What this does NOT model

- N >= 3 — Brooks's Law gets nonlinear fast; this cheat sheet stops at N=2 on purpose.
- Ramp-up time for engineers new to the codebase.
- Calendar holidays, on-call rotations, meeting load.

These are out of scope. Report them in the assumptions log if relevant.
