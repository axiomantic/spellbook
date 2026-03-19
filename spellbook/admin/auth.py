"""Authentication for the Spellbook Admin web interface.

Uses HMAC-SHA256 signed cookies derived from the MCP bearer token.
The signing key is deterministic: sha256("admin-session:{mcp_token}"),
so it remains stable across daemon restarts as long as the token file
does not change.
"""

import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from fastapi import Request, HTTPException

from spellbook.core.auth import load_token


def _get_signing_key() -> bytes:
    """Derive the cookie signing key from the MCP bearer token."""
    token = load_token()
    if not token:
        raise RuntimeError(
            "No .mcp-token found. Cannot start admin app without a signing key. "
            "Ensure the MCP server has been initialized."
        )
    return hashlib.sha256(f"admin-session:{token}".encode()).digest()


# In-memory stores (process-lifetime)
_exchange_tokens: dict[str, float] = {}  # token -> expiry timestamp
_ws_tickets: dict[str, float] = {}       # ticket -> expiry timestamp


def create_exchange_token() -> str:
    """Create a one-time exchange token valid for 60 seconds."""
    token = secrets.token_urlsafe(32)
    _exchange_tokens[token] = time.time() + 60
    _cleanup_expired(_exchange_tokens)
    return token


def validate_exchange_token(token: str) -> bool:
    """Validate and consume an exchange token (single use)."""
    _cleanup_expired(_exchange_tokens)
    expiry = _exchange_tokens.pop(token, None)
    return expiry is not None and time.time() < expiry


def create_session_cookie(session_id: str) -> str:
    """Create a signed session cookie value.

    Format: {json_payload}|{hmac_hex_signature}
    Payload contains session ID and expiry timestamp (24h from now).
    """
    payload = json.dumps({"sid": session_id, "exp": time.time() + 86400})
    sig = hmac.new(_get_signing_key(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def validate_session_cookie(cookie: str) -> Optional[str]:
    """Validate a signed session cookie, return session_id or None."""
    try:
        payload, sig = cookie.rsplit("|", 1)
        expected_sig = hmac.new(
            _get_signing_key(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        data = json.loads(payload)
        if time.time() > data.get("exp", 0):
            return None
        return data["sid"]
    except (ValueError, json.JSONDecodeError):
        return None


def create_ws_ticket() -> str:
    """Create a short-lived WebSocket auth ticket (30s, one-time)."""
    ticket = secrets.token_urlsafe(16)
    _ws_tickets[ticket] = time.time() + 30
    _cleanup_expired(_ws_tickets)
    return ticket


def validate_ws_ticket(ticket: str) -> bool:
    """Validate and consume a WebSocket ticket (single use)."""
    _cleanup_expired(_ws_tickets)
    expiry = _ws_tickets.pop(ticket, None)
    return expiry is not None and time.time() < expiry


def _cleanup_expired(store: dict[str, float]) -> None:
    """Remove expired entries from an in-memory token store."""
    now = time.time()
    expired = [k for k, v in store.items() if v < now]
    for k in expired:
        del store[k]


# FastAPI dependency
async def require_admin_auth(request: Request) -> str:
    """Dependency that validates admin session cookie.

    Returns the session_id if valid, raises 401 otherwise.
    """
    cookie = request.cookies.get("spellbook_admin_session")
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session_id = validate_session_cookie(cookie)
    if not session_id:
        raise HTTPException(status_code=401, detail="Session expired")
    return session_id
