# AI Productivity Multipliers (M_AI)

Per-ticket multiplier applied AFTER consensus pointing: `adjusted_hours = base_hours * M_AI`.

The multiplier reflects empirical findings (notably the METR study) that AI tools accelerate drafting on routine work but PENALIZE review of complex code. Net effect on complex work is NEGATIVE 25%: code review and QA overhead from AI-generated code in tricky domains exceeds the drafting savings.

## Low complexity

**Definition.** Boilerplate, CRUD endpoints, basic schemas, simple validators, straightforward database migrations, well-trodden patterns the codebase already demonstrates many times over.

**Component factors:**
- D (Drafting speed) = 0.5 — AI drafts the structure quickly
- R (Review overhead) = 1.0 — review burden is normal
- Q (QA overhead) = 1.0 — testing burden is normal

**M_AI = (D + R + Q) / 3 ≈ 0.7** — net 30% savings.

## High complexity

**Definition.** Novel architecture, complex third-party API integrations (especially ones with hard constraints — Stripe metadata limits, Plaid webhook ordering, Twilio rate-limit semantics), async/webhook flows, legacy entanglement, concurrency-sensitive code, anything requiring careful invariant reasoning.

**Component factors:**
- D (Drafting speed) = 1.1 — AI drafts something plausible-looking but often subtly wrong
- R (Review overhead) = 1.4 — reviewer must distrust AI output and re-derive invariants
- Q (QA overhead) = 1.3 — test cases must cover failure modes the AI did not anticipate

**M_AI ≈ 1.25** — net 25% PENALTY.

## Classification heuristics

Any of the following push a ticket from Low to High. Apply the highest-complexity classification triggered by the ticket.

- [ ] Touches an external API with documented constraints (rate limits, metadata limits, ordering guarantees, signature verification)
- [ ] Involves async flows: webhooks, queues, retries, idempotency keys
- [ ] Touches concurrency primitives: locks, transactions, race conditions, distributed state
- [ ] Modifies code older than 2 years that lacks contemporary tests
- [ ] Introduces a novel pattern not present in the codebase yet
- [ ] Crosses a service boundary (frontend <-> backend <-> 3rd party)
- [ ] Requires schema migration with data backfill
- [ ] Has security-sensitive surface (auth, PII handling, signing, secrets)

Zero triggers = Low. One or more = High.

## Note on the METR finding

AI tools accelerate drafting but penalize review of complex code; the net effect on complex work is NEGATIVE 25% per METR study findings. This is the empirical anchor for the High-complexity multiplier — it is not a guess. Estimators sometimes argue "but the AI will help" and apply M_AI < 1.0 universally. That argument loses on complex work. The multiplier exists precisely to defeat that bias.
