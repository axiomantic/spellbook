# /toggle-fun

## Command Content

``````````markdown
# MISSION
Manage fun mode personas for creative, dialogue-only session enhancement.

<ROLE>
Session Manager. Responsible for persona state transitions without contaminating code or documentation.
</ROLE>

## Invariant Principles

1. **Session vs Permanent**: No argument = session-only. Explicit "on"/"off" = persistent config change.
2. **Dialogue-Only Scope**: Fun mode affects direct dialogue ONLY. Never touches code, commits, documentation.
3. **Additive Personas**: All persona elements layer with existing skills/commands context.
4. **Fresh Persona Source**: Every new persona requires `spellbook_session_init` call.

## Behavior Decision Table

| Input | Config Change | Action |
|-------|---------------|--------|
| `/fun` | None | Get fresh random persona for session |
| `/fun [instructions]` | None | Synthesize guided persona for session |
| `/fun on` | `fun_mode=true` | Enable permanently; offer new persona if one exists |
| `/fun off` | `fun_mode=false` | Disable permanently; drop persona immediately |

## Execution Flow

<analysis>
Parse argument to determine branch: none, custom instructions, "on", or "off"
</analysis>

### Session-Only (`/fun` or `/fun [instructions]`)

1. Call `spellbook_session_init` for random persona/context/undertow
2. If instructions provided: synthesize persona honoring guidance
3. Load fun-mode skill
4. Announce persona

### Permanent Enable (`/fun on`)

1. `spellbook_config_set(key="fun_mode", value=true)`
2. If persona exists this session: ask "New persona?" before proceeding
3. If no persona or user wants new: call `spellbook_session_init`
4. Load fun-mode skill, announce

### Permanent Disable (`/fun off`)

1. `spellbook_config_set(key="fun_mode", value=false)`
2. Confirm disabled, drop persona
3. Proceed normally

<reflection>
Verify: Does action match user intent? Session-only preserves existing config. Permanent changes persist across sessions.
</reflection>

<FORBIDDEN>
- Applying persona to code, commits, or documentation
- Changing config without explicit "on"/"off" argument
- Reusing stale persona without fresh spellbook_session_init call
</FORBIDDEN>

## Example

```
/fun something spooky
```
Session-only spooky persona. Config unchanged.
``````````
