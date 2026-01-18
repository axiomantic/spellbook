"""Tests for pr_distill configuration management."""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from spellbook_mcp.pr_distill.config import (
    CONFIG_DIR,
    DEFAULT_CONFIG,
    encode_project_path,
    get_config_path,
    load_config,
    save_config,
    bless_pattern,
)


class TestEncodeProjectPath:
    """Test project path encoding."""

    def test_simple_path(self):
        """Encode a simple absolute path."""
        result = encode_project_path("/Users/alice/project")
        assert result == "Users-alice-project"

    def test_nested_path(self):
        """Encode a deeply nested path."""
        result = encode_project_path("/Users/alice/Development/work/myproject")
        assert result == "Users-alice-Development-work-myproject"

    def test_path_preserves_special_chars(self):
        """Non-slash special characters are preserved."""
        result = encode_project_path("/Users/alice/my-project_v2")
        assert result == "Users-alice-my-project_v2"

    def test_root_path(self):
        """Handle root-level directory."""
        result = encode_project_path("/project")
        assert result == "project"


class TestGetConfigPath:
    """Test config path generation."""

    def test_returns_correct_path(self):
        """Config path is in ~/.local/spellbook/docs/{encoded}/."""
        result = get_config_path("/Users/alice/project")
        expected = os.path.join(
            os.path.expanduser("~"),
            ".local", "spellbook", "docs",
            "Users-alice-project",
            "pr-distill-config.json"
        )
        assert result == expected

    def test_config_dir_constant(self):
        """CONFIG_DIR points to ~/.local/spellbook/docs."""
        expected = os.path.join(os.path.expanduser("~"), ".local", "spellbook", "docs")
        assert CONFIG_DIR == expected


class TestDefaultConfig:
    """Test default configuration values."""

    def test_default_config_structure(self):
        """DEFAULT_CONFIG has expected keys."""
        assert "blessed_patterns" in DEFAULT_CONFIG
        assert "always_review_paths" in DEFAULT_CONFIG
        assert "query_count_thresholds" in DEFAULT_CONFIG

    def test_default_blessed_patterns_empty(self):
        """blessed_patterns defaults to empty list."""
        assert DEFAULT_CONFIG["blessed_patterns"] == []

    def test_default_always_review_paths_empty(self):
        """always_review_paths defaults to empty list."""
        assert DEFAULT_CONFIG["always_review_paths"] == []

    def test_default_thresholds(self):
        """Query count thresholds have expected defaults."""
        thresholds = DEFAULT_CONFIG["query_count_thresholds"]
        assert thresholds["relative_percent"] == 20
        # Note: JS has absolute_delta=10, task says 3
        # Using the JS value as source of truth
        assert thresholds["absolute_delta"] == 10


class TestLoadConfig:
    """Test configuration loading."""

    def test_returns_defaults_when_file_not_exists(self, tmp_path):
        """Return DEFAULT_CONFIG when config file doesn't exist."""
        project_root = str(tmp_path / "nonexistent_project")

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = load_config(project_root)

        assert result == DEFAULT_CONFIG
        # Verify it's a copy, not the same object
        assert result is not DEFAULT_CONFIG

    def test_loads_existing_config(self, tmp_path):
        """Load config from existing file."""
        project_root = "/Users/alice/project"
        config_dir = tmp_path / "Users-alice-project"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-distill-config.json"

        custom_config = {
            "blessed_patterns": ["pattern-1", "pattern-2"],
            "always_review_paths": ["/important/"],
            "query_count_thresholds": {
                "relative_percent": 30,
                "absolute_delta": 5,
            },
        }
        config_file.write_text(json.dumps(custom_config))

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = load_config(project_root)

        assert result["blessed_patterns"] == ["pattern-1", "pattern-2"]
        assert result["always_review_paths"] == ["/important/"]
        assert result["query_count_thresholds"]["relative_percent"] == 30

    def test_merges_with_defaults_for_missing_keys(self, tmp_path):
        """Config missing keys gets defaults merged in."""
        project_root = "/Users/alice/project"
        config_dir = tmp_path / "Users-alice-project"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-distill-config.json"

        # Partial config missing always_review_paths
        partial_config = {
            "blessed_patterns": ["pattern-1"],
        }
        config_file.write_text(json.dumps(partial_config))

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = load_config(project_root)

        assert result["blessed_patterns"] == ["pattern-1"]
        assert result["always_review_paths"] == []  # From defaults
        assert result["query_count_thresholds"] == DEFAULT_CONFIG["query_count_thresholds"]

    def test_returns_defaults_on_invalid_json(self, tmp_path):
        """Return defaults when config file has invalid JSON."""
        project_root = "/Users/alice/project"
        config_dir = tmp_path / "Users-alice-project"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-distill-config.json"

        config_file.write_text("{ invalid json }")

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = load_config(project_root)

        assert result == DEFAULT_CONFIG


