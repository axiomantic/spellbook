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

import asyncio
import inspect
import json
import logging
import re
from typing import Any, Literal, Optional

MessagePriority = Literal["urgent", "high", "normal", "low"]

from fastmcp import Context

from spellbook.mcp.server import mcp
from spellbook.messaging.bus import MAX_ALIAS_LENGTH, message_bus
from spellbook.sessions.injection import inject_recovery_context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event topic declarations (MCP Events Spec v2)
# ---------------------------------------------------------------------------
#
# Under MCP Events Spec v2, topics use ``{agent_id}`` as the application-level
# identity placeholder. ``{agent_id}`` is a CLIENT-SIDE concept: the client
# substitutes its own agent id (e.g. the opencode session id) when subscribing.
# Servers receive fully-resolved topic strings. Spellbook maintains an
# ``alias <-> agent_id`` mapping populated by ``messaging_register`` and uses
# it to resolve the correct concrete topic for a given recipient alias before
# emitting an event.
#
# Topic declarations include ``kind`` and, where meaningful, ``schema`` and a
# ``suggestedHandle`` hint.

# ---------------------------------------------------------------------------
# FastMCP API compatibility shim
# ---------------------------------------------------------------------------
#
# MCP Events Spec v2 replaced the fastmcp ``requested_effects`` + embedded
# priority design with a top-level ``priority`` field, and added ``kind`` /
# ``suggestedHandle`` to topic declarations. The installed fastmcp version may
# pre-date these kwargs, so we feature-detect and only forward the new kwargs
# when supported. Once fastmcp is fully aligned with v2, the legacy branches
# become dead code and can be removed.

_EMIT_PARAMS = set(inspect.signature(mcp.emit_event).parameters.keys())
_DECLARE_PARAMS = set(inspect.signature(mcp.declare_event).parameters.keys())
_EMIT_SUPPORTS_PRIORITY = "priority" in _EMIT_PARAMS
_EMIT_SUPPORTS_REQUESTED_EFFECTS = "requested_effects" in _EMIT_PARAMS
_EMIT_SUPPORTS_CORRELATION_ID = "correlation_id" in _EMIT_PARAMS
_DECLARE_SUPPORTS_KIND = "kind" in _DECLARE_PARAMS
_DECLARE_SUPPORTS_SUGGESTED_HANDLE = "suggested_handle" in _DECLARE_PARAMS

# Message payload schema (per MCP Events Spec v2 example). Declared once and
# reused across messages/replies since they share the same shape.
_MESSAGE_PAYLOAD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sender": {
            "type": "string",
            "description": "Alias of the sending agent.",
        },
        "recipient": {
            "type": "string",
            "description": "Alias of the target agent.",
        },
        "message_id": {"type": "string", "description": "Unique message ID."},
        "payload": {
            "type": "object",
            "description": "Application-defined message content.",
        },
    },
    "required": ["sender", "recipient", "message_id", "payload"],
}


def _declare_event_v2(
    pattern: str,
    *,
    description: str,
    kind: str,
    retained: bool = False,
    schema: Optional[dict[str, Any]] = None,
    suggested_handle: Optional[str] = None,
) -> None:
    """Declare an event topic using MCP Events Spec v2 fields.

    Forwards ``kind``, ``schema``, and ``suggestedHandle`` when the installed
    fastmcp supports them. Older fastmcp versions transparently skip the new
    fields so spellbook can land ahead of a fastmcp release.
    """
    kwargs: dict[str, Any] = {"description": description, "retained": retained}
    if schema is not None:
        kwargs["schema"] = schema
    if _DECLARE_SUPPORTS_KIND:
        kwargs["kind"] = kind
    if suggested_handle is not None and _DECLARE_SUPPORTS_SUGGESTED_HANDLE:
        kwargs["suggested_handle"] = suggested_handle
    mcp.declare_event(pattern, **kwargs)


_declare_event_v2(
    "agents/{agent_id}/messages",
    description=(
        "Cross-agent direct messages and replies. The {agent_id} segment "
        "is the application-level identity (e.g. the opencode session id) "
        "that the client substitutes when subscribing. Content-kind, high "
        "priority by default."
    ),
    kind="content",
    schema=_MESSAGE_PAYLOAD_SCHEMA,
    suggested_handle="inject",
)

_declare_event_v2(
    "agents/{agent_id}/build/status",
    description=(
        "Build status for work owned by this agent. Retained so new "
        "subscribers receive the last known value on subscribe."
    ),
    kind="content",
    retained=True,
    suggested_handle="inject",
)


