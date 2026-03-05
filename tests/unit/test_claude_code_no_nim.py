"""Tests verifying Nim lifecycle is removed from claude_code.py (Task 4).

These tests verify that:
- _detect_nim, _compile_nim_hooks functions are removed from the module
- _check_nim_binaries_exist method is removed from ClaudeCodeInstaller
- No references to 'nim' remain in the module source
- Nim-only imports (subprocess, re, sys) are removed
- install() method no longer includes Nim compilation step
"""

import ast
import inspect
import textwrap

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

    def _get_module_imports(self):
        """Parse the module's AST and return all imported module names."""
        from installer.platforms import claude_code

        source = inspect.getsource(claude_code)
        tree = ast.parse(source)
        imported_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.append(node.module)
        return imported_names

    def test_no_subprocess_import(self):
        """subprocess import should be removed (only used by Nim functions)."""
        from installer.platforms import claude_code

        assert not hasattr(claude_code, "subprocess"), (
            "subprocess is still imported into claude_code module namespace"
        )
        imported = self._get_module_imports()
        assert "subprocess" not in imported, (
            "subprocess is still imported but is no longer used"
        )

    def test_no_re_module_import(self):
        """re module import should be removed (only used by _detect_nim)."""
        from installer.platforms import claude_code

        # Check that 're' is not available as an attribute (imported as re_module or re)
        members = dict(inspect.getmembers(claude_code))
        assert "re_module" not in members, (
            "re_module is still in claude_code module namespace"
        )
        imported = self._get_module_imports()
        assert "re" not in imported, (
            "re is still imported but is no longer used"
        )

    def test_no_sys_import(self):
        """sys import should be removed (only used by _compile_nim_hooks)."""
        from installer.platforms import claude_code

        assert not hasattr(claude_code, "sys"), (
            "sys is still imported into claude_code module namespace"
        )
        imported = self._get_module_imports()
        assert "sys" not in imported, (
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

    def _get_install_method_ast(self):
        """Parse ClaudeCodeInstaller.install() and return its AST."""
        from installer.platforms.claude_code import ClaudeCodeInstaller

        source = textwrap.dedent(inspect.getsource(ClaudeCodeInstaller.install))
        return ast.parse(source)

    def _collect_string_constants(self, tree):
        """Collect all string constants from an AST."""
        strings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                strings.append(node.value)
        return strings

    def _collect_name_references(self, tree):
        """Collect all Name node identifiers from an AST."""
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.append(node.id)
        return names

    def _collect_keyword_args(self, tree):
        """Collect all keyword argument names from function calls in an AST."""
        keywords = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg is not None:
                        keywords.append(kw.arg)
        return keywords

    def _collect_call_function_names(self, tree):
        """Collect all function names from Call nodes in an AST."""
        call_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    call_names.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    call_names.append(node.func.attr)
        return call_names

    def test_install_method_no_nim_step(self):
        """install() method should not reference 'Compiling Nim hooks' step."""
        tree = self._get_install_method_ast()
        string_constants = self._collect_string_constants(tree)
        nim_strings = [s for s in string_constants if "nim" in s.lower()]
        assert nim_strings == [], (
            f"install() still contains Nim-related string constants: {nim_strings}"
        )

    def test_install_method_no_nim_available(self):
        """install() method should not reference nim_available variable."""
        tree = self._get_install_method_ast()
        names = self._collect_name_references(tree)
        assert "nim_available" not in names, (
            "install() still references nim_available variable"
        )

    def test_install_method_no_nim_hooks_component(self):
        """install() method should not create nim_hooks InstallResult."""
        tree = self._get_install_method_ast()
        string_constants = self._collect_string_constants(tree)
        assert "nim_hooks" not in string_constants, (
            "install() still creates nim_hooks component results"
        )

    def test_install_hooks_call_no_nim_parameter(self):
        """install_hooks() call should not pass nim_available parameter."""
        tree = self._get_install_method_ast()
        keyword_args = self._collect_keyword_args(tree)
        assert "nim_available" not in keyword_args, (
            "install_hooks() call still passes nim_available keyword argument"
        )

    def test_install_hooks_still_called(self):
        """install_hooks() should still be called in install() method."""
        tree = self._get_install_method_ast()
        call_names = self._collect_call_function_names(tree)
        assert "install_hooks" in call_names, (
            "install_hooks() call is missing from install() method"
        )

    def test_hooks_import_present(self):
        """install_hooks and uninstall_hooks should still be imported."""
        from installer.platforms import claude_code

        assert hasattr(claude_code, "install_hooks"), (
            "install_hooks is not available in claude_code module"
        )
        assert hasattr(claude_code, "uninstall_hooks"), (
            "uninstall_hooks is not available in claude_code module"
        )
