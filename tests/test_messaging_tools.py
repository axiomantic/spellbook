"""Tests for MCP tool wrappers for cross-session messaging.

Tests call tool functions directly (bypassing MCP protocol), patching
the module-level message_bus singleton with a fresh test bus per test.
"""

import asyncio
import json
from datetime import datetime

import pytest

from spellbook.messaging.bus import MessageBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bus():
    """Fresh MessageBus instance per test (not the singleton)."""
    return MessageBus(queue_size=16)


@pytest.fixture
def large_bus():
    """MessageBus with larger queue for overflow/clamping tests."""
    return MessageBus(queue_size=64)


@pytest.fixture
def _patch_bus(bus, monkeypatch):
    """Replace message_bus in the tools module with the test bus fixture."""
    import spellbook.mcp.tools.messaging as tools_mod

    monkeypatch.setattr(tools_mod, "message_bus", bus)
    return bus


@pytest.fixture
def _patch_large_bus(large_bus, monkeypatch):
    """Replace message_bus with a larger queue for clamping tests."""
    import spellbook.mcp.tools.messaging as tools_mod

    monkeypatch.setattr(tools_mod, "message_bus", large_bus)
    return large_bus


# ---------------------------------------------------------------------------
# messaging_register
# ---------------------------------------------------------------------------


class TestMessagingRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register

        result = await messaging_register.__wrapped__(
            alias="tool-test", enable_sse=False,
        )
        # Pop the dynamic timestamp and verify it independently
        registered_at = result.pop("registered_at")
        # agent_id and fastmcp_session_id are both None when the tool is
        # called outside an MCP request context (as here via __wrapped__
        # direct invocation) and the caller did not pass an explicit
        # agent_id.
        assert result == {
            "ok": True,
            "alias": "tool-test",
            "agent_id": None,
            "fastmcp_session_id": None,
        }
        # Verify registered_at parses as ISO 8601
        parsed_dt = datetime.fromisoformat(registered_at)
        assert parsed_dt is not None

    @pytest.mark.asyncio
    async def test_register_invalid_alias_special_chars(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register

        result = await messaging_register.__wrapped__(
            alias="bad alias!", enable_sse=False,
        )
        assert result == {
            "ok": False,
            "error": "invalid_alias",
            "detail": "Alias must be 1-64 chars, alphanumeric/hyphens/underscores only.",
        }

    @pytest.mark.asyncio
    async def test_register_alias_too_long(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register

        result = await messaging_register.__wrapped__(
            alias="a" * 65, enable_sse=False,
        )
        assert result == {
            "ok": False,
            "error": "invalid_alias",
            "detail": "Alias must be 1-64 chars, alphanumeric/hyphens/underscores only.",
        }

    @pytest.mark.asyncio
    async def test_register_empty_alias(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register

        result = await messaging_register.__wrapped__(
            alias="", enable_sse=False,
        )
        assert result == {
            "ok": False,
            "error": "invalid_alias",
            "detail": "Alias must be 1-64 chars, alphanumeric/hyphens/underscores only.",
        }

    @pytest.mark.asyncio
    async def test_register_duplicate_without_force(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register

        await messaging_register.__wrapped__(alias="taken", enable_sse=False)
        result = await messaging_register.__wrapped__(alias="taken", enable_sse=False)
        assert result["ok"] is False
        assert result["error"] == "alias_already_registered"
        assert result["alias"] == "taken"

    @pytest.mark.asyncio
    async def test_register_force_replaces(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register

        await messaging_register.__wrapped__(alias="replaceable", enable_sse=False)
        result = await messaging_register.__wrapped__(
            alias="replaceable", enable_sse=False, force=True,
        )
        registered_at = result.pop("registered_at")
        assert result == {
            "ok": True,
            "alias": "replaceable",
            "agent_id": None,
            "fastmcp_session_id": None,
        }
        parsed_dt = datetime.fromisoformat(registered_at)
        assert parsed_dt is not None


# ---------------------------------------------------------------------------
# messaging_unregister
# ---------------------------------------------------------------------------


class TestMessagingUnregister:
    @pytest.mark.asyncio
    async def test_unregister_success(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_unregister

        await messaging_register.__wrapped__(alias="unreg-me", enable_sse=False)
        result = await messaging_unregister.__wrapped__(alias="unreg-me")
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_unregister_not_found(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_unregister

        result = await messaging_unregister.__wrapped__(alias="never-registered")
        assert result == {"ok": False, "error": "not_found"}


# ---------------------------------------------------------------------------
# messaging_send
# ---------------------------------------------------------------------------


class TestMessagingSend:
    @pytest.mark.asyncio
    async def test_send_success(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="tool-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="tool-receiver", enable_sse=False)
        result = await messaging_send.__wrapped__(
            sender="tool-sender",
            recipient="tool-receiver",
            payload='{"task": "test"}',
        )
        assert result["ok"] is True
        assert isinstance(result["message_id"], str)
        assert len(result["message_id"]) > 0

    @pytest.mark.asyncio
    async def test_send_invalid_json(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="json-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="json-receiver", enable_sse=False)
        result = await messaging_send.__wrapped__(
            sender="json-sender",
            recipient="json-receiver",
            payload="not valid json {{{",
        )
        assert result["ok"] is False
        assert result["error"] == "invalid_payload_json"

    @pytest.mark.asyncio
    async def test_send_non_object_json(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="arr-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="arr-receiver", enable_sse=False)
        result = await messaging_send.__wrapped__(
            sender="arr-sender",
            recipient="arr-receiver",
            payload='[1, 2, 3]',
        )
        assert result["ok"] is False
        assert result["error"] == "invalid_payload_json"
        assert result["detail"] == "Payload must be a JSON object."

    @pytest.mark.asyncio
    async def test_send_with_correlation(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="corr-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="corr-receiver", enable_sse=False)
        result = await messaging_send.__wrapped__(
            sender="corr-sender",
            recipient="corr-receiver",
            payload='{"q": "status?"}',
            correlation_id="test-corr-1",
        )
        assert result["ok"] is True
        assert isinstance(result["message_id"], str)

    @pytest.mark.asyncio
    async def test_send_ttl_clamped_high(self, _patch_bus, bus):
        """TTL > 300 should be clamped to 300."""
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="ttl-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="ttl-receiver", enable_sse=False)
        result = await messaging_send.__wrapped__(
            sender="ttl-sender",
            recipient="ttl-receiver",
            payload='{"test": 1}',
            correlation_id="ttl-corr",
            ttl=999,
        )
        assert result["ok"] is True
        # Verify the correlation was created with clamped TTL
        pending = bus._pending_correlations.get("ttl-corr")
        assert pending is not None
        assert pending.ttl == 300

    @pytest.mark.asyncio
    async def test_send_ttl_clamped_low(self, _patch_bus, bus):
        """TTL < 1 should be clamped to 1."""
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="ttl-lo-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="ttl-lo-receiver", enable_sse=False)
        result = await messaging_send.__wrapped__(
            sender="ttl-lo-sender",
            recipient="ttl-lo-receiver",
            payload='{"test": 1}',
            correlation_id="ttl-lo-corr",
            ttl=-5,
        )
        assert result["ok"] is True
        pending = bus._pending_correlations.get("ttl-lo-corr")
        assert pending is not None
        assert pending.ttl == 1

    @pytest.mark.asyncio
    async def test_send_correlation_id_too_long(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="long-corr-s", enable_sse=False)
        await messaging_register.__wrapped__(alias="long-corr-r", enable_sse=False)
        result = await messaging_send.__wrapped__(
            sender="long-corr-s",
            recipient="long-corr-r",
            payload='{"x": 1}',
            correlation_id="c" * 129,
        )
        assert result == {
            "ok": False,
            "error": "correlation_id_too_long",
            "detail": "Max 128 chars.",
        }

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_recipient(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="lonely-sender", enable_sse=False)
        result = await messaging_send.__wrapped__(
            sender="lonely-sender",
            recipient="ghost",
            payload='{"hi": 1}',
        )
        assert result["ok"] is False
        assert result["error"] == "recipient_not_found"

    @pytest.mark.asyncio
    async def test_send_unregistered_sender(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="target", enable_sse=False)
        result = await messaging_send.__wrapped__(
            sender="nobody",
            recipient="target",
            payload='{"hi": 1}',
        )
        assert result["ok"] is False
        assert result["error"] == "sender_not_registered"

    @pytest.mark.asyncio
    async def test_send_payload_too_large(self, _patch_bus):
        """Payload exceeding 64KB should be rejected."""
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send

        await messaging_register.__wrapped__(alias="big-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="big-receiver", enable_sse=False)
        # Create a payload that exceeds 64KB (65536 bytes)
        large_value = "x" * 70000
        result = await messaging_send.__wrapped__(
            sender="big-sender",
            recipient="big-receiver",
            payload=json.dumps({"data": large_value}),
        )
        assert result == {
            "ok": False,
            "error": "payload_too_large",
            "detail": "Payload exceeds 65536 bytes.",
        }


# ---------------------------------------------------------------------------
# messaging_broadcast
# ---------------------------------------------------------------------------


class TestMessagingBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_success(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_broadcast

        await messaging_register.__wrapped__(alias="bc-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="bc-listener", enable_sse=False)
        result = await messaging_broadcast.__wrapped__(
            sender="bc-sender",
            payload='{"info": "all"}',
        )
        assert result["ok"] is True
        assert result["delivered_count"] == 1
        assert result["failed_count"] == 0
        assert result["errors"] is None
        assert result["delivered_aliases"] == ["bc-listener"]

    @pytest.mark.asyncio
    async def test_broadcast_include_self(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_broadcast

        await messaging_register.__wrapped__(alias="bc-self", enable_sse=False)
        result = await messaging_broadcast.__wrapped__(
            sender="bc-self",
            payload='{"echo": true}',
            include_self=True,
        )
        assert result["ok"] is True
        assert result["delivered_count"] == 1
        assert result["failed_count"] == 0
        assert result["errors"] is None
        assert result["delivered_aliases"] == ["bc-self"]

    @pytest.mark.asyncio
    async def test_broadcast_invalid_json(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_broadcast

        await messaging_register.__wrapped__(alias="bc-bad", enable_sse=False)
        result = await messaging_broadcast.__wrapped__(
            sender="bc-bad",
            payload="not json",
        )
        assert result["ok"] is False
        assert result["error"] == "invalid_payload_json"

    @pytest.mark.asyncio
    async def test_broadcast_unregistered_sender(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_broadcast

        result = await messaging_broadcast.__wrapped__(
            sender="ghost",
            payload='{"hi": 1}',
        )
        assert result["ok"] is False
        assert result["error"] == "sender_not_registered"


# ---------------------------------------------------------------------------
# messaging_reply
# ---------------------------------------------------------------------------


class TestMessagingReply:
    @pytest.mark.asyncio
    async def test_reply_success(self, _patch_bus):
        from spellbook.mcp.tools.messaging import (
            messaging_register, messaging_send, messaging_reply, messaging_poll,
        )

        await messaging_register.__wrapped__(alias="req-tool", enable_sse=False)
        await messaging_register.__wrapped__(alias="resp-tool", enable_sse=False)
        await messaging_send.__wrapped__(
            sender="req-tool",
            recipient="resp-tool",
            payload='{"q": "status?"}',
            correlation_id="tool-corr-1",
        )
        result = await messaging_reply.__wrapped__(
            sender="resp-tool",
            correlation_id="tool-corr-1",
            payload='{"a": "ok"}',
        )
        assert result["ok"] is True
        assert isinstance(result["message_id"], str)
        assert result["recipient"] == "req-tool"

        # Verify reply arrives at the requester
        poll_result = await messaging_poll.__wrapped__(alias="req-tool")
        assert poll_result["ok"] is True
        assert len(poll_result["messages"]) == 1
        assert poll_result["messages"][0]["correlation_id"] == "tool-corr-1"
        assert poll_result["messages"][0]["payload"] == {"a": "ok"}
        assert poll_result["messages"][0]["message_type"] == "reply"

    @pytest.mark.asyncio
    async def test_reply_invalid_json(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_reply

        result = await messaging_reply.__wrapped__(
            sender="resp",
            correlation_id="some-corr",
            payload="bad json!!!",
        )
        assert result["ok"] is False
        assert result["error"] == "invalid_payload_json"


# ---------------------------------------------------------------------------
# messaging_poll
# ---------------------------------------------------------------------------


class TestMessagingPoll:
    @pytest.mark.asyncio
    async def test_poll_success(self, _patch_bus):
        from spellbook.mcp.tools.messaging import (
            messaging_register, messaging_send, messaging_poll,
        )

        await messaging_register.__wrapped__(alias="poll-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="poll-receiver", enable_sse=False)
        await messaging_send.__wrapped__(
            sender="poll-sender",
            recipient="poll-receiver",
            payload='{"hello": 1}',
        )
        result = await messaging_poll.__wrapped__(alias="poll-receiver")
        assert result["ok"] is True
        assert len(result["messages"]) == 1
        assert result["messages"][0]["payload"] == {"hello": 1}
        assert result["messages"][0]["sender"] == "poll-sender"
        assert result["messages"][0]["recipient"] == "poll-receiver"
        assert result["messages"][0]["message_type"] == "direct"
        assert "remaining" in result
        assert result["remaining"] == 0

    @pytest.mark.asyncio
    async def test_poll_empty(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_poll

        await messaging_register.__wrapped__(alias="empty-poller", enable_sse=False)
        result = await messaging_poll.__wrapped__(alias="empty-poller")
        assert result == {"ok": True, "messages": [], "remaining": 0}

    @pytest.mark.asyncio
    async def test_poll_respects_max(self, _patch_bus):
        from spellbook.mcp.tools.messaging import (
            messaging_register, messaging_send, messaging_poll,
        )

        await messaging_register.__wrapped__(alias="max-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="max-poller", enable_sse=False)
        for i in range(5):
            await messaging_send.__wrapped__(
                sender="max-sender",
                recipient="max-poller",
                payload=json.dumps({"i": i}),
            )
        result = await messaging_poll.__wrapped__(alias="max-poller", max_messages=2)
        assert result["ok"] is True
        assert len(result["messages"]) == 2
        assert result["remaining"] == 3

    @pytest.mark.asyncio
    async def test_poll_clamps_max_messages(self, _patch_large_bus):
        """max_messages > 50 should be clamped to 50."""
        from spellbook.mcp.tools.messaging import messaging_register, messaging_send, messaging_poll

        await messaging_register.__wrapped__(alias="clamp-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="clamp-poller", enable_sse=False)
        # Send 55 messages
        for i in range(55):
            await messaging_send.__wrapped__(
                sender="clamp-sender",
                recipient="clamp-poller",
                payload=json.dumps({"i": i}),
            )
        # Poll with max_messages=999 -- should be clamped to 50
        result = await messaging_poll.__wrapped__(alias="clamp-poller", max_messages=999)
        assert result["ok"] is True
        assert len(result["messages"]) == 50
        assert result["remaining"] == 5

    @pytest.mark.asyncio
    async def test_poll_unregistered_alias(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_poll

        result = await messaging_poll.__wrapped__(alias="nonexistent")
        assert result == {"ok": True, "messages": [], "remaining": 0}


# ---------------------------------------------------------------------------
# messaging_list_sessions
# ---------------------------------------------------------------------------


class TestMessagingListSessions:
    @pytest.mark.asyncio
    async def test_list_sessions(self, _patch_bus):
        from spellbook.mcp.tools.messaging import (
            messaging_register, messaging_list_sessions,
        )

        await messaging_register.__wrapped__(alias="listed-1", enable_sse=False)
        await messaging_register.__wrapped__(alias="listed-2", enable_sse=False)
        result = await messaging_list_sessions.__wrapped__()
        assert result["ok"] is True
        aliases = {s["alias"] for s in result["sessions"]}
        assert aliases == {"listed-1", "listed-2"}
        # Verify each session has registered_at
        for session in result["sessions"]:
            assert "registered_at" in session
            assert isinstance(session["registered_at"], str)

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_list_sessions

        result = await messaging_list_sessions.__wrapped__()
        assert result == {"ok": True, "sessions": []}


# ---------------------------------------------------------------------------
# messaging_stats
# ---------------------------------------------------------------------------


class TestMessagingStats:
    @pytest.mark.asyncio
    async def test_stats_after_registration(self, _patch_bus):
        from spellbook.mcp.tools.messaging import messaging_register, messaging_stats

        await messaging_register.__wrapped__(alias="stats-session", enable_sse=False)
        result = await messaging_stats.__wrapped__()
        assert result == {
            "ok": True,
            "sessions_registered": 1,
            "pending_correlations": 0,
            "total_sent": 0,
            "total_delivered": 0,
            "total_errors": 0,
        }

    @pytest.mark.asyncio
    async def test_stats_after_send(self, _patch_bus):
        from spellbook.mcp.tools.messaging import (
            messaging_register, messaging_send, messaging_stats,
        )

        await messaging_register.__wrapped__(alias="stats-s", enable_sse=False)
        await messaging_register.__wrapped__(alias="stats-r", enable_sse=False)
        await messaging_send.__wrapped__(
            sender="stats-s",
            recipient="stats-r",
            payload='{"x": 1}',
        )
        result = await messaging_stats.__wrapped__()
        assert result == {
            "ok": True,
            "sessions_registered": 2,
            "pending_correlations": 0,
            "total_sent": 1,
            "total_delivered": 1,
            "total_errors": 0,
        }


# ---------------------------------------------------------------------------
# Event emission from broadcast/reply
# ---------------------------------------------------------------------------


class TestBroadcastEventEmission:
    @pytest.mark.asyncio
    async def test_broadcast_emits_events_to_recipients(self, _patch_bus):
        """Broadcast emits v2 events keyed by recipient agent_id."""
        import spellbook.mcp.tools.messaging as tools_mod
        from spellbook.mcp.tools.messaging import messaging_broadcast, messaging_register

        bus = tools_mod.message_bus

        await messaging_register.__wrapped__(alias="b-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="b-recv1", enable_sse=False)
        await messaging_register.__wrapped__(alias="b-recv2", enable_sse=False)

        # Manually map aliases to agent_ids (primary v2 routing key) and
        # to transport UUIDs (for the target_session_ids filter).
        bus._alias_to_agent_id["b-recv1"] = "agent-r1"
        bus._alias_to_agent_id["b-recv2"] = "agent-r2"
        bus._alias_to_fastmcp_session["b-recv1"] = "uuid-r1"
        bus._alias_to_fastmcp_session["b-recv2"] = "uuid-r2"

        emitted: list[dict] = []
        original_emit = tools_mod.mcp.emit_event

        async def tracking_emit(**kwargs):
            emitted.append(kwargs)

        tools_mod.mcp.emit_event = tracking_emit  # type: ignore[assignment]
        try:
            result = await messaging_broadcast.__wrapped__(
                sender="b-sender",
                payload='{"msg": "hi all"}',
            )
        finally:
            tools_mod.mcp.emit_event = original_emit  # type: ignore[assignment]

        assert result["ok"] is True
        assert result["delivered_count"] == 2

        # Verify events emitted for both recipients using v2 topics
        assert len(emitted) == 2
        topics = {e["topic"] for e in emitted}
        assert "agents/agent-r1/messages" in topics
        assert "agents/agent-r2/messages" in topics

        # Check payload shape
        for e in emitted:
            assert e["payload"]["sender"] == "b-sender"
            assert e["payload"]["recipient"] == "*"
            assert e["payload"]["broadcast"] is True
            assert e["source"] == "spellbook/messaging"
            assert e["payload"]["payload"] == {"msg": "hi all"}
            # target_session_ids filter is set to the recipient's
            # transport UUID for defense in depth.
            assert "target_session_ids" in e
            assert len(e["target_session_ids"]) == 1

    @pytest.mark.asyncio
    async def test_broadcast_skips_sessions_without_agent_id(self, _patch_bus):
        """Broadcast skips event emission for sessions without an agent_id."""
        import spellbook.mcp.tools.messaging as tools_mod
        from spellbook.mcp.tools.messaging import messaging_broadcast, messaging_register

        bus = tools_mod.message_bus

        await messaging_register.__wrapped__(alias="b-sender2", enable_sse=False)
        await messaging_register.__wrapped__(alias="b-recv-aid", enable_sse=False)
        await messaging_register.__wrapped__(alias="b-recv-no-aid", enable_sse=False)

        # Only one recipient has an agent_id
        bus._alias_to_agent_id["b-recv-aid"] = "agent-yes"
        bus._alias_to_fastmcp_session["b-recv-aid"] = "uuid-yes"

        emitted: list[dict] = []
        original_emit = tools_mod.mcp.emit_event

        async def tracking_emit(**kwargs):
            emitted.append(kwargs)

        tools_mod.mcp.emit_event = tracking_emit  # type: ignore[assignment]
        try:
            result = await messaging_broadcast.__wrapped__(
                sender="b-sender2",
                payload='{"msg": "hi"}',
            )
        finally:
            tools_mod.mcp.emit_event = original_emit  # type: ignore[assignment]

        assert result["ok"] is True
        assert result["delivered_count"] == 2  # Both get queue delivery
        assert len(emitted) == 1  # Only one gets event
        assert emitted[0]["topic"] == "agents/agent-yes/messages"

    @pytest.mark.asyncio
    async def test_broadcast_event_failure_does_not_block_others(self, _patch_bus):
        """One recipient's event failure doesn't block others."""
        import spellbook.mcp.tools.messaging as tools_mod
        from spellbook.mcp.tools.messaging import messaging_broadcast, messaging_register

        bus = tools_mod.message_bus

        await messaging_register.__wrapped__(alias="b-sender3", enable_sse=False)
        await messaging_register.__wrapped__(alias="b-fail", enable_sse=False)
        await messaging_register.__wrapped__(alias="b-ok", enable_sse=False)

        bus._alias_to_agent_id["b-fail"] = "agent-fail"
        bus._alias_to_agent_id["b-ok"] = "agent-ok"
        bus._alias_to_fastmcp_session["b-fail"] = "uuid-fail"
        bus._alias_to_fastmcp_session["b-ok"] = "uuid-ok"

        successful_emits: list[dict] = []
        original_emit = tools_mod.mcp.emit_event

        async def flaky_emit(**kwargs):
            if "agent-fail" in kwargs.get("topic", ""):
                raise RuntimeError("emit failed")
            successful_emits.append(kwargs)

        tools_mod.mcp.emit_event = flaky_emit  # type: ignore[assignment]
        try:
            result = await messaging_broadcast.__wrapped__(
                sender="b-sender3",
                payload='{"msg": "test"}',
            )
        finally:
            tools_mod.mcp.emit_event = original_emit  # type: ignore[assignment]

        assert result["ok"] is True
        # The non-failing recipient still got its event
        assert len(successful_emits) == 1
        assert successful_emits[0]["topic"] == "agents/agent-ok/messages"


class TestReplyEventEmission:
    @pytest.mark.asyncio
    async def test_reply_emits_event_to_original_sender(self, _patch_bus):
        """Reply emits a v2 event to the original sender's agent topic."""
        import spellbook.mcp.tools.messaging as tools_mod
        from spellbook.mcp.tools.messaging import (
            messaging_register,
            messaging_reply,
            messaging_send,
        )

        bus = tools_mod.message_bus

        await messaging_register.__wrapped__(alias="rq-sender", enable_sse=False)
        await messaging_register.__wrapped__(alias="rq-replier", enable_sse=False)

        bus._alias_to_agent_id["rq-sender"] = "agent-sender"
        bus._alias_to_fastmcp_session["rq-sender"] = "uuid-sender"

        emitted: list[dict] = []
        original_emit = tools_mod.mcp.emit_event

        async def tracking_emit(**kwargs):
            emitted.append(kwargs)

        tools_mod.mcp.emit_event = tracking_emit  # type: ignore[assignment]
        try:
            # Send initial message with correlation
            await messaging_send.__wrapped__(
                sender="rq-sender",
                recipient="rq-replier",
                payload='{"q": "status?"}',
                correlation_id="corr-1",
            )

            # Reply
            result = await messaging_reply.__wrapped__(
                sender="rq-replier",
                correlation_id="corr-1",
                payload='{"a": "ok"}',
            )
        finally:
            tools_mod.mcp.emit_event = original_emit  # type: ignore[assignment]

        assert result["ok"] is True
        assert result["recipient"] == "rq-sender"

        # Verify event emitted to original sender (filter to reply event only)
        reply_calls = [
            e for e in emitted
            if e.get("payload", {}).get("is_reply")
        ]
        assert len(reply_calls) == 1
        c = reply_calls[0]
        assert c["topic"] == "agents/agent-sender/messages"
        # correlation_id lives in the payload under v2, not on the wire
        assert c["payload"]["correlation_id"] == "corr-1"
        assert c["payload"]["sender"] == "rq-replier"
        assert "correlation_id" not in c
        assert c["source"] == "spellbook/messaging"

    @pytest.mark.asyncio
    async def test_reply_no_agent_id_skips_event(self, _patch_bus):
        """Reply skips event emission when the original sender has no agent_id."""
        import spellbook.mcp.tools.messaging as tools_mod
        from spellbook.mcp.tools.messaging import (
            messaging_register,
            messaging_reply,
            messaging_send,
        )

        await messaging_register.__wrapped__(alias="rq-noid", enable_sse=False)
        await messaging_register.__wrapped__(alias="rq-rep2", enable_sse=False)
        # No agent_id mapping for rq-noid

        emitted: list[dict] = []
        original_emit = tools_mod.mcp.emit_event

        async def tracking_emit(**kwargs):
            emitted.append(kwargs)

        tools_mod.mcp.emit_event = tracking_emit  # type: ignore[assignment]
        try:
            await messaging_send.__wrapped__(
                sender="rq-noid",
                recipient="rq-rep2",
                payload='{"q": "hi"}',
                correlation_id="corr-2",
            )

            result = await messaging_reply.__wrapped__(
                sender="rq-rep2",
                correlation_id="corr-2",
                payload='{"a": "yo"}',
            )
        finally:
            tools_mod.mcp.emit_event = original_emit  # type: ignore[assignment]

        assert result["ok"] is True
        # No event emitted for reply because original sender has no agent_id
        reply_calls = [
            e for e in emitted
            if e.get("payload", {}).get("is_reply")
        ]
        assert len(reply_calls) == 0
