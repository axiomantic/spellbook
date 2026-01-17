"""Tests for workflow pattern detection."""

import pytest


def test_extract_workflow_default_sequential():
    """Test that default workflow is sequential."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/some/file.py"}}
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    assert result == "sequential"


def test_extract_workflow_empty_messages():
    """Test extraction with empty message list."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    result = extract_workflow_pattern([])
    assert result == "sequential"


def test_extract_workflow_tdd_pattern():
    """Test detecting TDD pattern: pytest interleaved with Edit calls."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/tests/test_foo.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:01:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "uv run pytest tests/test_foo.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:02:00Z",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/src/foo.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:03:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "pytest tests/"}}
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    assert result == "test-driven-development"


def test_extract_workflow_tdd_needs_interleaving():
    """Test that TDD requires actual interleaving, not just presence of both."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    # All edits first, then all tests - not interleaved
    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/tests/test_foo.py"}},
                {"tool": "Edit", "args": {"file_path": "/src/foo.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:01:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "pytest tests/"}}
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    # Single test run after edits is not TDD pattern
    assert result == "sequential"


def test_extract_workflow_parallel_agents():
    """Test detecting parallel agents pattern: multiple Task with run_in_background."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {
                    "tool": "Task",
                    "args": {
                        "prompt": "Investigate module A",
                        "run_in_background": True
                    }
                },
                {
                    "tool": "Task",
                    "args": {
                        "prompt": "Investigate module B",
                        "run_in_background": True
                    }
                }
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    assert result == "parallel-agents"


def test_extract_workflow_parallel_agents_across_messages():
    """Test detecting parallel agents across multiple messages."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {
                    "tool": "Task",
                    "args": {"prompt": "Task 1", "run_in_background": True}
                }
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:01Z",
            "tool_calls": [
                {
                    "tool": "Task",
                    "args": {"prompt": "Task 2", "run_in_background": True}
                }
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    assert result == "parallel-agents"


def test_extract_workflow_single_background_task_not_parallel():
    """Test that a single background task is not parallel pattern."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {
                    "tool": "Task",
                    "args": {"prompt": "Single task", "run_in_background": True}
                }
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    assert result == "sequential"


def test_extract_workflow_foreground_tasks_not_parallel():
    """Test that foreground Task calls are not parallel pattern."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Task", "args": {"prompt": "Task 1"}},
                {"tool": "Task", "args": {"prompt": "Task 2"}}
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    assert result == "sequential"


def test_extract_workflow_tdd_priority_over_parallel():
    """Test that TDD pattern takes priority over parallel agents."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    # Both patterns present - TDD should win
    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/tests/test_foo.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:01:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "pytest tests/"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:02:00Z",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/src/foo.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:03:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "pytest tests/"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:04:00Z",
            "tool_calls": [
                {
                    "tool": "Task",
                    "args": {"prompt": "Task 1", "run_in_background": True}
                },
                {
                    "tool": "Task",
                    "args": {"prompt": "Task 2", "run_in_background": True}
                }
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    assert result == "test-driven-development"


def test_extract_workflow_handles_missing_args():
    """Test extraction handles tool calls with missing args."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Task"},
                {"tool": "Edit"}
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    assert result == "sequential"


def test_extract_workflow_handles_none_tool_calls():
    """Test extraction handles messages with None tool_calls."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    messages = [
        {"role": "assistant", "timestamp": "2026-01-16T10:00:00Z", "tool_calls": None}
    ]

    result = extract_workflow_pattern(messages)
    assert result == "sequential"


def test_extract_workflow_pytest_variants():
    """Test that various pytest command variants are detected."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/tests/test_foo.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:01:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "python -m pytest tests/"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:02:00Z",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/src/foo.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:03:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "uv run pytest -v tests/"}}
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    assert result == "test-driven-development"


def test_extract_workflow_tdd_minimum_iterations():
    """Test that TDD needs at least 2 test-edit cycles."""
    from spellbook_mcp.extractors.workflow import extract_workflow_pattern

    # Only one cycle - not enough to be TDD
    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/tests/test_foo.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:01:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "pytest tests/"}}
            ]
        }
    ]

    result = extract_workflow_pattern(messages)
    # Single edit-test is not enough to confirm TDD
    assert result == "sequential"
