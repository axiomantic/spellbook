---
description: "Toggle fun mode or get a new random persona for creative sessions"
---

# /fun

Manage fun mode for your sessions.

## Usage

- `/fun` - Get a new random persona for this session only
- `/fun [instructions]` - Get a new persona with custom guidance (session only)
- `/fun on` - Enable fun mode permanently (asks about new persona if already enabled)
- `/fun off` - Disable fun mode permanently

## Behavior

### No arguments (`/fun`):

1. Call `spellbook_session_init` to get new random persona/context/undertow
2. Load the fun-mode skill
3. Announce the new persona
4. **Does NOT modify the fun_mode setting** - this is session-only

### With instructions (`/fun [instructions]`):

1. Call `spellbook_session_init` to get random selections as a starting point
2. Use the instructions to guide selection or synthesis:
   - If instructions match a vibe, select from the lists accordingly
   - Otherwise, synthesize something that honors the instruction
3. Load the fun-mode skill
4. Announce the persona
5. **Does NOT modify the fun_mode setting** - this is session-only

### "on" argument (`/fun on`):

1. Call `spellbook_config_set(key="fun_mode", value=true)`
2. Check if already have a persona this session:
   - If yes: Ask user "Would you like a new persona?"
   - If no or user wants new: Call `spellbook_session_init` for random selections
3. Load fun-mode skill and announce

### "off" argument (`/fun off`):

1. Call `spellbook_config_set(key="fun_mode", value=false)`
2. Confirm fun mode is disabled (drop persona immediately)
3. Proceed normally

## Examples

```
/fun
```
Get a fresh random persona for this session. Does not change your fun_mode setting.

```
/fun something spooky
```
Get a spooky persona for this session. Does not change your fun_mode setting.

```
/fun give me an unhinged persona but a tender undertow
```
Custom guidance for each element. Session only.

```
/fun on
```
Enable fun mode permanently. Future sessions will start with random personas.

```
/fun off
```
Disable fun mode permanently.

## Notes

- Fun mode affects ONLY direct dialogue with you, never code, commits, or documentation
- All three elements are additive with any other personas from skills/commands
- `/fun` and `/fun [instructions]` are temporary; `/fun on` and `/fun off` are permanent
