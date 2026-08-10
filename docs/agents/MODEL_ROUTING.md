# MODEL_ROUTING
## Agent Content

```markdown
# Agent Model Routing

## Operator Verbatim (2026-08-07 / 2026-08-08)

- "don't use Claude/Anthropic at all"
- "Minimax version 4 is a great all-around model" (M4 not yet on OpenRouter; M3 is closest)
- "for simpler tasks, something cheap like DeepSeek V4 Flash"
- "i dont know anything about kimi, wasnt my suggestion. open to whatever but that pricing is way too much"
- "its not just nemotron, actually it may be faster than the other ollamas. ollama is slow - the local inference"

## EXCLUDED

| Model family | Why | Date |
|---|---|---|
| `anthropic/*` | any Claude, any version. Sonnet budget-burned 2026-08-07 | 2026-08-07 |
| `google/*` | proprietary; operator excluded as not "open weights" | 2026-08-07 |
| `fable` (operator-side Anthropic flag) | FORBIDDEN unless operator names explicitly | 2026-08-07 |
| `kimi-k2.7-code` (moonshotai) | above operator's cost tolerance; not operator-suggested | 2026-08-07 |

## TIER 1 — thinking (API)

Use for: planning, design, architecture, code/design review, fact-checking, adversarial review, debugging unknowns, research, synthesis, arbitration, anything requiring judgment.

| Model | $/M input | $/M output | When |
|---|---|---|---|
| `openrouter/minimax/minimax-m3` (DEFAULT) | $0.24 | $0.96 | operator's stated max-spend tier |
| `openrouter/deepseek/deepseek-v4-pro` (FALLBACK) | $0.44 | $0.87 | if M3 fails quality gate after retry |

Subagents that map here: code-reviewer, justice-resolver, lovers-integrator, hierophant-distiller, web-researcher

Effort: inherit session.

## TIER 2 — mechanical (API)

Use for: TDD green-bar, schema-strict code refactor, rote edits, git/PR/Jira mechanics, applying a described change, running tests, completion/artifact verification against a checklist, precisely-specified amends.

| Model | $/M input | $/M output | When |
|---|---|---|---|
| `openrouter/deepseek/deepseek-v4-flash-0731` | $0.09 | $0.18 | pinned to dated snapshot for predictable output; rolls of `-latest` alias won't change behavior |

Subagents that map here: implementer, chariot-implementer, test-runner, git-committer, git-pusher, pr-creator, pr-merger, jira-reader, jira-mutator.

Effort: low.

Escalation path: mechanical fails → thinking (minimax-m3) → STOP and surface to operator. (kimi escalation removed 2026-08-07.)

## TIER 3 — ollama (OFFLINE — SLOW AS A CLASS)

Operator confirmed 2026-08-08: ollama local inference is slow. The free tier is for genuinely short, low-shape tasks where the API round-trip overhead is itself the cost concern.

**Do NOT default to ollama because it is free.** Prefer API tiers whenever the task has shape, time budget, or reasoning requirement.

Fallback rule: if the chosen ollama is unavailable or not pulled, fall back to the next tier up — which by operator preference is an API tier, NOT another ollama.

| Model | Size | Use case |
|---|---|---|
| `ollama/gemma4:e4b` | 8B sparse (~10GB) | trivial/rote: formatting, simple renames, file listings, single-token fill-ins, completions, spell-check passes |
| `ollama/gpt-oss:20b` | 20.8B / 3.6B active (~12GB) | short single-file reasoning: bug root-cause, small algorithm selection, docstring-to-test, function-body fill from clear spec. **CAVEAT:** contradictory benchmarks (benchlm.ai 41.8/100 vs Ian Paterson 2026 98.3%) — verify on first use |
| `ollama/nemotron-3-nano:30b` | 30B-A3B MoE (~24GB, 1M context) | unique 1M context via hybrid Mamba-2 + MoE. Per operator 2026-08-08, "may be faster than the other ollamas" — still constrained to short tasks because ollama is slow as a class |

## ESCALATION ORDER

Shape match first:
1. trivial/rote single-token   → ollama_trivial (gemma4:e4b)
2. short single-file reasoning  → ollama_reasoning (gpt-oss:20b) OR ollama_agentic (nemotron)
3. schema-strict mechanical     → mechanical (deepseek-v4-flash-0731) — **API**
4. design / planning / unknown  → thinking (minimax-m3) — **API**

Auto-escalate UP through tiers; never auto-de-escalate DOWN.

Default to the cheapest tier whose shape matches the task. If the chosen ollama is unavailable, fall back to the **API** tier, not another ollama.

STOP and surface to operator when thinking tier fails or operator names a model.

## ROUTING BY SUBAGENT TYPE

| Agent type | Tier | Model |
|---|---|---|
| code-reviewer | thinking | minimax/minimax-m3 |
| justice-resolver | thinking | minimax/minimax-m3 |
| lovers-integrator | thinking | minimax/minimax-m3 |
| hierophant-distiller | thinking | minimax/minimax-m3 |
| web-researcher | thinking | minimax/minimax-m3 |
| implementer | mechanical | deepseek-v4-flash-0731 |
| chariot-implementer | mechanical | deepseek-v4-flash-0731 |
| test-runner | mechanical | deepseek-v4-flash-0731 |
| git-committer | mechanical | deepseek-v4-flash-0731 |
| git-pusher | mechanical | deepseek-v4-flash-0731 |
| pr-creator | mechanical | deepseek-v4-flash-0731 |
| pr-merger | mechanical | deepseek-v4-flash-0731 |
| jira-reader | mechanical | deepseek-v4-flash-0731 |
| jira-mutator | mechanical | deepseek-v4-flash-0731 |
| emperor-governor | (no model specified; cheap local OK for status checks) | gemma4:e4b or none |
| queen-affective | (no model specified; cheap local OK for sentiment) | gemma4:e4b or none |

## PER-CALL OVERRIDE

Operator names opus / sonnet / haiku / MiniMax-M4 / any specific model in a request → may use it for that specific dispatch. Otherwise default routing applies.

## SESSION-START CONFIRMATION

At session start, BEFORE any subagent dispatch, the agent should confirm the tier-to-model mapping with the operator. If the operator declines or doesn't respond in 30s, apply the defaults above.

## BUDGET ENFORCEMENT

Before dispatching ANY subagent, check that the chosen model is not in the excluded list. NEVER silently fall back to a more expensive tier.

## GLOSSARY

- "operator": the human running the session, who specifies model preferences
- "tier": a routing bucket (thinking, mechanical, ollama_*) based on task shape
- "shape": the cognitive load / reasoning depth of a task, not its file size
- "opt-in": ollama tiers require explicit operator consent, not default
- "escalation": moving UP through tiers when a lower one fails; never DOWN
```
