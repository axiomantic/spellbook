"""Tiny URL helpers shared by worker-LLM subprocess paths.

Import-light (stdlib only) so hook subprocesses, MCP stdio workers, and CLI
invocations can pull it in without dragging in larger dependencies.
"""

from __future__ import annotations


def build_host_url(host: str, port: int | str, path: str) -> str:
    """Return ``http://{host}:{port}{path}`` with IPv6 literals bracketed.

    An IPv6 literal (e.g. ``::1``, ``fe80::1``) cannot appear in a URL
    authority unbracketed; the colons collide with the port separator.
    IPv4 literals and hostnames never contain a colon, so the bracket branch
    is a no-op for them.

    The ``path`` argument is concatenated verbatim; callers supply the
    leading slash (e.g. ``"/api/events/publish"``). An empty path is valid
    and yields a bare authority URL.
    """
    host_part = f"[{host}]" if ":" in host else host
    return f"http://{host_part}:{port}{path}"
