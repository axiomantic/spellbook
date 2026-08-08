"""Slim MCP server orchestrator.

Creates the FastMCP instance, registers tools, manages lifecycle (startup/shutdown),
and builds HTTP transport configuration. Replaces the 3,945-line monolith.
"""

import atexit
import functools
import logging
import os
import time
from typing import Any, Dict

import fastmcp as _fastmcp_module
from fastmcp import FastMCP


from spellbook.mcp import state

logger = logging.getLogger(__name__)

# FastMCP version detection for v2/v3 compatibility
_FASTMCP_MAJOR = int(_fastmcp_module.__version__.split(".")[0])

mcp = FastMCP("spellbook")

# Apply v2/v3 compatibility shim
if _FASTMCP_MAJOR >= 3:
    # In FastMCP v3, @mcp.tool() returns the original function instead of a
    # FunctionTool object. Wrap the decorator so it adds .fn and .description
    # attributes, preserving backward compatibility with code that accesses
    # tool_func.fn or tool_func.description (the v2 FunctionTool pattern).
    _original_tool = mcp.tool

    def _add_compat_attrs(func):
        """Add v2-compatible attributes to a v3-decorated function."""
        if callable(func) and not hasattr(func, "fn"):
            func.fn = func
        if callable(func) and not hasattr(func, "description"):
            func.description = func.__doc__
        return func

    @functools.wraps(_original_tool)
    def _compat_tool(*args, **kwargs):
        decorator = _original_tool(*args, **kwargs)
        if callable(decorator) and not isinstance(decorator, type):
            if hasattr(decorator, "__name__"):
                # Direct registration: decorator IS the function
                return _add_compat_attrs(decorator)
            else:
                # Deferred registration: decorator is a callable that takes fn
                @functools.wraps(decorator)
                def wrapper(fn):
                    result = decorator(fn)
                    return _add_compat_attrs(result)

                return wrapper
        return decorator

    mcp.tool = _compat_tool


def register_all_tools() -> None:
    """Import tool modules and route modules to register them with the mcp instance.

    NOTE: This will fail until tool/route modules are created (Task 16/18).
    Wrapped in try/except ImportError for forward compatibility.
    """
    try:
        import spellbook.mcp.tools  # noqa: F401
    except ImportError:
        logger.debug("spellbook.mcp.tools not yet available")

    try:
        import spellbook.mcp.routes  # noqa: F401
    except ImportError:
        logger.debug("spellbook.mcp.routes not yet available")


def startup() -> None:
    """Initialize server state: DB schemas, watchers.

    Called from the daemon entry point before mcp.run().
    """
    from spellbook.core.config import config_get, get_spellbook_dir
    from spellbook.core.db import get_db_path, init_db
    from spellbook.updates.watcher import UpdateWatcher

    timings: dict[str, float] = {}

    def _timed(label: str, fn, *args, **kwargs):
        t0 = time.monotonic()
        result = fn(*args, **kwargs)
        timings[label] = time.monotonic() - t0
        return result

    # Initialize database
    db_path = str(get_db_path())
    _timed("init_db", init_db, db_path)

    # Start update watcher if auto-update is not explicitly disabled
    auto_update_enabled = config_get("auto_update")
    if auto_update_enabled is not False:
        update_watcher = _timed(
            "update_watcher_init",
            UpdateWatcher,
            str(get_spellbook_dir()),
            check_interval=float(
                os.environ.get("SPELLBOOK_UPDATE_INTERVAL", "86400")
            ),
        )
        _timed("update_watcher_start", update_watcher.start)
        state.update_watcher = update_watcher

    logger.info("startup timings: %s", {k: f"{v:.3f}s" for k, v in timings.items()})


def shutdown() -> None:
    """Stop watcher threads and close database connections on exit."""
    if state.update_watcher is not None:
        state.update_watcher.stop()

    try:
        from spellbook.core.db import close_all_connections

        close_all_connections()
    except Exception:
        pass

atexit.register(shutdown)



def build_http_run_kwargs() -> Dict[str, Any]:
    """Build kwargs for mcp.run() with auth middleware for HTTP transport.

    Reads SPELLBOOK_MCP_HOST, SPELLBOOK_MCP_PORT, and SPELLBOOK_MCP_AUTH
    from environment. When auth is not disabled, generates a bearer token,
    writes it to the token file, and includes BearerAuthMiddleware in the
    middleware list.

    Returns:
        Dict of kwargs to pass to mcp.run() for streamable-http transport.
    """
    from starlette.middleware import Middleware

    from spellbook.core.auth import (
        BearerAuthMiddleware,
        auth_is_disabled,
        generate_and_store_token,
    )
    from spellbook.core.config import get_env

    host = get_env("HOST", "127.0.0.1")
    port = int(get_env("PORT", "8765"))

    auth_middleware = []
    if not auth_is_disabled():
        token = generate_and_store_token()
        auth_middleware = [Middleware(BearerAuthMiddleware, token=token)]

    return {
        "transport": "streamable-http",
        "host": host,
        "port": port,
        "stateless_http": True,
        "middleware": auth_middleware,
    }
