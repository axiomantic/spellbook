# Session Context

!!! info "Optional module"
    The installer offers this module pre-checked. Config key: `rules.module.session`.

Notification configuration, the project-knowledge offer protocol, and the focus-stint stack you own across a session.

**Why keep it:** Keeps stints, OS notifications, and AGENTS.md offers working across every session.

**If you decline:** The agent will not offer to create project knowledge files, will not track a focus stint stack, and will not configure OS notifications.

**Related artifacts:**

- `skills/audio-notifications`
- `skills/session-resume`

## Rule Content

``````````markdown
## Notification Configuration

Load `audio-notifications` skill for OS notification configuration, MCP tool tables, and quick commands.

## Project Knowledge (AGENTS.md)

AGENTS.md is the canonical location for project-specific AI assistant knowledge. Prioritize build/test/run commands, architecture overview, key conventions, and gotchas.

This is the project-knowledge offer protocol referenced by the session-start checks.
Apply it after greeting, once the session-start read of `AGENTS.md` has happened:

**File exists but is thin or empty:** Offer to flesh it out.
**Offer to create** (if not exists): "This project doesn't have an AGENTS.md. Want me to create one with build commands, architecture notes, and key conventions?"
**User declines:** Proceed without. Do not ask again this session.
**Subdirectory AGENTS.md:** For modules with distinct conventions, create `<subdir>/AGENTS.md`.

## Focus Tracking (Stints)

Spellbook tracks your focus context via a stint stack. You own this state.

**When to push:** Starting a distinct work context (new feature, debugging session, code review).
**When to pop:** Completing or abandoning a work context.
**When to replace:** Correcting a stale or wrong stack.

Tools: `stint_push`, `stint_pop`, `stint_check`, `stint_replace`

Keep the stack shallow (2-3 typical, max 6). An empty stack is fine.
The system will nudge you once if your stack is empty, and warn about stale entries (>4h old).
``````````
