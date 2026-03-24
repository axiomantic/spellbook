"""Tests for crypto signing/verification MCP tools."""


def test_security_sign_content_exists():
    from spellbook.mcp.tools import security
    assert hasattr(security, "security_sign_content")


def test_security_verify_signature_exists():
    from spellbook.mcp.tools import security
    assert hasattr(security, "security_verify_signature")


def test_sign_content_in_all():
    from spellbook.mcp.tools.security import __all__
    assert "security_sign_content" in __all__


def test_verify_signature_in_all():
    from spellbook.mcp.tools.security import __all__
    assert "security_verify_signature" in __all__


def test_sign_content_is_not_mcp_tool():
    """security_sign_content must NOT be exposed as an MCP tool (security hole).
    It should be a plain function, not decorated with @mcp.tool()."""
    from spellbook.mcp.tools.security import security_sign_content
    # MCP tools have a __wrapped__ or specific FastMCP metadata
    # A plain function should not have tool_name attribute from mcp registration
    assert not hasattr(security_sign_content, "tool_name"), (
        "security_sign_content should NOT be an MCP tool"
    )
