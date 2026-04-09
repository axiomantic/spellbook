# MCP Events

The Spellbook MCP server publishes asynchronous events to MCP clients that declare support for the `events` capability. Events are pushed via `events/emit` notifications outside the normal request/response cycle, so clients can react to cross-session activity without polling.

## Topics

The server publishes these topics:

| Topic | Retained | Description |
|-------|----------|-------------|
| `spellbook/sessions/{session_id}/messages` | No | Cross-session messages delivered to a registered session |
| `spellbook/sessions/{session_id}/build/status` | Yes | Build status updates for the work happening in this session |

Retained topics deliver the last published event to new subscribers immediately on subscribe, so clients that connect mid-stream still see the current build status.

## Session ID scoping

`{session_id}` in topic patterns is a magic placeholder enforced by FastMCP. The server only allows a session to subscribe to topics containing its own UUID. Any subscription attempt that places a wildcard (`+` or `#`) in the session ID segment is rejected with `permission_denied`. This provides implicit authorization: no manual auth check is needed because sessions can only listen on their own topics.

Clients discover their UUID via `client.session_id` (assigned by FastMCP at connection time) and subscribe to `spellbook/sessions/<their-uuid>/messages`.

## Alias-to-UUID mapping

`messaging_register(alias=...)` captures the calling session's FastMCP UUID and stores it alongside the human-readable alias. When a sender calls `messaging_send(recipient=<alias>)`, the server resolves the alias to the recipient's UUID and emits the event on `spellbook/sessions/<uuid>/messages`.

This means:
- **Senders** use human-readable aliases (e.g., `worker-auth`).
- **Recipients** subscribe to their own UUID-based topic (discovered from `client.session_id`).
- The alias-to-UUID lookup is transparent to both sides.

## Dual-path delivery

Every `messaging_send` delivers through two independent paths:

1. **Queue path**: `bus.send()` enqueues the message. The recipient retrieves it via `messaging_poll` (or the SSE bridge). This is the legacy path and always fires.
2. **Event path**: `emit_event(topic=spellbook/sessions/<uuid>/messages, target_session_ids=[uuid])` pushes the message reactively to subscribed clients. This is the preferred path for low-latency delivery.

Both paths fire on every send (when the recipient has an events-capable session). If the event emission fails (no subscribers, transport error), the queue path still succeeds. The two paths are independent.

`target_session_ids=[recipient_uuid]` is passed alongside topic-based routing as defense-in-depth. Even if a topic subscription leaked to the wrong session (which the session-scoped enforcement already prevents), `target_session_ids` provides a second gate ensuring only the intended recipient receives the event.

## Event payload

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

## Source field

All events emitted by the messaging integration include `source: "spellbook/messaging"`, which lets clients route or filter events by the originating subsystem.
