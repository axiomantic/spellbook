"""Tests for spellbook.core.path_utils module."""

from spellbook.core.path_utils import (
    encode_cwd,
    get_project_dir,
    get_project_dir_for_path,
    get_project_dir_from_context,
    get_project_path_from_context,
    get_spellbook_config_dir,
    resolve_repo_root,
)


def test_resolve_repo_root_callable():
    """resolve_repo_root is callable."""
    assert callable(resolve_repo_root)


def test_encode_cwd_callable():
    """encode_cwd is callable and encodes paths correctly."""
    result = encode_cwd("/Users/alice/Development/spellbook", resolve_git_root=False)
    assert result == "Users-alice-Development-spellbook"


def test_get_spellbook_config_dir_returns_path():
    """get_spellbook_config_dir returns a Path."""
    from pathlib import Path
    result = get_spellbook_config_dir()
    assert isinstance(result, Path)


def test_get_project_dir_returns_path():
    """get_project_dir returns a Path."""
    from pathlib import Path
    result = get_project_dir()
    assert isinstance(result, Path)


def test_get_project_dir_for_path_returns_path():
    """get_project_dir_for_path returns a Path."""
    from pathlib import Path
    result = get_project_dir_for_path("/tmp/test-project")
    assert isinstance(result, Path)


def test_async_functions_are_coroutines():
    """Async functions are proper coroutine functions."""
    import asyncio
    assert asyncio.iscoroutinefunction(get_project_path_from_context)
    assert asyncio.iscoroutinefunction(get_project_dir_from_context)