async def _emit_event_v2(
    *,
    topic: str,
    payload: Any,
    source: str,
    priority: str,
    target_session_ids: Optional[list[str]] = None,
) -> None:
    """Emit an event using MCP Events Spec v2 wire fields.

    - ``priority`` is forwarded as a top-level kwarg when supported.
    - Legacy fastmcp versions that still require ``requested_effects`` get
      a best-effort translation so spellbook can land ahead of a fastmcp
      release without breaking event delivery.
    - ``correlation_id`` is NOT a wire field under v2; applications that
      need correlation embed it in the payload.
    """
    kwargs: dict[str, Any] = {
        "topic": topic,
        "payload": payload,
        "source": source,
    }
    if target_session_ids is not None:
        kwargs["target_session_ids"] = target_session_ids

    if _EMIT_SUPPORTS_PRIORITY:
        kwargs["priority"] = priority
    elif _EMIT_SUPPORTS_REQUESTED_EFFECTS:
        # Transitional compatibility with pre-v2 fastmcp: synthesize a
        # requested_effects entry so events continue to flow with the
        # correct priority until fastmcp exposes a top-level field.
        try:
            from fastmcp.server.events import EventEffect  # type: ignore

            kwargs["requested_effects"] = [
                EventEffect(type="inject_context", priority=priority),
            ]
        except ImportError:
            logger.debug("fastmcp missing both priority and EventEffect; emitting without priority")

    await mcp.emit_event(**kwargs)


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
    """Return the caller's MCP transport session UUID, or None.

    The transport session id lives on the low-level ServerSession as
    ``_fastmcp_event_session_id``. This is distinct from ``ctx.session_id``
    (the StreamableHTTP state prefix) and from ``agent_id`` (the
    application-level identity supplied by the client).
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
    agent_id: str = "",
    enable_sse: bool = True,
    force: bool = False,
    session_id: str = "",
    ctx: Optional[Context] = None,
) -> dict:
    """Register this session for cross-session messaging.

    Claim an alias for this session. Aliases are first-come-first-served.
    You MUST register before sending or receiving messages.

    Typical LLM usage is a single argument::

        messaging_register(alias="session-b")

    or, if re-registering after a previous session left a stale entry::

        messaging_register(alias="session-b", force=True)

    You do NOT need to pass ``agent_id`` or ``session_id`` manually. The
    MCP client (for example the opencode harness) auto-injects those so
    the server can resolve your application-level identity and route
    topic-based events (``agents/{agent_id}/messages``) to your transport.
    Passing them explicitly is only useful if you are writing a custom
    client that does not auto-inject.

    Args:
        alias: Unique name for this session (e.g. ``"orchestrator-main"``,
              ``"worker-auth"``). Letters, numbers, hyphens, underscores
              only. Max 64 chars.
        agent_id: Application-level agent identifier (MCP Events Spec v2).
                 Normally auto-injected by the client; leave unset unless
                 your client does not inject. Used to parameterize event
                 topics like ``agents/{agent_id}/messages``. If omitted
                 and no client injection occurs, the session registers
                 without an agent_id and will not receive events over the
                 topic-routed path (messaging still works via the
                 hook-based inbox).
        enable_sse: If True (default), spawn a MessageBridge that consumes
                   the SSE stream and writes to the session's inbox
                   directory for hook-based delivery.
        force: If True, replace an existing registration for this alias.
              The old queue is discarded (a disconnect sentinel is sent
              first for SSE cleanup) and a warning is logged. Use this
              when recovering an alias claimed by a dead prior session.
        session_id: Caller's local session marker (e.g. Claude Code
                   session id). Normally auto-injected by the client.
                   Used to write a marker file so the hook only drains
                   inboxes belonging to this session. Distinct from
                   ``agent_id`` and from the MCP transport UUID.

    Returns:
        ``{"ok": true, "alias": str, "registered_at": str,
        "agent_id": str|None, "fastmcp_session_id": str|None}`` on success.
        ``{"ok": false, "error": "alias_already_registered", ...}`` if
        the alias is taken and ``force`` is False.
        ``{"ok": false, "error": "invalid_alias", ...}`` if ``alias``
        fails validation.
    """
    err = _validate_alias(alias)
    if err:
        return err
    # Capture the caller's MCP transport session UUID so emit_event's
    # target_session_ids filter can restrict delivery to the right
    # connection. This is distinct from the application-level agent_id.
    fastmcp_session_id = _extract_fastmcp_session_id(ctx)
    try:
        reg = await message_bus.register(
            alias,
            enable_sse=enable_sse,
            force=force,
            session_id=session_id,
            agent_id=agent_id or None,
            fastmcp_session_id=fastmcp_session_id,
        )
        return {
            "ok": True,
            "alias": reg.alias,
            "registered_at": reg.registered_at,
            "agent_id": reg.agent_id,
            "fastmcp_session_id": reg.fastmcp_session_id,
        }
    except ValueError as e:
        return {"ok": False, "error": "alias_already_registered", "alias": alias, "detail": str(e)}


@mcp.tool()
@inject_recovery_context
async def messaging_unregister(alias: str) -> dict:
    """Unregister this session from messaging.

    Removes the alias from the registry and discards any queued messages
    and pending correlations. Call this on clean session shutdown so
    other agents don't try to deliver to a dead queue.

    Args:
        alias: The alias to unregister (must be one previously claimed
              via ``messaging_register``).

    Returns:
        ``{"ok": true}`` if removed.
        ``{"ok": false, "error": "not_found"}`` if the alias was not
        registered.
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
    ttl: int = 60,
    priority: MessagePriority = "high",
) -> dict:
    """Send a direct message to another registered session.

    Delivers immediately to the recipient's queue and, when the recipient
    has an ``agent_id``, also emits an MCP Events Spec v2 event on the
    topic ``agents/{recipient_agent_id}/messages``. Events-capable
    clients receive the message as a context injection; legacy clients
    receive it by polling or via the SSE hook bridge.

    Fails if ``recipient`` is not registered or their queue is full.

    Correlation IDs (v2):
        Under MCP Events Spec v2, correlation identifiers are NOT a
        wire-level field. To track a request/reply pair, put a
        ``"correlation_id"`` key directly in the ``payload`` dict. The
        tool extracts it and registers a pending correlation so
        ``messaging_reply`` can route the reply back. Example::

            messaging_send(
                sender="alice",
                recipient="bob",
                payload='{"question": "status?", "correlation_id": "req-42"}',
            )

    Args:
        sender: Your registered alias.
        recipient: Target session's registered alias.
        payload: JSON string with message content. Must parse to a JSON
                object (dict). Max 64 KB. If it contains a top-level
                ``"correlation_id"`` string (max 128 chars), that value
                is used to track a request/reply pair.
        ttl: Seconds before a pending correlation expires. Clamped to
            ``[1, 300]``. Default 60. Only meaningful when the payload
            carries a ``correlation_id``.
        priority: Delivery priority hint for the v2 event. Controls how
                 aggressively the receiving client injects the message.
                 One of:
                   - ``"urgent"`` - interrupt the agent immediately
                     (reserved for actionable blockers)
                   - ``"high"`` - inject at the next safe point
                     (direct messages default; human-routed replies)
                   - ``"normal"`` - inject on the next turn
                     (informational updates)
                   - ``"low"`` - deliver opportunistically
                     (background chatter, metrics)
                 Defaults to ``"high"`` for direct messages.

    Returns:
        ``{"ok": true, "message_id": str}`` on success.
        ``{"ok": false, "error": str, "detail": str}`` on failure
        (e.g. ``recipient_not_found``, ``queue_full``,
        ``invalid_payload_json``, ``payload_too_large``,
        ``correlation_id_too_long``).
    """
    parsed, err = _parse_payload(payload)
    if err:
        return err

    # Clamp TTL
    ttl = max(_TTL_MIN, min(ttl, _TTL_MAX))

    # Extract correlation_id from the payload dict (v2: caller-owned, not a
    # wire field). Must be a string to be usable as a routing key.
    correlation_id: Optional[str] = None
    raw_corr = parsed.get("correlation_id")
    if isinstance(raw_corr, str) and raw_corr:
        if len(raw_corr) > 128:
            return {
                "ok": False,
                "error": "correlation_id_too_long",
                "detail": "Max 128 chars.",
            }
        correlation_id = raw_corr

    result = await message_bus.send(
        sender=sender,
        recipient=recipient,
        payload=parsed,
        correlation_id=correlation_id,
        ttl=ttl,
    )

    # Emit MCP event alongside queue-based delivery for events-capable clients.
    # Under MCP Events Spec v2, topics are parameterized by the recipient's
    # application-level ``agent_id``. If the recipient registered without an
    # agent_id, skip event emission; queue-based delivery above still
    # happened. We also pass the recipient's MCP transport UUID as the
    # ``target_session_ids`` defense-in-depth filter to avoid cross-session
    # leakage inside clients that multiplex several agents per transport.
    if result.get("ok"):
        recipient_agent_id = message_bus.resolve_alias_to_agent_id(recipient)
        if recipient_agent_id:
            recipient_transport_sid = message_bus.resolve_alias_to_session_id(recipient)
            try:
                await _emit_event_v2(
                    topic=f"agents/{recipient_agent_id}/messages",
                    payload={
                        "message_id": result.get("message_id"),
                        "sender": sender,
                        "recipient": recipient,
                        # v2: correlation_id (if any) lives inside ``parsed``;
                        # nothing extra at the event-payload level.
                        "payload": parsed,
                    },
                    source="spellbook/messaging",
                    priority=priority,
                    target_session_ids=(
                        [recipient_transport_sid] if recipient_transport_sid else None
                    ),
                )
            except Exception:
                logger.warning("Failed to emit event for message delivery", exc_info=True)
        else:
            logger.debug(
                "recipient %s has no agent_id; skipping event emission (queue-only)",
                recipient,
            )

    return result


