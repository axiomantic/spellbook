"""End-to-end integration tests for cross-session messaging.

Verifies the success criteria from the understanding document:
- Two sessions exchange direct messages
- Broadcast discovery ("who is on project X?")
- Orchestrator coordinates 2+ workers (request/reply)
- SSE delivers messages
- Disconnected target returns error
"""

import asyncio
import json

import httpx
import pytest

from spellbook.messaging.bus import MessageBus, _DISCONNECT
from spellbook.messaging import sse as sse_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bus():
    """Fresh MessageBus instance per test (not the singleton)."""
    return MessageBus(queue_size=64)


# ---------------------------------------------------------------------------
# 1. Two sessions exchange direct messages
# ---------------------------------------------------------------------------


class TestDirectMessageExchange:
    @pytest.mark.asyncio
    async def test_two_sessions_exchange_messages(self, bus):
        """Register session A and B. A sends to B. B polls and gets the message.
        Verify full message envelope fields."""
        reg_a = await bus.register("session-a", enable_sse=False)
        reg_b = await bus.register("session-b", enable_sse=False)

        # A sends to B
        send_result = await bus.send(
            sender="session-a",
            recipient="session-b",
            payload={"greeting": "hello from A"},
        )
        assert send_result["ok"] is True
        assert "message_id" in send_result

        # B polls and gets the message
        messages, _ = await bus.poll("session-b", max_messages=10)
        assert len(messages) == 1

        msg = messages[0]
        # Verify full envelope
        assert msg["sender"] == "session-a"
        assert msg["recipient"] == "session-b"
        assert msg["payload"] == {"greeting": "hello from A"}
        assert msg["message_type"] == "direct"
        assert msg["id"] == send_result["message_id"]
        assert msg["timestamp"]  # non-empty ISO timestamp
        assert msg["correlation_id"] is None
        assert msg["reply_to"] is None
        assert msg["ttl"] == 60  # default TTL

    @pytest.mark.asyncio
    async def test_bidirectional_exchange(self, bus):
        """Both sessions send and receive messages to/from each other."""
        await bus.register("alice", enable_sse=False)
        await bus.register("bob", enable_sse=False)

        await bus.send("alice", "bob", {"msg": "hi bob"})
        await bus.send("bob", "alice", {"msg": "hi alice"})

        alice_msgs, _ = await bus.poll("alice", max_messages=10)
        bob_msgs, _ = await bus.poll("bob", max_messages=10)

        assert len(alice_msgs) == 1
        assert alice_msgs[0]["sender"] == "bob"
        assert alice_msgs[0]["payload"] == {"msg": "hi alice"}

        assert len(bob_msgs) == 1
        assert bob_msgs[0]["sender"] == "alice"
        assert bob_msgs[0]["payload"] == {"msg": "hi bob"}


# ---------------------------------------------------------------------------
# 2. Broadcast discovery ("who is on project X?")
# ---------------------------------------------------------------------------


class TestBroadcastDiscovery:
    @pytest.mark.asyncio
    async def test_broadcast_question_reaches_all_others(self, bus):
        """Register 3 sessions. One broadcasts a question. Others receive it."""
        await bus.register("coordinator", enable_sse=False)
        await bus.register("worker-1", enable_sse=False)
        await bus.register("worker-2", enable_sse=False)

        result = await bus.broadcast(
            sender="coordinator",
            payload={"question": "who is working on project-alpha?"},
            exclude_sender=True,
        )
        assert result["ok"] is True
        assert result["delivered_count"] == 2
        assert result["failed_count"] == 0

        # Both workers received the broadcast
        w1_msgs, _ = await bus.poll("worker-1", max_messages=10)
        w2_msgs, _ = await bus.poll("worker-2", max_messages=10)

        assert len(w1_msgs) == 1
        assert len(w2_msgs) == 1

        for msg in [w1_msgs[0], w2_msgs[0]]:
            assert msg["sender"] == "coordinator"
            assert msg["recipient"] == "*"
            assert msg["message_type"] == "broadcast"
            assert msg["payload"] == {
                "question": "who is working on project-alpha?",
            }

        # Coordinator did NOT receive its own broadcast
        coord_msgs, _ = await bus.poll("coordinator", max_messages=10)
        assert len(coord_msgs) == 0


# ---------------------------------------------------------------------------
# 3. Orchestrator coordinates 2+ workers (request/reply)
# ---------------------------------------------------------------------------


