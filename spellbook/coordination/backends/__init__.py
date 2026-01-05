"""Pluggable coordination backends."""
from .base import CoordinationBackend, BACKENDS, register_backend, get_backend
from .mcp_streamable_http import MCPStreamableHTTPBackend

# Register built-in backends
register_backend("mcp-streamable-http", MCPStreamableHTTPBackend)

__all__ = [
    "CoordinationBackend",
    "BACKENDS",
    "register_backend",
    "get_backend",
    "MCPStreamableHTTPBackend"
]
