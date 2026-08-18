"""MCP tool modules.

Importing this package triggers registration of all @mcp.tool() decorated
functions from the tool submodules with the shared FastMCP instance.
"""

from spellbook.mcp.tools import (  # noqa: F401
    config,
    curator,
    fractal,
    health,
    model_tiers,
    tooling,
    updates,
)
