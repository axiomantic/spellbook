"""FastAPI sub-application factory for Spellbook Admin."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def create_admin_app() -> FastAPI:
    """Create and configure the admin FastAPI sub-application."""
    app = FastAPI(
        title="Spellbook Admin",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Global exception handler for fault isolation
    @app.exception_handler(Exception)
    async def admin_exception_handler(request, exc):
        logger.error(f"Admin error: {exc}", exc_info=True)
        return JSONResponse({"error": "Internal admin error"}, status_code=500)

    # Register route modules
    from spellbook_mcp.admin.routes import auth as auth_routes
    from spellbook_mcp.admin.routes import config as config_routes
    from spellbook_mcp.admin.routes import dashboard as dashboard_routes
    from spellbook_mcp.admin.routes import memory as memory_routes
    from spellbook_mcp.admin.routes import security as security_routes
    from spellbook_mcp.admin.routes import sessions as sessions_routes
    from spellbook_mcp.admin.routes import fractal as fractal_routes

    app.include_router(auth_routes.router, prefix="/api")
    app.include_router(config_routes.router, prefix="/api")
    app.include_router(dashboard_routes.router, prefix="/api")
    app.include_router(memory_routes.router, prefix="/api")
    app.include_router(security_routes.router, prefix="/api")
    app.include_router(sessions_routes.router, prefix="/api")
    app.include_router(fractal_routes.router, prefix="/api")

    # WebSocket endpoint (no /api prefix -- connects at /ws)
    from spellbook_mcp.admin.routes.ws import websocket_handler

    app.websocket("/ws")(websocket_handler)

    # Serve static frontend (must be last -- catch-all)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True))

    return app
