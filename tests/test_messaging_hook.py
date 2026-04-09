"""Tests for the messaging_check hook function in spellbook_hook.py.

These tests mock _http_post to simulate daemon responses rather than
setting up local inbox files (the daemon now handles file I/O).
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers to load _messaging_check from the hook script
# ---------------------------------------------------------------------------

def _load_hook_module():
    """Import the hook module.

    Uses importlib to load the hook module without requiring it to be
    on sys.path or in a package.
    """
    import importlib.util

    hook_path = Path(__file__).parent.parent / "hooks" / "spellbook_hook.py"
    spec = importlib.util.spec_from_file_location("spellbook_hook", hook_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def hook_module():
    """Provide the loaded hook module."""
    return _load_hook_module()


@pytest.fixture
def messaging_check(hook_module):
    """Provide the _messaging_check function."""
    return hook_module._messaging_check


_TEST_SESSION_ID = "test-session-001"


def _mock_http_post(responses):
    """Create a mock _http_post that returns pre-canned responses.

    ``responses`` maps path strings to return values. If the path
    is not in the map, returns None (simulating daemon unreachable).
    """
    calls = []

    def _mock(path, payload, timeout=5):
        calls.append({"path": path, "payload": payload})
        if callable(responses.get(path)):
            return responses[path](payload)
        return responses.get(path)

    _mock.calls = calls
    return _mock


# ---------------------------------------------------------------------------
# Tests: reading and deleting inbox files (now via daemon HTTP)
# ---------------------------------------------------------------------------

class TestMessagingCheckReadDelete:
    def test_reads_and_deletes_inbox_files(self, hook_module, messaging_check):
        mock = _mock_http_post({
            "/api/messaging/poll": {
                "messages": [{
                    "message_type": "direct",
                    "sender": "orchestrator",
                    "payload": {"task": "run auth tests"},
                    "correlation_id": None,
                    "filename": "msg-001.json",
                }]
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = '[MESSAGE from orchestrator]\n{\n  "task": "run auth tests"\n}'
            assert result == expected
            # Verify the correct path and session_id were sent
            poll_calls = [c for c in mock.calls if c["path"] == "/api/messaging/poll"]
            assert len(poll_calls) == 1
            assert poll_calls[0]["payload"]["session_id"] == _TEST_SESSION_ID
        finally:
            hook_module._http_post = original

    def test_reads_multiple_files_in_order(self, hook_module, messaging_check):
        mock = _mock_http_post({
            "/api/messaging/poll": {
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
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = (
                '[MESSAGE from sender-0]\n{\n  "seq": 0\n}'
                '\n\n'
                '[MESSAGE from sender-1]\n{\n  "seq": 1\n}'
                '\n\n'
                '[MESSAGE from sender-2]\n{\n  "seq": 2\n}'
            )
            assert result == expected
        finally:
            hook_module._http_post = original

    def test_reads_from_multiple_alias_dirs(self, hook_module, messaging_check):
        """Daemon aggregates messages from multiple alias dirs."""
        mock = _mock_http_post({
            "/api/messaging/poll": {
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
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = (
                '[MESSAGE from sender]\n{\n  "target": "session-a"\n}'
                '\n\n'
                '[MESSAGE from sender]\n{\n  "target": "session-b"\n}'
            )
            assert result == expected
        finally:
            hook_module._http_post = original

    def test_only_drains_own_session_inboxes(self, hook_module, messaging_check):
        """Session filtering is done by the daemon; hook just sends session_id."""
        mock = _mock_http_post({
            "/api/messaging/poll": {
                "messages": [{
                    "message_type": "direct",
                    "sender": "friend",
                    "payload": {"greeting": "hello"},
                    "correlation_id": None,
                    "filename": "msg-mine.json",
                }]
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = '[MESSAGE from friend]\n{\n  "greeting": "hello"\n}'
            assert result == expected
            # Confirm session_id was passed to daemon
            assert mock.calls[0]["payload"]["session_id"] == _TEST_SESSION_ID
        finally:
            hook_module._http_post = original

    def test_returns_none_without_session_id(self, hook_module, messaging_check):
        """Without session_id, no HTTP call is made."""
        mock = _mock_http_post({})
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check()
            assert result is None
            # No HTTP calls should have been made
            assert len(mock.calls) == 0
        finally:
            hook_module._http_post = original


# ---------------------------------------------------------------------------
# Tests: message formatting per type
# ---------------------------------------------------------------------------

class TestMessagingCheckFormatting:
    def test_direct_message_format(self, hook_module, messaging_check):
        mock = _mock_http_post({
            "/api/messaging/poll": {
                "messages": [{
                    "message_type": "direct",
                    "sender": "alice",
                    "payload": {"question": "status?"},
                    "correlation_id": "corr-123",
                    "filename": "direct-001.json",
                }]
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = '[MESSAGE from alice] (correlation_id: corr-123)\n{\n  "question": "status?"\n}'
            assert result == expected
        finally:
            hook_module._http_post = original

    def test_direct_message_no_correlation(self, hook_module, messaging_check):
        mock = _mock_http_post({
            "/api/messaging/poll": {
                "messages": [{
                    "message_type": "direct",
                    "sender": "bob",
                    "payload": {"info": "done"},
                    "correlation_id": None,
                    "filename": "direct-002.json",
                }]
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = '[MESSAGE from bob]\n{\n  "info": "done"\n}'
            assert result == expected
        finally:
            hook_module._http_post = original

    def test_broadcast_message_format(self, hook_module, messaging_check):
        mock = _mock_http_post({
            "/api/messaging/poll": {
                "messages": [{
                    "message_type": "broadcast",
                    "sender": "announcer",
                    "payload": {"info": "deploy starting"},
                    "correlation_id": None,
                    "filename": "bc-001.json",
                }]
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = '[BROADCAST from announcer]\n{\n  "info": "deploy starting"\n}'
            assert result == expected
        finally:
            hook_module._http_post = original

    def test_reply_message_format(self, hook_module, messaging_check):
        mock = _mock_http_post({
            "/api/messaging/poll": {
                "messages": [{
                    "message_type": "reply",
                    "sender": "responder",
                    "payload": {"answer": "feature/auth"},
                    "correlation_id": "corr-456",
                    "filename": "reply-001.json",
                }]
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = '[REPLY from responder] (correlation_id: corr-456)\n{\n  "answer": "feature/auth"\n}'
            assert result == expected
        finally:
            hook_module._http_post = original

    def test_reply_without_correlation(self, hook_module, messaging_check):
        mock = _mock_http_post({
            "/api/messaging/poll": {
                "messages": [{
                    "message_type": "reply",
                    "sender": "responder",
                    "payload": {"answer": "ok"},
                    "correlation_id": None,
                    "filename": "reply-002.json",
                }]
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = '[REPLY from responder]\n{\n  "answer": "ok"\n}'
            assert result == expected
        finally:
            hook_module._http_post = original


# ---------------------------------------------------------------------------
# Tests: no-op on empty inbox
# ---------------------------------------------------------------------------

class TestMessagingCheckNoop:
    def test_returns_none_when_no_messages(self, hook_module, messaging_check):
        """Daemon returns empty message list."""
        mock = _mock_http_post({
            "/api/messaging/poll": {"messages": []}
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            assert result is None
        finally:
            hook_module._http_post = original

    def test_returns_none_when_daemon_unreachable(self, hook_module, messaging_check):
        """Daemon unreachable returns None from _http_post."""
        mock = _mock_http_post({})  # No response for any path
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            assert result is None
        finally:
            hook_module._http_post = original

    def test_returns_none_when_daemon_returns_no_messages_key(self, hook_module, messaging_check):
        """Daemon returns a response without 'messages' key."""
        mock = _mock_http_post({
            "/api/messaging/poll": {"ok": True}
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            assert result is None
        finally:
            hook_module._http_post = original


# ---------------------------------------------------------------------------
# Tests: malformed/missing field handling (daemon still returns entries)
# ---------------------------------------------------------------------------

class TestMessagingCheckMalformed:
    def test_handles_missing_fields_gracefully(self, hook_module, messaging_check):
        """Message with minimal fields uses defaults."""
        mock = _mock_http_post({
            "/api/messaging/poll": {
                "messages": [{
                    "message_type": "direct",
                    "sender": "unknown",
                    "payload": {},
                    "correlation_id": None,
                    "filename": "partial-001.json",
                }]
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = '[MESSAGE from unknown]\n{}'
            assert result == expected
        finally:
            hook_module._http_post = original

    def test_valid_and_invalid_mixed(self, hook_module, messaging_check):
        """Daemon skips invalid JSON files; only valid messages returned."""
        mock = _mock_http_post({
            "/api/messaging/poll": {
                "messages": [{
                    "message_type": "direct",
                    "sender": "alice",
                    "payload": {"ok": True},
                    "correlation_id": None,
                    "filename": "zzz-good.json",
                }]
            }
        })
        original = hook_module._http_post
        hook_module._http_post = mock
        try:
            result = messaging_check(session_id=_TEST_SESSION_ID)
            expected = '[MESSAGE from alice]\n{\n  "ok": true\n}'
            assert result == expected
        finally:
            hook_module._http_post = original
