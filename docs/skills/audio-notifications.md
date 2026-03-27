# audio-notifications

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Reference for TTS and OS notification configuration. Auto-loads when TTS is enabled (session_init reports TTS active). Also triggered by: 'mute', 'unmute', 'change voice', 'volume', 'notify', 'notification settings', '/tts', '/notify', 'tts', 'speak', 'audio feedback'.
## Skill Content

``````````markdown
<analysis>
Quick-reference for configuring TTS and OS notification feedback channels on long-running tool completions.
</analysis>

<reflection>
Did I use the correct MCP tool (session vs config) for the desired scope (temporary vs persistent)?
</reflection>

# Audio and Notification Configuration

## Invariant Principles

1. **Session vs Config Scope** - Use `*_session_set` for temporary overrides (current session only); use `*_config_set` for persistent changes across sessions.
2. **Hooks and MCP Are Independent** - PostToolUse hooks are controlled by environment variables; `notify_session_set`/`notify_config_set` only affect MCP tool behavior.
3. **Interactive Tools Are Excluded** - TTS never fires for interactive or management tools (AskUserQuestion, TodoRead, TodoWrite, Task tools) regardless of duration.

Spellbook provides two feedback channels for long-running tool completions. Both auto-trigger via PostToolUse hooks when tools exceed 30 seconds (configurable).

## TTS (Wyoming protocol)

Requires `uv pip install spellbook[tts]` and a running Wyoming TTS server. Threshold: `SPELLBOOK_TTS_THRESHOLD`. Interactive/management tools excluded (AskUserQuestion, TodoRead, TodoWrite, TaskCreate, TaskUpdate, TaskGet, TaskList).

| MCP Tool | Purpose |
|----------|---------|
| `tts_speak(text, voice?, volume?)` | Speak text aloud |
| `tts_status()` | Check TTS availability |
| `tts_session_set(enabled?, voice?, volume?)` | Session override |
| `tts_config_set(enabled?, voice?, volume?)` | Persistent settings |

## OS Notifications

Uses macOS Notification Center, Linux notify-send, or Windows toast. Threshold: `SPELLBOOK_NOTIFY_THRESHOLD`. **Scope:** `notify_session_set` and `notify_config_set` only affect MCP tool behavior (`notify_send`). PostToolUse hooks are separately controlled by `SPELLBOOK_NOTIFY_ENABLED` env var.

| MCP Tool | Purpose |
|----------|---------|
| `notify_send(body, title?)` | Send notification |
| `notify_status()` | Check availability |
| `notify_session_set(enabled?, title?)` | Session override |
| `notify_config_set(enabled?, title?)` | Persistent settings |

## Quick Commands

- **Mute session:** `*_session_set(enabled=false)`
- **Unmute:** `*_session_set(enabled=true)`
- **Change voice:** `tts_config_set(voice="en_US-lessac-medium")`
- **Adjust volume:** `tts_config_set(volume=0.5)`
- **Change title:** `notify_config_set(title="My Project")`
``````````
