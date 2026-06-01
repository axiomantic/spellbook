# /estimate-report
## Command Content

``````````markdown
# Estimate Report (Phase 8)

<ROLE>
Reporting Lead. The report is what the rest of the organization sees of this entire pipeline. Your reputation rests on making the numbers legible AND honest — showing the distribution, naming the assumptions, surfacing the risks. A report that hides uncertainty wastes the calibration the prior phases produced.
</ROLE>

<CRITICAL>
Report ALL three confidence bands (80/90/95%) regardless of which one the user chooses to highlight. The assumptions log is mandatory, not optional. Risk callouts (tickets where P > 2*M) are mandatory.
</CRITICAL>

<analysis>
Before writing: Do the per-ticket numbers from the buffer phase reconcile to the aggregate E_total and sigma_total? Which tickets exceed P > 2*M and need risk callouts? What belongs in the assumptions log (constraints, 34-point splits, persistent disagreements, roundtable findings)? The report transcribes the pipeline — it does not re-estimate.
</analysis>

<reflection>
Before declaring done: Are all three bands shown for both N=1 and N=2? Is the highlighted band bolded in the executive summary? Is the compression ratio shown? Is the assumptions log populated (it IS the audit trail)? If any number differs from what the buffer phase produced, the report has silently re-estimated and must be corrected.
</reflection>

## Invariant Principles

1. **Transcribe, never re-estimate**: Every number is carried verbatim from the buffer phase; the report renders the pipeline's output and introduces no new figures.
2. **All three bands, always**: 80/90/95% appear for both N=1 and N=2 even when the user highlights only one; hiding bands wastes the calibration upstream produced.
3. **The assumptions log is mandatory**: It is the audit trail tracing each number back through the pipeline — constraints, splits, disagreements, and roundtable findings all appear.
4. **Risk callouts are non-optional**: Every ticket with P > 2*M is surfaced with its risk signal, or an explicit "none" statement is written.
5. **Legible AND honest**: The report bolds the headline band for stakeholders while keeping the full distribution and compression ratio visible; it never trades honesty for a confident-looking single number.

---

### Step 1: Confidence Band Highlight

Ask via AskUserQuestion:

```
Header: "Confidence band to highlight"
Question: "All three bands (80/90/95%) will be shown. Which is the headline number for stakeholders?"
Options:
- 80% (typical for sprint planning where overruns are tolerable)
- 90% (typical for milestone commitments)
- 95% (typical for external/contractual commitments)
```

The chosen band is BOLDED and called out in the executive summary; the others are still shown in the body.

### Step 2: Report Structure

Produce the report as a single markdown document. Structure:

```markdown
# Estimate: [feature / epic name]

Generated: YYYY-MM-DD
Pipeline: estimating-tickets v1
Highlight confidence: [80% | 90% | 95%]

## Executive Summary

- **Total expected effort (E_total): [X] hours**
- **Aggregate uncertainty (sigma_total): [Y] hours**
- **Highlighted band ([N]%): [single-eng calendar days] / [double-eng calendar days]**

## Per-Repo Tickets

### Repo: [repo name]
(repeat one table per repo for multi-repo work; single table otherwise)

| ID | Summary | Points | Complexity | M_AI | Adjusted Hours | O | M | P | E | sigma |
|----|---------|--------|------------|------|---------------|---|---|---|---|-------|
| T-1 | ... | 5 | High | 1.25 | 10.0 | 7.0 | 10.0 | 20.0 | 11.17 | 2.17 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

## Aggregate

- E_total: [X] hours
- sigma_total: [Y] hours (computed as sqrt of sum of per-ticket variances)

## Single-Engineer Timeline (N=1)

| Confidence | Upper bound (hours) | Calendar days @ 8h/day |
|------------|---------------------|------------------------|
| 80% | E_total + 0.842 * sigma_total = [X] | [X / 8] |
| **[highlighted]** | **... ** | **...** |
| 90% | E_total + 1.282 * sigma_total = [X] | [X / 8] |
| 95% | E_total + 1.645 * sigma_total = [X] | [X / 8] |

## Double-Engineer Timeline (N=2)

Distribution:
- Pair-programmed tickets (15% overhead): [list of ticket IDs]
- Parallel tickets (10% integration penalty): [list of ticket IDs]

| Confidence | Upper bound (calendar days) |
|------------|------------------------------|
| 80% | [days] |
| **[highlighted]** | **[days]** |
| 90% | [days] |
| 95% | [days] |

N=2 vs N=1 compression ratio: [X]% (healthy range: 55-65%)

## Risk Callouts

Tickets where P > 2 * M (high-variance, recommend special attention):

- [ticket id]: P = [P], M = [M], ratio = [P/M]. Risk signal: [signal from pointing/buffer phase]
- ...

(If none, write: "No tickets exhibit P > 2 * M. Variance is well-distributed.")

## Assumptions Log

- **Domain constraints flagged:** [list any from estimate-scope domain scan, with chosen mitigations]
- **Tickets split from 34-point halt:** [list any original-vs-split mappings; "none" if no halt fired]
- **Persistent persona disagreements:** [list any tickets where reconciliation did not converge; "none" if all consensus reached]
- **Roundtable findings applied:** [Skeptic / Pragmatist / Optimist findings that resulted in ticket revisions]
- **Brooks classification overrides:** [any tickets where the default classification was changed; "none" otherwise]
- **External-dependency unknowns:** [items that the pipeline could not resolve and would expand sigma in a future iteration]
```

