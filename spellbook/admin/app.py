"""FastAPI sub-application factory for Spellbook Admin."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import logging

from spellbook.admin.events import event_bus
from spellbook.admin.middleware import HostValidatorMiddleware, OriginCheckMiddleware
from spellbook.core.config import config_get, get_env
from spellbook.hooks.observability import purge_loop as hook_purge_loop
from spellbook.worker_llm.observability import purge_loop, threshold_eval_loop
from spellbook.worker_llm.queue import start_queue, stop_queue

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Mark the event bus as in-daemon and spawn worker-LLM background tasks.

    ``spellbook.worker_llm.events._in_daemon_process`` consults the daemon
    flag to choose between direct ``publish_sync`` and the HTTP fallback.

    ``purge_loop`` and ``threshold_eval_loop`` are daemon-lifetime async
    tasks. They are created here so they spawn exactly once per daemon
    process (not per request, not per test-client instance) and are
    cancelled + awaited on shutdown so no orphan task holds an in-flight
    DB writer lock past daemon exit.

    The monkeypatch-friendly indirection via ``purge_loop`` /
    ``threshold_eval_loop`` module-level names lets tests swap in
    lightweight stubs without patching the observability module itself.
    """
    event_bus._in_daemon = True
    purge_task = asyncio.create_task(
        purge_loop(), name="spellbook-worker-llm-purge"
    )
    eval_task = asyncio.create_task(
        threshold_eval_loop(), name="spellbook-worker-llm-threshold-eval"
    )
    hook_purge_task = asyncio.create_task(
        hook_purge_loop(), name="spellbook-hook-events-purge"
    )
    # Opt-in fire-and-forget queue (design: async enqueue for hook-originated
    # worker calls). Only start the consumer when the operator enabled it;
    # otherwise the module stays dormant and ``is_available()`` returns
    # False so callers fall back to the sync path.
    queue_started = False
    if config_get("worker_llm_queue_enabled"):
        try:
            await start_queue()
            queue_started = True
        except Exception:
            logger.warning(
                "worker_llm queue failed to start; continuing without it",
                exc_info=True,
            )
    try:
        yield
    finally:
        event_bus._in_daemon = False
        # Cancel and await the purge + threshold tasks. ``CancelledError``
        # is the expected terminal exception; any other exception is logged
        # but does not block shutdown (an in-flight DB error on cancel must
        # not hang the daemon).
        for task in (purge_task, eval_task, hook_purge_task):
            task.cancel()
        for task in (purge_task, eval_task, hook_purge_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.debug(
                    "worker-llm background task raised during shutdown",
                    exc_info=True,
                )
        if queue_started:
            try:
                await stop_queue()
            except Exception:
                logger.debug(
                    "worker_llm queue failed to stop cleanly",
                    exc_info=True,
                )


def create_admin_app() -> FastAPI:
    """Create and configure the admin FastAPI sub-application."""
    app = FastAPI(
        title="Spellbook Admin",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=_lifespan,
    )

    # Capture the bound port from the same alias the CLI uses
    # (``spellbook.admin.cli`` resolves ``PORT`` -> ``SPELLBOOK_MCP_PORT`` via
    # ``get_env``). Stored on ``app.state`` so downstream middleware (Origin)
    # and the WebSocket handler can derive their loopback allowlists without
    # re-reading the environment at request time.
    bound_port = int(get_env("PORT", "8765"))
    app.state.bound_port = bound_port
    # Stored as a frozenset: membership (``origin in allowed_origins``) is
    # the only operation performed by both the OriginCheck middleware and
    # the WS handler, so O(1) lookup and an immutable, order-independent
    # type are the right end-to-end contract.
    app.state.allowed_origins = frozenset(
        {
            "http://127.0.0.1:" + str(bound_port),
            "http://localhost:" + str(bound_port),
            "http://[::1]:" + str(bound_port),
        }
    )

    # CSRF defense (design-doc C4): require a same-origin ``Origin`` header
    # on state-changing methods (POST/PUT/PATCH/DELETE) when the request is
    # not authenticated via a valid Bearer token. ``allowed_origins`` is
    # sourced from ``app.state.allowed_origins`` (populated above from the
    # bound port) so the allowlist tracks whatever port the daemon actually
    # bound.
    #
    # Middleware add order is load-bearing: Starlette wraps middleware in
    # LIFO order (last added = outermost = runs first). The required
    # execution order per design §3 is HostValidator FIRST (reject bad Host
    # before any other processing) then OriginCheck SECOND. So we add
    # OriginCheck here (inner) and HostValidator below (outer).
    app.add_middleware(
        OriginCheckMiddleware,
        allowed_origins=app.state.allowed_origins,
    )

    # DNS-rebinding defense (design-doc C1): reject requests whose ``Host``
    # header is not one of the bare loopback hostnames. MUST be added after
    # ``app.state`` is populated so the middleware stack is built with the
    # final state object. Added LAST so it runs FIRST in the execution
    # order (outermost middleware).
    app.add_middleware(
        HostValidatorMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "::1"],
    )

    # Global exception handler for fault isolation
    @app.exception_handler(Exception)
    async def admin_exception_handler(request, exc):
        logger.error(f"Admin error: {exc}", exc_info=True)
        return JSONResponse({"error": "Internal admin error"}, status_code=500)

    # Register route modules
    from spellbook.admin.routes import auth as auth_routes
    from spellbook.admin.routes import config as config_routes
    from spellbook.admin.routes import dashboard as dashboard_routes
    from spellbook.admin.routes import canvas as canvas_routes
    from spellbook.admin.routes import sessions as sessions_routes
    from spellbook.admin.routes import fractal as fractal_routes
    from spellbook.admin.routes import events as events_routes
    from spellbook.admin.routes import focus as focus_routes
    from spellbook.admin.routes import health as health_routes
    from spellbook.admin.routes import worker_llm as worker_llm_routes
    from spellbook.admin.routes import hooks as hooks_routes

    app.include_router(auth_routes.router, prefix="/api")
    app.include_router(config_routes.router, prefix="/api")
    app.include_router(dashboard_routes.router, prefix="/api")
    app.include_router(canvas_routes.router, prefix="/api")
    app.include_router(sessions_routes.router, prefix="/api")
    app.include_router(fractal_routes.router, prefix="/api")
    app.include_router(events_routes.router, prefix="/api")
    app.include_router(focus_routes.router, prefix="/api")
    app.include_router(health_routes.router, prefix="/api")
    app.include_router(worker_llm_routes.router, prefix="/api")
    app.include_router(hooks_routes.router, prefix="/api")

    # WebSocket endpoint (no /api prefix -- connects at /ws)
    from spellbook.admin.routes.ws import websocket_handler

    app.websocket("/ws")(websocket_handler)

    # Serve static frontend with SPA fallback. The bundle is built at install
    # time (npm ci + npm run build); it is not committed to the repo. If it is
    # absent, the admin API still works but the browser UI 404s -- warn loudly
    # and name the fix.
    if not STATIC_DIR.exists():
        logger.warning(
            "Admin SPA bundle not found at %s; the admin UI will not load. "
            "Build it with: cd spellbook/admin/frontend && npm ci "
            "--legacy-peer-deps && npm run build (or re-run the spellbook "
            "installer).",
            STATIC_DIR,
        )

    if STATIC_DIR.exists():
        # Mount static assets (JS, CSS, etc.) at /assets
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)))

        # SPA catch-all: serve index.html for any non-API path
        @app.get("/{full_path:path}")
        async def spa_fallback(request: Request, full_path: str):
            # Serve actual static files if they exist (favicon, etc.)
            if full_path:
                file_path = (STATIC_DIR / full_path).resolve()
                # Prevent path traversal outside STATIC_DIR
                if file_path.is_relative_to(STATIC_DIR) and file_path.is_file():
                    return FileResponse(file_path)
            # Otherwise serve index.html for client-side routing
            return FileResponse(STATIC_DIR / "index.html")

    return app
