"""Dependency-light bearer-token loader for worker-LLM subprocess paths.

Mirrors ``spellbook.core.auth.TOKEN_PATH`` / ``load_token`` without
importing the auth module. ``spellbook.core.auth`` pulls in starlette at
module top level; worker-LLM helpers run inside hook subprocesses, MCP
stdio workers, and CLI invocations where that dependency is unnecessary
and slow to import.

Keep this module import-light: stdlib only.
"""

from __future__ import annotations

from pathlib import Path

_TOKEN_PATH = Path.home() / ".local" / "spellbook" / ".mcp-token"


def _load_bearer_token() -> str | None:
    """Read the daemon bearer token from the canonical location.

    Returns ``None`` when the token file is missing, empty, or unreadable.
    Never raises.
    """
    try:
        if _TOKEN_PATH.exists():
            token = _TOKEN_PATH.read_text().strip()
            return token or None
    except OSError:
        return None
    return None
