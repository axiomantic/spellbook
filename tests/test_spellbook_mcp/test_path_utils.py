"""Tests for path encoding and project directory resolution."""

import pytest
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


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
    """Test project directory resolution uses portable default."""
    from spellbook_mcp.path_utils import get_project_dir

    monkeypatch.setattr(os, 'getcwd', lambda: '/Users/test/Development/myproject')
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    monkeypatch.delenv('SPELLBOOK_CONFIG_DIR', raising=False)

    result = get_project_dir()
    # Default is ~/.local/spellbook (portable location)
    expected = Path.home() / '.local' / 'spellbook' / 'projects' / 'Users-test-Development-myproject'
    assert result == expected


def test_get_project_dir_respects_spellbook_config_dir(monkeypatch):
    """Test that SPELLBOOK_CONFIG_DIR environment variable is respected."""
    from spellbook_mcp.path_utils import get_project_dir

    monkeypatch.setattr(os, 'getcwd', lambda: '/Users/test/project')
    monkeypatch.setenv('SPELLBOOK_CONFIG_DIR', '/custom/config')

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
    monkeypatch.delenv('SPELLBOOK_CONFIG_DIR', raising=False)

    result = get_project_dir()

    # Should be a Path object
    assert isinstance(result, Path)

    # Should contain expected components
    assert 'projects' in result.parts
    assert result.parts[-1] == 'Users-test-myapp'


def test_get_project_dir_for_path(monkeypatch):
    """Test get_project_dir_for_path with explicit path."""
    from spellbook_mcp.path_utils import get_project_dir_for_path

    monkeypatch.delenv('SPELLBOOK_CONFIG_DIR', raising=False)

    result = get_project_dir_for_path('/Users/alice/Development/myproject')

    assert isinstance(result, Path)
    assert result.parts[-1] == 'Users-alice-Development-myproject'
    assert 'projects' in result.parts


def test_get_project_dir_for_path_with_config_dir(monkeypatch):
    """Test get_project_dir_for_path respects SPELLBOOK_CONFIG_DIR."""
    from spellbook_mcp.path_utils import get_project_dir_for_path

    monkeypatch.setenv('SPELLBOOK_CONFIG_DIR', '/custom/spellbook')

    result = get_project_dir_for_path('/Users/bob/project')

    assert result == Path('/custom/spellbook/projects/Users-bob-project')


@pytest.mark.asyncio
async def test_get_project_path_from_context_with_roots(monkeypatch):
    """Test extracting project path from MCP context roots."""
    from spellbook_mcp.path_utils import get_project_path_from_context

    # Create a mock Root object
    mock_root = MagicMock()
    mock_root.uri = 'file:///Users/alice/Development/myproject'

    # Create a mock context
    mock_ctx = MagicMock()
    mock_ctx.list_roots = AsyncMock(return_value=[mock_root])

    result = await get_project_path_from_context(mock_ctx)

    assert result == '/Users/alice/Development/myproject'
    mock_ctx.list_roots.assert_called_once()


@pytest.mark.asyncio
async def test_get_project_path_from_context_no_roots(monkeypatch):
    """Test fallback to cwd when no roots available."""
    from spellbook_mcp.path_utils import get_project_path_from_context

    monkeypatch.setattr(os, 'getcwd', lambda: '/fallback/cwd')

    # Context with empty roots
    mock_ctx = MagicMock()
    mock_ctx.list_roots = AsyncMock(return_value=[])

    result = await get_project_path_from_context(mock_ctx)

    assert result == '/fallback/cwd'


@pytest.mark.asyncio
async def test_get_project_path_from_context_none_context(monkeypatch):
    """Test fallback to cwd when context is None."""
    from spellbook_mcp.path_utils import get_project_path_from_context

    monkeypatch.setattr(os, 'getcwd', lambda: '/fallback/cwd')

    result = await get_project_path_from_context(None)

    assert result == '/fallback/cwd'


@pytest.mark.asyncio
async def test_get_project_path_from_context_list_roots_error(monkeypatch):
    """Test fallback to cwd when list_roots raises an exception."""
    from spellbook_mcp.path_utils import get_project_path_from_context

    monkeypatch.setattr(os, 'getcwd', lambda: '/fallback/cwd')

    # Context that raises on list_roots
    mock_ctx = MagicMock()
    mock_ctx.list_roots = AsyncMock(side_effect=RuntimeError("MCP not connected"))

    result = await get_project_path_from_context(mock_ctx)

    assert result == '/fallback/cwd'


@pytest.mark.asyncio
async def test_get_project_path_from_context_non_file_uri(monkeypatch):
    """Test fallback when root URI is not a file:// URI."""
    from spellbook_mcp.path_utils import get_project_path_from_context

    monkeypatch.setattr(os, 'getcwd', lambda: '/fallback/cwd')

    # Root with non-file URI
    mock_root = MagicMock()
    mock_root.uri = 'https://example.com/project'

    mock_ctx = MagicMock()
    mock_ctx.list_roots = AsyncMock(return_value=[mock_root])

    result = await get_project_path_from_context(mock_ctx)

    assert result == '/fallback/cwd'


@pytest.mark.asyncio
async def test_get_project_dir_from_context(monkeypatch):
    """Test get_project_dir_from_context returns correct Path."""
    from spellbook_mcp.path_utils import get_project_dir_from_context

    monkeypatch.delenv('SPELLBOOK_CONFIG_DIR', raising=False)

    # Create mock context with root
    mock_root = MagicMock()
    mock_root.uri = 'file:///Users/alice/myproject'

    mock_ctx = MagicMock()
    mock_ctx.list_roots = AsyncMock(return_value=[mock_root])

    result = await get_project_dir_from_context(mock_ctx)

    assert isinstance(result, Path)
    assert result.parts[-1] == 'Users-alice-myproject'
    assert 'projects' in result.parts
