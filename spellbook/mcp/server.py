"""Slim MCP server orchestrator.

Creates the FastMCP instance, registers tools, manages lifecycle (startup/shutdown),
and builds HTTP transport configuration. Replaces the 3,945-line monolith.
"""

import asyncio
import atexit
import functools
import logging
import os
import threading
import time
from typing import Any, Dict

import fastmcp as _fastmcp_module
from fastmcp import FastMCP

from spellbook.mcp import state
from spellbook.messaging import message_bus
from spellbook.messaging.sse import create_messaging_app

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


async def _cleanup_forged() -> None:
    """Clean up old forged workflow data (>90 days) using ORM."""
    try:
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import delete
        from spellbook.db import get_forged_session
        from spellbook.db.forged_models import ForgeToken, ToolAnalytic, ForgeReflection

        cutoff_90d = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

        async with get_forged_session() as session:
            for stmt in [
                delete(ForgeToken).where(
                    ForgeToken.invalidated_at.isnot(None),
                    ForgeToken.invalidated_at < cutoff_90d,
                ),
                delete(ToolAnalytic).where(ToolAnalytic.called_at < cutoff_90d),
                delete(ForgeReflection).where(
                    ForgeReflection.created_at < cutoff_90d,
                    ForgeReflection.status == "RESOLVED",
                ),
            ]:
                try:
                    await session.execute(stmt)
                except Exception:
                    pass
    except Exception:
        pass


def startup() -> None:
    """Initialize server state: DB schemas, watchers, admin app.

    Called from the daemon entry point before mcp.run().
    """
    from spellbook.core.config import config_get, get_spellbook_dir
    from spellbook.core.db import get_db_path, init_db
    from spellbook.sessions.watcher import SessionWatcher
    from spellbook.updates.watcher import UpdateWatcher
    from spellbook.forged.schema import init_forged_schema
    from spellbook.fractal.schema import init_fractal_schema
    from spellbook.coordination.curator import init_curator_tables

    # Initialize databases
    db_path = str(get_db_path())
    init_db(db_path)
    init_forged_schema()
    init_fractal_schema()
    init_curator_tables()

    # Start session watcher with cross-domain cleanup hooks
    watcher = SessionWatcher(db_path)
    watcher.start()
    state.watcher = watcher

    # Start update watcher if auto-update is not explicitly disabled
    auto_update_enabled = config_get("auto_update")
    if auto_update_enabled is not False:
        update_watcher = UpdateWatcher(
            str(get_spellbook_dir()),
            check_interval=float(
                os.environ.get("SPELLBOOK_UPDATE_INTERVAL", "86400")
            ),
        )
        update_watcher.start()
        state.update_watcher = update_watcher

    # Preload TTS model in background (non-blocking)
    try:
        from spellbook.notifications import tts as tts_module

        tts_preload = threading.Thread(target=tts_module.preload, daemon=True)
        tts_preload.start()
    except Exception:
        pass

    # Mount admin web interface
    _mount_admin_app()

    # Mount messaging SSE sub-app
    _mount_messaging_app()


def shutdown() -> None:
    """Stop watcher threads and close database connections on exit."""
    if state.watcher is not None:
        state.watcher.stop()
    if state.update_watcher is not None:
        state.update_watcher.stop()

    # Clean up message bus sessions
    try:
        async def _cleanup_message_bus():
            aliases = [s["alias"] for s in await message_bus.list_sessions()]
            for alias in aliases:
                await message_bus.unregister(alias)

        # atexit runs after the event loop has stopped, so asyncio.run() is safe
        asyncio.run(_cleanup_message_bus())
    except Exception:
        logger.warning("Failed to clean up message bus sessions during shutdown", exc_info=True)

    try:
        from spellbook.core.db import close_all_connections

        close_all_connections()
    except Exception:
        pass
    try:
        from spellbook.forged.schema import close_forged_connections

        close_forged_connections()
    except Exception:
        pass
    try:
        from spellbook.fractal.schema import close_all_fractal_connections

        close_all_fractal_connections()
    except Exception:
        pass


atexit.register(shutdown)


def _mount_admin_app() -> None:
    """Mount the admin web interface if admin_enabled config is true."""
    try:
        from spellbook.core.config import config_get

        admin_enabled = config_get("admin_enabled")
        if admin_enabled is not None and not admin_enabled:
            logger.debug("Admin interface disabled via admin_enabled config")
            return

        from spellbook.admin.app import create_admin_app
        from starlette.routing import Mount

        admin_app = create_admin_app()
        mcp._additional_http_routes.append(Mount("/admin", app=admin_app))
        logger.info("Admin web interface mounted at /admin")
    except ImportError:
        logger.debug("Admin package not available, skipping mount")
    except Exception:
        logger.warning("Failed to mount admin interface", exc_info=True)


def _mount_messaging_app() -> None:
    """Mount the messaging SSE sub-app for cross-session communication."""
    try:
        from starlette.routing import Mount

        messaging_app = create_messaging_app()
        mcp._additional_http_routes.append(Mount("/messaging", app=messaging_app))
        logger.info("Messaging SSE interface mounted at /messaging")
    except ImportError:
        logger.debug("Messaging package not available, skipping mount")
    except Exception:
        logger.warning("Failed to mount messaging interface", exc_info=True)


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
