"""Spike test: validate SSE StreamingResponse through FastMCP mount.

Proves that a FastAPI sub-app mounted via mcp._additional_http_routes
can serve SSE (Server-Sent Events) through the FastMCP ASGI app.
"""

import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastmcp import FastMCP
from starlette.responses import StreamingResponse
from starlette.routing import Mount


async def _sse_generator():
    """Yield three SSE events then close."""
    for i in range(3):
        yield f"data: event-{i}\n\n"
        await asyncio.sleep(0)  # yield control


def _make_sse_sub_app() -> FastAPI:
    app = FastAPI()

    @app.get("/events")
    async def sse_events():
        return StreamingResponse(
            _sse_generator(),
            media_type="text/event-stream",
        )

    return app


def _make_mcp_with_sse() -> FastMCP:
    mcp = FastMCP("spike-test")
    sub_app = _make_sse_sub_app()
    mcp._additional_http_routes.append(Mount("/test-sse", app=sub_app))
    return mcp


@pytest.mark.allow("network")
async def test_sse_streaming_through_fastmcp_mount():
    """SSE StreamingResponse works when sub-app is mounted via _additional_http_routes."""
    mcp = _make_mcp_with_sse()
    asgi_app = mcp.http_app()

    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/test-sse/events")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    # Verify all three SSE events arrived
    body = resp.text
    for i in range(3):
        assert f"data: event-{i}" in body, f"Missing event-{i} in response body: {body!r}"