@mcp.tool()
@inject_recovery_context
async def messaging_broadcast(
    sender: str,
    payload: str,
    include_self: bool = False,
    priority: MessagePriority = "normal",
) -> dict:
    """Broadcast a message to all registered sessions.

    Delivers the message to every registered alias (optionally
    including the sender) via the queue, and also emits an MCP Events
    Spec v2 event on ``agents/{recipient_agent_id}/messages`` for each
    recipient that has an ``agent_id``. Useful for discovery ("who is
    working on X?") and project-wide announcements.

    Correlation IDs have no meaning for broadcasts; do not set one in
    the payload.

    Args:
        sender: Your registered alias.
        payload: JSON string with message content. Must parse to a JSON
                object (dict). Max 64 KB.
        include_self: If True, also deliver to ``sender``. Default False.
        priority: Delivery priority hint for the v2 events. One of
                 ``"urgent"`` / ``"high"`` / ``"normal"`` / ``"low"``.
                 Defaults to ``"normal"`` because broadcasts are usually
                 informational. Use ``"high"`` only for project-wide
                 alerts that warrant interrupting every agent. See
                 ``messaging_send`` for priority semantics.

    Returns:
        ``{"ok": true, "delivered_count": int, "failed_count": int,
        "delivered_aliases": list[str], "errors": list|null}``. The
        ``delivered_aliases`` list is authoritative and is what the
        server uses when emitting per-recipient v2 events (no TOCTOU
        races against ``messaging_list_sessions``).
    """
    parsed, err = _parse_payload(payload)
    if err:
        return err
    result = await message_bus.broadcast(
        sender=sender,
        payload=parsed,
        exclude_sender=not include_self,
    )

    # Emit events for each recipient with a known agent_id.
    # Use delivered_aliases from broadcast() result (NOT a separate
    # list_sessions() call) to avoid TOCTOU race conditions.
    # Gather all coroutines in parallel so N recipients cost one round-trip,
    # not N serial awaits. return_exceptions=True prevents one failure from
    # cancelling delivery to other recipients.
    if result.get("ok"):
        async def _emit_one(alias: str) -> None:
            agent_id = message_bus.resolve_alias_to_agent_id(alias)
            if not agent_id:
                return
            transport_sid = message_bus.resolve_alias_to_session_id(alias)
            try:
                await _emit_event_v2(
                    topic=f"agents/{agent_id}/messages",
                    payload={
                        "sender": sender,
                        "recipient": "*",
                        "payload": parsed,
                        "broadcast": True,
                    },
                    source="spellbook/messaging",
                    priority=priority,
                    target_session_ids=[transport_sid] if transport_sid else None,
                )
            except Exception:
                logger.warning(
                    "Failed to emit broadcast event for recipient %s",
                    alias,
                    exc_info=True,
                )

        coros = [_emit_one(alias) for alias in result.get("delivered_aliases", [])]
        if coros:
            await asyncio.gather(*coros, return_exceptions=True)

    return result


