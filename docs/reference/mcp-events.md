# MCP Events

The Spellbook MCP server publishes asynchronous events to MCP clients that declare support for the `events` capability. Events are pushed via `events/emit` notifications outside the normal request/response cycle, so clients can react to cross-agent activity without polling. Spellbook follows [MCP Events Spec v2](https://github.com/axiomantic/python-sdk/blob/mcp-events/README.md).

## Topics

The server publishes these topics:

| Topic | Kind | Retained | Description |
|-------|------|----------|-------------|
| `agents/{agent_id}/messages` | `content` | No | Cross-agent direct messages and replies delivered to a registered agent |
| `agents/{agent_id}/build/status` | `content` | Yes | Build status updates for the work owned by this agent |

Retained topics deliver the last published event to new subscribers immediately on subscribe, so clients that connect mid-stream still see the current build status.

Each topic declaration carries the spec v2 metadata: `kind`, `description`, `suggestedHandle`, and (for `messages`) a JSON Schema for the payload.

## Identity model

Under spec v2, three distinct identities exist and must not be conflated:

1. **MCP transport session**: the connection-level UUID assigned by the MCP server when a client connects. Ephemeral. Used for transport-level authorization and for spellbook's `target_session_ids` defense-in-depth filter on `emit_event` calls.
2. **Agent**: the application-level identity of the entity doing work (e.g. an opencode chat session). Stable across reconnects. This is the identifier substituted into `{agent_id}` topic patterns.
3. **Messaging alias**: the human-readable name registered for cross-agent messaging (e.g. `orchestrator-main`, `worker-auth`). Maps to an `agent_id`.

`{agent_id}` is a CLIENT-SIDE concept. The client substitutes its own agent id when subscribing to a topic like `agents/<my-agent-id>/messages`. The server receives a fully-resolved topic string and does not need to understand agent semantics.

## Alias-to-agent_id mapping

`messaging_register(alias=..., agent_id=...)` stores an `alias <-> agent_id` mapping alongside the alias claim. Clients pass their own `agent_id` explicitly at registration time. When a sender calls `messaging_send(recipient=<alias>)`, the server resolves the alias to the recipient's `agent_id` and emits the event on `agents/<agent_id>/messages`.

This means:
- **Senders** use human-readable aliases (e.g., `worker-auth`).
- **Recipients** subscribe to their own `agents/<my-agent-id>/messages` topic.
- The alias-to-agent_id lookup is transparent to both sides.

`messaging_register` also captures the MCP transport session UUID from the tool Context and stores it as `fastmcp_session_id` for defense-in-depth routing (see below). The register response returns both identifiers.

## Dual-path delivery

Every `messaging_send` delivers through two independent paths:

1. **Queue path**: `bus.send()` enqueues the message. The recipient retrieves it via `messaging_poll` (or the SSE bridge). This is the legacy path and always fires.
2. **Event path**: `emit_event(topic="agents/<agent_id>/messages", priority="high", target_session_ids=[transport_uuid])` pushes the message reactively to subscribed clients. This is the preferred path for low-latency delivery.

Both paths fire on every send (when the recipient has an events-capable session with a registered `agent_id`). If the event emission fails (no subscribers, transport error), the queue path still succeeds. The two paths are independent.

`target_session_ids=[recipient_transport_uuid]` is passed alongside topic-based routing as defense-in-depth. Even if a topic subscription leaked to the wrong agent inside a multi-agent client, `target_session_ids` provides a second gate ensuring only the intended MCP transport session receives the event.

## Priority

Each event is emitted with a top-level `priority`:

| Tool | Priority | Rationale |
|------|----------|-----------|
| `messaging_send` | `high` | Direct messages deserve prompt delivery. |
| `messaging_reply` | `high` | Replies are latency-sensitive. |
| `messaging_broadcast` | `normal` | Broadcasts are announcements, not requests. |

Priority controls WHEN an event is processed, not how. The client always has final say on how events are handled (see `suggestedHandle` and client configuration in the spec).

## Event payload

The event payload conforms to the JSON Schema declared alongside the `agents/{agent_id}/messages` topic:

```json
{
  "message_id": "msg_...",
  "sender": "orchestrator-main",
  "recipient": "worker-auth",
  "payload": { /* arbitrary user JSON */ },
  "correlation_id": "req-123"
}
```

Note: `correlation_id` is NOT a wire-level field under spec v2. Applications that need request/reply correlation embed it in the event payload, as shown above.

## Source field

All events emitted by the messaging integration include `source: "spellbook/messaging"`, which lets clients route or filter events by the originating subsystem.

## Transport requirement

MCP events require a stateful transport. Spellbook runs streamable HTTP in stateful mode (`stateless_http=False`) so persistent SSE streams can carry server-initiated event notifications.
