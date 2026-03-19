"""Tests for spellbook.mcp.server module.

Verifies that the slim server orchestrator exists with expected exports:
- mcp: FastMCP instance
- register_all_tools: callable
- startup: callable
- shutdown: callable
- build_http_run_kwargs: callable
"""

import pytest


class TestMcpServerImports:
    """Test that spellbook.mcp.server is importable with expected exports."""

    def test_mcp_is_fastmcp_instance(self):
        from spellbook.mcp.server import mcp
        from fastmcp import FastMCP

        assert isinstance(mcp, FastMCP)

    def test_register_all_tools_is_callable(self):
        from spellbook.mcp.server import register_all_tools

        assert callable(register_all_tools)

    def test_startup_is_callable(self):
        from spellbook.mcp.server import startup

        assert callable(startup)

    def test_shutdown_is_callable(self):
        from spellbook.mcp.server import shutdown

        assert callable(shutdown)

    def test_build_http_run_kwargs_is_callable(self):
        from spellbook.mcp.server import build_http_run_kwargs

        assert callable(build_http_run_kwargs)
