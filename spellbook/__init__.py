"""Spellbook: AI assistant enhancement toolkit."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("spellbook")
except PackageNotFoundError:
    __version__ = "dev"
