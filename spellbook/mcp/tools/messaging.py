"""MCP tools for cross-session messaging."""

__all__ = [
    "messaging_register",
    "messaging_unregister",
    "messaging_send",
    "messaging_broadcast",
    "messaging_reply",
    "messaging_poll",
    "messaging_list_sessions",
    "messaging_stats",
]

import json
import logging
import re
from typing import Optional

from fastmcp import Context
from fastmcp.server.events import EventEffect

from spellbook.mcp.server import mcp
from spellbook.messaging.bus import MAX_ALIAS_LENGTH, message_bus
from spellbook.sessions.injection import inject_recovery_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event topic declarations (MCP events integration)
# ---------------------------------------------------------------------------
#
# The ``{session_id}`` segment in these topic patterns is magic: fastmcp
# enforces that only the session whose ``_fastmcp_event_session_id`` matches
# the substituted UUID may subscribe. Subscribers must pass their own
# ``client.session_id`` (exposed on the client after initialize) in the topic
# pattern they subscribe to. Human-readable aliases such as
# ``"orchestrator-main"`` will never authorize because they cannot match a
# UUID. Callers route from alias to UUID via the MessageBus resolver
# (see ``messaging_send`` below).

mcp.declare_event(
    "spellbook/sessions/{session_id}/messages",
    description=(
        "Cross-session direct messages. The {session_id} segment is magic: "
        "only the fastmcp session whose UUID matches may subscribe, so a "
        "client must substitute its own client.session_id when subscribing."
    ),
)
mcp.declare_event(
    "spellbook/sessions/{session_id}/build/status",
    description=(
        "Build status for this session's work. The {session_id} segment is "
        "magic: only the fastmcp session whose UUID matches may subscribe, "
        "so a client must substitute its own client.session_id when "
        "subscribing."
    ),
    retained=True,
)

_ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_PAYLOAD_MAX_BYTES = 65536  # 64KB
_TTL_MIN = 1
_TTL_MAX = 300
_POLL_MAX = 50


def _validate_alias(alias: str) -> Optional[dict]:
    """Return error dict if alias is invalid, else None."""
    if not alias or len(alias) > MAX_ALIAS_LENGTH or not _ALIAS_PATTERN.match(alias):
        return {
            "ok": False,
            "error": "invalid_alias",
            "detail": f"Alias must be 1-{MAX_ALIAS_LENGTH} chars, alphanumeric/hyphens/underscores only.",
        }
    return None


def _parse_payload(payload_str: str) -> tuple[Optional[dict], Optional[dict]]:
    """Parse JSON payload string. Returns (parsed_dict, error_dict)."""
    try:
        if len(payload_str.encode("utf-8")) > _PAYLOAD_MAX_BYTES:
            return None, {
                "ok": False,
                "error": "payload_too_large",
                "detail": f"Payload exceeds {_PAYLOAD_MAX_BYTES} bytes.",
            }
        parsed = json.loads(payload_str)
        if not isinstance(parsed, dict):
            return None, {
                "ok": False,
                "error": "invalid_payload_json",
                "detail": "Payload must be a JSON object.",
            }
        return parsed, None
    except (json.JSONDecodeError, ValueError) as e:
        return None, {
            "ok": False,
            "error": "invalid_payload_json",
            "detail": str(e),
        }


def _extract_fastmcp_session_id(ctx: Optional[Context]) -> Optional[str]:
    """Return the caller's fastmcp event session UUID, or None.

    The event session id lives on the low-level ServerSession as
    ``_fastmcp_event_session_id``. This is distinct from ``ctx.session_id``
    (the StreamableHTTP state prefix used for Redis-style state).
    """
    if ctx is None:
        return None
    try:
        request_context = ctx.request_context
    except (RuntimeError, AttributeError):
        return None
    if request_context is None:
        return None
    session = getattr(request_context, "session", None)
    if session is None:
        return None
    sid = getattr(session, "_fastmcp_event_session_id", None)
    if isinstance(sid, str) and sid:
        return sid
    return None