class TestSaveConfig:
    """Test configuration saving."""

    def test_creates_directories(self, tmp_path):
        """save_config creates parent directories if needed."""
        project_root = "/Users/alice/project"

        config = {
            "blessed_patterns": ["test-pattern"],
            "always_review_paths": [],
            "query_count_thresholds": {
                "relative_percent": 20,
                "absolute_delta": 10,
            },
        }

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            save_config(project_root, config)

        config_path = tmp_path / "Users-alice-project" / "pr-distill-config.json"
        assert config_path.exists()

    def test_writes_json_content(self, tmp_path):
        """save_config writes valid JSON."""
        project_root = "/Users/alice/project"

        config = {
            "blessed_patterns": ["pattern-1"],
            "always_review_paths": ["/critical/"],
            "query_count_thresholds": {
                "relative_percent": 25,
                "absolute_delta": 5,
            },
        }

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            save_config(project_root, config)

        config_path = tmp_path / "Users-alice-project" / "pr-distill-config.json"
        loaded = json.loads(config_path.read_text())

        assert loaded["blessed_patterns"] == ["pattern-1"]
        assert loaded["always_review_paths"] == ["/critical/"]
        assert loaded["query_count_thresholds"]["relative_percent"] == 25

    def test_overwrites_existing_config(self, tmp_path):
        """save_config overwrites existing config file."""
        project_root = "/Users/alice/project"
        config_dir = tmp_path / "Users-alice-project"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-distill-config.json"

        # Write initial config
        config_file.write_text(json.dumps({"blessed_patterns": ["old"]}))

        new_config = {
            "blessed_patterns": ["new"],
            "always_review_paths": [],
            "query_count_thresholds": DEFAULT_CONFIG["query_count_thresholds"],
        }

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            save_config(project_root, new_config)

        loaded = json.loads(config_file.read_text())
        assert loaded["blessed_patterns"] == ["new"]


class TestBlessPattern:
    """Test pattern blessing functionality."""

    def test_adds_pattern_to_empty_list(self, tmp_path):
        """Bless a pattern when no config exists."""
        project_root = "/Users/alice/project"

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = bless_pattern(project_root, "new-pattern")

        assert "new-pattern" in result["blessed_patterns"]

        # Verify it was saved
        config_path = tmp_path / "Users-alice-project" / "pr-distill-config.json"
        loaded = json.loads(config_path.read_text())
        assert "new-pattern" in loaded["blessed_patterns"]

    def test_adds_pattern_to_existing_list(self, tmp_path):
        """Add pattern to existing blessed patterns."""
        project_root = "/Users/alice/project"
        config_dir = tmp_path / "Users-alice-project"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-distill-config.json"

        existing_config = {
            "blessed_patterns": ["existing-pattern"],
            "always_review_paths": [],
            "query_count_thresholds": DEFAULT_CONFIG["query_count_thresholds"],
        }
        config_file.write_text(json.dumps(existing_config))

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = bless_pattern(project_root, "new-pattern")

        assert result["blessed_patterns"] == ["existing-pattern", "new-pattern"]

    def test_does_not_duplicate_pattern(self, tmp_path):
        """Blessing same pattern twice doesn't create duplicates."""
        project_root = "/Users/alice/project"
        config_dir = tmp_path / "Users-alice-project"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "pr-distill-config.json"

        existing_config = {
            "blessed_patterns": ["pattern-1"],
            "always_review_paths": [],
            "query_count_thresholds": DEFAULT_CONFIG["query_count_thresholds"],
        }
        config_file.write_text(json.dumps(existing_config))

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            # Bless same pattern twice
            bless_pattern(project_root, "pattern-1")
            result = bless_pattern(project_root, "pattern-1")

        assert result["blessed_patterns"] == ["pattern-1"]
        assert result["blessed_patterns"].count("pattern-1") == 1

    def test_returns_updated_config(self, tmp_path):
        """bless_pattern returns the full updated config."""
        project_root = "/Users/alice/project"

        with patch("spellbook_mcp.pr_distill.config.CONFIG_DIR", str(tmp_path)):
            result = bless_pattern(project_root, "test-pattern")

        assert "blessed_patterns" in result
        assert "always_review_paths" in result
        assert "query_count_thresholds" in result
