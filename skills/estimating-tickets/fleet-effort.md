# Fleet Effort — Bucket A (AI-collapsible)

This is the **Bucket A** model: how long coding/test/mechanical work takes to
become **code-ready PRs**. It REPLACES the old M_AI penalty entirely. There is
no complexity penalty multiplier here.

<RULE>Bucket A output is "code-ready PRs," not "merged work." Code-ready is rarely the bottleneck — Bucket B (fleet-calendar.md) sets the date.</RULE>

## Effort speed classes (assign one per ticket)

| Class | What it is | Effort |
|-------|------------|--------|
| **DERIVATIVE / existing-code** | Verify, adjust, mechanical refresh, test rewrites, follow-an-existing-pattern changes. | **Near-instant.** Effectively free vs Bucket B. If a human-anchor is ever forced, ~0.15–0.3× a human estimate — but prefer "a few hours, parallel." |
| **NET-NEW STRAIGHTFORWARD** | New code, known architecture, no novel invariants. | **A few hours, parallel.** |
| **NET-NEW COMPLEX** | Novel architecture / invariants the operator must shepherd. | **Up to ~half a day** of operator-shepherded agent work. **Still parallel.** |

## Key principles

<RULE>NO high-complexity penalty. A 13-point ticket is more complex than a 5, but agents parallelize the coding AND its review — complexity does NOT inflate Bucket A time the way it would for a serial human.</RULE>

- **Parallelism is capped by operator review throughput**, NOT agent count.
  Parameter: **REVIEW_THROUGHPUT** (default **2**; tunable concurrent PRs the
  operator can actively shepherd). Spinning up ten agents does not help if the
  operator can only review two PRs at once.
- **More agents ≠ faster past the cap.** Beyond REVIEW_THROUGHPUT, additional
  agents produce PRs that queue — that queue is Bucket B latency, not Bucket A
  effort.
- **Code-ready is the deliverable of this bucket.** Estimate Bucket A as: the
  time to get the critical-path PRs code-ready given REVIEW_THROUGHPUT
  parallelism. For most epics this is **~1 day or less**.

## Deriving Bucket A for an epic

1. Assign each ticket a speed class above.
2. Group tickets into PRs (fewer, bundled PRs is usually better — see the
   bundling lever in `fleet-calendar.md`).
3. Feed PRs through REVIEW_THROUGHPUT: at most REVIEW_THROUGHPUT PRs are
   "active" at once; the rest are code-ready-and-waiting.
4. Bucket A code-ready time ≈ the time to author the longest single PR plus a
   small shepherding tail for NET-NEW COMPLEX work. Report it as a parallel,
   not summed, number.

<FORBIDDEN>
- Summing per-ticket hours into a serial total.
- Treating agent count as the throughput limiter (REVIEW_THROUGHPUT is).
- Applying any complexity-based time multiplier to Bucket A.
</FORBIDDEN>
