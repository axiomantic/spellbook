"""Tests for active skill extraction."""

import pytest


def test_extract_skill_from_tool_call():
    """Test extracting skill name from Skill tool invocation."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {
                    "tool": "Skill",
                    "args": {"skill": "writing-plans"}
                }
            ]
        }
    ]

    result = extract_active_skill(messages)
    assert result == "writing-plans"


def test_extract_skill_takes_latest():
    """Test that latest skill invocation wins."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [{"tool": "Skill", "args": {"skill": "debugging"}}]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:05:00Z",
            "tool_calls": [{"tool": "Skill", "args": {"skill": "executing-plans"}}]
        }
    ]

    result = extract_active_skill(messages)
    assert result == "executing-plans"


def test_extract_skill_none():
    """Test extraction when no skill active."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    messages = [
        {"role": "user", "timestamp": "2026-01-16T10:00:00Z"},
        {"role": "assistant", "timestamp": "2026-01-16T10:01:00Z"}
    ]

    result = extract_active_skill(messages)
    assert result is None


def test_extract_skill_empty_messages():
    """Test extraction with empty message list."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    result = extract_active_skill([])
    assert result is None


def test_extract_skill_handles_missing_tool_calls():
    """Test extraction handles messages without tool_calls field."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    messages = [
        {"role": "assistant", "timestamp": "2026-01-16T10:00:00Z"}
    ]

    result = extract_active_skill(messages)
    assert result is None


def test_extract_skill_handles_none_tool_calls():
    """Test extraction handles messages with None tool_calls."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    messages = [
        {"role": "assistant", "timestamp": "2026-01-16T10:00:00Z", "tool_calls": None}
    ]

    result = extract_active_skill(messages)
    assert result is None


def test_extract_skill_handles_missing_args():
    """Test extraction handles Skill tool call with missing args."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [{"tool": "Skill"}]
        }
    ]

    result = extract_active_skill(messages)
    assert result is None


def test_extract_skill_handles_missing_skill_key():
    """Test extraction handles args without skill key."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [{"tool": "Skill", "args": {}}]
        }
    ]

    result = extract_active_skill(messages)
    assert result is None


def test_extract_skill_ignores_other_tools():
    """Test extraction ignores non-Skill tool calls."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/some/file.py"}},
                {"tool": "Write", "args": {"file_path": "/another/file.py", "content": "..."}}
            ]
        }
    ]

    result = extract_active_skill(messages)
    assert result is None


def test_extract_skill_finds_in_multiple_tool_calls():
    """Test extraction finds Skill among multiple tool calls in same message."""
    from spellbook_mcp.extractors.skill import extract_active_skill

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/some/file.py"}},
                {"tool": "Skill", "args": {"skill": "test-driven-development"}},
                {"tool": "Write", "args": {"file_path": "/another/file.py", "content": "..."}}
            ]
        }
    ]

    result = extract_active_skill(messages)
    assert result == "test-driven-development"
