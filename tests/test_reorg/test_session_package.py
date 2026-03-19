"""Tests that the session spawner package is importable from spellbook.session."""

import importlib

import pytest


def test_session_package_importable() -> None:
    """The session package should be importable."""
    mod = importlib.import_module("spellbook.session")
    assert mod is not None


def test_session_spawner_importable() -> None:
    """The spawner submodule should be importable."""
    mod = importlib.import_module("spellbook.session.spawner")
    assert mod is not None


def test_session_spawner_class_accessible() -> None:
    """SessionSpawner should be accessible from spellbook.session."""
    from spellbook.session import SessionSpawner

    assert SessionSpawner is not None
