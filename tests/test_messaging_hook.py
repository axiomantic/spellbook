"""Tests for the messaging_check hook function in spellbook_hook.py."""

import json
import os
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers to load _messaging_check from the hook script
# ---------------------------------------------------------------------------

def _load_messaging_check():
    """Import _messaging_check from hooks/spellbook_hook.py.

    Uses importlib to load the hook module without requiring it to be
    on sys.path or in a package.
    """
    import importlib.util

    hook_path = Path(__file__).parent.parent / "hooks" / "spellbook_hook.py"
    spec = importlib.util.spec_from_file_location("spellbook_hook", hook_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._messaging_check


@pytest.fixture
def messaging_check():
    """Provide the _messaging_check function."""
    return _load_messaging_check()


@pytest.fixture
def inbox_env(tmp_path, monkeypatch):
    """Set SPELLBOOK_CONFIG_DIR to a temp directory and return it."""
    monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(tmp_path))
    return tmp_path


def _write_msg(inbox_dir: Path, msg: dict) -> Path:
    """Write a message JSON file to the inbox directory."""
    inbox_dir.mkdir(parents=True, exist_ok=True)
    msg_id = msg.get("id", "msg-unknown")
    path = inbox_dir / f"{msg_id}.json"
    path.write_text(json.dumps(msg))
    return path


# ---------------------------------------------------------------------------
# Tests: reading and deleting inbox files
# ---------------------------------------------------------------------------

