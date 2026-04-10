"""Tests for the messaging_check hook function in spellbook_hook.py.

These tests mock _http_post to simulate daemon responses rather than
setting up local inbox files (the daemon now handles file I/O).
"""

import json

import bigfoot
import pytest


_TEST_SESSION_ID = "test-session-001"

_EXPECTED_POLL_ARGS = (
    "/api/messaging/poll",
    {"session_id": _TEST_SESSION_ID},
)


# ---------------------------------------------------------------------------
# Tests: reading and deleting inbox files (now via daemon HTTP)
# ---------------------------------------------------------------------------

class TestMessagingCheckReadDelete:
    def test_reads_and_deletes_inbox_files(self):
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [{
                "message_type": "direct",
                "sender": "orchestrator",
                "payload": {"task": "run auth tests"},
                "correlation_id": None,
                "filename": "msg-001.json",
            }]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = '[MESSAGE from orchestrator]\n{\n  "task": "run auth tests"\n}'
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_reads_multiple_files_in_order(self):
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [
                {
                    "message_type": "direct",
                    "sender": f"sender-{i}",
                    "payload": {"seq": i},
                    "correlation_id": None,
                    "filename": f"msg-{i:03d}.json",
                }
                for i in range(3)
            ]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = (
            '[MESSAGE from sender-0]\n{\n  "seq": 0\n}'
            '\n\n'
            '[MESSAGE from sender-1]\n{\n  "seq": 1\n}'
            '\n\n'
            '[MESSAGE from sender-2]\n{\n  "seq": 2\n}'
        )
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_reads_from_multiple_alias_dirs(self):
        """Daemon aggregates messages from multiple alias dirs."""
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [
                {
                    "message_type": "direct",
                    "sender": "sender",
                    "payload": {"target": "session-a"},
                    "correlation_id": None,
                    "filename": "msg-session-a.json",
                },
                {
                    "message_type": "direct",
                    "sender": "sender",
                    "payload": {"target": "session-b"},
                    "correlation_id": None,
                    "filename": "msg-session-b.json",
                },
            ]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = (
            '[MESSAGE from sender]\n{\n  "target": "session-a"\n}'
            '\n\n'
            '[MESSAGE from sender]\n{\n  "target": "session-b"\n}'
        )
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_only_drains_own_session_inboxes(self):
        """Session filtering is done by the daemon; hook just sends session_id."""
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [{
                "message_type": "direct",
                "sender": "friend",
                "payload": {"greeting": "hello"},
                "correlation_id": None,
                "filename": "msg-mine.json",
            }]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = '[MESSAGE from friend]\n{\n  "greeting": "hello"\n}'
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_returns_none_without_session_id(self):
        """Without session_id, no HTTP call is made."""
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.__call__.required(False).returns(None)

        with bigfoot:
            result = _messaging_check()

        assert result is None


# ---------------------------------------------------------------------------
# Tests: message formatting per type
# ---------------------------------------------------------------------------

class TestMessagingCheckFormatting:
    def test_direct_message_format(self):
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [{
                "message_type": "direct",
                "sender": "alice",
                "payload": {"question": "status?"},
                "correlation_id": "corr-123",
                "filename": "direct-001.json",
            }]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = '[MESSAGE from alice] (correlation_id: corr-123)\n{\n  "question": "status?"\n}'
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_direct_message_no_correlation(self):
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [{
                "message_type": "direct",
                "sender": "bob",
                "payload": {"info": "done"},
                "correlation_id": None,
                "filename": "direct-002.json",
            }]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = '[MESSAGE from bob]\n{\n  "info": "done"\n}'
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_broadcast_message_format(self):
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [{
                "message_type": "broadcast",
                "sender": "announcer",
                "payload": {"info": "deploy starting"},
                "correlation_id": None,
                "filename": "bc-001.json",
            }]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = '[BROADCAST from announcer]\n{\n  "info": "deploy starting"\n}'
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_reply_message_format(self):
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [{
                "message_type": "reply",
                "sender": "responder",
                "payload": {"answer": "feature/auth"},
                "correlation_id": "corr-456",
                "filename": "reply-001.json",
            }]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = '[REPLY from responder] (correlation_id: corr-456)\n{\n  "answer": "feature/auth"\n}'
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_reply_without_correlation(self):
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [{
                "message_type": "reply",
                "sender": "responder",
                "payload": {"answer": "ok"},
                "correlation_id": None,
                "filename": "reply-002.json",
            }]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = '[REPLY from responder]\n{\n  "answer": "ok"\n}'
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})


# ---------------------------------------------------------------------------
# Tests: no-op on empty inbox
# ---------------------------------------------------------------------------

class TestMessagingCheckNoop:
    def test_returns_none_when_no_messages(self):
        """Daemon returns empty message list."""
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({"messages": []})

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        assert result is None

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_returns_none_when_daemon_unreachable(self):
        """Daemon unreachable returns None from _http_post."""
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns(None)

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        assert result is None

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_returns_none_when_daemon_returns_no_messages_key(self):
        """Daemon returns a response without 'messages' key."""
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({"ok": True})

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        assert result is None

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})


# ---------------------------------------------------------------------------
# Tests: malformed/missing field handling (daemon still returns entries)
# ---------------------------------------------------------------------------

class TestMessagingCheckMalformed:
    def test_handles_missing_fields_gracefully(self):
        """Message with minimal fields uses defaults."""
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [{
                "message_type": "direct",
                "sender": "unknown",
                "payload": {},
                "correlation_id": None,
                "filename": "partial-001.json",
            }]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = '[MESSAGE from unknown]\n{}'
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})

    def test_valid_and_invalid_mixed(self):
        """Daemon skips invalid JSON files; only valid messages returned."""
        from hooks.spellbook_hook import _messaging_check

        mock_post = bigfoot.mock("hooks.spellbook_hook:_http_post")
        mock_post.returns({
            "messages": [{
                "message_type": "direct",
                "sender": "alice",
                "payload": {"ok": True},
                "correlation_id": None,
                "filename": "zzz-good.json",
            }]
        })

        with bigfoot:
            result = _messaging_check(session_id=_TEST_SESSION_ID)

        expected = '[MESSAGE from alice]\n{\n  "ok": true\n}'
        assert result == expected

        mock_post.assert_call(args=_EXPECTED_POLL_ARGS, kwargs={})
