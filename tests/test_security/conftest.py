"""Shared fixtures for security tests."""

import pytest
from pathlib import Path


class _Utf8PathWrapper:
    """Wraps a Path object to ensure write_text always uses UTF-8 encoding.

    On Windows, the default encoding may not be UTF-8, causing
    UnicodeEncodeError when writing files with special characters
    (zero-width spaces, RTL overrides, etc.). This wrapper ensures
    all write_text calls use encoding='utf-8' by default.
    """

    def __init__(self, path: Path):
        self._path = path

    def write_text(self, content: str, encoding: str = "utf-8", **kwargs) -> int:
        return self._path.write_text(content, encoding=encoding, **kwargs)

    def read_text(self, encoding: str = "utf-8", **kwargs) -> str:
        return self._path.read_text(encoding=encoding, **kwargs)

    def __str__(self) -> str:
        return str(self._path)

    def __fspath__(self) -> str:
        return str(self._path)

    def __getattr__(self, name):
        return getattr(self._path, name)


@pytest.fixture
def tmp_skill(tmp_path):
    """Create a temporary skill file for testing."""
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    return _Utf8PathWrapper(skill_file)


@pytest.fixture
def tmp_command(tmp_path):
    """Create a temporary command file for testing."""
    cmd_dir = tmp_path / "commands"
    cmd_dir.mkdir(parents=True)
    cmd_file = cmd_dir / "test-command.md"
    return _Utf8PathWrapper(cmd_file)
