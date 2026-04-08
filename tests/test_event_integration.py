"""Integration tests for MCP events in spellbook.

Verifies that:
- Event topics are declared on the spellbook MCP server
- messaging_send emits an EventEmitNotification alongside queue delivery
- The event is delivered only to the subscribed recipient session, not the sender

Note: These tests intentionally access private attributes (e.g., _event_topics,
_active_sessions, _subscription_registry, _retained_store, _fastmcp_event_session_id,
_session_state) to verify subscription and session state. No public API exposes this
information yet.
"""

from typing import Any

import pytest

from fastmcp import Client, FastMCP
from fastmcp.server.events import EventEffect, EventEmitNotification


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_server() -> FastMCP:
    """Create a fresh FastMCP instance with messaging event topics declared.

    We create a standalone server rather than importing the spellbook global
    singleton to avoid side effects from other tool registrations and startup
    dependencies (DB init, watchers, etc).
    """
    server = FastMCP("spellbook-test")
    server.declare_event(
        "spellbook/sessions/{session_id}/messages",
        description="Cross-session messages",
    )
    server.declare_event(
        "spellbook/sessions/{session_id}/build/status",
        description="Build status for this session's work",
        retained=True,
    )
    return server


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEventTopicDeclaration:
    """Verify event topics are declared correctly."""

    def test_message_topic_declared(self):
        server = _make_server()
        assert "spellbook/sessions/{session_id}/messages" in server._event_topics

    def test_build_status_topic_declared(self):
        server = _make_server()
        desc = server._event_topics["spellbook/sessions/{session_id}/build/status"]
        assert desc.retained is True

    async def test_events_capability_advertised(self):
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
            assert "spellbook/sessions/{session_id}/messages" in patterns
            assert "spellbook/sessions/{session_id}/build/status" in patterns
            # Verify descriptions are present
            for t in topics:
                desc = t.get("description") if isinstance(t, dict) else getattr(t, "description", None)
                assert desc is not None, f"Topic {t} missing description"


class TestEventEmissionOnSend:
    """Verify that messaging_send emits events to subscribed sessions."""

    async def test_recipient_receives_event_on_send(self):
        """Session B subscribes to its messages topic. Session A sends a
        message via emit_event. Session B's subscription receives the event."""
        server = _make_server()

        received_notifications: list[Any] = []

        async with Client(server) as client_a:
            session_a = list(server._active_sessions.values())[0]
            session_a_id = getattr(session_a, "_fastmcp_event_session_id")

            async with Client(server) as client_b:
                # Find session B (the one that is not session A)
                session_b = [
                    s for s in server._active_sessions.values() if s is not session_a
                ][0]
                session_b_id = getattr(session_b, "_fastmcp_event_session_id")

                # Subscribe session B to its messages topic
                await server._subscription_registry.add(
                    session_b_id, "spellbook/sessions/session-b/messages"
                )

                # Capture notifications sent to session B
                original_send = session_b.send_notification

                async def capturing_send(notification, related_request_id=None):
                    received_notifications.append(notification)

                session_b.send_notification = capturing_send

                # Emit an event targeting session B (simulating what
                # messaging_send does after a successful queue delivery)
                await server.emit_event(
                    topic="spellbook/sessions/session-b/messages",
                    payload={
                        "message_id": "test-msg-001",
                        "sender": "session-a",
                        "recipient": "session-b",
                        "payload": {"greeting": "hello from A"},
                        "correlation_id": None,
                    },
                    source="spellbook/messaging",
                    requested_effects=[
                        EventEffect(type="inject_context", priority="high"),
                    ],
                )

                # Verify session B received the event
                assert len(received_notifications) == 1
                notif = received_notifications[0]
                assert isinstance(notif, EventEmitNotification)
                assert notif.params.topic == "spellbook/sessions/session-b/messages"
                assert notif.params.payload["sender"] == "session-a"
                assert notif.params.payload["payload"] == {"greeting": "hello from A"}
                assert notif.params.source == "spellbook/messaging"

    async def test_sender_does_not_receive_event(self):
        """Session A sends a message to B. A should NOT receive the event
        because A is not subscribed to B's topic."""
        server = _make_server()

        sender_notifications: list[Any] = []

        async with Client(server) as client_a:
            session_a = list(server._active_sessions.values())[0]
            session_a_id = getattr(session_a, "_fastmcp_event_session_id")

            # Subscribe session A to its OWN messages topic (not B's)
            await server._subscription_registry.add(
                session_a_id, "spellbook/sessions/session-a/messages"
            )

            # Capture notifications sent to session A
            original_send = session_a.send_notification

            async def capturing_send(notification, related_request_id=None):
                sender_notifications.append(notification)

            session_a.send_notification = capturing_send

            async with Client(server) as client_b:
                session_b = [
                    s for s in server._active_sessions.values() if s is not session_a
                ][0]
                session_b_id = getattr(session_b, "_fastmcp_event_session_id")

                # Subscribe session B to its own messages topic
                await server._subscription_registry.add(
                    session_b_id, "spellbook/sessions/session-b/messages"
                )

                # Emit event targeting session B
                await server.emit_event(
                    topic="spellbook/sessions/session-b/messages",
                    payload={"sender": "session-a", "payload": {"hello": "B"}},
                    source="spellbook/messaging",
                )

                # Session A should NOT have received this event
                assert len(sender_notifications) == 0

    async def test_wildcard_subscription_receives_all_sessions(self):
        """A session subscribed with a wildcard pattern receives events for
        any session_id."""
        server = _make_server()

        received: list[Any] = []

        async with Client(server) as client:
            session = list(server._active_sessions.values())[0]
            session_id = getattr(session, "_fastmcp_event_session_id")

            # Subscribe with wildcard: all sessions' messages
            await server._subscription_registry.add(
                session_id, "spellbook/sessions/+/messages"
            )

            original_send = session.send_notification

            async def capturing_send(notification, related_request_id=None):
                received.append(notification)

            session.send_notification = capturing_send

            # Emit to two different session topics
            await server.emit_event(
                "spellbook/sessions/alpha/messages",
                payload={"from": "alpha"},
            )
            await server.emit_event(
                "spellbook/sessions/beta/messages",
                payload={"from": "beta"},
            )

            assert len(received) == 2
            topics = {n.params.topic for n in received}
            assert topics == {
                "spellbook/sessions/alpha/messages",
                "spellbook/sessions/beta/messages",
            }


