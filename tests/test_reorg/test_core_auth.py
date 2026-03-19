"""Tests for spellbook.core.auth module."""

from spellbook.core.auth import (
    BearerAuthMiddleware,
    TOKEN_PATH,
    generate_and_store_token,
    load_token,
    auth_is_disabled,
)


def test_generate_and_store_token_exists():
    """generate_and_store_token is callable."""
    assert callable(generate_and_store_token)


def test_load_token_exists():
    """load_token is callable."""
    assert callable(load_token)


def test_auth_is_disabled_exists():
    """auth_is_disabled is callable."""
    assert callable(auth_is_disabled)


def test_bearer_auth_middleware_is_class():
    """BearerAuthMiddleware is a class that can be instantiated."""
    assert isinstance(BearerAuthMiddleware, type)


def test_token_path_is_path():
    """TOKEN_PATH is a Path object."""
    from pathlib import Path
    assert isinstance(TOKEN_PATH, Path)
