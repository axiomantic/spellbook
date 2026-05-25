"""MCP tools for the canvas feature.

Four tools matching design §4:

- ``canvas_open`` — create or re-attach to a named canvas
- ``canvas_write`` — write markdown content to a canvas page
- ``canvas_close`` — mark a canvas closed (does not delete files)
- ``canvas_list`` — read-only listing of all canvases

Event publishing diverges from ``memory.py`` (which uses
``except Exception: pass``): canvas wants observability on publish
failures, so this module uses ``logger.warning(..., exc_info=True)``
per design §6.3. Tool results are unaffected by publish failures.
"""

from __future__ import annotations

import logging

from fastmcp import Context

from spellbook.admin.events import Event, Subsystem, event_bus
from spellbook.canvas import store as canvas_store
from spellbook.core.config import get_env
from spellbook.mcp.server import mcp

logger = logging.getLogger(__name__)


def _canvas_url(name: str) -> str:
    """Construct the admin URL for a canvas page.

    Mirrors the host/port precedent at ``spellbook/admin/cli.py:31`` and
    ``spellbook/mcp/server.py:241`` so the URL respects operator env
    overrides without hard-coding 127.0.0.1:8765.
    """
    host = get_env("HOST", "127.0.0.1")
    port = int(get_env("PORT", "8765"))
    return f"http://{host}:{port}/admin/canvas/{name}"


async def _publish_canvas_event(event_type: str, data: dict) -> None:
    """Publish a canvas event, swallowing all errors with a warning.

    Tool callers must never break on publish failures. Defense-in-depth
    only; in current behavior ``event_bus.publish`` does not raise.
    """
    try:
        await event_bus.publish(
            Event(subsystem=Subsystem.CANVAS, event_type=event_type, data=data)
        )
    except Exception:
        logger.warning(
            "event_bus.publish failed for %s", event_type, exc_info=True
        )


@mcp.tool()
async def canvas_open(ctx: Context, name: str, title: str = "") -> dict:
    """Open (create or re-attach to) a named canvas.

    Idempotent: if the canvas already exists, returns its current metadata
    without modifying files. If it doesn't exist, creates the directory tree
    (pages/, inbox/, meta.json) and returns the new metadata.

    Threat model: canvas content is TRUSTED-LOCAL-AGENT output. Agents MUST
    NOT write unsanitized external content (chat transcripts, fetched web
    pages, untrusted MCP tool outputs) into a canvas. Raw HTML is permitted
    via rehype-raw and executes under the admin's auth context — a script
    tag is a session-takeover primitive.

    Args:
        name: Canvas name. Must match ^[a-z0-9][a-z0-9-_]{0,63}$.
        title: Human-readable title. Defaults to `name` if empty.

    Returns:
        dict with one of:
        - {"status": "opened", "name": str, "title": str, "url": str,
           "created_at": str, "last_updated": str, "created": bool}
          (created=True if newly created, False if pre-existing)
        - {"error": str, "code": str} where code in {"invalid_name"}
    """
    try:
        meta, created, reopened = canvas_store.open_canvas(name, title=title)
    except ValueError as e:
        return {"error": str(e), "code": "invalid_name"}

    await _publish_canvas_event(
        "canvas.opened",
        {"canvas": name, "created": created, "reopened": reopened},
    )
    return {
        "status": "opened",
        "name": meta.name,
        "title": meta.title,
        "url": _canvas_url(meta.name),
        "created_at": meta.created_at.isoformat(),
        "last_updated": meta.last_updated.isoformat(),
        "created": created,
    }


