"""Tests for spellbook.core.compat module (runtime subset)."""

from spellbook.core.compat import (
    CrossPlatformLock,
    Platform,
    get_config_dir,
    _pid_exists,
)


def test_cross_platform_lock_is_class():
    """CrossPlatformLock is a class."""
    assert isinstance(CrossPlatformLock, type)


def test_cross_platform_lock_instantiable(tmp_path):
    """CrossPlatformLock can be instantiated with a lock path."""
    lock = CrossPlatformLock(tmp_path / "test.lock")
    assert lock.lock_path == tmp_path / "test.lock"


def test_platform_is_enum():
    """Platform is an enum with expected members."""
    assert hasattr(Platform, "MACOS")
    assert hasattr(Platform, "LINUX")
    assert hasattr(Platform, "WINDOWS")


def test_get_config_dir_callable():
    """get_config_dir is callable and returns a Path."""
    from pathlib import Path
    result = get_config_dir()
    assert isinstance(result, Path)


def test_pid_exists_callable():
    """_pid_exists is callable."""
    import os
    # Current process should exist
    assert _pid_exists(os.getpid()) is True
