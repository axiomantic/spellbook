# audio-notifications

**Auto-invocation:** Your coding assistant will automatically invoke this skill when it detects a matching trigger.

> Reference for OS notification configuration. Auto-loads when notifications are enabled (session_init reports notifications active). Also triggered by: 'mute', 'unmute', 'notify', 'notification settings', '/notify', 'notification', 'audio feedback'.
## Skill Content

``````````markdown
<analysis>
Quick-reference for configuring OS notification feedback on long-running tool completions.
</analysis>

<reflection>
Did I use the correct MCP tool (session vs config) for the desired scope (temporary vs persistent)?
</reflection>

# Notification Configuration

## Invariant Principles

1. **Session vs Config Scope** - Use `notify_session_set` for temporary overrides (current session only); use `notify_config_set` for persistent changes across sessions.
2. **Hooks and MCP Are Independent** - PostToolUse hooks are controlled by environment variables; `notify_session_set`/`notify_config_set` only affect MCP tool behavior.
3. **Interactive Tools Are Excluded** - Notifications never fire for interactive or management tools (AskUserQuestion, TodoRead, TodoWrite, Task tools) regardless of duration.

Spellbook provides native OS notifications on long-running tool completions. They auto-trigger via PostToolUse hooks when tools exceed 30 seconds (configurable).

## OS Notifications

Uses macOS Notification Center, Linux notify-send, or Windows toast. Threshold: `SPELLBOOK_NOTIFY_THRESHOLD`. **Scope:** `notify_session_set` and `notify_config_set` only affect MCP tool behavior (`notify_send`). PostToolUse hooks are separately controlled by `SPELLBOOK_NOTIFY_ENABLED` env var.

| MCP Tool | Purpose |
|----------|---------|
| `notify_send(body, title?)` | Send notification |
| `notify_status()` | Check availability |
| `notify_session_set(enabled?, title?)` | Session override |
| `notify_config_set(enabled?, title?)` | Persistent settings |

## Quick Commands

- **Mute session:** `notify_session_set(enabled=false)`
- **Unmute:** `notify_session_set(enabled=true)`
- **Change title:** `notify_config_set(title="My Project")`
``````````
