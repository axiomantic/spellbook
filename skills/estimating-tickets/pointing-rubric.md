# Pointing Rubric (Canonical)

This rubric is the SINGLE SOURCE OF TRUTH for translating Fibonacci story points into hours and calendar days. All pointing subagents READ this file and map their consensus point value to base_hours via this table.

| Points | Definition | Base hours | Base days |
|--------|------------|------------|-----------|
| 3 | Half day of work (morning to lunch, or lunch to sign-off) | 4 | 0.5 |
| 5 | Full day of work | 8 | 1.0 |
| 8 | 1.5 to 2 full days of work | 14 (mean) | 1.75 |
| 13 | 3 to 5 days of work | 32 (mean) | 4.0 |
| 21 | >1 week, <2 weeks | 60 (mean) | 7.5 |
| 34 | >2 weeks of work — MUST BE SPLIT by the agent into smaller tickets, never estimated as-is | N/A | N/A |

## Why hours-per-day matters

Story points are abstract; hours are not. Teams and product partners reason about delivery in days and weeks, and the only way to make a points estimate actionable is to commit to a hours-per-point translation up front. This rubric assumes an 8-hour productive day. If the team's actual focused-coding capacity is lower (meetings, reviews, on-call), the calendar days expand proportionally — but the BASE hours stay anchored to this table so the pointing conversation stays comparable across tickets and across estimators.

Without a fixed hours-per-day, "5 points" means whatever the speaker wants it to mean, and the multi-agent consensus loses its grounding. With this table, two personas disagreeing on a 5 vs an 8 are disagreeing about real work, not vocabulary.

## Why 34 must be split

A 34-point ticket is, by this rubric's own definition, more than two weeks of work. At that horizon, PERT three-point estimation loses calibration: the pessimistic case explodes (sigma becomes the dominant term), the cone of uncertainty makes any single number meaningless, and AI productivity multipliers compound errors instead of correcting them. A ticket pointed 34 is signaling decomposition failure in the scoping phase, not a large-but-estimable unit of work.

When the pointing phase produces a 34 for any ticket, the pipeline HALTS and loops back to `estimate-scope`. The user is asked (via AskUserQuestion) to split the ticket into smaller units that individually point at 21 or below. There is no exception to this rule — not for "obvious" 34s, not for "I know how to build this." The estimate is unreliable above 21 points regardless of estimator confidence.
