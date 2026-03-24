"""Verify new dependencies are importable."""
import importlib

import pytest


def test_cryptography_importable():
    """cryptography package must be installed for Ed25519 signing."""
    mod = importlib.import_module("cryptography.hazmat.primitives.asymmetric.ed25519")
    assert hasattr(mod, "Ed25519PrivateKey")


def test_rich_importable():
    """rich package must be installed for TUI installer."""
    mod = importlib.import_module("rich.console")
    assert hasattr(mod, "Console")


@pytest.mark.external
def test_anthropic_importable():
    """anthropic package must be installed when [sleuth] extra is used."""
    mod = importlib.import_module("anthropic")
    assert hasattr(mod, "AsyncAnthropic")