class TestOrchestratorRequestReply:
    @pytest.mark.asyncio
    async def test_orchestrator_sends_request_worker_replies(self, bus):
        """Orchestrator sends request with correlation_id to worker-1.
        Worker-1 replies. Orchestrator polls and gets the reply matching
        the correlation_id."""
        await bus.register("orchestrator", enable_sse=False)
        await bus.register("worker-1", enable_sse=False)
        await bus.register("worker-2", enable_sse=False)

        # Orchestrator sends a request to worker-1 with correlation_id
        send_result = await bus.send(
            sender="orchestrator",
            recipient="worker-1",
            payload={"task": "run-tests", "module": "auth"},
            correlation_id="req-001",
        )
        assert send_result["ok"] is True

        # Worker-1 polls and gets the request
        w1_msgs, _ = await bus.poll("worker-1", max_messages=10)
        assert len(w1_msgs) == 1
        assert w1_msgs[0]["correlation_id"] == "req-001"
        assert w1_msgs[0]["payload"]["task"] == "run-tests"

        # Worker-1 replies using the correlation_id
        reply_result = await bus.reply(
            sender="worker-1",
            correlation_id="req-001",
            payload={"status": "passed", "duration_ms": 1234},
        )
        assert reply_result["ok"] is True

        # Orchestrator polls and gets the reply
        orch_msgs, _ = await bus.poll("orchestrator", max_messages=10)
        assert len(orch_msgs) == 1

        reply_msg = orch_msgs[0]
        assert reply_msg["sender"] == "worker-1"
        assert reply_msg["recipient"] == "orchestrator"
        assert reply_msg["message_type"] == "reply"
        assert reply_msg["correlation_id"] == "req-001"
        assert reply_msg["payload"] == {"status": "passed", "duration_ms": 1234}

        # Worker-2 was not involved, queue empty
        w2_msgs, _ = await bus.poll("worker-2", max_messages=10)
        assert len(w2_msgs) == 0

    @pytest.mark.asyncio
    async def test_orchestrator_parallel_requests_to_multiple_workers(self, bus):
        """Orchestrator sends different requests to 2 workers, each replies."""
        await bus.register("orch", enable_sse=False)
        await bus.register("w1", enable_sse=False)
        await bus.register("w2", enable_sse=False)

        # Send requests with distinct correlation IDs
        await bus.send("orch", "w1", {"task": "lint"}, correlation_id="corr-lint")
        await bus.send("orch", "w2", {"task": "typecheck"}, correlation_id="corr-type")

        # Workers reply
        await bus.reply("w1", "corr-lint", {"result": "clean"})
        await bus.reply("w2", "corr-type", {"result": "no errors"})

        # Orchestrator gets both replies
        orch_msgs, _ = await bus.poll("orch", max_messages=10)
        assert len(orch_msgs) == 2

        by_corr = {m["correlation_id"]: m for m in orch_msgs}
        assert by_corr["corr-lint"]["payload"] == {"result": "clean"}
        assert by_corr["corr-lint"]["sender"] == "w1"
        assert by_corr["corr-type"]["payload"] == {"result": "no errors"}
        assert by_corr["corr-type"]["sender"] == "w2"


# ---------------------------------------------------------------------------
# 4. SSE delivers messages
# ---------------------------------------------------------------------------


class TestSSEDelivery:
    @pytest.mark.asyncio
    async def test_sse_delivers_message_via_stream(self, bus, monkeypatch):
        """Register a session, get its queue, create the SSE app, use httpx
        AsyncClient with ASGITransport to connect to /stream/{alias}, send a
        message to the queue, verify SSE stream delivers it. Put _DISCONNECT
        sentinel to terminate."""
        # Patch sse module's message_bus to use our test bus
        monkeypatch.setattr(sse_module, "message_bus", bus)

        await bus.register("sse-target", enable_sse=False)
        await bus.register("sse-sender", enable_sse=False)

        # Get the queue for the target session
        queue = await bus.get_queue("sse-target")
        assert queue is not None

        # Send a message through the bus
        await bus.send("sse-sender", "sse-target", {"data": "via-sse"})

        # Put _DISCONNECT sentinel so the stream terminates
        await queue.put(_DISCONNECT)

        # Create the SSE app and connect
        app = sse_module.create_messaging_app()
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

        async with client:
            resp = await client.get("/stream/sse-target")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        # Parse SSE output
        lines = resp.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        assert len(data_lines) == 1

        payload = json.loads(data_lines[0][len("data: "):])
        assert payload["sender"] == "sse-sender"
        assert payload["recipient"] == "sse-target"
        assert payload["payload"] == {"data": "via-sse"}
        assert payload["message_type"] == "direct"

        # Verify SSE event structure
        id_lines = [l for l in lines if l.startswith("id: ")]
        event_lines = [l for l in lines if l.startswith("event: ")]
        assert len(id_lines) == 1
        assert event_lines == ["event: message"]


# ---------------------------------------------------------------------------
# 5. Disconnected target returns error
# ---------------------------------------------------------------------------


class TestDisconnectedTarget:
    @pytest.mark.asyncio
    async def test_send_to_nonexistent_recipient_returns_error(self, bus):
        """Register sender only. Sender tries to send to nonexistent recipient.
        Verify error response with 'recipient_not_found'."""
        await bus.register("sender-only", enable_sse=False)

        result = await bus.send(
            sender="sender-only",
            recipient="nonexistent-target",
            payload={"hello": "anyone?"},
        )

        assert result["ok"] is False
        assert result["error"] == "recipient_not_found"
        assert result["recipient"] == "nonexistent-target"

    @pytest.mark.asyncio
    async def test_unregistered_sender_returns_error(self, bus):
        """Unregistered sender cannot send messages."""
        await bus.register("target", enable_sse=False)

        result = await bus.send(
            sender="ghost",
            recipient="target",
            payload={"hello": "from ghost"},
        )

        assert result["ok"] is False
        assert result["error"] == "sender_not_registered"


