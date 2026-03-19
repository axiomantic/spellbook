"""Tests that the admin package is importable from spellbook.admin."""

import importlib

import pytest


def test_admin_importable() -> None:
    """The admin package should be importable."""
    mod = importlib.import_module("spellbook.admin")
    assert mod is not None


@pytest.mark.parametrize(
    "submodule",
    [
        "spellbook.admin.app",
        "spellbook.admin.auth",
        "spellbook.admin.routes",
    ],
)
def test_admin_submodule_importable(submodule: str) -> None:
    """Key admin submodules should be importable."""
    mod = importlib.import_module(submodule)
    assert mod is not None
