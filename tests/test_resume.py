"""Tests for session resume detection and boot prompt generation."""

import pytest
from typing import Optional


class TestContinuationIntent:
    """Tests for continuation intent detection."""

    def test_continuation_intent_has_required_fields(self):
        """Test that ContinuationIntent TypedDict has all required fields."""
        from spellbook_mcp.resume import ContinuationIntent

        # Create instance to verify structure
        intent: ContinuationIntent = {
            "intent": "continue",
            "confidence": "high",
            "pattern": r"^\s*continue\s*$",
        }

        assert intent["intent"] == "continue"
        assert intent["confidence"] == "high"
        assert intent["pattern"] == r"^\s*continue\s*$"

    def test_continuation_intent_pattern_can_be_none(self):
        """Test that pattern field can be None for neutral intent."""
        from spellbook_mcp.resume import ContinuationIntent

        intent: ContinuationIntent = {
            "intent": "neutral",
            "confidence": "low",
            "pattern": None,
        }

        assert intent["pattern"] is None


class TestDetectContinuationIntent:
    """Tests for detect_continuation_intent function."""

    @pytest.mark.parametrize("message,expected_intent,expected_confidence", [
        ("continue", "continue", "high"),
        ("Continue", "continue", "high"),
        ("  continue  ", "continue", "high"),
        ("resume", "continue", "high"),
        ("where were we", "continue", "high"),
        ("pick up where we left off", "continue", "high"),
        ("let's continue", "continue", "high"),
        ("lets continue", "continue", "high"),
        ("carry on", "continue", "high"),
        ("what were we doing", "continue", "high"),
        ("what were we working on", "continue", "high"),
        ("back to it", "continue", "high"),
        ("back to work", "continue", "high"),
    ])
    def test_explicit_continue_patterns(self, message, expected_intent, expected_confidence):
        """Test explicit continue patterns are detected with high confidence."""
        from spellbook_mcp.resume import detect_continuation_intent

        result = detect_continuation_intent(message, has_recent_session=False)

        assert result["intent"] == expected_intent
        assert result["confidence"] == expected_confidence
        assert result["pattern"] is not None

    @pytest.mark.parametrize("message", [
        "start fresh",
        "begin fresh",
        "start new",
        "begin new",
        "start over",
        "new session",
        "new task",
        "new project",
        "forget previous",
        "forget last",
        "forget prior",
        "clean slate",
        "from scratch",
        "from beginning",
    ])
    def test_fresh_start_patterns(self, message):
        """Test fresh start patterns override resume even if session exists."""
        from spellbook_mcp.resume import detect_continuation_intent

        result = detect_continuation_intent(message, has_recent_session=True)

        assert result["intent"] == "fresh_start"
        assert result["confidence"] == "high"
        assert result["pattern"] is not None

    @pytest.mark.parametrize("message", [
        "ok",
        "okay",
        "alright",
        "sure",
        "ready",
        "go",
        "next",
        "next step",
        "next task",
        "next item",
        "and then",
        "also, let's",
    ])
    def test_implicit_continue_with_session(self, message):
        """Test implicit patterns trigger continue only with recent session."""
        from spellbook_mcp.resume import detect_continuation_intent

        # With recent session: medium confidence continue
        result = detect_continuation_intent(message, has_recent_session=True)
        assert result["intent"] == "continue"
        assert result["confidence"] == "medium"

    @pytest.mark.parametrize("message", [
        "ok",
        "okay",
        "next",
        "sure",
    ])
    def test_implicit_patterns_without_session(self, message):
        """Test implicit patterns return neutral without recent session."""
        from spellbook_mcp.resume import detect_continuation_intent

        result = detect_continuation_intent(message, has_recent_session=False)
        assert result["intent"] == "neutral"
        assert result["confidence"] == "low"


class TestCountPendingTodos:
    """Tests for count_pending_todos function."""

    def test_count_pending_todos_none_input(self):
        """Test None input returns (0, False)."""
        from spellbook_mcp.resume import count_pending_todos

        count, corrupted = count_pending_todos(None)

        assert count == 0
        assert corrupted is False

    def test_count_pending_todos_empty_array(self):
        """Test empty array returns (0, False)."""
        from spellbook_mcp.resume import count_pending_todos

        count, corrupted = count_pending_todos("[]")

        assert count == 0
        assert corrupted is False

    def test_count_pending_todos_with_pending(self):
        """Test counts non-completed todos."""
        from spellbook_mcp.resume import count_pending_todos
        import json

        todos = json.dumps([
            {"content": "Task 1", "status": "pending"},
            {"content": "Task 2", "status": "in_progress"},
            {"content": "Task 3", "status": "completed"},
        ])

        count, corrupted = count_pending_todos(todos)

        assert count == 2
        assert corrupted is False

    def test_count_pending_todos_all_completed(self):
        """Test all completed returns 0."""
        from spellbook_mcp.resume import count_pending_todos
        import json

        todos = json.dumps([
            {"content": "Task 1", "status": "completed"},
            {"content": "Task 2", "status": "completed"},
        ])

        count, corrupted = count_pending_todos(todos)

        assert count == 0
        assert corrupted is False

    def test_count_pending_todos_malformed_json(self):
        """Test malformed JSON returns (0, True)."""
        from spellbook_mcp.resume import count_pending_todos

        count, corrupted = count_pending_todos("not valid json")

        assert count == 0
        assert corrupted is True

    def test_count_pending_todos_not_array(self):
        """Test non-array JSON returns (0, True)."""
        from spellbook_mcp.resume import count_pending_todos

        count, corrupted = count_pending_todos('{"key": "value"}')

        assert count == 0
        assert corrupted is True

    def test_count_pending_todos_mixed_items(self):
        """Test handles mixed item types gracefully."""
        from spellbook_mcp.resume import count_pending_todos
        import json

        todos = json.dumps([
            {"content": "Valid", "status": "pending"},
            "not a dict",
            None,
            {"content": "Also valid", "status": "in_progress"},
        ])

        count, corrupted = count_pending_todos(todos)

        # Should count valid pending items and not crash
        assert count == 2
        assert corrupted is False
