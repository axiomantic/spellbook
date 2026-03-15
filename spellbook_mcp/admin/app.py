"""FastAPI sub-application factory for Spellbook Admin."""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


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
    from spellbook_mcp.admin.routes import analytics as analytics_routes
    from spellbook_mcp.admin.routes import focus as focus_routes
    from spellbook_mcp.admin.routes import health as health_routes

    app.include_router(auth_routes.router, prefix="/api")
    app.include_router(config_routes.router, prefix="/api")
    app.include_router(dashboard_routes.router, prefix="/api")
    app.include_router(memory_routes.router, prefix="/api")
    app.include_router(security_routes.router, prefix="/api")
    app.include_router(sessions_routes.router, prefix="/api")
    app.include_router(fractal_routes.router, prefix="/api")
    app.include_router(analytics_routes.router, prefix="/api")
    app.include_router(focus_routes.router, prefix="/api")
    app.include_router(health_routes.router, prefix="/api")

    # WebSocket endpoint (no /api prefix -- connects at /ws)
    from spellbook_mcp.admin.routes.ws import websocket_handler

    app.websocket("/ws")(websocket_handler)

    # Serve static frontend with SPA fallback
    if STATIC_DIR.exists():
        # Mount static assets (JS, CSS, etc.) at /assets
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)))

        # SPA catch-all: serve index.html for any non-API path
        @app.get("/{full_path:path}")
        async def spa_fallback(request: Request, full_path: str):
            # Serve actual static files if they exist (favicon, etc.)
            file_path = STATIC_DIR / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
            # Otherwise serve index.html for client-side routing
            return FileResponse(STATIC_DIR / "index.html")

    return app
