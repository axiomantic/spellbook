# MCP Events

The Spellbook MCP server publishes asynchronous events to MCP clients that declare support for the `events` capability. Events are pushed via `events/emit` notifications outside the normal request/response cycle, so clients can react to cross-session activity without polling.

## Topics

The server publishes these topics:

| Topic | Retained | Description |
|-------|----------|-------------|
| `spellbook/sessions/{session_id}/messages` | No | Cross-session messages delivered to a registered session |
| `spellbook/sessions/{session_id}/build/status` | Yes | Build status updates for the work happening in this session |

The `{session_id}` segment is the recipient session's registered messaging alias. Clients subscribe with MQTT-style wildcards (e.g., `spellbook/sessions/+/messages` to receive messages for any session, or `spellbook/sessions/my-alias/messages` for a specific one).

Retained topics deliver the last published event to new subscribers immediately on subscribe, so clients that connect mid-stream still see the current build status.

## Messaging integration

When a session calls `messaging_send`, the spellbook server delivers the message through two channels in parallel:

1. The recipient's in-process message queue (the existing path used by `messaging_poll` and the SSE bridge).
2. An `events/emit` notification on `spellbook/sessions/{recipient}/messages`, for clients that have subscribed via the events capability.

The event payload mirrors the queued message envelope:

```json
{
  "message_id": "msg_...",
  "sender": "orchestrator-main",
  "recipient": "worker-auth",
  "payload": { /* arbitrary user JSON */ },
  "correlation_id": "req-123"
}
```

Each message event is emitted with a `requested_effects` hint of `inject_context` at `high` priority, suggesting that capable clients inject the message into the recipient session's context on its next turn rather than waiting for an explicit poll. Clients are free to honor or ignore this hint based on their own permission model. See [OpenCode's MCP events permissions](https://opencode.ai/docs/mcp-servers#events) for an example of how a client gates these effects.

If the event emission fails (no subscribed clients, transport error, etc.), the queue-based delivery still succeeds. The two paths are independent.

## Source field

All events emitted by the messaging integration include `source: "spellbook/messaging"`, which lets clients route or filter events by the originating subsystem.
