"""SSE endpoint for real-time cross-session message delivery.

Mounted as a FastAPI sub-app via mcp._additional_http_routes,
following the admin app pattern.
"""

import asyncio
import json
import logging

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from spellbook.messaging.bus import _DISCONNECT, message_bus

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 15  # seconds (typical SSE keep-alive)


async def stream_messages(request: Request) -> StreamingResponse:
    """SSE endpoint for real-time message delivery.

    The ``/messaging/`` path requires bearer token authentication via the
    existing BearerAuthMiddleware. The bridge includes the token in the
    ``Authorization`` header. No middleware exemption is needed.
    """
    alias = request.path_params["alias"]

    queue = await message_bus.get_queue(alias)
    if queue is None:
        return JSONResponse(
            {"error": "not_registered", "alias": alias},
            status_code=404,
        )

    async def event_generator():
        """Yield SSE events from the session's queue."""
        try:
            while True:
                try:
                    envelope = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_INTERVAL
                    )
                    # Check for disconnect sentinel from unregister()
                    if envelope is _DISCONNECT:
                        return
                    data = json.dumps(envelope.to_dict())
                    # id: is informational only; Last-Event-ID reconnection
                    # is not supported.
                    yield f"id: {envelope.id}\n"
                    yield f"event: message\n"
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            logger.debug(f"SSE stream cancelled for {alias}")
            return
        except Exception:
            logger.error(f"SSE stream error for {alias}", exc_info=True)
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def health(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "ok"})


def create_messaging_app() -> FastAPI:
    """Create the FastAPI sub-app for messaging SSE routes.

    Follows the admin app mount pattern (verified).
    """
    app = FastAPI()
    app.routes.append(Route("/stream/{alias}", stream_messages))
    app.routes.append(Route("/health", health))
    return app