class TestRetainedEvents:
    """Verify retained event behavior for build/status topic."""

    async def test_retained_event_stored(self):
        """Emitting to a retained topic stores the value.

        Note: parameterized topic patterns (with {session_id}) require
        explicit retained=True on emit since the exact lookup for the
        descriptor won't match the concrete topic string.
        """
        server = _make_server()

        await server.emit_event(
            "spellbook/sessions/worker-1/build/status",
            payload={"status": "building", "progress": 42},
            retained=True,
        )

        stored = await server._retained_store.get(
            "spellbook/sessions/worker-1/build/status"
        )
        assert stored is not None
        assert stored.payload["status"] == "building"
        assert stored.payload["progress"] == 42
        assert stored.topic == "spellbook/sessions/worker-1/build/status"
        assert stored.event_id is not None and len(stored.event_id) > 0

    async def test_retained_event_overwritten(self):
        """New retained events replace previous ones for the same topic."""
        server = _make_server()

        await server.emit_event(
            "spellbook/sessions/worker-1/build/status",
            payload={"status": "building"},
            retained=True,
        )

        first_stored = await server._retained_store.get(
            "spellbook/sessions/worker-1/build/status"
        )
        assert first_stored is not None
        first_event_id = first_stored.event_id

        await server.emit_event(
            "spellbook/sessions/worker-1/build/status",
            payload={"status": "complete"},
            retained=True,
        )

        stored = await server._retained_store.get(
            "spellbook/sessions/worker-1/build/status"
        )
        assert stored is not None
        assert stored.payload["status"] == "complete"
        # Verify old payload is truly gone (not merged)
        assert "building" not in str(stored.payload)
        # Verify event_id was updated (new event replaces old)
        assert stored.event_id is not None
        assert stored.event_id != first_event_id
        assert stored.topic == "spellbook/sessions/worker-1/build/status"


    async def test_retained_event_delivered_on_subscribe(self):
        """When a client subscribes to a topic with a retained event,
        the retained value is included in the subscribe result via get_matching."""
        server = _make_server()

        # Emit a retained event before any subscriptions exist
        await server.emit_event(
            "spellbook/sessions/worker-1/build/status",
            payload={"status": "passing", "commit": "abc123"},
            retained=True,
        )

        # Verify retained store has the event
        stored = await server._retained_store.get(
            "spellbook/sessions/worker-1/build/status"
        )
        assert stored is not None

        # Simulate what subscribe does: get_matching returns retained events
        # for patterns matching the topic
        matching = await server._retained_store.get_matching(
            "spellbook/sessions/+/build/status"
        )
        assert len(matching) >= 1
        matched_topics = [m.topic for m in matching]
        assert "spellbook/sessions/worker-1/build/status" in matched_topics

        # Verify the retained event payload is complete
        match = next(
            m for m in matching
            if m.topic == "spellbook/sessions/worker-1/build/status"
        )
        assert match.payload["status"] == "passing"
        assert match.payload["commit"] == "abc123"
        assert match.event_id is not None


