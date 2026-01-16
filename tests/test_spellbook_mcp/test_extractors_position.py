"""Tests for position tracker (last 10 tool actions)."""

import pytest


def test_extract_position_last_10_actions():
    """Test extracting last 10 tool invocations."""
    from spellbook_mcp.extractors.position import extract_position

    messages = []
    for i in range(20):
        messages.append({
            "role": "assistant",
            "timestamp": f"2026-01-16T10:{i:02d}:00Z",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": f"/file{i}.py"}}
            ]
        })

    result = extract_position(messages)

    # Should have exactly 10 actions
    assert len(result) == 10

    # Should be most recent 10
    assert result[0]["tool"] == "Read"
    assert result[0]["primary_arg"] == "/file10.py"
    assert result[-1]["primary_arg"] == "/file19.py"


def test_extract_position_primary_args():
    """Test correct primary argument extraction per tool."""
    from spellbook_mcp.extractors.position import extract_position

    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/test.py"}},
                {"tool": "Bash", "args": {"command": "pytest tests/"}},
                {"tool": "Grep", "args": {"pattern": "TODO"}},
                {"tool": "Task", "args": {"prompt": "Analyze this code for bugs"}}
            ]
        }
    ]

    result = extract_position(messages)

    assert len(result) == 4
    assert result[0]["tool"] == "Read"
    assert result[0]["primary_arg"] == "/test.py"

    assert result[1]["tool"] == "Bash"
    assert result[1]["primary_arg"] == "pytest tests/"

    assert result[2]["tool"] == "Grep"
    assert result[2]["primary_arg"] == "TODO"

    assert result[3]["tool"] == "Task"
    assert "Analyze" in result[3]["primary_arg"]


def test_extract_position_truncates_long_args():
    """Test that long arguments are truncated."""
    from spellbook_mcp.extractors.position import extract_position

    long_command = "x" * 200
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": long_command}}
            ]
        }
    ]

    result = extract_position(messages)

    assert len(result) == 1
    assert len(result[0]["primary_arg"]) <= 100


def test_extract_position_empty_messages():
    """Test extraction with no tool calls."""
    from spellbook_mcp.extractors.position import extract_position

    messages = [
        {"role": "user", "timestamp": "2026-01-16T10:00:00Z"},
        {"role": "assistant", "timestamp": "2026-01-16T10:01:00Z"}
    ]

    result = extract_position(messages)
    assert result == []


def test_extract_position_includes_success_flag():
    """Test that success flag is included when present."""
    from spellbook_mcp.extractors.position import extract_position

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "echo hello"}, "success": True},
                {"tool": "Bash", "args": {"command": "false"}, "success": False}
            ]
        }
    ]

    result = extract_position(messages)

    assert len(result) == 2
    assert result[0]["success"] is True
    assert result[1]["success"] is False


def test_extract_position_returns_typed_actions():
    """Test that results conform to ToolAction type."""
    from spellbook_mcp.extractors.position import extract_position
    from spellbook_mcp.extractors.types import ToolAction

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/test.py"}}
            ]
        }
    ]

    result = extract_position(messages)

    assert len(result) == 1
    action = result[0]
    # Verify all required keys for ToolAction
    assert "tool" in action
    assert "primary_arg" in action
    assert "timestamp" in action
    assert "success" in action  # Optional but should be present
