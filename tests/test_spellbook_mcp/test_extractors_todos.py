"""Tests for todo extraction from session transcript."""

import pytest


def test_extract_todos_from_tool_calls():
    """Test extracting active todos from TodoWrite tool calls."""
    from spellbook_mcp.extractors.todos import extract_todos

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {
                    "tool": "TodoWrite",
                    "args": {
                        "todos": [
                            {"content": "Task 1", "status": "pending", "activeForm": "Doing task 1"},
                            {"content": "Task 2", "status": "in_progress", "activeForm": "Doing task 2"},
                            {"content": "Task 3", "status": "completed", "activeForm": "Did task 3"}
                        ]
                    }
                }
            ]
        }
    ]

    result = extract_todos(messages)

    # Should only include non-completed todos
    assert len(result) == 2
    assert result[0]["content"] == "Task 1"
    assert result[0]["status"] == "pending"
    assert result[1]["content"] == "Task 2"
    assert result[1]["status"] == "in_progress"


def test_extract_todos_takes_latest():
    """Test that latest TodoWrite call wins."""
    from spellbook_mcp.extractors.todos import extract_todos

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {
                    "tool": "TodoWrite",
                    "args": {
                        "todos": [
                            {"content": "Old task", "status": "pending", "activeForm": "Doing old"}
                        ]
                    }
                }
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:05:00Z",
            "tool_calls": [
                {
                    "tool": "TodoWrite",
                    "args": {
                        "todos": [
                            {"content": "New task", "status": "in_progress", "activeForm": "Doing new"}
                        ]
                    }
                }
            ]
        }
    ]

    result = extract_todos(messages)

    # Should use the latest TodoWrite call
    assert len(result) == 1
    assert result[0]["content"] == "New task"


def test_extract_todos_empty():
    """Test extraction with no TodoWrite calls."""
    from spellbook_mcp.extractors.todos import extract_todos

    messages = [
        {"role": "user", "timestamp": "2026-01-16T10:00:00Z"},
        {"role": "assistant", "timestamp": "2026-01-16T10:01:00Z"}
    ]

    result = extract_todos(messages)
    assert result == []
