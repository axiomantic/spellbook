"""WebSocket route for real-time event streaming.

Authenticates via short-lived WS ticket (from POST /api/auth/ws-ticket),
subscribes to the event bus, and forwards events as JSON frames.
Ping/pong keepalive every 30 seconds.
"""

import asyncio
import json
import logging
import uuid

from starlette.websockets import WebSocket, WebSocketDisconnect

from spellbook_mcp.admin.auth import validate_ws_ticket
from spellbook_mcp.admin.events import Event, Subsystem, event_bus

logger = logging.getLogger(__name__)

PING_INTERVAL = 30  # seconds


async def _send_loop(ws: WebSocket, queue: asyncio.Queue) -> None:
    """Forward events from the subscriber queue to the WebSocket client."""
    while True:
        event: Event = await queue.get()
        try:
            payload = {
                "type": "event",
                "subsystem": event.subsystem.value if isinstance(event.subsystem, Subsystem) else str(event.subsystem),
                "event": event.event_type,
                "data": event.data,
                "timestamp": event.timestamp,
            }
            await ws.send_json(payload)
        except Exception:
            return  # Connection closed


async def _receive_loop(ws: WebSocket) -> None:
    """Handle incoming WebSocket messages (pong, subscribe/unsubscribe)."""
    while True:
        try:
            data = await ws.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "pong":
                pass  # Keepalive acknowledged
            elif msg_type in ("subscribe", "unsubscribe"):
                # Future: subsystem-level filtering
                pass
        except (WebSocketDisconnect, json.JSONDecodeError):
            return
        except Exception:
            return


async def _ping_loop(ws: WebSocket) -> None:
    """Send periodic ping frames to keep the connection alive."""
    while True:
        await asyncio.sleep(PING_INTERVAL)
        try:
            await ws.send_json({"type": "ping"})
        except Exception:
            return


async def websocket_handler(ws: WebSocket) -> None:
    """WebSocket endpoint handler at /ws.

    Query parameter ?ticket= must contain a valid WS ticket.
    """
    # Validate ticket before accepting
    ticket = ws.query_params.get("ticket", "")
    if not ticket or not validate_ws_ticket(ticket):
        await ws.close(code=4001, reason="Invalid or expired ticket")
        return

    await ws.accept()

    subscriber_id = f"ws-{uuid.uuid4().hex[:8]}"
    queue = await event_bus.subscribe(subscriber_id)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_send_loop(ws, queue))
            tg.create_task(_receive_loop(ws))
            tg.create_task(_ping_loop(ws))
    except* (WebSocketDisconnect, Exception):
        pass  # Any task failure cancels the group
    finally:
        await event_bus.unsubscribe(subscriber_id)
        try:
            await ws.close()
        except Exception:
            pass  # Already closed
