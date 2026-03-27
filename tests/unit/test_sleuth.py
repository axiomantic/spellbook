"""Tests for PromptSleuth semantic intent classifier."""
import json

import pytest


def test_parse_classification_valid():
    from spellbook.security.sleuth import parse_classification
    result = parse_classification('{"classification": "DIRECTIVE", "confidence": 0.85, "evidence": "found override"}')
    assert result["classification"] == "DIRECTIVE"
    assert result["confidence"] == 0.85
    assert result["evidence"] == "found override"


def test_parse_classification_invalid_json():
    from spellbook.security.sleuth import parse_classification
    result = parse_classification("not json")
    assert result["classification"] == "UNKNOWN"
    assert result["confidence"] == 0.0


def test_parse_classification_missing_fields():
    from spellbook.security.sleuth import parse_classification
    result = parse_classification('{"classification": "DATA"}')
    assert result["classification"] == "DATA"
    assert result["confidence"] == 0.0


def test_classification_prompt_contains_placeholders():
    from spellbook.security.sleuth import CLASSIFICATION_PROMPT
    assert "{content}" in CLASSIFICATION_PROMPT


def test_truncate_content():
    from spellbook.security.sleuth import _truncate_content
    long_content = "x" * 100000
    truncated = _truncate_content(long_content, max_bytes=50000)
    assert len(truncated) <= 50000


def test_truncate_content_short_passthrough():
    from spellbook.security.sleuth import _truncate_content
    short = "hello"
    assert _truncate_content(short, max_bytes=50000) == "hello"


class TestSleuthBudget:
    """Test budget enforcement logic."""

    def test_check_budget_available(self):
        from spellbook.security.sleuth import _check_budget
        budget = {"calls_remaining": 10}
        assert _check_budget(budget) is True

    def test_check_budget_exhausted(self):
        from spellbook.security.sleuth import _check_budget
        budget = {"calls_remaining": 0}
        assert _check_budget(budget) is False

    def test_check_budget_none(self):
        from spellbook.security.sleuth import _check_budget
        assert _check_budget(None) is True  # No budget record = unlimited


def test_content_hash_deterministic():
    from spellbook.security.sleuth import content_hash
    h1 = content_hash("test content")
    h2 = content_hash("test content")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_content_hash_different_for_different_content():
    from spellbook.security.sleuth import content_hash
    h1 = content_hash("content a")
    h2 = content_hash("content b")
    assert h1 != h2
