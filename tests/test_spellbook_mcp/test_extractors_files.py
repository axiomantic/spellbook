"""Tests for recent files extraction."""

import pytest


def test_extract_recent_files_from_tool_calls():
    """Test extracting file paths from Read/Edit/Write tools."""
    from spellbook_mcp.extractors.files import extract_recent_files

    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/path/to/file1.py"}}
            ]
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/path/to/file2.py"}}
            ]
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Write", "args": {"file_path": "/path/to/file3.py"}}
            ]
        }
    ]

    result = extract_recent_files(messages)

    assert len(result) == 3
    assert "/path/to/file1.py" in result
    assert "/path/to/file2.py" in result
    assert "/path/to/file3.py" in result


def test_extract_recent_files_deduplicates():
    """Test that duplicate paths are removed."""
    from spellbook_mcp.extractors.files import extract_recent_files

    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/same/file.py"}}
            ]
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/same/file.py"}}
            ]
        }
    ]

    result = extract_recent_files(messages)

    assert len(result) == 1
    assert result[0] == "/same/file.py"


def test_extract_recent_files_bounded():
    """Test that result is bounded to last 50 calls."""
    from spellbook_mcp.extractors.files import extract_recent_files

    messages = []
    for i in range(100):
        messages.append({
            "role": "assistant",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": f"/file{i}.py"}}
            ]
        })

    result = extract_recent_files(messages)

    # Should have max 50 unique files (from last 50 tool calls)
    assert len(result) <= 50
    # Should include recent files
    assert "/file99.py" in result
    assert "/file90.py" in result


def test_extract_recent_files_empty():
    """Test extraction with no file operations."""
    from spellbook_mcp.extractors.files import extract_recent_files

    messages = [
        {"role": "user", "timestamp": "2026-01-16T10:00:00Z"},
        {"role": "assistant", "timestamp": "2026-01-16T10:01:00Z"}
    ]

    result = extract_recent_files(messages)
    assert result == []


def test_extract_recent_files_ignores_other_tools():
    """Test that non-file tools are ignored."""
    from spellbook_mcp.extractors.files import extract_recent_files

    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "ls -la"}}
            ]
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/real/file.py"}}
            ]
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Grep", "args": {"pattern": "foo"}}
            ]
        }
    ]

    result = extract_recent_files(messages)

    assert len(result) == 1
    assert result[0] == "/real/file.py"


def test_extract_recent_files_handles_missing_args():
    """Test graceful handling of missing args or file_path."""
    from spellbook_mcp.extractors.files import extract_recent_files

    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Read", "args": {}}  # Missing file_path
            ]
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Edit"}  # Missing args entirely
            ]
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Write", "args": {"file_path": "/valid/path.py"}}
            ]
        }
    ]

    result = extract_recent_files(messages)

    assert len(result) == 1
    assert result[0] == "/valid/path.py"


def test_extract_recent_files_handles_none_tool_calls():
    """Test graceful handling of None or invalid tool_calls."""
    from spellbook_mcp.extractors.files import extract_recent_files

    messages = [
        {
            "role": "assistant",
            "tool_calls": None  # Explicitly None
        },
        {
            "role": "assistant"
            # Missing tool_calls key entirely
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/valid/path.py"}}
            ]
        }
    ]

    result = extract_recent_files(messages)

    assert len(result) == 1
    assert result[0] == "/valid/path.py"


def test_extract_recent_files_preserves_order():
    """Test that files are returned in chronological order."""
    from spellbook_mcp.extractors.files import extract_recent_files

    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/first.py"}}
            ]
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/second.py"}}
            ]
        },
        {
            "role": "assistant",
            "tool_calls": [
                {"tool": "Write", "args": {"file_path": "/third.py"}}
            ]
        }
    ]

    result = extract_recent_files(messages)

    assert result == ["/first.py", "/second.py", "/third.py"]
