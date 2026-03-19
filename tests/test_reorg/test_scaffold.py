"""Tests for the spellbook package scaffold.

Verifies that all packages in the three-layer architecture are importable.
"""

import importlib

import pytest


class TestSpellbookPackage:
    """Test that the top-level spellbook package is importable and configured."""

    def test_import_spellbook(self):
        import spellbook

        assert hasattr(spellbook, "__file__")
        assert spellbook.__file__ is not None

    def test_spellbook_has_version(self):
        import spellbook

        assert hasattr(spellbook, "__version__")
        assert isinstance(spellbook.__version__, str)
        assert len(spellbook.__version__) > 0


class TestCoreLayer:
    """Test that the core package is importable."""

    def test_import_core(self):
        import spellbook.core

        assert hasattr(spellbook.core, "__file__")


class TestDomainPackages:
    """Test that all domain packages are importable."""

    @pytest.mark.parametrize(
        "package",
        [
            "spellbook.memory",
            "spellbook.health",
            "spellbook.sessions",
            "spellbook.notifications",
            "spellbook.updates",
            "spellbook.experiments",
        ],
    )
    def test_import_domain_package(self, package):
        mod = importlib.import_module(package)
        assert hasattr(mod, "__file__")


class TestInterfacePackages:
    """Test that all interface packages are importable."""

    @pytest.mark.parametrize(
        "package",
        [
            "spellbook.mcp",
            "spellbook.mcp.tools",
            "spellbook.daemon",
            "spellbook.cli",
            "spellbook.cli.commands",
        ],
    )
    def test_import_interface_package(self, package):
        mod = importlib.import_module(package)
        assert hasattr(mod, "__file__")


class TestCLIEntryPoint:
    """Test that the CLI main module is importable and has a main function."""

    def test_cli_main_importable(self):
        from spellbook.cli.main import main

        assert callable(main)

    def test_cli_main_prints_placeholder(self, capsys):
        from spellbook.cli.main import main

        main()
        captured = capsys.readouterr()
        assert "not yet implemented" in captured.out.lower()


class TestMainModule:
    """Test that python -m spellbook entry point exists."""

    def test_main_module_importable(self):
        mod = importlib.import_module("spellbook.__main__")
        assert hasattr(mod, "__file__")
