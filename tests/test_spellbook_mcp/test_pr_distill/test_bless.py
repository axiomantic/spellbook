"""Tests for pr_distill pattern blessing with validation."""

import json
from unittest.mock import patch

import pytest

from spellbook_mcp.pr_distill.bless import (
    validate_pattern_id,
    bless_pattern,
    list_blessed_patterns,
)


class TestValidatePatternId:
    """Test pattern ID validation rules."""

    def test_valid_simple_pattern(self):
        """Valid simple pattern ID passes validation."""
        result = validate_pattern_id("my-pattern")
        assert result["valid"] is True
        assert "error" not in result

    def test_valid_minimum_length(self):
        """Pattern ID at minimum length (2 chars) is valid."""
        result = validate_pattern_id("ab")
        assert result["valid"] is True

    def test_valid_maximum_length(self):
        """Pattern ID at maximum length (50 chars) is valid."""
        pattern = "a" + "b" * 48 + "c"  # 50 chars total
        assert len(pattern) == 50
        result = validate_pattern_id(pattern)
        assert result["valid"] is True

    def test_valid_with_numbers(self):
        """Pattern ID with numbers is valid."""
        result = validate_pattern_id("pattern-v2")
        assert result["valid"] is True

    def test_invalid_too_short(self):
        """Pattern ID with 1 character is invalid."""
        result = validate_pattern_id("a")
        assert result["valid"] is False
        assert "2-50 characters" in result["error"]

    def test_invalid_too_long(self):
        """Pattern ID over 50 characters is invalid."""
        pattern = "a" * 51
        result = validate_pattern_id(pattern)
        assert result["valid"] is False
        assert "2-50 characters" in result["error"]

    def test_invalid_reserved_prefix(self):
        """Pattern ID starting with _builtin- is invalid."""
        result = validate_pattern_id("_builtin-test")
        assert result["valid"] is False
        assert "_builtin-" in result["error"]

    def test_invalid_uppercase_characters(self):
        """Pattern ID with uppercase letters is invalid."""
        result = validate_pattern_id("MyPattern")
        assert result["valid"] is False
        assert "lowercase" in result["error"]

    def test_invalid_special_characters(self):
        """Pattern ID with special characters (underscore) is invalid."""
        result = validate_pattern_id("my_pattern")
        assert result["valid"] is False
        assert "lowercase letters, numbers, and hyphens" in result["error"]

    def test_invalid_starts_with_number(self):
        """Pattern ID starting with a number is invalid."""
        result = validate_pattern_id("1pattern")
        assert result["valid"] is False
        assert "start with a letter" in result["error"]

    def test_invalid_starts_with_hyphen(self):
        """Pattern ID starting with a hyphen is invalid."""
        result = validate_pattern_id("-pattern")
        assert result["valid"] is False
        assert "start with a letter" in result["error"]

    def test_invalid_ends_with_hyphen(self):
        """Pattern ID ending with a hyphen is invalid."""
        result = validate_pattern_id("pattern-")
        assert result["valid"] is False
        assert "end with a letter or number" in result["error"]

    def test_invalid_double_hyphen(self):
        """Pattern ID with double hyphen is invalid."""
        result = validate_pattern_id("my--pattern")
        assert result["valid"] is False
        assert "double hyphen" in result["error"]


class TestBlessPattern:
    """Test pattern blessing with validation."""

    def test_bless_valid_pattern(self, tmp_path):
        """Bless a valid pattern succeeds."""
        project_root = "/Users/alice/project"

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = bless_pattern(project_root, "my-pattern")

        assert result["success"] is True
        assert "my-pattern" in result["config"]["blessed_patterns"]

    def test_bless_invalid_pattern(self, tmp_path):
        """Bless an invalid pattern fails with error."""
        project_root = "/Users/alice/project"

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = bless_pattern(project_root, "a")  # Too short

        assert result["success"] is False
        assert "error" in result
        assert "2-50 characters" in result["error"]

    def test_bless_already_blessed_is_idempotent(self, tmp_path):
        """Blessing an already-blessed pattern is idempotent."""
        project_root = "/Users/alice/project"
        config_dir = tmp_path / "Users-alice-project"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-distill-config.json"

        existing_config = {
            "blessed_patterns": ["my-pattern"],
            "always_review_paths": [],
            "query_count_thresholds": {
                "relative_percent": 20,
                "absolute_delta": 10,
            },
        }
        config_file.write_text(json.dumps(existing_config))

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = bless_pattern(project_root, "my-pattern")

        assert result["success"] is True
        # Should still have exactly one occurrence
        assert result["config"]["blessed_patterns"].count("my-pattern") == 1


class TestListBlessedPatterns:
    """Test listing blessed patterns."""

    def test_list_empty_when_no_config(self, tmp_path):
        """Returns empty list when no config exists."""
        project_root = "/Users/alice/project"

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = list_blessed_patterns(project_root)

        assert result == []

    def test_list_returns_blessed_patterns(self, tmp_path):
        """Returns list of blessed patterns from config."""
        project_root = "/Users/alice/project"
        config_dir = tmp_path / "Users-alice-project"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-distill-config.json"

        config = {
            "blessed_patterns": ["pattern-1", "pattern-2"],
            "always_review_paths": [],
            "query_count_thresholds": {
                "relative_percent": 20,
                "absolute_delta": 10,
            },
        }
        config_file.write_text(json.dumps(config))

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = list_blessed_patterns(project_root)

        assert result == ["pattern-1", "pattern-2"]

    def test_list_after_blessing(self, tmp_path):
        """List shows newly blessed patterns."""
        project_root = "/Users/alice/project"

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            bless_pattern(project_root, "new-pattern")
            result = list_blessed_patterns(project_root)

        assert "new-pattern" in result
