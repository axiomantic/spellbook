"""Unit and integration tests for cross-session messaging."""

import asyncio
import json

import pytest

from spellbook.messaging.bus import (
    DEFAULT_CORRELATION_TTL,
    QUEUE_SIZE,
    MessageBus,
    MessageEnvelope,
    SessionRegistration,
    _DISCONNECT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh MessageBus instance per test (not the singleton)."""
    return MessageBus(queue_size=16)


@pytest.fixture
def small_bus():
    """Bus with tiny queue for overflow testing."""
    return MessageBus(queue_size=2)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    @pytest.mark.asyncio
    async def test_register_success(self, bus):
        reg = await bus.register("session-a", enable_sse=False)
        assert reg.alias == "session-a"
        assert isinstance(reg.queue, asyncio.Queue)
        assert reg.registered_at  # ISO 8601 string

    @pytest.mark.asyncio
    async def test_register_duplicate_alias_raises(self, bus):
        await bus.register("dup", enable_sse=False)
        with pytest.raises(ValueError, match="Alias already registered"):
            await bus.register("dup", enable_sse=False)

    @pytest.mark.asyncio
    async def test_register_force_replaces(self, bus):
        old_reg = await bus.register("force-me", enable_sse=False)
        new_reg = await bus.register("force-me", enable_sse=False, force=True)
        assert new_reg.alias == "force-me"
        # Old queue gets disconnect sentinel
        sentinel = old_reg.queue.get_nowait()
        assert sentinel is _DISCONNECT

    @pytest.mark.asyncio
    async def test_unregister_success(self, bus):
        await bus.register("gone", enable_sse=False)
        removed = await bus.unregister("gone")
        assert removed is True
        sessions = await bus.list_sessions()
        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_unregister_nonexistent(self, bus):
        removed = await bus.unregister("nope")
        assert removed is False

    @pytest.mark.asyncio
    async def test_list_sessions(self, bus):
        await bus.register("alpha", enable_sse=False)
        await bus.register("beta", enable_sse=False)
        sessions = await bus.list_sessions()
        aliases = {s["alias"] for s in sessions}
        assert aliases == {"alpha", "beta"}


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

class TestSending:
    @pytest.mark.asyncio
    async def test_send_direct(self, bus):
        await bus.register("sender", enable_sse=False)
        reg_b = await bus.register("receiver", enable_sse=False)
        result = await bus.send("sender", "receiver", {"hello": "world"})
        assert result["ok"] is True
        assert "message_id" in result
        envelope = reg_b.queue.get_nowait()
        assert envelope.sender == "sender"
        assert envelope.recipient == "receiver"
        assert envelope.payload == {"hello": "world"}
        assert envelope.message_type == "direct"

    @pytest.mark.asyncio
    async def test_send_to_nonexistent(self, bus):
        await bus.register("sender", enable_sse=False)
        result = await bus.send("sender", "ghost", {"hi": 1})
        assert result["ok"] is False
        assert result["error"] == "recipient_not_found"

    @pytest.mark.asyncio
    async def test_send_unregistered_sender(self, bus):
        await bus.register("receiver", enable_sse=False)
        result = await bus.send("nobody", "receiver", {"hi": 1})
        assert result["ok"] is False
        assert result["error"] == "sender_not_registered"

    @pytest.mark.asyncio
    async def test_send_queue_full(self, small_bus):
        await small_bus.register("sender", enable_sse=False)
        await small_bus.register("receiver", enable_sse=False)
        # Fill queue (size 2)
        await small_bus.send("sender", "receiver", {"msg": 1})
        await small_bus.send("sender", "receiver", {"msg": 2})
        result = await small_bus.send("sender", "receiver", {"msg": 3})
        assert result["ok"] is False
        assert result["error"] == "recipient_queue_full"

    @pytest.mark.asyncio
    async def test_self_message(self, bus):
        reg = await bus.register("echo", enable_sse=False)
        result = await bus.send("echo", "echo", {"self": True})
        assert result["ok"] is True
        envelope = reg.queue.get_nowait()
        assert envelope.sender == "echo"
        assert envelope.recipient == "echo"


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_all(self, bus):
        await bus.register("broadcaster", enable_sse=False)
        reg_b = await bus.register("listener-b", enable_sse=False)
        reg_c = await bus.register("listener-c", enable_sse=False)
        result = await bus.broadcast("broadcaster", {"announcement": True})
        assert result["ok"] is True
        assert result["delivered_count"] == 2
        # Sender excluded by default
        assert bus._sessions["broadcaster"].queue.empty()
        # Drain and verify envelope content for both listeners
        env_b = reg_b.queue.get_nowait()
        assert env_b.sender == "broadcaster"
        assert env_b.recipient == "*"
        assert env_b.payload == {"announcement": True}
        assert env_b.message_type == "broadcast"
        env_c = reg_c.queue.get_nowait()
        assert env_c.sender == "broadcaster"
        assert env_c.recipient == "*"
        assert env_c.payload == {"announcement": True}
        assert env_c.message_type == "broadcast"

    @pytest.mark.asyncio
    async def test_broadcast_include_self(self, bus):
        reg = await bus.register("self-bc", enable_sse=False)
        result = await bus.broadcast("self-bc", {"echo": True}, exclude_sender=False)
        assert result["ok"] is True
        assert result["delivered_count"] == 1
        # Drain and verify envelope content
        env = reg.queue.get_nowait()
        assert env.sender == "self-bc"
        assert env.recipient == "*"
        assert env.payload == {"echo": True}
        assert env.message_type == "broadcast"

    @pytest.mark.asyncio
    async def test_broadcast_zero_recipients(self, bus):
        await bus.register("alone", enable_sse=False)
        result = await bus.broadcast("alone", {"lonely": True})
        assert result["ok"] is True
        assert result["delivered_count"] == 0

    @pytest.mark.asyncio
    async def test_broadcast_unregistered_sender(self, bus):
        result = await bus.broadcast("ghost", {"hi": 1})
        assert result["ok"] is False
        assert result["error"] == "sender_not_registered"


# ---------------------------------------------------------------------------
# Reply / Correlation
# ---------------------------------------------------------------------------

class TestReplyCorrelation:
    @pytest.mark.asyncio
    async def test_reply_success(self, bus):
        reg_a = await bus.register("requester", enable_sse=False)
        await bus.register("responder", enable_sse=False)
        # Send with correlation
        await bus.send(
            "requester", "responder",
            {"question": "status?"},
            correlation_id="corr-1",
        )
        # Responder replies
        result = await bus.reply("responder", "corr-1", {"answer": "ok"})
        assert result["ok"] is True
        # Reply lands in requester's queue
        envelope = reg_a.queue.get_nowait()
        assert envelope.message_type == "reply"
        assert envelope.correlation_id == "corr-1"
        assert envelope.payload == {"answer": "ok"}

    @pytest.mark.asyncio
    async def test_reply_expired_correlation(self, bus):
        bus_with_short_ttl = MessageBus(queue_size=16)
        await bus_with_short_ttl.register("req", enable_sse=False)
        await bus_with_short_ttl.register("resp", enable_sse=False)
        await bus_with_short_ttl.send(
            "req", "resp", {"q": 1}, correlation_id="expired-1", ttl=0,
        )
        # TTL=0 means it expires immediately on next sweep
        # Force a sweep by calling stats or reply
        result = await bus_with_short_ttl.reply("resp", "expired-1", {"a": 1})
        assert result["ok"] is False
        assert result["error"] == "correlation_not_found_or_expired"

    @pytest.mark.asyncio
    async def test_reply_sender_disconnected(self, bus):
        await bus.register("req2", enable_sse=False)
        await bus.register("resp2", enable_sse=False)
        await bus.send("req2", "resp2", {"q": 1}, correlation_id="corr-dc")
        # Requester disconnects -- unregister cleans up their correlations
        await bus.unregister("req2")
        result = await bus.reply("resp2", "corr-dc", {"a": 1})
        assert result["ok"] is False
        # Correlation was cleaned up by unregister, so reply finds nothing
        assert result["error"] == "correlation_not_found_or_expired"

    @pytest.mark.asyncio
    async def test_correlation_sweep(self, bus):
        await bus.register("sweeper", enable_sse=False)
        await bus.register("target", enable_sse=False)
        await bus.send(
            "sweeper", "target", {"q": 1},
            correlation_id="sweep-test", ttl=0,
        )
        # Sweep via stats
        stats = await bus.stats()
        assert stats["pending_correlations"] == 0  # TTL=0 -> swept


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

class TestPolling:
    @pytest.mark.asyncio
    async def test_poll_messages(self, bus):
        await bus.register("poller-sender", enable_sse=False)
        await bus.register("poller", enable_sse=False)
        await bus.send("poller-sender", "poller", {"msg": 1})
        await bus.send("poller-sender", "poller", {"msg": 2})
        messages = await bus.poll("poller", max_messages=10)
        assert len(messages) == 2
        assert messages[0]["payload"] == {"msg": 1}
        assert messages[1]["payload"] == {"msg": 2}
        # Queue now empty
        messages2 = await bus.poll("poller", max_messages=10)
        assert len(messages2) == 0

    @pytest.mark.asyncio
    async def test_poll_empty(self, bus):
        await bus.register("empty-poller", enable_sse=False)
        messages = await bus.poll("empty-poller", max_messages=10)
        assert messages == []

    @pytest.mark.asyncio
    async def test_poll_unregistered(self, bus):
        messages = await bus.poll("nonexistent", max_messages=10)
        assert messages == []

    @pytest.mark.asyncio
    async def test_poll_respects_max(self, bus):
        await bus.register("limited-sender", enable_sse=False)
        await bus.register("limited-poller", enable_sse=False)
        for i in range(5):
            await bus.send("limited-sender", "limited-poller", {"i": i})
        messages = await bus.poll("limited-poller", max_messages=2)
        assert len(messages) == 2
        # 3 remaining
        remaining = await bus.poll("limited-poller", max_messages=10)
        assert len(remaining) == 3


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    @pytest.mark.asyncio
    async def test_stats_accurate(self, bus):
        await bus.register("s1", enable_sse=False)
        await bus.register("s2", enable_sse=False)
        await bus.send("s1", "s2", {"a": 1})
        await bus.broadcast("s1", {"b": 2})
        stats = await bus.stats()
        assert stats["sessions_registered"] == 2
        assert stats["total_sent"] == 2  # 1 direct + 1 broadcast delivery
        assert stats["total_delivered"] == 2
        assert stats["total_errors"] == 0


# ---------------------------------------------------------------------------
# MessageEnvelope
# ---------------------------------------------------------------------------

class TestMessageEnvelope:
    def test_to_dict(self):
        env = MessageEnvelope(
            id="test-id",
            sender="a",
            recipient="b",
            payload={"k": "v"},
            timestamp="2026-04-03T00:00:00Z",
            message_type="direct",
            correlation_id="c1",
            reply_to=None,
            ttl=60,
        )
        d = env.to_dict()
        assert d == {
            "id": "test-id",
            "sender": "a",
            "recipient": "b",
            "payload": {"k": "v"},
            "timestamp": "2026-04-03T00:00:00Z",
            "message_type": "direct",
            "correlation_id": "c1",
            "reply_to": None,
            "ttl": 60,
        }
