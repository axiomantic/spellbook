"""Tests for soul extractor integration."""

import pytest
import json


def test_extract_soul_full_integration(tmp_path):
    """Test extracting complete soul from session transcript."""
    from spellbook_mcp.soul_extractor import extract_soul

    # Create test transcript
    transcript = tmp_path / "session.jsonl"
    messages = [
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:00:00Z",
            "content": "SESSION MODE: Fun mode active\nPERSONA: Grizzled Detective"
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:01:00Z",
            "tool_calls": [
                {"tool": "Skill", "args": {"skill": "writing-plans"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:02:00Z",
            "tool_calls": [
                {"tool": "Read", "args": {"file_path": "/test.py"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:03:00Z",
            "tool_calls": [
                {
                    "tool": "TodoWrite",
                    "args": {
                        "todos": [
                            {"content": "Task 1", "status": "pending", "activeForm": "Working on Task 1"}
                        ]
                    }
                }
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:04:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "uv run pytest tests/"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:05:00Z",
            "tool_calls": [
                {"tool": "Edit", "args": {"file_path": "/test.py", "old_string": "a", "new_string": "b"}}
            ]
        },
        {
            "role": "assistant",
            "timestamp": "2026-01-16T10:06:00Z",
            "tool_calls": [
                {"tool": "Bash", "args": {"command": "uv run pytest tests/"}}
            ]
        }
    ]

    with open(transcript, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    soul = extract_soul(str(transcript))

    assert soul["persona"] == "fun:Grizzled Detective"
    assert soul["active_skill"] == "writing-plans"
    assert len(soul["todos"]) == 1
    assert soul["todos"][0]["content"] == "Task 1"
    assert "/test.py" in soul["recent_files"]
    assert len(soul["exact_position"]) > 0
    assert soul["workflow_pattern"] in ["test-driven-development", "parallel-agents", "sequential"]


def test_extract_soul_bounded_scan(tmp_path):
    """Test that extraction only scans last 200 messages."""
    from spellbook_mcp.soul_extractor import extract_soul

    transcript = tmp_path / "session.jsonl"

    # Create 300 messages with old data at start
    messages = []
    for i in range(100):
        messages.append({
            "role": "assistant",
            "timestamp": f"2026-01-16T09:{i:02d}:00Z",
            "tool_calls": [
                {"tool": "Skill", "args": {"skill": "old-skill"}}
            ]
        })

    # Then 200 messages with new skill
    for i in range(200):
        messages.append({
            "role": "assistant",
            "timestamp": f"2026-01-16T10:{i:02d}:00Z",
            "tool_calls": [
                {"tool": "Skill", "args": {"skill": "new-skill"}}
            ]
        })

    with open(transcript, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    soul = extract_soul(str(transcript))

    # Should use recent skill, not old one
    assert soul["active_skill"] == "new-skill"


def test_extract_soul_empty_transcript(tmp_path):
    """Test extraction from empty transcript returns valid empty soul."""
    from spellbook_mcp.soul_extractor import extract_soul

    transcript = tmp_path / "session.jsonl"
    transcript.write_text("")

    soul = extract_soul(str(transcript))

    assert soul["todos"] == []
    assert soul["active_skill"] is None
    assert soul["persona"] is None
    assert soul["recent_files"] == []
    assert soul["exact_position"] == []
    assert soul["workflow_pattern"] == "sequential"


def test_extract_soul_returns_soul_typed_dict(tmp_path):
    """Test that extract_soul returns all expected keys."""
    from spellbook_mcp.soul_extractor import extract_soul

    transcript = tmp_path / "session.jsonl"
    transcript.write_text(json.dumps({"role": "assistant", "content": "test"}) + "\n")

    soul = extract_soul(str(transcript))

    # Verify all Soul TypedDict keys are present
    expected_keys = {
        "todos",
        "active_skill",
        "skill_phase",
        "persona",
        "recent_files",
        "exact_position",
        "workflow_pattern"
    }
    assert set(soul.keys()) == expected_keys
