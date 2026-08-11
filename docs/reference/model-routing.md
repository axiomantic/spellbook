# Model Routing

Spellbook dispatches subagents at three generic **tiers**. Which model a tier
means is **yours to decide, per harness** -- spellbook ships the tiers, never
the models.

## Why there is no shipped routing table

Spellbook installs to nine harnesses. A model identifier that is correct in one
is meaningless in another: `openrouter/minimax/minimax-m3` does nothing on
Claude Code, and `opus` does nothing on a harness wired to OpenRouter. Any
single table this repo shipped would be right for whoever wrote it and wrong
for everyone else.

Earlier versions of this file *did* ship one operator's OpenRouter choices as
though they were universal, and pinned them into every agent's `model:`
frontmatter. That is the coupling this design removes.

## The tiers

Tiers name the **shape of the work**, not a vendor or a size.

| Tier | Use for | Pick |
|---|---|---|
| `heavy` | Reasoning-dominant work where a wrong answer is expensive to discover later: code review, conflict synthesis, design critique, research synthesis | Your most capable available model |
| `standard` | Judgement work with a bounded blast radius: monitoring, scope assessment, integration review | A mid-capability model |
| `light` | Mechanical work with a checkable result: applying a known edit, running a test command, git and PR plumbing | Your cheapest and fastest available model |

Ordering is load-bearing. **Escalation goes UP a tier, never down.** A task that
outgrew its tier needs more capability; silently giving it less is how the one
job that actually mattered gets handed to the cheapest model.

## Which agent runs at which tier

Each agent declares its tier in frontmatter (`tier: heavy`). Agents carry **no**
`model:` field -- that is what made them harness-specific.

- **heavy** -- `code-reviewer`, `justice-resolver`, `lovers-integrator`,
  `hierophant-distiller`, `web-researcher`
- **standard** -- `emperor-governor`, `queen-affective`
- **light** -- `implementer`, `chariot-implementer`, `test-runner`,
  `git-committer`, `git-pusher`, `pr-creator`, `pr-merger`, `jira-reader`,
  `jira-mutator`

## Where your preferences live

One key per tier per harness, in `~/.config/spellbook/spellbook.json`
(`%APPDATA%/spellbook/spellbook.json` on Windows):

```text
model.tier.<tier>.<harness>
```

For example:

```json
{
  "model.tier.heavy.claude_code": "opus",
  "model.tier.light.claude_code": "haiku",
  "model.tier.heavy.prime_agent": "openrouter/minimax/minimax-m3"
}
```

Harness ids are the installer's platform ids, underscored: `claude_code`,
`antigravity`, `opencode`, `codex`, `gemini`, `forgecode`, `pi`, `prime_agent`,
`goose`. Note `claude_code`, not `claude-code`.

Scoping by harness is what keeps one harness's answer from being applied to
another. The same tier legitimately maps to a different model in each.

## How a preference gets set

There is **no install-time wizard** for this. A typical install targets many
harnesses at once, and prompting three times per harness during install would
be unusable -- and at install time you may not yet know which models a given
harness offers you.

Instead the orchestrator resolves tiers **at dispatch time**:

1. Before dispatching subagents, it checks which tiers are unset for the
   harness it is running in.
2. If any are unset, it asks you once -- offering only models it can actually
   see in your harness -- and records your answers.
3. It then passes the resolved model as a per-call override.

An unset tier is **not** an error. It resolves to "no override", so the harness
uses its own default and the dispatch proceeds. A missing preference never
blocks work, which matters for non-interactive and CI runs where there is
nobody to ask.

Nothing invents a model id on your behalf. Any model spellbook could name here
would be wrong on most harnesses.

## Tools

| Tool | Purpose |
|---|---|
| `spellbook_model_tier_status(harness)` | Which tiers are set/unset, with guidance for each |
| `spellbook_model_tier_resolve(tier, harness)` | The model for one tier, or null if unset |
| `spellbook_model_tier_set(tier, harness, model)` | Record a preference |

These validate the tier and the harness id before writing. Setting the key
through the generic `spellbook_config_set` instead is unvalidated -- a typo
such as `model.teir.heavy.claude_code` persists silently and reads back null
forever, which presents as "my preference is being ignored" with nothing to
grep for. Use the tier tools.

The model value itself is deliberately **not** validated: the set of models
available to you is a property of your harness and account, which spellbook
cannot see.

## Escalation and overrides

- **Per-call override beats the tier.** Precedence is per-call override >
  tier resolution > harness default.
- **`fork` subagents ignore model overrides** -- they always inherit the
  parent model.
- **Escalate up, never down.** If a tier's model fails to produce a usable
  result, retry at the next tier up rather than down.
