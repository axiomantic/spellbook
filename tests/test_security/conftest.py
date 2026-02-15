"""Shared fixtures for security tests."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_skill(tmp_path):
    """Create a temporary skill file for testing."""
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    return skill_file


@pytest.fixture
def tmp_command(tmp_path):
    """Create a temporary command file for testing."""
    cmd_dir = tmp_path / "commands"
    cmd_dir.mkdir(parents=True)
    cmd_file = cmd_dir / "test-command.md"
    return cmd_file
