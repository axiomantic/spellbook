# Fleet Calendar — Bucket B (irreducible latency, the date driver)

This is **Bucket B**: the wall-clock latency that does NOT compress with more
agents. **This sets the delivery date.** Everything here is a fixed gate once a
PR is code-ready.

<RULE>Adding agents does nothing in this bucket. The only levers are: fewer PRs on the critical path, and where the merge lands relative to the deploy cutoff / Friday.</RULE>

## Cadence parameters (operator-configurable; defaults from this operator's real workflow)

### CODE REVIEW
- **Bot review:** instant / automatic.
- **Human review:** **2–3 cycles** on a large (~100-file) PR; **1–3 days per
  cycle**.
- **Merge requires:** **2 approvals (1 bot + 1 human)** + **CI green**.
- Parameter: `CR_CYCLES` (default 2–3), `CR_CYCLE_DAYS` (default 1–3).

### LC QA (PRE-merge)
- Code goes to an **ephemeral "launch control" QA instance**: manual testing +
  Cypress e2e.
- **1–2 days + ~1 feedback cycle = 2–4 days total.**
- Parameter: `QA_DAYS` (default 2–4).

### DEPLOY CADENCE
- After QA approval → **merge**.
- **2pm cutoff:** merged **before 2pm** → deploy to **stage same day**.
- **Prod** deploys at **2pm the NEXT day**.
- **NO PROD DEPLOYS ON FRIDAYS.**
  - A **Thursday-before-cutoff** merge would target Friday prod → **slips to
    Monday**.
  - A **Friday** merge rides Friday staging → **Monday prod**.
- Parameters: `DEPLOY_CUTOFF` (default 14:00), `NO_DEPLOY_DAYS` (default {Fri, Sat, Sun}).

### PARALLELISM
- Multiple PRs can be in flight, **bounded by REVIEW_THROUGHPUT (default 2)**.
- **Independent tickets fill the review/QA wait windows** — while PR #1 sits in
  QA, the operator shepherds PR #2. This is the main way Bucket B is hidden, but
  it does NOT shorten the critical path of a single dependent chain.

### OPERATIONAL TAILS
- **Backfill / one-shot run shipped INSIDE the feature PR:** adds only a
  **same-day run after prod** — no second pipeline.
- **Backfill / command in a SEPARATE PR:** adds a **whole second deploy
  pipeline** (its own CR + QA + deploy). Avoid when possible.
- **Scheduled-job (e.g. nightly) first-fire validation:** typically **OFF the
  critical path** — validated async after deploy.

## CRITICAL PATH formula

```
critical_path =
    Bucket A code-ready (~1 day, parallel)
  + (ONE deploy pipeline per SEQUENTIAL PR on the path)
  + same-day operational runs (if in-PR)

where one deploy pipeline =
    CR dance (CR_CYCLES × CR_CYCLE_DAYS)
  + LC QA (QA_DAYS)
  + merge → deploy (cutoff + next-day prod + Friday-skip)
```

Independent PRs run their pipelines in parallel up to REVIEW_THROUGHPUT and do
NOT add to the critical path; only the longest sequential chain counts.

## Best / expected / worst bands

| Band | Assumptions |
|------|-------------|
| **Best** | 1 CR cycle, clean QA (no bounce), merge before cutoff on a non-Friday-straddling day. |
| **Expected** | 2 CR cycles, 1 QA feedback round, normal cutoff timing. |
| **Worst** | 3 CR cycles, bounced QA, a Thursday/Friday straddle pushing prod to Monday. |

Report all three. The "date" is the **expected** band with worst called out.

## The main lever: bundle into FEWER PRs

<RULE>Each additional sequential PR on the critical path adds a whole deploy pipeline (CR cycles + QA + deploy). Bundling independent-but-related work into FEWER PRs reduces CR-cycle count and is the single biggest lever on the date. Trade off against PR size making human review slower per cycle.</RULE>

<FORBIDDEN>
- Assuming more agents shrink any Bucket B gate.
- Omitting the 2pm cutoff or Friday-skip from a date calculation.
- Counting parallel independent PRs as additive to the critical path.
- Putting a backfill in a separate PR without flagging the extra pipeline cost.
</FORBIDDEN>
