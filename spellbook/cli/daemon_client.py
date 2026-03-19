"""HTTP/WebSocket client for the spellbook daemon.

Provides helpers for CLI commands that need to communicate with the
running MCP server.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.error import URLError
from urllib.request import Request, urlopen


def _token_path() -> Path:
    """Return the path to the bearer token file."""
    return Path.home() / ".local" / "spellbook" / ".mcp-token"


def get_token() -> str | None:
    """Read the bearer token from ``~/.local/spellbook/.mcp-token``.

    Returns ``None`` when the file is missing or empty.
    """
    try:
        text = _token_path().read_text().strip()
        return text or None
    except FileNotFoundError:
        return None


def daemon_request(
    path: str,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> dict[str, Any]:
    """Send an HTTP request to the spellbook daemon.

    Parameters
    ----------
    path:
        URL path (e.g. ``/health``).
    method:
        HTTP method.
    data:
        JSON body for POST/PUT/PATCH requests.
    host:
        Daemon host.
    port:
        Daemon port.

    Returns
    -------
    dict
        Parsed JSON response.

    Raises
    ------
    ConnectionError
        When the daemon is unreachable.
    """
    url = f"http://{host}:{port}{path}"

    body = None
    if data is not None:
        body = json.dumps(data).encode()

    headers: dict[str, str] = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"

    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except URLError as exc:
        raise ConnectionError(
            f"Cannot connect to spellbook daemon at {host}:{port}: {exc}"
        ) from exc


async def stream_events(
    host: str = "127.0.0.1",
    port: int = 8765,
) -> AsyncIterator[dict[str, Any]]:
    """Stream events from the daemon via WebSocket with ticket auth.

    Yields parsed JSON event dicts.  Requires an async context.
    """
    try:
        import websockets  # noqa: F811
    except ImportError:
        raise ImportError(
            "websockets package is required for event streaming. "
            "Install with: uv pip install websockets"
        )

    # Exchange bearer token for a short-lived ticket
    ticket_resp = daemon_request(
        "/auth/ticket",
        method="POST",
        host=host,
        port=port,
    )
    ticket = ticket_resp.get("ticket", "")

    ws_url = f"ws://{host}:{port}/events?ticket={ticket}"

    async with websockets.connect(ws_url) as ws:
        async for message in ws:
            yield json.loads(message)