@mcp.tool()
async def canvas_write(
    ctx: Context,
    canvas: str,
    content: str,
    page: str = "index.md",
) -> dict:
    """Write markdown content to a canvas page, replacing existing content.

    Last-write-wins: this replaces the whole page atomically. Concurrent
    writes to the same canvas from different sessions can clobber each
    other. Use distinct canvas names per concurrent workflow.

    Threat model: TRUSTED-LOCAL-AGENT only. Do NOT write unsanitized external
    content (chat transcripts, fetched web pages, untrusted MCP tool
    outputs). Raw HTML is rendered via rehype-raw and executes under the
    admin's auth context.

    Args:
        canvas: Canvas name. Must match ^[a-z0-9][a-z0-9-_]{0,63}$ and
            already be opened (canvas_open) or this is a no-op error.
        content: Markdown content. Custom shortcodes (<diagram>, <chart>,
            <callout>, <tabs>, <choice>, <approve>) supported. Raw HTML
            permitted. Max 1 MB UTF-8.
        page: Page filename within pages/. MVP only supports "index.md".
            Pass through unchanged; v2 enables multi-page.

    Returns:
        dict with one of:
        - {"status": "written", "canvas": str, "page": str, "bytes": int,
           "last_updated": str, "url": str}
        - {"error": str, "code": str} where code in {"invalid_name",
           "not_found", "closed", "page_too_large", "invalid_content",
           "queue_overflow"}
    """
    # Validate name. canvas_store.NAME_RE is the single source of truth.
    if not canvas_store.NAME_RE.match(canvas):
        return {"error": f"invalid canvas name: {canvas!r}", "code": "invalid_name"}

    # Read existing meta to enforce open/closed semantics.
    meta = canvas_store.read_meta(canvas)
    if meta is None:
        return {"error": f"canvas {canvas!r} not found", "code": "not_found"}
    if meta.closed:
        return {"error": f"canvas {canvas!r} is closed", "code": "closed"}

    # Delegate write; store raises ValueError with code prefix on each
    # error path (invalid_content, page_too_large).
    try:
        nbytes = canvas_store.write_page(canvas, content, page=page)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("page_too_large"):
            code = "page_too_large"
        elif msg.startswith("invalid_content"):
            code = "invalid_content"
        else:
            # Shouldn't reach: name was already validated above.
            code = "invalid_name"
        return {"error": msg, "code": code}

    # Bump meta.last_updated and persist.
    from datetime import datetime, timezone

    bumped = meta.model_copy(update={"last_updated": datetime.now(timezone.utc)})
    canvas_store.write_meta(canvas, bumped)

    await _publish_canvas_event(
        "canvas.updated",
        {"canvas": canvas, "page": page, "bytes": nbytes},
    )
    return {
        "status": "written",
        "canvas": canvas,
        "page": page,
        "bytes": nbytes,
        "last_updated": bumped.last_updated.isoformat(),
        "url": _canvas_url(canvas),
    }


@mcp.tool()
async def canvas_close(ctx: Context, name: str) -> dict:
    """Mark a canvas closed. Does NOT delete files; the directory remains
    on disk and can be removed manually if desired.

    Args:
        name: Canvas name.

    Returns:
        - {"status": "closed", "name": str, "last_updated": str}
        - {"error": str, "code": str} where code in {"invalid_name", "not_found"}
    """
    if not canvas_store.NAME_RE.match(name):
        return {"error": f"invalid canvas name: {name!r}", "code": "invalid_name"}
    closed_meta = canvas_store.close_canvas(name)
    if closed_meta is None:
        return {"error": f"canvas {name!r} not found", "code": "not_found"}
    await _publish_canvas_event("canvas.closed", {"canvas": name})
    return {
        "status": "closed",
        "name": name,
        "last_updated": closed_meta.last_updated.isoformat(),
    }


@mcp.tool()
async def canvas_list(ctx: Context) -> dict:
    """List all canvases on disk with their metadata.

    Symmetric recovery: regenerates meta.json with defaults if missing
    or corrupt, so a canvas always appears in the list with at least
    the inferred name + timestamps.

    Returns:
        {"canvases": [
            {"name": str, "title": str, "created_at": str,
             "last_updated": str, "closed": bool, "url": str}
        ], "count": int}
    """
    items = canvas_store.list_canvases()
    enriched = [{**item, "url": _canvas_url(item["name"])} for item in items]
    return {"canvases": enriched, "count": len(enriched)}
