"""Entry point for ``python -m spellbook.mcp.server``."""

import logging
import os

from spellbook.mcp.server import (
    build_http_run_kwargs,
    mcp,
    register_all_tools,
    startup,
)

logger = logging.getLogger(__name__)

register_all_tools()
startup()

transport = os.environ.get("SPELLBOOK_MCP_TRANSPORT", "streamable-http")

if transport == "streamable-http":
    http_kwargs = build_http_run_kwargs()
    auth_status = "auth enabled" if http_kwargs["middleware"] else "auth DISABLED"
    print(
        f"Starting spellbook MCP server on "
        f"{http_kwargs['host']}:{http_kwargs['port']} ({auth_status})"
    )
    if not http_kwargs["middleware"]:
        logger.warning("MCP auth disabled via SPELLBOOK_MCP_AUTH=disabled")
    mcp.run(**http_kwargs)
else:
    mcp.run()
