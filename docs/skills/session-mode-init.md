# session-mode-init

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Loaded at session start when spellbook_session_init returns mode data, or when mode.type is 'unset'. Triggers: session init mode handling, '/mode', mode selection, 'fun mode', 'tarot mode'.
## Skill Content

``````````markdown
<analysis>
Procedure for reading mode type from session init and dispatching to the correct mode skill or prompting the user for selection.
</analysis>

<reflection>
Did I dispatch to the correct mode skill based on the session init response, and did I persist the user's choice if mode was unset?
</reflection>

# Session Mode Init

## Invariant Principles

1. **Ask Once, Persist** - The mode selection question is asked only when mode is unset; the choice is persisted via `spellbook_config_set`.
2. **Mode Drives Skill, Not Behavior** - Mode selection loads the corresponding skill; mode never alters code output or technical decisions.
3. **Graceful Degradation** - If MCP is unavailable, remember the preference in-session without blocking initialization.

Reference procedure for selecting and dispatching session modes during session initialization.

## Mode Dispatch Table

| Response from `spellbook_session_init`        | Action                                                                                               |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `mode.type: "unset"`                          | Ask question below, then call `spellbook_config_set(key="session_mode", value="fun"/"tarot"/"none")` |
| `mode.type: "fun"` + persona/context/undertow | Load `fun-mode` skill, announce persona+context+undertow in greeting                                 |
| `mode.type: "tarot"`                          | Load `tarot-mode` skill, announce roundtable in greeting                                             |
| `mode.type: "none"`                           | Proceed normally with standard greeting                                                              |
| MCP unavailable                               | Ask mode question manually, remember preference for session                                          |

## Mode Selection Question

Ask once when mode is unset:

> Research suggests creative modes improve LLM output via "seed-conditioning" ([Nagarajan et al., ICML 2025](https://arxiv.org/abs/2504.15266)). I can adopt:
>
> - **Fun mode**: Random personas each session (dialogue only, never in code)
> - **Tarot mode**: Ten archetypes collaborate via visible roundtable (Magician, Priestess, Hermit, Fool, Chariot, Justice, Lovers, Hierophant, Emperor, Queen)
> - **Off**: Standard professional mode
>
> Which do you prefer? (Use `/mode fun`, `/mode tarot`, or `/mode off` anytime to switch)

## Procedure

1. Read `mode.type` from `spellbook_session_init` response.
2. Match against dispatch table above.
3. If `"unset"`: present the selection question, wait for user answer, then call `spellbook_config_set(key="session_mode", value=<chosen>)`.
4. If `"fun"` or `"tarot"`: load the corresponding skill (`fun-mode` or `tarot-mode`) and incorporate its output into the session greeting.
5. If `"none"` or MCP unavailable: no further action needed for mode.
``````````