class TestMessagingCheckReadDelete:
    def test_reads_and_deletes_inbox_files(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "my-session" / "inbox"
        msg = {
            "id": "msg-001",
            "sender": "orchestrator",
            "recipient": "my-session",
            "payload": {"task": "run auth tests"},
            "message_type": "direct",
            "timestamp": "2026-04-03T12:00:00Z",
        }
        msg_path = _write_msg(inbox, msg)
        assert msg_path.exists()

        result = messaging_check()

        assert result is not None
        assert "orchestrator" in result
        assert "run auth tests" in result
        # File should be deleted after processing
        assert not msg_path.exists()

    def test_reads_multiple_files_in_order(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "worker" / "inbox"
        for i in range(3):
            _write_msg(inbox, {
                "id": f"msg-{i:03d}",
                "sender": f"sender-{i}",
                "recipient": "worker",
                "payload": {"seq": i},
                "message_type": "direct",
                "timestamp": "2026-04-03T12:00:00Z",
            })

        result = messaging_check()

        assert result is not None
        # All three messages should appear
        for i in range(3):
            assert f"sender-{i}" in result
        # All files deleted
        remaining = list(inbox.glob("*.json"))
        assert len(remaining) == 0

    def test_reads_from_multiple_alias_dirs(self, messaging_check, inbox_env):
        for alias in ("session-a", "session-b"):
            inbox = inbox_env / "messaging" / alias / "inbox"
            _write_msg(inbox, {
                "id": f"msg-{alias}",
                "sender": "sender",
                "recipient": alias,
                "payload": {"target": alias},
                "message_type": "direct",
                "timestamp": "2026-04-03T12:00:00Z",
            })

        result = messaging_check()

        assert result is not None
        assert "session-a" in result
        assert "session-b" in result


# ---------------------------------------------------------------------------
# Tests: message formatting per type
# ---------------------------------------------------------------------------

class TestMessagingCheckFormatting:
    def test_direct_message_format(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "target" / "inbox"
        _write_msg(inbox, {
            "id": "direct-001",
            "sender": "alice",
            "recipient": "target",
            "payload": {"question": "status?"},
            "message_type": "direct",
            "correlation_id": "corr-123",
            "timestamp": "2026-04-03T12:00:00Z",
        })

        result = messaging_check()

        assert "[MESSAGE from alice]" in result
        assert "(correlation_id: corr-123)" in result
        assert '"question": "status?"' in result

    def test_direct_message_no_correlation(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "target" / "inbox"
        _write_msg(inbox, {
            "id": "direct-002",
            "sender": "bob",
            "recipient": "target",
            "payload": {"info": "done"},
            "message_type": "direct",
            "timestamp": "2026-04-03T12:00:00Z",
        })

        result = messaging_check()

        assert "[MESSAGE from bob]" in result
        assert "correlation_id" not in result

    def test_broadcast_message_format(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "listener" / "inbox"
        _write_msg(inbox, {
            "id": "bc-001",
            "sender": "announcer",
            "recipient": "*",
            "payload": {"info": "deploy starting"},
            "message_type": "broadcast",
            "timestamp": "2026-04-03T12:00:00Z",
        })

        result = messaging_check()

        assert "[BROADCAST from announcer]" in result
        assert "deploy starting" in result

    def test_reply_message_format(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "requester" / "inbox"
        _write_msg(inbox, {
            "id": "reply-001",
            "sender": "responder",
            "recipient": "requester",
            "payload": {"answer": "feature/auth"},
            "message_type": "reply",
            "correlation_id": "corr-456",
            "timestamp": "2026-04-03T12:00:00Z",
        })

        result = messaging_check()

        assert "[REPLY from responder]" in result
        assert "(correlation_id: corr-456)" in result
        assert "feature/auth" in result

    def test_reply_without_correlation(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "requester" / "inbox"
        _write_msg(inbox, {
            "id": "reply-002",
            "sender": "responder",
            "recipient": "requester",
            "payload": {"answer": "ok"},
            "message_type": "reply",
            "timestamp": "2026-04-03T12:00:00Z",
        })

        result = messaging_check()

        assert "[REPLY from responder]" in result
        assert "correlation_id" not in result


# ---------------------------------------------------------------------------
# Tests: no-op on empty inbox
# ---------------------------------------------------------------------------

class TestMessagingCheckNoop:
    def test_returns_none_when_no_messaging_dir(self, messaging_check, inbox_env):
        """No messaging directory at all."""
        result = messaging_check()
        assert result is None

    def test_returns_none_when_messaging_dir_empty(self, messaging_check, inbox_env):
        """messaging/ exists but has no alias subdirs."""
        (inbox_env / "messaging").mkdir(parents=True)
        result = messaging_check()
        assert result is None

    def test_returns_none_when_inbox_empty(self, messaging_check, inbox_env):
        """Alias dir exists with empty inbox."""
        inbox = inbox_env / "messaging" / "my-session" / "inbox"
        inbox.mkdir(parents=True)
        result = messaging_check()
        assert result is None

    def test_returns_none_when_no_json_files(self, messaging_check, inbox_env):
        """Inbox has non-JSON files."""
        inbox = inbox_env / "messaging" / "my-session" / "inbox"
        inbox.mkdir(parents=True)
        (inbox / "readme.txt").write_text("not a message")
        result = messaging_check()
        assert result is None


# ---------------------------------------------------------------------------
# Tests: malformed JSON handling
# ---------------------------------------------------------------------------

class TestMessagingCheckMalformed:
    def test_handles_invalid_json_gracefully(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "target" / "inbox"
        inbox.mkdir(parents=True)
        bad_file = inbox / "bad-msg.json"
        bad_file.write_text("this is not valid json {{{")

        result = messaging_check()

        # Should not crash, returns None since no valid messages
        assert result is None
        # Malformed file should be deleted to prevent re-processing
        assert not bad_file.exists()

    def test_handles_partial_json_gracefully(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "target" / "inbox"
        inbox.mkdir(parents=True)
        # Valid JSON but missing expected fields
        partial_file = inbox / "partial-msg.json"
        partial_file.write_text(json.dumps({"id": "partial-001"}))

        result = messaging_check()

        # Should use defaults for missing fields
        assert result is not None
        assert "[MESSAGE from unknown]" in result
        # File deleted after processing
        assert not partial_file.exists()

    def test_valid_and_invalid_mixed(self, messaging_check, inbox_env):
        inbox = inbox_env / "messaging" / "target" / "inbox"
        inbox.mkdir(parents=True)

        # One bad file
        bad_file = inbox / "aaa-bad.json"
        bad_file.write_text("not json")

        # One good file
        _write_msg(inbox, {
            "id": "zzz-good",
            "sender": "alice",
            "recipient": "target",
            "payload": {"ok": True},
            "message_type": "direct",
            "timestamp": "2026-04-03T12:00:00Z",
        })

        result = messaging_check()

        # Good message should still be processed
        assert result is not None
        assert "[MESSAGE from alice]" in result
        # Both files deleted
        assert not bad_file.exists()
        assert not (inbox / "zzz-good.json").exists()
