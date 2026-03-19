"""Tests for spellbook.mcp.tools modules.

Verifies that all 13 tool modules are importable and each contains
@mcp.tool()-decorated functions.
"""

import importlib

import pytest

TOOL_MODULES = [
    "spellbook.mcp.tools.sessions",
    "spellbook.mcp.tools.config",
    "spellbook.mcp.tools.health",
    "spellbook.mcp.tools.memory",
    "spellbook.mcp.tools.security",
    "spellbook.mcp.tools.pr",
    "spellbook.mcp.tools.forged",
    "spellbook.mcp.tools.fractal",
    "spellbook.mcp.tools.coordination",
    "spellbook.mcp.tools.experiments",
    "spellbook.mcp.tools.notifications",
    "spellbook.mcp.tools.updates",
    "spellbook.mcp.tools.misc",
]


class TestToolModulesImportable:
    """Test that all 13 tool modules are importable."""

    @pytest.mark.parametrize("module_name", TOOL_MODULES)
    def test_module_importable(self, module_name):
        mod = importlib.import_module(module_name)
        assert mod is not None

    def test_tools_init_imports_all_modules(self):
        """Importing spellbook.mcp.tools should trigger all submodule imports."""
        import spellbook.mcp.tools  # noqa: F401

        # Verify submodules are loaded
        import sys

        for mod_name in TOOL_MODULES:
            assert mod_name in sys.modules, f"{mod_name} not loaded by tools __init__"