@mcp.tool()
@inject_recovery_context
async def messaging_reply(
    sender: str,
    payload: str,
    priority: MessagePriority = "high",
) -> dict:
    """Reply to a message using its correlation ID.

    Routes the reply back to the original sender and emits an MCP
    Events Spec v2 event to the original sender's
    ``agents/{agent_id}/messages`` topic (when they have an
    ``agent_id``). Fails if the correlation has expired (the pending
    correlation lives for at most ``ttl`` seconds, default 60) or the
    original sender has unregistered.

    Correlation IDs (v2):
        Under MCP Events Spec v2, ``correlation_id`` is NOT a wire-level
        field. The replier copies the ``correlation_id`` from the
        received message into a top-level key inside the reply
        ``payload`` dict; this tool extracts it and uses it to route
        the reply. Example (responding to the send example above)::

            messaging_reply(
                sender="bob",
                payload='{"answer": "all green", "correlation_id": "req-42"}',
            )

        You do NOT need to specify the original ``recipient`` — it is
        resolved from the pending correlation table.

    Args:
        sender: Your registered alias (the replier).
        payload: JSON string with reply content. Must parse to a JSON
                object (dict). MUST include a top-level
                ``"correlation_id"`` string matching the received
                message. Max 64 KB. Correlation id max 128 chars.
        priority: Delivery priority hint for the v2 event. One of
                 ``"urgent"`` / ``"high"`` / ``"normal"`` / ``"low"``.
                 Defaults to ``"high"`` because a reply is usually what
                 the requester is blocked waiting for. See
                 ``messaging_send`` for the full priority semantics.

    Returns:
        ``{"ok": true, "message_id": str, "recipient": str}`` on
        success, where ``recipient`` is the alias of the original
        sender the reply was routed to.
        ``{"ok": false, "error": str, "detail": str}`` if the
        correlation expired, the original sender is gone, or
        ``correlation_id`` is missing/invalid in the payload.
    """
    parsed, err = _parse_payload(payload)
    if err:
        return err

    raw_corr = parsed.get("correlation_id")
    if not isinstance(raw_corr, str) or not raw_corr:
        return {
            "ok": False,
            "error": "missing_correlation_id",
            "detail": "Reply payload must include a top-level 'correlation_id' string.",
        }
    if len(raw_corr) > 128:
        return {
            "ok": False,
            "error": "correlation_id_too_long",
            "detail": "Max 128 chars.",
        }
    correlation_id = raw_corr

    result = await message_bus.reply(
        sender=sender,
        correlation_id=correlation_id,
        payload=parsed,
    )

    # Emit event to the reply recipient (the original sender of the
    # correlated message).
    if result.get("ok"):
        recipient_alias = result.get("recipient")
        if recipient_alias:
            recipient_agent_id = message_bus.resolve_alias_to_agent_id(recipient_alias)
            if recipient_agent_id:
                recipient_transport_sid = message_bus.resolve_alias_to_session_id(
                    recipient_alias
                )
                try:
                    await _emit_event_v2(
                        topic=f"agents/{recipient_agent_id}/messages",
                        payload={
                            "message_id": result.get("message_id"),
                            "sender": sender,
                            "recipient": recipient_alias,
                            # v2: correlation_id is inside ``parsed``
                            # (placed there by the replier); no separate
                            # wire-level field.
                            "payload": parsed,
                            "is_reply": True,
                        },
                        source="spellbook/messaging",
                        priority=priority,
                        target_session_ids=(
                            [recipient_transport_sid]
                            if recipient_transport_sid
                            else None
                        ),
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
    """Poll for pending messages (fallback when SSE / v2 events unavailable).

    Drains up to ``max_messages`` from your queue. Messages are removed
    once polled (at-most-once delivery). Use this path when your client
    does not subscribe to MCP v2 event topics
    (``agents/{agent_id}/messages``) or when you want to reconcile the
    queue after a reconnect.

    Args:
        alias: Your registered alias.
        max_messages: Maximum messages to retrieve. Clamped to
                     ``[1, 50]``. Default 10.

    Returns:
        ``{"ok": true, "messages": list[MessageEnvelope],
        "remaining": int}``. Each ``MessageEnvelope`` carries the
        sender, payload, and any correlation metadata recorded at send
        time.
    """
    max_messages = max(1, min(max_messages, _POLL_MAX))
    messages, remaining = await message_bus.poll(alias, max_messages=max_messages)
    return {"ok": True, "messages": messages, "remaining": remaining}


@mcp.tool()
@inject_recovery_context
async def messaging_list_sessions() -> dict:
    """List all registered messaging sessions.

    Returns:
        {"ok": true, "sessions": [{"alias": str, "registered_at": str,
         "agent_id": str|None, "fastmcp_session_id": str|None}, ...]}
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
