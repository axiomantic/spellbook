"""Tests for MessageBridge: SSE-to-inbox daemon thread."""

import json
import threading

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def inbox_dir(tmp_path):
    """Pre-created inbox directory."""
    d = tmp_path / "inbox"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# MessageBridge Tests
# ---------------------------------------------------------------------------

class TestMessageBridgeWriteToInbox:
    """Tests for _write_to_inbox: atomic file writing."""

    def test_write_to_inbox_creates_correct_json_file(self, inbox_dir):
        """Bridge writes a single JSON file named by message id."""
        from spellbook.messaging.bridge import MessageBridge

        bridge = MessageBridge(
            alias="test-bridge",
            server_url="http://127.0.0.1:8765",
            token="fake-token",
            inbox_dir=inbox_dir,
        )
        envelope = {
            "id": "msg-001",
            "sender": "session-a",
            "recipient": "test-bridge",
            "payload": {"task": "run tests"},
            "timestamp": "2026-04-03T12:00:00Z",
            "message_type": "direct",
            "correlation_id": None,
            "reply_to": None,
            "ttl": 60,
        }
        bridge._write_to_inbox(json.dumps(envelope))

        files = list(inbox_dir.glob("*.json"))
        assert len(files) == 1
        assert files[0].name == "msg-001.json"
        content = json.loads(files[0].read_text())
        assert content == envelope

    def test_write_to_inbox_no_tmp_files_remain(self, inbox_dir):
        """No .tmp files left after successful write."""
        from spellbook.messaging.bridge import MessageBridge

        bridge = MessageBridge(
            alias="test-bridge",
            server_url="http://127.0.0.1:8765",
            token="fake-token",
            inbox_dir=inbox_dir,
        )
        envelope = {
            "id": "msg-002",
            "sender": "a",
            "recipient": "test-bridge",
            "payload": {"x": 1},
            "timestamp": "2026-04-03T12:00:00Z",
            "message_type": "direct",
            "correlation_id": None,
            "reply_to": None,
            "ttl": 60,
        }
        bridge._write_to_inbox(json.dumps(envelope))

        tmp_files = list(inbox_dir.glob("*.tmp"))
        assert tmp_files == []
        # Confirm the json file does exist
        json_files = list(inbox_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_write_to_inbox_multiple_messages(self, inbox_dir):
        """Multiple writes create separate files."""
        from spellbook.messaging.bridge import MessageBridge

        bridge = MessageBridge(
            alias="test-bridge",
            server_url="http://127.0.0.1:8765",
            token="fake-token",
            inbox_dir=inbox_dir,
        )
        for i in range(3):
            envelope = {
                "id": f"msg-{i:03d}",
                "sender": "a",
                "recipient": "test-bridge",
                "payload": {"seq": i},
                "timestamp": "2026-04-03T12:00:00Z",
                "message_type": "direct",
                "correlation_id": None,
                "reply_to": None,
                "ttl": 60,
            }
            bridge._write_to_inbox(json.dumps(envelope))

        files = sorted(inbox_dir.glob("*.json"))
        assert len(files) == 3
        assert [f.name for f in files] == ["msg-000.json", "msg-001.json", "msg-002.json"]
        # Verify content of each
        for i, f in enumerate(files):
            content = json.loads(f.read_text())
            assert content["id"] == f"msg-{i:03d}"
            assert content["payload"] == {"seq": i}

    def test_write_to_inbox_fallback_id_when_missing(self, inbox_dir):
        """When JSON has no 'id' field, bridge uses a generated filename."""
        from spellbook.messaging.bridge import MessageBridge

        bridge = MessageBridge(
            alias="test-bridge",
            server_url="http://127.0.0.1:8765",
            token="fake-token",
            inbox_dir=inbox_dir,
        )
        # JSON without 'id' field
        bridge._write_to_inbox(json.dumps({"payload": "no-id"}))

        files = list(inbox_dir.glob("*.json"))
        assert len(files) == 1
        # Filename should be a hex string (uuid4 fallback) with .json suffix
        assert files[0].suffix == ".json"
        # The stem should be a valid hex string (32 chars for uuid4.hex)
        assert len(files[0].stem) == 32
        assert all(c in "0123456789abcdef" for c in files[0].stem)
        content = json.loads(files[0].read_text())
        assert content == {"payload": "no-id"}


class TestMessageBridgeLifecycle:
    """Tests for start/stop lifecycle."""

    def test_start_creates_inbox_dir(self, tmp_path):
        """Bridge.start() creates inbox directory if it doesn't exist."""
        from spellbook.messaging.bridge import MessageBridge

        inbox = tmp_path / "nonexistent" / "inbox"
        assert not inbox.exists()

        bridge = MessageBridge(
            alias="mkdir-test",
            server_url="http://127.0.0.1:8765",
            token="fake-token",
            inbox_dir=inbox,
        )
        # Replace _run to prevent actual HTTP connection
        run_called = threading.Event()
        bridge._run = lambda: run_called.set()

        bridge.start()
        run_called.wait(timeout=2.0)
        assert inbox.exists()
        assert inbox.is_dir()
        bridge.stop()

    def test_start_spawns_daemon_thread(self, tmp_path):
        """Bridge.start() creates a daemon thread with correct name."""
        from spellbook.messaging.bridge import MessageBridge

        bridge = MessageBridge(
            alias="thread-test",
            server_url="http://127.0.0.1:8765",
            token="fake-token",
            inbox_dir=tmp_path,
        )
        run_called = threading.Event()
        bridge._run = lambda: run_called.set()

        bridge.start()
        run_called.wait(timeout=2.0)
        assert bridge._thread is not None
        assert bridge._thread.daemon is True
        assert bridge._thread.name == "msg-bridge-thread-test"
        bridge.stop()

    def test_stop_sets_event(self, tmp_path):
        """Bridge.stop() signals the stop event."""
        from spellbook.messaging.bridge import MessageBridge

        bridge = MessageBridge(
            alias="stop-test",
            server_url="http://127.0.0.1:8765",
            token="fake-token",
            inbox_dir=tmp_path,
        )
        assert not bridge._stop_event.is_set()
        bridge.stop()
        assert bridge._stop_event.is_set()

    def test_stop_event_is_threading_event(self, tmp_path):
        """Stop event is a threading.Event (not asyncio)."""
        from spellbook.messaging.bridge import MessageBridge

        bridge = MessageBridge(
            alias="event-type-test",
            server_url="http://127.0.0.1:8765",
            token="fake-token",
            inbox_dir=tmp_path,
        )
        assert isinstance(bridge._stop_event, threading.Event)


class TestMessageBridgeInit:
    """Tests for constructor parameter storage."""

    def test_constructor_stores_params(self, tmp_path):
        """Bridge stores all constructor params correctly."""
        from spellbook.messaging.bridge import MessageBridge

        inbox = tmp_path / "inbox"
        bridge = MessageBridge(
            alias="init-test",
            server_url="http://localhost:9999",
            token="test-tok-123",
            inbox_dir=inbox,
        )
        assert bridge.alias == "init-test"
        assert bridge.server_url == "http://localhost:9999"
        assert bridge.token == "test-tok-123"
        assert bridge.inbox_dir == inbox

    def test_constructor_thread_initially_none(self, tmp_path):
        """Thread is None before start() is called."""
        from spellbook.messaging.bridge import MessageBridge

        bridge = MessageBridge(
            alias="no-thread",
            server_url="http://127.0.0.1:8765",
            token="fake",
            inbox_dir=tmp_path,
        )
        assert bridge._thread is None

    def test_constructor_stop_event_initially_clear(self, tmp_path):
        """Stop event is not set on construction."""
        from spellbook.messaging.bridge import MessageBridge

        bridge = MessageBridge(
            alias="clear-event",
            server_url="http://127.0.0.1:8765",
            token="fake",
            inbox_dir=tmp_path,
        )
        assert not bridge._stop_event.is_set()
