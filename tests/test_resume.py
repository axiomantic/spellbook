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