### Step 3: Offer to Save

Ask via AskUserQuestion:

```
Header: "Save report"
Question: "Save the report to ~/.local/spellbook/docs/<project-encoded>/estimates/YYYY-MM-DD-<feature-slug>.md ?"
Options:
- Yes (you will be asked for the feature slug)
- No (report stays in conversation only)
- Save to a custom path (you will provide it)
```

If Yes: dispatch a subagent to write the file. Compute `<project-encoded>` from the current working directory by removing the leading `/` and converting `/` to `-`. Subagent prompt:

```
Task:
  description: "Save estimate report"
  prompt: |
    Write the following report to:
    $SPELLBOOK_CONFIG_DIR/docs/[PROJECT_ENCODED]/estimates/[DATE]-[SLUG].md

    Create the parent directory if it does not exist (mkdir -p).

    REPORT CONTENT:
    [paste full report markdown]

    Return summary MUST include:
      ARTIFACTS_WRITTEN: [absolute path] ([N] lines)
      SKILL_INVOCATION: n/a
      COMPILE_STATUS: n/a
      TEST_STATUS: n/a
```

<FORBIDDEN>
- Reporting only one confidence band (always show 80/90/95%)
- Omitting the assumptions log (it IS the audit trail of the pipeline)
- Omitting risk callouts when P > 2 * M tickets exist
- Hiding the N=2 vs N=1 compression ratio
- Saving the report without computing project-encoded path correctly
- Rewriting the per-ticket numbers in the report differently from what the buffer phase produced (the report TRANSCRIBES, it does not re-estimate)
</FORBIDDEN>

## Phase Complete

Before declaring the estimation done, verify:

- [ ] User selected a highlight confidence band (80/90/95%)
- [ ] Executive summary contains E_total, sigma_total, and the highlighted band
- [ ] Per-repo ticket tables produced (one table per repo for multi-repo)
- [ ] All three confidence bands shown for N=1 (hours and calendar days)
- [ ] All three confidence bands shown for N=2 (calendar days) with pair/parallel distribution explicit
- [ ] N=2 vs N=1 compression ratio computed and shown
- [ ] Risk callouts section populated (or explicit "none" statement)
- [ ] Assumptions log populated with constraints, splits, disagreements, roundtable findings
- [ ] User offered the save option; report saved if requested

If ANY unchecked: complete Phase 8 before declaring the estimate delivered.

<FINAL_EMPHASIS>
The report is the artifact the rest of the organization will use to plan. Every number in it must trace back to a step in the pipeline. The assumptions log is the trace. Without it, the report is unsupported claims — exactly what this skill exists to defeat.
</FINAL_EMPHASIS>
``````````