class TestMessagingSendEventIntegration:
    """End-to-end test: messaging_send tool emits events alongside queue delivery."""

    async def test_messaging_send_emits_event(self, monkeypatch):
        """Use a patched messaging bus with the real mcp event infrastructure.
        Verify that calling messaging_send produces both queue delivery AND
        event emission."""
        from spellbook.messaging.bus import MessageBus
        import spellbook.mcp.tools.messaging as tools_mod

        # Create a fresh bus and patch it into the tools module
        bus = MessageBus(queue_size=64)
        monkeypatch.setattr(tools_mod, "message_bus", bus)

        # Register sender and recipient on the bus (no SSE)
        await bus.register("session-a", enable_sse=False)
        await bus.register("session-b", enable_sse=False)

        # Track emit_event calls on the mcp instance
        from spellbook.mcp.server import mcp

        emitted_events: list[dict] = []
        original_emit = mcp.emit_event

        async def tracking_emit(topic, payload, **kwargs):
            emitted_events.append({"topic": topic, "payload": payload, **kwargs})
            # Don't call original since no sessions are actually connected
            # to the spellbook global mcp singleton in this test context

        monkeypatch.setattr(mcp, "emit_event", tracking_emit)

        # Call the tool function (bypass the decorator)
        result = await tools_mod.messaging_send.__wrapped__(
            sender="session-a",
            recipient="session-b",
            payload='{"task": "run tests"}',
        )

        assert result["ok"] is True

        # Verify queue delivery happened
        messages, _ = await bus.poll("session-b", max_messages=10)
        assert len(messages) == 1
        assert messages[0]["sender"] == "session-a"
        assert messages[0]["payload"] == {"task": "run tests"}

        # Verify event was emitted
        assert len(emitted_events) == 1
        evt = emitted_events[0]
        assert evt["topic"] == "spellbook/sessions/session-b/messages"
        assert evt["payload"]["sender"] == "session-a"
        assert evt["payload"]["recipient"] == "session-b"
        assert evt["payload"]["payload"] == {"task": "run tests"}
        assert evt["source"] == "spellbook/messaging"
        # Verify the message_id is present in the payload
        assert "message_id" in evt["payload"]
        # Verify requested_effects include inject_context for cross-session messages
        assert "requested_effects" in evt
        effects = evt["requested_effects"]
        assert len(effects) >= 1
        effect_types = [e.type for e in effects]
        assert "inject_context" in effect_types

    async def test_messaging_send_event_not_emitted_on_failure(self, monkeypatch):
        """If the bus send fails, no event should be emitted."""
        from spellbook.messaging.bus import MessageBus
        import spellbook.mcp.tools.messaging as tools_mod

        bus = MessageBus(queue_size=64)
        monkeypatch.setattr(tools_mod, "message_bus", bus)

        # Register only the sender
        await bus.register("sender-only", enable_sse=False)

        from spellbook.mcp.server import mcp

        emitted_events: list[dict] = []
        original_emit = mcp.emit_event

        async def tracking_emit(topic, payload, **kwargs):
            emitted_events.append({"topic": topic, "payload": payload})

        monkeypatch.setattr(mcp, "emit_event", tracking_emit)

        # Send to nonexistent recipient
        result = await tools_mod.messaging_send.__wrapped__(
            sender="sender-only",
            recipient="nonexistent",
            payload='{"hello": "world"}',
        )

        assert result["ok"] is False
        assert result["error"] == "recipient_not_found"

        # No event should have been emitted
        assert len(emitted_events) == 0
