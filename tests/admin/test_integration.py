import pytest


@pytest.mark.integration
def test_fastmcp_has_additional_routes_attribute():
    """Guard: verify FastMCP exposes _additional_http_routes."""
    from fastmcp import FastMCP

    mcp_instance = FastMCP("test")
    assert hasattr(mcp_instance, "_additional_http_routes"), (
        "FastMCP no longer exposes _additional_http_routes. "
        "Activate fallback: wrap FastMCP's Starlette app in a parent app."
    )


@pytest.mark.integration
def test_admin_mount_accepts_starlette_mount():
    """Verify Mount object can be appended to _additional_http_routes."""
    from fastmcp import FastMCP
    from starlette.routing import Mount
    from spellbook.admin.app import create_admin_app

    mcp_instance = FastMCP("test")
    admin_app = create_admin_app()
    mount = Mount("/admin", app=admin_app)
    mcp_instance._additional_http_routes.append(mount)
    assert any(
        isinstance(r, Mount) and r.path == "/admin"
        for r in mcp_instance._additional_http_routes
    )