@mcp.tool()
@inject_recovery_context
async def messaging_register(
    alias: str,
    enable_sse: bool = True,
    force: bool = False,
    session_id: str = "",
    ctx: Optional[Context] = None,
) -> dict:
    """Register this session for cross-session messaging.

    Claim an alias for this session. Aliases are first-come-first-served.
    Must register before sending or receiving messages.

    Args:
        alias: Unique name for this session (e.g., "orchestrator-main", "worker-auth").
              Letters, numbers, hyphens, underscores only. Max 64 chars.
        enable_sse: If True (default), spawn a MessageBridge that consumes the
                   SSE stream and writes to the session's inbox directory for
                   hook-based delivery.
        force: If True, replace existing registration for this alias. Old
              queue is discarded (disconnect sentinel sent first for SSE
              cleanup) and a warning is logged.
        session_id: Caller's session identifier. Used to write a marker file
                   so the hook only drains inboxes belonging to this session.

    Returns:
        {"ok": true, "alias": str, "registered_at": str} on success
        {"ok": false, "error": str} if alias taken (and force=False) or invalid
    """
    err = _validate_alias(alias)
    if err:
        return err
    # Capture the caller's fastmcp event session UUID so cross-session event
    # topic substitution (spellbook/sessions/{session_id}/messages) can route
    # by alias. See the topic docstring at the top of this module.
    fastmcp_session_id = _extract_fastmcp_session_id(ctx)
    try:
        reg = await message_bus.register(
            alias,
            enable_sse=enable_sse,
            force=force,
            session_id=session_id,
            fastmcp_session_id=fastmcp_session_id,
        )
        return {
            "ok": True,
            "alias": reg.alias,
            "registered_at": reg.registered_at,
            "fastmcp_session_id": reg.fastmcp_session_id,
        }
    except ValueError as e:
        return {"ok": False, "error": "alias_already_registered", "alias": alias, "detail": str(e)}


@mcp.tool()
@inject_recovery_context
async def messaging_unregister(alias: str) -> dict:
    """Unregister this session from messaging.

    Removes the session from the registry and discards any queued messages.

    Args:
        alias: The alias to unregister

    Returns:
        {"ok": true} if removed
        {"ok": false, "error": "not_found"} if alias not registered
    """
    removed = await message_bus.unregister(alias)
    if removed:
        return {"ok": True}
    return {"ok": False, "error": "not_found"}


@mcp.tool()
@inject_recovery_context
async def messaging_send(
    sender: str,
    recipient: str,
    payload: str,
    correlation_id: Optional[str] = None,
    ttl: int = 60,
) -> dict:
    """Send a direct message to another session.

    Delivers immediately to the recipient's queue. Fails if recipient is
    not registered or their queue is full.

    Args:
        sender: Your registered alias
        recipient: Target session alias
        payload: JSON string with message content (will be parsed)
        correlation_id: Optional ID to track request/reply pairs. Recipient
                       can use messaging_reply with this ID.
        ttl: Seconds before correlation expires (default 60, max 300)

    Returns:
        {"ok": true, "message_id": str} on success
        {"ok": false, "error": str} on failure
    """
    parsed, err = _parse_payload(payload)
    if err:
        return err

    # Clamp TTL
    ttl = max(_TTL_MIN, min(ttl, _TTL_MAX))

    # Validate correlation_id length
    if correlation_id and len(correlation_id) > 128:
        return {"ok": False, "error": "correlation_id_too_long", "detail": "Max 128 chars."}

    result = await message_bus.send(
        sender=sender,
        recipient=recipient,
        payload=parsed,
        correlation_id=correlation_id,
        ttl=ttl,
    )

    # Emit MCP event alongside queue-based delivery for events-capable clients.
    # The {session_id} segment is magic: fastmcp authorizes subscriptions by
    # matching the caller's _fastmcp_event_session_id against the substituted
    # UUID. The recipient alias is a human-readable name that cannot match
    # that authorization check, so we resolve it to the recipient's UUID
    # first. If the recipient never registered via MCP (e.g., legacy direct
    # bus caller), the UUID mapping is absent and we skip event emission;
    # queue-based delivery above still happened.
    if result.get("ok"):
        recipient_uuid = message_bus.resolve_alias_to_session_id(recipient)
        if recipient_uuid:
            try:
                await mcp.emit_event(
                    topic=f"spellbook/sessions/{recipient_uuid}/messages",
                    payload={
                        "message_id": result.get("message_id"),
                        "sender": sender,
                        "recipient": recipient,
                        "payload": parsed,
                        "correlation_id": correlation_id,
                    },
                    source="spellbook/messaging",
                    correlation_id=correlation_id,
                    requested_effects=[
                        EventEffect(type="inject_context", priority="high"),
                    ],
                    target_session_ids=[recipient_uuid],
                )
            except Exception:
                logger.warning("Failed to emit event for message delivery", exc_info=True)
        else:
            logger.debug(
                "recipient %s has no session_id; skipping event emission (queue-only)",
                recipient,
            )

    return result


