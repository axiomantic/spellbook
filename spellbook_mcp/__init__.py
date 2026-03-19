"""Backward compatibility shim. Will be removed in the next release.

All functionality has moved to the ``spellbook`` package.  Importing
``spellbook_mcp`` still works but emits a DeprecationWarning.

Submodule access (e.g. ``spellbook_mcp.db``, ``spellbook_mcp.server``)
is redirected to the corresponding ``spellbook.*`` module via
``__getattr__``.
"""

import importlib
import warnings

warnings.warn(
    "spellbook_mcp is deprecated. Use 'spellbook' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from spellbook import *  # noqa: F401,F403


def __getattr__(name: str):
    """Redirect attribute lookups to the spellbook package."""
    warnings.warn(
        f"spellbook_mcp.{name} is deprecated. Use spellbook.{name} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        return importlib.import_module(f"spellbook.{name}")
    except ImportError:
        raise AttributeError(f"module 'spellbook_mcp' has no attribute '{name}'")
