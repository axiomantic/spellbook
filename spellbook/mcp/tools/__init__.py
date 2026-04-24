"""MCP tool modules.

Importing this package triggers registration of all @mcp.tool() decorated
functions from the 13 tool submodules with the shared FastMCP instance.
"""

from spellbook.mcp.tools import (  # noqa: F401
    config,
    coordination,
    forged,
    fractal,
    health,
    memory,
    misc,
    notifications,
    pr,
    security,
    sessions,
    tooling,
    updates,
)
