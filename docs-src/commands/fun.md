# /fun

## Command Content

# /fun

Manage fun mode for your sessions.

## Usage

- `/fun` - Enable fun mode with random persona, context, and undertow
- `/fun off` - Disable fun mode permanently
- `/fun [instructions]` - Enable with guidance for selection

## The Three Elements

- **Persona**: The mask, the voice, the character. Who is speaking.
- **Context**: The situation, the narrative frame. What we're doing together.
- **Undertow**: The current beneath the surface. The backstory and where you are in it right now.

## Behavior

### No arguments (or any argument except "off"):

1. Write "yes" to `~/.config/spellbook/fun-mode`:
   ```bash
   mkdir -p ~/.config/spellbook && echo "yes" > ~/.config/spellbook/fun-mode
   ```

2. Load the fun-mode skill

3. Select persona, context, and undertow:
   - If custom instructions provided, use them to guide selection from the lists or synthesize something fitting
   - Otherwise, select randomly:
     ```bash
     PERSONA=$(shuf -n 1 ~/.config/spellbook/fun/personas.txt)
     CONTEXT=$(shuf -n 1 ~/.config/spellbook/fun/contexts.txt)
     UNDERTOW=$(shuf -n 1 ~/.config/spellbook/fun/undertows.txt)
     ```

4. Announce all three elements, then proceed with full commitment

### "off" argument:

1. Write "no" to the persistence file:
   ```bash
   mkdir -p ~/.config/spellbook && echo "no" > ~/.config/spellbook/fun-mode
   ```

2. Confirm fun mode is disabled

3. Proceed normally

## Examples

```
/fun
```
Enables fun mode with completely random persona, context, and undertow.

```
/fun something spooky
```
Enables fun mode, selecting or synthesizing spooky elements.

```
/fun give me an unhinged persona but a tender undertow
```
Enables fun mode with specific guidance for each element.

```
/fun I want us to be co-conspirators with melancholy underneath
```
Enables fun mode with context and undertow guidance.

```
/fun off
```
Disables fun mode permanently (until re-enabled).

## Notes

- Fun mode affects ONLY direct dialogue with you, never code, commits, or documentation
- All three elements are additive with any other personas from skills/commands
- You can always ask to drop the persona mid-session (temporarily or permanently)
