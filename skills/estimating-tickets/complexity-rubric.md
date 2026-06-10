# Complexity Rubric — Points as Risk, Not Time

Story points here are a **COMPLEXITY / RISK tier**, explicitly **DECOUPLED from
time**. A point never becomes hours and is never multiplied by a day-rate.

<RULE>The complexity tier feeds two things only: (1) Bucket-A parallelizability (how independently agents can chew the work), and (2) Bucket-B risk (more complex = more review cycles + more QA bounce). It is NEVER converted to calendar directly.</RULE>

## Fibonacci complexity tiers (descriptors, NOT hours)

| Tier | Complexity descriptor |
|------|-----------------------|
| **3** | Trivial / mechanical. Boilerplate, registry entry, scaffold, single-file derivative change. No invariant reasoning. |
| **5** | Small, well-understood, localized. One module, known pattern, no surprises. |
| **8** | Moderate. Touches an external API or one integration point. Some invariant reasoning required. |
| **13** | Complex. Multiple integration points, concurrency/ordering concerns, or legacy entanglement. |
| **21** | Very complex. Cross-service, many unknowns, novel architecture. High estimation variance. |
| **34** | **MUST SPLIT before estimating.** Do not point a 34. Decompose into smaller tickets and re-tier. |

## How the tier propagates into the buckets

- **Bucket A (effort):** higher tier → more operator-shepherding per ticket and
  less clean parallelism (novel work needs the operator in the loop). But there
  is **no high-complexity time penalty** — agents parallelize the work AND its
  review. See `fleet-effort.md`.
- **Bucket B (latency):** higher tier → expect MORE CR cycles and MORE QA
  bounce. A 13 is more likely to take 3 review cycles and a QA round-trip than a
  5. This is where complexity actually moves the date. See `fleet-calendar.md`.

## Multi-agent consensus pointing

<RULE>Point each ticket via PARALLEL persona subagents and reconcile — do not assign a tier from a single read.</RULE>

- Dispatch **Backend**, **QA**, and **Data** persona subagents in parallel; each
  returns a tier + one-line rationale under a strict schema.
- **Reconcile:** if personas diverge by more than one Fibonacci step, surface
  the disagreement and the reason (usually a hidden integration point or
  invariant one persona saw and another missed) before settling on a tier. Take
  the higher tier when the disagreement is about discovered risk, not noise.
- **Halt + split** any ticket any persona scores a **34**. Return to Phase 1
  decomposition, re-tier the pieces, then continue.
