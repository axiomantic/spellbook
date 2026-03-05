"""Tests verifying Nim lifecycle is removed from claude_code.py (Task 4).

These tests verify that:
- _detect_nim, _compile_nim_hooks functions are removed from the module
- _check_nim_binaries_exist method is removed from ClaudeCodeInstaller
- No references to 'nim' remain in the module source
- Nim-only imports (subprocess, re, sys) are removed
- install() method no longer includes Nim compilation step
"""

import inspect

import pytest


class TestNimFunctionsRemoved:
    """Verify all Nim-related functions and methods are deleted."""

    def test_detect_nim_not_in_module(self):
        """_detect_nim function should not exist in claude_code module."""
        from installer.platforms import claude_code

        assert not hasattr(claude_code, "_detect_nim"), (
            "_detect_nim function still exists in claude_code module"
        )

    def test_compile_nim_hooks_not_in_module(self):
        """_compile_nim_hooks function should not exist in claude_code module."""
        from installer.platforms import claude_code

        assert not hasattr(claude_code, "_compile_nim_hooks"), (
            "_compile_nim_hooks function still exists in claude_code module"
        )

    def test_check_nim_binaries_exist_not_on_class(self):
        """_check_nim_binaries_exist method should not exist on ClaudeCodeInstaller."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        assert not hasattr(ClaudeCodeInstaller, "_check_nim_binaries_exist"), (
            "_check_nim_binaries_exist method still exists on ClaudeCodeInstaller"
        )


class TestNimImportsRemoved:
    """Verify Nim-only imports are cleaned up."""

    def test_no_subprocess_import(self):
        """subprocess import should be removed (only used by Nim functions)."""
        from installer.platforms import claude_code

        source = inspect.getsource(claude_code)
        # Check the import section (top of file) for subprocess
        import_lines = [
            line.strip()
            for line in source.split("\n")
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        assert "import subprocess" not in import_lines, (
            "subprocess is still imported but is no longer used"
        )

    def test_no_re_module_import(self):
        """re_module import should be removed (only used by _detect_nim)."""
        from installer.platforms import claude_code

        source = inspect.getsource(claude_code)
        import_lines = [
            line.strip()
            for line in source.split("\n")
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        assert "import re as re_module" not in import_lines, (
            "re as re_module is still imported but is no longer used"
        )

    def test_no_sys_import(self):
        """sys import should be removed (only used by _compile_nim_hooks)."""
        from installer.platforms import claude_code

        source = inspect.getsource(claude_code)
        import_lines = [
            line.strip()
            for line in source.split("\n")
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        assert "import sys" not in import_lines, (
            "sys is still imported but is no longer used"
        )


class TestNoNimReferences:
    """Verify no references to 'nim' remain in the module."""

    def test_no_nim_in_module_source(self):
        """No references to 'nim' should remain in claude_code.py source."""
        from installer.platforms import claude_code

        source = inspect.getsource(claude_code)
        # Check each line for 'nim' (case-insensitive), excluding this test's own imports
        nim_lines = []
        for i, line in enumerate(source.split("\n"), 1):
            if "nim" in line.lower():
                nim_lines.append(f"  line {i}: {line.strip()}")
        assert nim_lines == [], (
            f"Found 'nim' references in claude_code.py:\n" + "\n".join(nim_lines)
        )


class TestInstallMethodCleanedUp:
    """Verify the install() method no longer has Nim compilation logic."""

    def test_install_method_no_nim_step(self):
        """install() method should not reference 'Compiling Nim hooks' step."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        source = inspect.getsource(ClaudeCodeInstaller.install)
        assert "Compiling Nim hooks" not in source, (
            "install() still contains 'Compiling Nim hooks' step"
        )

    def test_install_method_no_nim_available(self):
        """install() method should not reference nim_available variable."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        source = inspect.getsource(ClaudeCodeInstaller.install)
        assert "nim_available" not in source, (
            "install() still references nim_available variable"
        )

    def test_install_method_no_nim_hooks_component(self):
        """install() method should not create nim_hooks InstallResult."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        source = inspect.getsource(ClaudeCodeInstaller.install)
        assert 'component="nim_hooks"' not in source, (
            "install() still creates nim_hooks component results"
        )

    def test_install_hooks_call_no_nim_parameter(self):
        """install_hooks() call should not pass nim_available parameter."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        source = inspect.getsource(ClaudeCodeInstaller.install)
        # Find the install_hooks call and verify no nim_available
        assert "nim_available=" not in source, (
            "install_hooks() call still passes nim_available parameter"
        )

    def test_install_hooks_still_called(self):
        """install_hooks() should still be called in install() method."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        source = inspect.getsource(ClaudeCodeInstaller.install)
        assert "install_hooks(" in source, (
            "install_hooks() call is missing from install() method"
        )

    def test_hooks_import_present(self):
        """install_hooks and uninstall_hooks should still be imported."""
        from installer.platforms import claude_code

        source = inspect.getsource(claude_code)
        assert "from ..components.hooks import install_hooks, uninstall_hooks" in source, (
            "hooks import is missing or incorrect"
        )
