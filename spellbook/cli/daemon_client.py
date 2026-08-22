"""HTTP client for the spellbook daemon.

Provides helpers for CLI commands that need to communicate with the
running MCP server.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


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
    from urllib.parse import urlunsplit

    def _build_host_url(host: str, port: int | str, path: str) -> str:
        host_part = f"[{host}]" if ":" in host else host
        return f"http://{host_part}:{port}{path}"

    url = _build_host_url(host, port, path)

    body = None
    if data is not None:
        body = json.dumps(data).encode()

    headers: dict[str, str] = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"

    req = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except URLError as exc:
        raise ConnectionError(
            f"Cannot connect to spellbook daemon at {host}:{port}: {exc}"
        ) from exc

