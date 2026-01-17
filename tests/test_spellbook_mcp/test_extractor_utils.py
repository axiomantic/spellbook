"""Tests for extractor shared utilities."""

import pytest
from spellbook_mcp.extractors.message_utils import (
    get_tool_calls,
    get_content,
    get_timestamp,
    get_role,
    is_assistant_message,
    is_user_message,
)


class TestGetToolCalls:
    def test_returns_tool_calls_when_present(self):
        msg = {"tool_calls": [{"tool": "Read", "args": {"file_path": "/foo"}}]}
        assert get_tool_calls(msg) == [{"tool": "Read", "args": {"file_path": "/foo"}}]

    def test_returns_empty_list_when_missing(self):
        msg = {"role": "user", "content": "hello"}
        assert get_tool_calls(msg) == []

    def test_returns_empty_list_when_none(self):
        msg = {"tool_calls": None}
        assert get_tool_calls(msg) == []

    def test_returns_empty_list_when_not_list(self):
        msg = {"tool_calls": "invalid"}
        assert get_tool_calls(msg) == []


class TestGetContent:
    def test_returns_string_content(self):
        msg = {"content": "hello world"}
        assert get_content(msg) == "hello world"

    def test_returns_empty_string_when_missing(self):
        msg = {"role": "user"}
        assert get_content(msg) == ""

    def test_handles_content_blocks(self):
        msg = {"content": [{"text": "line 1"}, {"text": "line 2"}]}
        assert get_content(msg) == "line 1\nline 2"

    def test_handles_mixed_content_blocks(self):
        msg = {"content": [{"text": "text"}, {"image": "base64..."}]}
        assert get_content(msg) == "text"


class TestGetTimestamp:
    def test_returns_timestamp_when_present(self):
        msg = {"timestamp": "2026-01-16T14:32:00Z"}
        assert get_timestamp(msg) == "2026-01-16T14:32:00Z"

    def test_returns_none_when_missing(self):
        msg = {"role": "user"}
        assert get_timestamp(msg) is None


class TestRoleHelpers:
    def test_is_assistant_message(self):
        assert is_assistant_message({"role": "assistant"}) is True
        assert is_assistant_message({"role": "user"}) is False

    def test_is_user_message(self):
        assert is_user_message({"role": "user"}) is True
        assert is_user_message({"role": "assistant"}) is False
