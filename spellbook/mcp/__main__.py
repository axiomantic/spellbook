"""Entry point for ``python -m spellbook.mcp.server``."""

import os

from spellbook.mcp.server import (
    announce_request_validation_status,
    build_http_run_kwargs,
    mcp,
    register_all_tools,
    startup,
)

register_all_tools()
startup()

transport = os.environ.get("SPELLBOOK_MCP_TRANSPORT", "streamable-http")

if transport == "streamable-http":
    http_kwargs = build_http_run_kwargs()
    announce_request_validation_status(http_kwargs["host"], http_kwargs["port"])
    mcp.run(**http_kwargs)
else:
    mcp.run()
