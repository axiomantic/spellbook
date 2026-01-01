"""Tests for path encoding and project directory resolution."""

import pytest
import os
from pathlib import Path


def test_encode_cwd_basic():
    """Test basic path encoding."""
    from spellbook_mcp.path_utils import encode_cwd

    result = encode_cwd('/Users/alice/Development/spellbook')
    assert result == 'Users-alice-Development-spellbook'


def test_encode_cwd_with_leading_slash():
    """Test that leading slash is stripped."""
    from spellbook_mcp.path_utils import encode_cwd

    result = encode_cwd('/home/bob/projects/my-app')
    assert result == 'home-bob-projects-my-app'


def test_encode_cwd_root_directory():
    """Test encoding of root directory."""
    from spellbook_mcp.path_utils import encode_cwd

    result = encode_cwd('/')
    assert result == ''


def test_get_project_dir_with_cwd(monkeypatch):
    """Test project directory resolution."""
    from spellbook_mcp.path_utils import get_project_dir

    monkeypatch.setattr(os, 'getcwd', lambda: '/Users/test/Development/myproject')
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)

    result = get_project_dir()
    expected = Path.home() / '.claude' / 'projects' / 'Users-test-Development-myproject'
    assert result == expected


def test_get_project_dir_respects_claude_config_dir(monkeypatch):
    """Test that CLAUDE_CONFIG_DIR environment variable is respected."""
    from spellbook_mcp.path_utils import get_project_dir

    monkeypatch.setattr(os, 'getcwd', lambda: '/Users/test/project')
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', '/custom/config')

    result = get_project_dir()
    expected = Path('/custom/config/projects/Users-test-project')
    assert result == expected


def test_encode_cwd_with_trailing_slash():
    """Test encoding path with trailing slash."""
    from spellbook_mcp.path_utils import encode_cwd

    result = encode_cwd('/Users/alice/project/')
    assert result == 'Users-alice-project-'


def test_get_project_dir_creates_valid_path(monkeypatch):
    """Test that project dir path is valid."""
    from spellbook_mcp.path_utils import get_project_dir

    monkeypatch.setattr(os, 'getcwd', lambda: '/Users/test/myapp')
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)

    result = get_project_dir()

    # Should be a Path object
    assert isinstance(result, Path)

    # Should contain expected components
    assert 'projects' in result.parts
    assert result.parts[-1] == 'Users-test-myapp'
