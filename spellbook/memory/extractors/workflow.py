"""Extract workflow pattern from session transcript.

Detects workflow patterns:
- "test-driven-development": pytest runs interleaved with Edit calls
- "parallel-agents": multiple Task tool calls with run_in_background
- "sequential": default pattern
"""

from typing import Any, Dict, List

from spellbook_mcp.extractors.message_utils import get_tool_calls
from spellbook_mcp.extractors.types import WorkflowPattern


def _is_pytest_command(command: str) -> bool:
    """Check if a command is a pytest invocation."""
    if not command:
        return False
    # Match various pytest invocation patterns
    return "pytest" in command


def _is_edit_call(call: Dict[str, Any]) -> bool:
    """Check if a tool call is an Edit invocation."""
    return call.get("tool") == "Edit"


def _is_pytest_call(call: Dict[str, Any]) -> bool:
    """Check if a tool call is a Bash command running pytest."""
    if call.get("tool") != "Bash":
        return False
    args = call.get("args", {})
    if args is None:
        return False
    command = args.get("command", "")
    return _is_pytest_command(command)


def _is_background_task(call: Dict[str, Any]) -> bool:
    """Check if a tool call is a Task with run_in_background=True."""
    if call.get("tool") != "Task":
        return False
    args = call.get("args", {})
    if args is None:
        return False
    return args.get("run_in_background") is True


def _detect_tdd_pattern(messages: List[Dict[str, Any]]) -> bool:
    """Detect test-driven-development pattern.

    TDD is detected when pytest runs are interleaved with Edit calls,
    requiring at least 2 cycles of edit-test to confirm the pattern.
    """
    # Flatten all tool calls into a sequence with their types
    sequence: List[str] = []  # "edit" or "pytest"

    for msg in messages:
        tool_calls = get_tool_calls(msg)
        for call in tool_calls:
            if _is_edit_call(call):
                sequence.append("edit")
            elif _is_pytest_call(call):
                sequence.append("pytest")

    # Need at least 2 pytest runs interleaved with edits
    # Pattern: edit...pytest...edit...pytest (minimum)
    pytest_count = sequence.count("pytest")
    if pytest_count < 2:
        return False

    # Check for actual interleaving: need at least one edit between two pytest runs
    pytest_indices = [i for i, s in enumerate(sequence) if s == "pytest"]
    edit_indices = [i for i, s in enumerate(sequence) if s == "edit"]

    if len(pytest_indices) < 2 or not edit_indices:
        return False

    # Check if there's at least one edit between first and last pytest
    first_pytest = pytest_indices[0]
    last_pytest = pytest_indices[-1]

    for edit_idx in edit_indices:
        if first_pytest < edit_idx < last_pytest:
            return True

    return False


def _detect_parallel_pattern(messages: List[Dict[str, Any]]) -> bool:
    """Detect parallel-agents pattern.

    Parallel agents pattern is detected when there are multiple
    Task tool calls with run_in_background=True.
    """
    background_task_count = 0

    for msg in messages:
        tool_calls = get_tool_calls(msg)
        for call in tool_calls:
            if _is_background_task(call):
                background_task_count += 1

    return background_task_count >= 2


def extract_workflow_pattern(messages: List[Dict[str, Any]]) -> WorkflowPattern:
    """Extract workflow pattern from session messages.

    Detects workflow patterns in priority order:
    1. "test-driven-development": pytest runs interleaved with Edit calls
    2. "parallel-agents": multiple Task tool calls with run_in_background
    3. "sequential": default pattern

    Args:
        messages: List of session messages

    Returns:
        WorkflowPattern literal: "test-driven-development", "parallel-agents", or "sequential"
    """
    # TDD takes priority
    if _detect_tdd_pattern(messages):
        return "test-driven-development"

    # Then check for parallel agents
    if _detect_parallel_pattern(messages):
        return "parallel-agents"

    # Default to sequential
    return "sequential"