@mcp.tool()
@inject_recovery_context
async def messaging_broadcast(
    sender: str,
    payload: str,
    include_self: bool = False,
) -> dict:
    """Broadcast a message to all registered sessions.

    Useful for discovery ("who is working on X?") and announcements.

    Args:
        sender: Your registered alias
        payload: JSON string with message content
        include_self: Whether to include sender in broadcast (default false)

    Returns:
        {"ok": true, "delivered_count": int, "failed_count": int,
         "delivered_aliases": list[str], "errors": list|null}
    """
    parsed, err = _parse_payload(payload)
    if err:
        return err
    result = await message_bus.broadcast(
        sender=sender,
        payload=parsed,
        exclude_sender=not include_self,
    )

    # Emit events for each recipient with a known session UUID.
    # Use delivered_aliases from broadcast() result (NOT a separate
    # list_sessions() call) to avoid TOCTOU race conditions.
    # Fire-and-forget: one failure must not block other recipients.
    if result.get("ok"):
        for alias in result.get("delivered_aliases", []):
            uuid = message_bus.resolve_alias_to_session_id(alias)
            if not uuid:
                continue
            try:
                await mcp.emit_event(
                    topic=f"spellbook/sessions/{uuid}/messages",
                    payload={
                        "sender": sender,
                        "recipient": "*",
                        "payload": parsed,
                        "broadcast": True,
                    },
                    source="spellbook/messaging",
                    requested_effects=[
                        EventEffect(type="inject_context", priority="normal"),
                    ],
                    target_session_ids=[uuid],
                )
            except Exception:
                logger.warning(
                    "Failed to emit broadcast event for recipient %s",
                    alias,
                    exc_info=True,
                )

    return result


@mcp.tool()
@inject_recovery_context
async def messaging_reply(
    sender: str,
    correlation_id: str,
    payload: str,
) -> dict:
    """Reply to a message using its correlation ID.

    Routes the reply back to the original sender. Fails if the correlation
    has expired (default 60s TTL) or the original sender disconnected.

    Args:
        sender: Your registered alias (the replier)
        correlation_id: The correlation_id from the received message
        payload: JSON string with reply content

    Returns:
        {"ok": true, "message_id": str, "recipient": str} on success
        {"ok": false, "error": str} if expired or sender gone
    """
    parsed, err = _parse_payload(payload)
    if err:
        return err
    result = await message_bus.reply(
        sender=sender,
        correlation_id=correlation_id,
        payload=parsed,
    )

    # Emit event to the reply recipient (the original sender of the
    # correlated message). Guard on result having recipient field.
    if result.get("ok"):
        recipient_alias = result.get("recipient")
        if recipient_alias:
            recipient_uuid = message_bus.resolve_alias_to_session_id(recipient_alias)
            if recipient_uuid:
                try:
                    await mcp.emit_event(
                        topic=f"spellbook/sessions/{recipient_uuid}/messages",
                        payload={
                            "message_id": result.get("message_id"),
                            "sender": sender,
                            "recipient": recipient_alias,
                            "payload": parsed,
                            "correlation_id": correlation_id,
                            "is_reply": True,
                        },
                        source="spellbook/messaging",
                        correlation_id=correlation_id,
                        requested_effects=[
                            EventEffect(type="inject_context", priority="high"),
                        ],
                        target_session_ids=[recipient_uuid],
                    )
                except Exception:
                    logger.warning(
                        "Failed to emit event for reply delivery",
                        exc_info=True,
                    )

    return result


@mcp.tool()
@inject_recovery_context
async def messaging_poll(
    alias: str,
    max_messages: int = 10,
) -> dict:
    """Poll for pending messages (fallback when SSE unavailable).

    Drains up to max_messages from your queue. Messages are removed
    once polled (at-most-once delivery).

    Args:
        alias: Your registered alias
        max_messages: Maximum messages to retrieve (1-50, default 10)

    Returns:
        {"ok": true, "messages": list[MessageEnvelope], "remaining": int}
    """
    max_messages = max(1, min(max_messages, _POLL_MAX))
    messages, remaining = await message_bus.poll(alias, max_messages=max_messages)
    return {"ok": True, "messages": messages, "remaining": remaining}


@mcp.tool()
@inject_recovery_context
async def messaging_list_sessions() -> dict:
    """List all registered messaging sessions.

    Returns:
        {"ok": true, "sessions": [{"alias": str, "registered_at": str}, ...]}
    """
    sessions = await message_bus.list_sessions()
    return {"ok": True, "sessions": sessions}


@mcp.tool()
@inject_recovery_context
async def messaging_stats() -> dict:
    """Get messaging bus statistics.

    Returns:
        {"ok": true, "sessions_registered": int, "pending_correlations": int,
         "total_sent": int, "total_delivered": int, "total_errors": int}
    """
    stats = await message_bus.stats()
    return {"ok": True, **stats}
