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

    app.include_router(auth_routes.router, prefix="/api")

    # Serve static frontend (must be last -- catch-all)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True))

    return app
