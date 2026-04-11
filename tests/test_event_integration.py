"""Integration tests for MCP events in spellbook.

Verifies that:
- Event topics are declared on the spellbook MCP server
- messaging_send emits an EventEmitNotification alongside queue delivery
- The event is delivered only to the subscribed recipient agent, not the sender

Under MCP Events Spec v2, topics are parameterized by the application-level
``agent_id`` (e.g. the opencode session id) rather than the MCP transport UUID.
These tests use the transport UUID as the agent_id value for simplicity so that
the same identifier feeds both the topic slot and the ``target_session_ids``
defense-in-depth filter.

Note: These tests intentionally access private attributes (e.g., _event_topics,
_active_sessions, _subscription_registry, _retained_store, _fastmcp_event_session_id,
_session_state) to verify subscription and session state. No public API exposes this
information yet.

Why no bigfoot mocks: These are integration tests that exercise real FastMCP server
and MessageBus objects end-to-end. The test doubles used here (capturing_send closures,
tracking_emit functions) replace attributes on live objects to observe real event
flow -- they are not mocks of dependencies but probes on real instances. Pytest's
monkeypatch is used for the two places a module-level attribute needs to be swapped
(per AGENTS.md, monkeypatch is the approved tool for environment/attribute patching).
"""

import inspect
import json
from typing import Any

import pytest
from mcp.types import EventParams, TextContent

from fastmcp import Client, FastMCP
from fastmcp.server.events import EventEmitNotification


# ---------------------------------------------------------------------------
# FastMCP API compatibility shim (mirrors the one in spellbook.mcp.tools.messaging)
# ---------------------------------------------------------------------------

_EMIT_PARAMS = set(inspect.signature(FastMCP.emit_event).parameters.keys())
_EMIT_SUPPORTS_PRIORITY = "priority" in _EMIT_PARAMS
_EMIT_SUPPORTS_REQUESTED_EFFECTS = "requested_effects" in _EMIT_PARAMS


async def _emit_v2(
    server: FastMCP,
    *,
    topic: str,
    payload: Any,
    source: str | None = None,
    priority: str = "high",
    target_session_ids: list[str] | None = None,
    retained: bool | None = None,
) -> None:
    """Emit an event using v2 wire fields with transitional fastmcp compat."""
    kwargs: dict[str, Any] = {"topic": topic, "payload": payload}
    if source is not None:
        kwargs["source"] = source
    if target_session_ids is not None:
        kwargs["target_session_ids"] = target_session_ids
    if retained is not None:
        kwargs["retained"] = retained
    if _EMIT_SUPPORTS_PRIORITY:
        kwargs["priority"] = priority
    elif _EMIT_SUPPORTS_REQUESTED_EFFECTS:
        from fastmcp.server.events import EventEffect  # type: ignore

        kwargs["requested_effects"] = [
            EventEffect(type="inject_context", priority=priority),
        ]
    await server.emit_event(**kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_server() -> FastMCP:
    """Create a fresh FastMCP instance with messaging event topics declared.

    Topic declarations use the MCP Events Spec v2 pattern
    ``agents/{agent_id}/...``. We create a standalone server rather than
    importing the spellbook global singleton to avoid side effects from
    other tool registrations and startup dependencies (DB init, watchers,
    etc).

    The literal placeholder name ``{agent_id}`` is magic in fastmcp: it
    enforces that the subscriber's transport session UUID matches the
    value substituted into that slot. A secondary
    ``spellbook/sessions/{agent_id}/messages`` topic is declared so the
    authorization tests can exercise magic enforcement on a
    non-``agents/`` pattern too.
    """
    server = FastMCP("spellbook-test")
    server.declare_event(
        "agents/{agent_id}/messages",
        kind="content",
        description="Cross-agent messages",
    )
    server.declare_event(
        "agents/{agent_id}/build/status",
        kind="content",
        description="Build status for this agent's work",
        retained=True,
    )
    # Parallel declaration used by TestSessionScopedAuthorization to
    # exercise the ``{agent_id}`` magic-placeholder convention on a
    # non-``agents/`` pattern.
    server.declare_event(
        "spellbook/sessions/{agent_id}/messages",
        kind="content",
        description="Per-agent messages (magic-auth slot)",
    )
    return server


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEventTopicDeclaration:
    """Verify event topics are declared correctly."""

    def test_message_topic_declared(self) -> None:
        server = _make_server()
        assert "agents/{agent_id}/messages" in server._event_topics

    def test_build_status_topic_declared(self) -> None:
        server = _make_server()
        desc = server._event_topics["agents/{agent_id}/build/status"]
        assert desc.retained is True

    async def test_events_capability_advertised(self) -> None:
        """When event topics are declared, the events capability is visible."""
        server = _make_server()
        async with Client(server) as client:
            result = client._session_state.initialize_result
            assert result is not None
            extras = result.capabilities.model_extra or {}
            assert "events" in extras or hasattr(result.capabilities, "events")
            # Verify capability content: topics with patterns and descriptions
            events_cap = extras.get("events") or getattr(
                result.capabilities, "events", None
            )
            assert events_cap is not None
            if isinstance(events_cap, dict):
                topics = events_cap.get("topics", [])
            else:
                topics = getattr(events_cap, "topics", [])
            assert len(topics) >= 2
            # Convert topic dicts/objects to pattern strings for verification
            patterns = [
                t.get("pattern") if isinstance(t, dict) else getattr(t, "pattern", None)
                for t in topics
            ]
            assert "agents/{agent_id}/messages" in patterns
            assert "agents/{agent_id}/build/status" in patterns
            # Verify descriptions are present
            for t in topics:
                desc = t.get("description") if isinstance(t, dict) else getattr(t, "description", None)
                assert desc is not None, f"Topic {t} missing description"


class TestEventEmissionOnSend:
    """Verify that messaging_send emits events to subscribed sessions."""

    async def test_recipient_receives_event_on_send(self) -> None:
        """Agent B subscribes to its messages topic. Agent A sends a
        message via emit_event. Agent B's subscription receives the event."""
        server = _make_server()

        received_notifications: list[Any] = []

        async with Client(server) as client_a:
            session_a = list(server._active_sessions.values())[0]

            async with Client(server) as client_b:
                # Find session B (the one that is not session A)
                session_b = [
                    s for s in server._active_sessions.values() if s is not session_a
                ][0]
                session_b_id = getattr(session_b, "_fastmcp_event_session_id")

                # Subscribe session B to agent B's messages topic. For this
                # test the agent_id value is chosen arbitrarily ("agent-b");
                # in production it would be the opencode session id.
                await server._subscription_registry.add(
                    session_b_id, "agents/agent-b/messages"
                )

                # Capture notifications sent to session B
                async def capturing_send(notification: Any, related_request_id: Any = None) -> None:
                    received_notifications.append(notification)

                session_b.send_notification = capturing_send

                # Emit an event targeting agent B (simulating what
                # messaging_send does after a successful queue delivery)
                await _emit_v2(
                    server,
                    topic="agents/agent-b/messages",
                    payload={
                        "message_id": "test-msg-001",
                        "sender": "agent-a",
                        "recipient": "agent-b",
                        "payload": {"greeting": "hello from A"},
                    },
                    source="spellbook/messaging",
                    priority="high",
                )

                # Verify session B received the event
                assert len(received_notifications) == 1
                notif = received_notifications[0]
                assert isinstance(notif, EventEmitNotification)
                assert notif.params.topic == "agents/agent-b/messages"
                assert notif.params.payload["sender"] == "agent-a"
                assert notif.params.payload["payload"] == {"greeting": "hello from A"}
                assert notif.params.source == "spellbook/messaging"

    async def test_sender_does_not_receive_event(self) -> None:
        """Agent A sends a message to B. A should NOT receive the event
        because A is not subscribed to B's topic."""
        server = _make_server()

        sender_notifications: list[Any] = []

        async with Client(server) as client_a:
            session_a = list(server._active_sessions.values())[0]
            session_a_id = getattr(session_a, "_fastmcp_event_session_id")

            # Subscribe session A to agent A's messages topic (not B's)
            await server._subscription_registry.add(
                session_a_id, "agents/agent-a/messages"
            )

            # Capture notifications sent to session A
            async def capturing_send(notification: Any, related_request_id: Any = None) -> None:
                sender_notifications.append(notification)

            session_a.send_notification = capturing_send

            async with Client(server) as client_b:
                session_b = [
                    s for s in server._active_sessions.values() if s is not session_a
                ][0]
                session_b_id = getattr(session_b, "_fastmcp_event_session_id")

                # Subscribe session B to agent B's messages topic
                await server._subscription_registry.add(
                    session_b_id, "agents/agent-b/messages"
                )

                # Emit event targeting agent B
                await _emit_v2(
                    server,
                    topic="agents/agent-b/messages",
                    payload={"sender": "agent-a", "payload": {"hello": "B"}},
                    source="spellbook/messaging",
                )

                # Session A should NOT have received this event
                assert len(sender_notifications) == 0

    async def test_wildcard_subscription_receives_all_sessions(self) -> None:
        """A session subscribed with a wildcard pattern receives events for
        any agent_id."""
        server = _make_server()

        received: list[Any] = []

        async with Client(server) as client:
            session = list(server._active_sessions.values())[0]
            session_id = getattr(session, "_fastmcp_event_session_id")

            # Subscribe with wildcard: all agents' messages
            await server._subscription_registry.add(
                session_id, "agents/+/messages"
            )

            async def capturing_send(notification: Any, related_request_id: Any = None) -> None:
                received.append(notification)

            session.send_notification = capturing_send

            # Emit to two different agent topics
            await _emit_v2(
                server,
                topic="agents/alpha/messages",
                payload={"from": "alpha"},
            )
            await _emit_v2(
                server,
                topic="agents/beta/messages",
                payload={"from": "beta"},
            )

            assert len(received) == 2
            topics = {n.params.topic for n in received}
            assert topics == {
                "agents/alpha/messages",
                "agents/beta/messages",
            }


class TestRetainedEvents:
    """Verify retained event behavior for build/status topic."""

    async def test_retained_event_stored(self) -> None:
        """Emitting to a retained topic stores the value.

        Note: parameterized topic patterns (with {agent_id}) require
        explicit retained=True on emit since the exact lookup for the
        descriptor won't match the concrete topic string.
        """
        server = _make_server()

        await _emit_v2(
            server,
            topic="agents/worker-1/build/status",
            payload={"status": "building", "progress": 42},
            retained=True,
        )

        stored = await server._retained_store.get(
            "agents/worker-1/build/status"
        )
        assert stored is not None
        assert stored.payload["status"] == "building"
        assert stored.payload["progress"] == 42
        assert stored.topic == "agents/worker-1/build/status"
        assert stored.event_id is not None and len(stored.event_id) > 0

    async def test_retained_event_overwritten(self) -> None:
        """New retained events replace previous ones for the same topic."""
        server = _make_server()

        await _emit_v2(
            server,
            topic="agents/worker-1/build/status",
            payload={"status": "building"},
            retained=True,
        )

        first_stored = await server._retained_store.get(
            "agents/worker-1/build/status"
        )
        assert first_stored is not None
        first_event_id = first_stored.event_id

        await _emit_v2(
            server,
            topic="agents/worker-1/build/status",
            payload={"status": "complete"},
            retained=True,
        )

        stored = await server._retained_store.get(
            "agents/worker-1/build/status"
        )
        assert stored is not None
        assert stored.payload["status"] == "complete"
        # Verify old payload is truly gone (not merged)
        assert "building" not in str(stored.payload)
        # Verify event_id was updated (new event replaces old)
        assert stored.event_id is not None
        assert stored.event_id != first_event_id
        assert stored.topic == "agents/worker-1/build/status"


    async def test_retained_event_delivered_on_subscribe(self) -> None:
        """When a client subscribes to a topic with a retained event,
        the retained value is included in the subscribe result via get_matching."""
        server = _make_server()

        # Emit a retained event before any subscriptions exist
        await _emit_v2(
            server,
            topic="agents/worker-1/build/status",
            payload={"status": "passing", "commit": "abc123"},
            retained=True,
        )

        # Verify retained store has the event
        stored = await server._retained_store.get(
            "agents/worker-1/build/status"
        )
        assert stored is not None

        # Simulate what subscribe does: get_matching returns retained events
        # for patterns matching the topic
        matching = await server._retained_store.get_matching(
            "agents/+/build/status"
        )
        assert len(matching) >= 1
        matched_topics = [m.topic for m in matching]
        assert "agents/worker-1/build/status" in matched_topics

        # Verify the retained event payload is complete
        match = next(
            m for m in matching
            if m.topic == "agents/worker-1/build/status"
        )
        assert match.payload["status"] == "passing"
        assert match.payload["commit"] == "abc123"
        assert match.event_id is not None


def _make_messaging_server() -> tuple[FastMCP, Any]:
    """Create a FastMCP server with real messaging tools wired to a local bus.

    Returns (server, bus) so tests can inspect bus state. The tools registered
    here mirror spellbook.mcp.tools.messaging but avoid importing the global
    mcp singleton (which drags in DB init, watchers, etc).

    Topic declarations use MCP Events Spec v2 (``agents/{agent_id}/...``).
    The test ``messaging_register`` tool auto-derives an ``agent_id`` from
    the MCP transport UUID so the same identifier is usable for topic
    substitution and for ``target_session_ids`` defense-in-depth filtering.
    """
    from spellbook.messaging.bus import MessageBus

    server = FastMCP("spellbook-messaging-test")
    bus = MessageBus(queue_size=64)

    # Declare the same event topics the real server does (v2 style).
    server.declare_event(
        "agents/{agent_id}/messages",
        kind="content",
        description="Cross-agent messages",
    )
    server.declare_event(
        "agents/{agent_id}/build/status",
        kind="content",
        description="Build status for this agent's work",
        retained=True,
    )

    # A non-scoped public topic for authorization tests
    server.declare_event(
        "spellbook/server/status",
        kind="content",
        description="Server-wide status (public, no scoping)",
    )

    # A public broadcast topic for targeted-emit tests
    server.declare_event(
        "spellbook/broadcasts/announcements",
        kind="content",
        description="Public announcements channel",
    )

    # Parallel declaration used by TestSessionScopedAuthorization to
    # exercise the ``{agent_id}`` magic-placeholder convention on a
    # non-``agents/`` pattern.
    server.declare_event(
        "spellbook/sessions/{agent_id}/messages",
        kind="content",
        description="Per-agent messages (magic-auth slot)",
    )

    from fastmcp import Context

    def _extract_session_id(ctx: Context | None) -> str | None:
        """Extract the MCP transport session UUID from a tool Context."""
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
        return sid if isinstance(sid, str) and sid else None

    @server.tool()
    async def messaging_register(
        alias: str,
        ctx: Context | None = None,
    ) -> dict:
        """Register for messaging.

        Captures the MCP transport UUID from the Context and reuses it as
        the application-level ``agent_id``. Real clients pass their own
        ``agent_id`` (e.g. opencode session id) explicitly; this test
        helper uses the transport UUID as a convenient stand-in so topic
        routing and ``target_session_ids`` filtering both work with a
        single identifier.
        """
        transport_sid = _extract_session_id(ctx)
        try:
            reg = await bus.register(
                alias,
                enable_sse=False,
                agent_id=transport_sid,
                fastmcp_session_id=transport_sid,
            )
            return {
                "ok": True,
                "alias": reg.alias,
                "registered_at": reg.registered_at,
                "agent_id": reg.agent_id,
                "fastmcp_session_id": reg.fastmcp_session_id,
            }
        except ValueError as e:
            return {"ok": False, "error": "alias_already_registered", "detail": str(e)}

    @server.tool()
    async def messaging_send(
        sender: str,
        recipient: str,
        payload: str,
    ) -> dict:
        """Send a message. Emits a v2 MCP event to the recipient's agent topic."""
        import json as _json

        try:
            parsed = _json.loads(payload)
        except (ValueError, _json.JSONDecodeError) as e:
            return {"ok": False, "error": "invalid_payload_json", "detail": str(e)}

        result = await bus.send(sender=sender, recipient=recipient, payload=parsed)

        if result.get("ok"):
            recipient_agent_id = bus.resolve_alias_to_agent_id(recipient)
            recipient_transport_sid = bus.resolve_alias_to_session_id(recipient)
            if recipient_agent_id:
                await _emit_v2(
                    server,
                    topic=f"agents/{recipient_agent_id}/messages",
                    payload={
                        "message_id": result.get("message_id"),
                        "sender": sender,
                        "recipient": recipient,
                        "payload": parsed,
                    },
                    source="spellbook/messaging",
                    priority="high",
                    target_session_ids=(
                        [recipient_transport_sid] if recipient_transport_sid else None
                    ),
                )
        return result

    return server, bus


@pytest.mark.allow("mcp")
class TestCrossSessionMessaging:
    """Real MCP client round-trip tests for cross-session messaging events.

    Each test spins up two (or three) in-process Client sessions connected
    to a fresh FastMCP server with messaging tools. Events are captured
    via set_event_handler on the client's low-level session.
    """

    async def test_bob_receives_message_from_alice(self) -> None:
        """Alice sends a message to Bob. Bob receives the EventEmitNotification
        reactively via his event handler. Alice does NOT receive it."""
        import asyncio as _asyncio

        server, bus = _make_messaging_server()

        alice_events: list[Any] = []
        bob_events: list[Any] = []

        async with Client(server) as alice_client:
            alice_session = alice_client.session

            async with Client(server) as bob_client:
                bob_session = bob_client.session

                # Register both on the bus via MCP tool calls.
                # The test helper sets agent_id = MCP transport UUID so the
                # response's ``agent_id`` can be reused as both the topic
                # slot value and the target_session_ids filter input.
                alice_reg_result = await alice_client.call_tool(
                    "messaging_register", {"alias": "alice"}
                )
                alice_reg_data = json.loads(alice_reg_result.content[0].text)
                assert alice_reg_data["ok"] is True, f"Alice register failed: {alice_reg_data}"
                alice_agent_id = alice_reg_data.get("agent_id")
                assert alice_agent_id is not None, "Server must populate agent_id"

                bob_reg_result = await bob_client.call_tool(
                    "messaging_register", {"alias": "bob"}
                )
                bob_reg_data = json.loads(bob_reg_result.content[0].text)
                assert bob_reg_data["ok"] is True, f"Bob register failed: {bob_reg_data}"
                bob_agent_id = bob_reg_data.get("agent_id")
                assert bob_agent_id is not None

                # Subscribe each to their own agent topic (v2)
                alice_sub = await alice_session.subscribe_events(
                    [f"agents/{alice_agent_id}/messages"]
                )
                assert len(alice_sub.rejected) == 0

                bob_sub = await bob_session.subscribe_events(
                    [f"agents/{bob_agent_id}/messages"]
                )
                assert len(bob_sub.rejected) == 0

                # Set up event handlers (must be async for type safety)
                async def _alice_handler(params: EventParams) -> None:
                    alice_events.append(params)

                async def _bob_handler(params: EventParams) -> None:
                    bob_events.append(params)

                alice_session.set_event_handler(_alice_handler)
                bob_session.set_event_handler(_bob_handler)

                # Alice sends a message to Bob
                send_result = await alice_client.call_tool(
                    "messaging_send",
                    {
                        "sender": "alice",
                        "recipient": "bob",
                        "payload": '{"text": "hello"}',
                    },
                )
                # Verify tool returned success
                first_content = send_result.content[0]
                assert isinstance(first_content, TextContent)
                result_data = json.loads(first_content.text)
                assert result_data["ok"] is True

                # Poll until event propagates (up to 2 seconds)
                for _ in range(20):
                    await _asyncio.sleep(0.1)
                    if len(bob_events) >= 1:
                        break

                # Bob SHOULD have received the event
                assert len(bob_events) == 1, (
                    f"Bob should receive exactly 1 event, got {len(bob_events)}"
                )
                bob_event = bob_events[0]
                assert bob_event.topic == f"agents/{bob_agent_id}/messages"
                assert bob_event.payload["sender"] == "alice"
                assert bob_event.payload["payload"] == {"text": "hello"}
                assert bob_event.source == "spellbook/messaging"

                # Alice should NOT have received it
                assert len(alice_events) == 0, (
                    f"Alice should receive 0 events, got {len(alice_events)}"
                )

    async def test_alice_does_not_receive_bobs_message(self) -> None:
        """Bob sends to Alice. Alice receives the event. Bob does NOT."""
        import asyncio as _asyncio

        server, bus = _make_messaging_server()

        alice_events: list[Any] = []
        bob_events: list[Any] = []

        async with Client(server) as alice_client:
            alice_session = alice_client.session

            async with Client(server) as bob_client:
                bob_session = bob_client.session

                # Register both; use agent_id from response for topic subscription.
                alice_reg_result = await alice_client.call_tool(
                    "messaging_register", {"alias": "alice"}
                )
                alice_reg_data = json.loads(alice_reg_result.content[0].text)
                assert alice_reg_data["ok"] is True
                alice_agent_id = alice_reg_data.get("agent_id")
                assert alice_agent_id is not None

                bob_reg_result = await bob_client.call_tool(
                    "messaging_register", {"alias": "bob"}
                )
                bob_reg_data = json.loads(bob_reg_result.content[0].text)
                assert bob_reg_data["ok"] is True
                bob_agent_id = bob_reg_data.get("agent_id")
                assert bob_agent_id is not None

                # Subscribe each to their OWN topic (v2)
                await alice_session.subscribe_events(
                    [f"agents/{alice_agent_id}/messages"]
                )
                await bob_session.subscribe_events(
                    [f"agents/{bob_agent_id}/messages"]
                )

                # Set up handlers (must be async for type safety)
                async def _alice_handler(params: EventParams) -> None:
                    alice_events.append(params)

                async def _bob_handler(params: EventParams) -> None:
                    bob_events.append(params)

                alice_session.set_event_handler(_alice_handler)
                bob_session.set_event_handler(_bob_handler)

                # Bob sends to Alice
                send_result = await bob_client.call_tool(
                    "messaging_send",
                    {
                        "sender": "bob",
                        "recipient": "alice",
                        "payload": '{"text": "reply"}',
                    },
                )
                first_content = send_result.content[0]
                assert isinstance(first_content, TextContent)
                result_data = json.loads(first_content.text)
                assert result_data["ok"] is True

                # Poll until event propagates (up to 2 seconds)
                for _ in range(20):
                    await _asyncio.sleep(0.1)
                    if len(alice_events) >= 1:
                        break

                # Alice SHOULD receive
                assert len(alice_events) == 1
                assert alice_events[0].payload["sender"] == "bob"

                # Bob should NOT
                assert len(bob_events) == 0


@pytest.mark.allow("mcp")
class TestSessionScopedAuthorization:
    """Verify {agent_id} enforcement prevents cross-session snooping."""

    async def test_cannot_subscribe_to_other_session_topic(self) -> None:
        """Alice tries to subscribe to Bob's session topic. Must be rejected."""
        server = _make_server()

        async with Client(server) as alice_client:
            alice_session = alice_client.session
            # Read Alice's UUID from the server-side session object.
            alice_sid = list(server._active_sessions.values())[0]._fastmcp_event_session_id
            assert alice_sid is not None

            async with Client(server) as bob_client:
                bob_session = bob_client.session
                # Bob is the newly-added session (set difference).
                all_sids = {s._fastmcp_event_session_id for s in server._active_sessions.values()}
                bob_sid = (all_sids - {alice_sid}).pop()
                assert bob_sid is not None
                assert alice_sid != bob_sid

                # Alice tries to subscribe to Bob's topic
                result = await alice_session.subscribe_events(
                    [f"spellbook/sessions/{bob_sid}/messages"]
                )
                assert len(result.rejected) == 1
                assert result.rejected[0].reason == "permission_denied"
                assert len(result.subscribed) == 0

    async def test_cannot_use_wildcard_in_session_slot(self) -> None:
        """Subscribing with + in the {session_id} slot must be rejected."""
        server = _make_server()

        async with Client(server) as client:
            session = client.session
            # sid is only needed to confirm the client is connected; the
            # wildcard test doesn't reference it in the subscription pattern.
            assert len(server._active_sessions) == 1

            result = await session.subscribe_events(
                ["spellbook/sessions/+/messages"]
            )
            assert len(result.rejected) == 1
            assert result.rejected[0].reason == "permission_denied"
            assert len(result.subscribed) == 0

    async def test_can_subscribe_to_own_session_topic(self) -> None:
        """A client can subscribe to its own session topic."""
        server = _make_server()

        async with Client(server) as client:
            session = client.session
            # Read own UUID from the server-side session.
            sid = list(server._active_sessions.values())[0]._fastmcp_event_session_id
            assert sid is not None

            result = await session.subscribe_events(
                [f"spellbook/sessions/{sid}/messages"]
            )
            assert len(result.rejected) == 0
            assert len(result.subscribed) == 1
            assert result.subscribed[0].pattern == f"spellbook/sessions/{sid}/messages"

    async def test_public_topic_allows_any_subscriber(self) -> None:
        """A non-scoped topic (no {session_id}) allows any subscriber."""
        server, _bus = _make_messaging_server()

        async with Client(server) as client:
            session = client.session

            result = await session.subscribe_events(
                ["spellbook/server/status"]
            )
            assert len(result.rejected) == 0
            assert len(result.subscribed) == 1


@pytest.mark.allow("mcp")
class TestTargetedEmission:
    """Verify target_session_ids restricts delivery to specified sessions."""

    async def test_targeted_emit_only_reaches_specified_sessions(self) -> None:
        """Three clients subscribe to a public topic. Emit with
        target_session_ids=[A, B] -- only A and B receive; C does not."""
        import asyncio as _asyncio

        server, _bus = _make_messaging_server()

        a_events: list[Any] = []
        b_events: list[Any] = []
        c_events: list[Any] = []

        async with Client(server) as client_a:
            session_a = client_a.session

            async with Client(server) as client_b:
                session_b = client_b.session

                async with Client(server) as client_c:
                    session_c = client_c.session

                    # Register each client to obtain the fastmcp_session_id UUID
                    # assigned by the server (needed for target_session_ids).
                    reg_a = json.loads(
                        (await client_a.call_tool("messaging_register", {"alias": "client-a"})).content[0].text
                    )
                    assert reg_a["ok"] is True
                    sid_a = reg_a["fastmcp_session_id"]
                    assert sid_a is not None

                    reg_b = json.loads(
                        (await client_b.call_tool("messaging_register", {"alias": "client-b"})).content[0].text
                    )
                    assert reg_b["ok"] is True
                    sid_b = reg_b["fastmcp_session_id"]
                    assert sid_b is not None

                    reg_c = json.loads(
                        (await client_c.call_tool("messaging_register", {"alias": "client-c"})).content[0].text
                    )
                    assert reg_c["ok"] is True
                    sid_c = reg_c["fastmcp_session_id"]
                    assert sid_c is not None

                    # All three subscribe to the public topic
                    for s in (session_a, session_b, session_c):
                        result = await s.subscribe_events(
                            ["spellbook/broadcasts/announcements"]
                        )
                        assert len(result.rejected) == 0

                    # Set up handlers (must be async for type safety)
                    async def _a_handler(params: EventParams) -> None:
                        a_events.append(params)

                    async def _b_handler(params: EventParams) -> None:
                        b_events.append(params)

                    async def _c_handler(params: EventParams) -> None:
                        c_events.append(params)

                    session_a.set_event_handler(_a_handler)
                    session_b.set_event_handler(_b_handler)
                    session_c.set_event_handler(_c_handler)

                    # Emit with target_session_ids restricting to A and B
                    await _emit_v2(
                        server,
                        topic="spellbook/broadcasts/announcements",
                        payload={"msg": "targeted broadcast"},
                        source="test",
                        target_session_ids=[sid_a, sid_b],
                    )

                    # Poll until events propagate (up to 2 seconds)
                    for _ in range(20):
                        await _asyncio.sleep(0.1)
                        if len(a_events) >= 1 and len(b_events) >= 1:
                            break

                    # A and B received
                    assert len(a_events) == 1
                    assert a_events[0].payload["msg"] == "targeted broadcast"
                    assert len(b_events) == 1
                    assert b_events[0].payload["msg"] == "targeted broadcast"

                    # C did NOT receive
                    assert len(c_events) == 0
