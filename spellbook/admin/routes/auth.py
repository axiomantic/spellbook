"""Admin authentication routes: bearer-token login, handoff-flow session bootstrap, session check, and logout."""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from spellbook.core.auth import load_token
from spellbook.admin.auth import (
    create_handoff_token,
    create_session_cookie,
    create_ws_ticket,
    require_admin_auth,
    validate_handoff_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request):
    """Authenticate with the MCP token as password and set session cookie."""
    body = await request.json()
    password = body.get("password", "")
    stored_token = load_token()
    if not stored_token or not secrets.compare_digest(password, stored_token):
        raise HTTPException(status_code=401, detail="Invalid password")
    session_id = secrets.token_urlsafe(16)
    cookie_value = create_session_cookie(session_id)
    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        "spellbook_admin_session",
        cookie_value,
        httponly=True,
        samesite="strict",
        max_age=86400,
    )
    return response


@router.get("/check")
async def check_auth(session_id: str = Depends(require_admin_auth)):
    """Check if the current session is valid. Returns 200 or 401."""
    return {"status": "ok"}


@router.post("/handoff")
async def handoff_mint(request: Request):
    """Mint a single-use opaque handoff URL for browser login.

    Bearer-authenticated. Empty body. The returned ``login_url`` is an
    absolute loopback URL whose path component contains an opaque,
    server-side single-use identifier; the bearer token itself never
    appears in any URL. The opaque id has a 60-second TTL and is consumed
    on first GET (browser back/refresh hitting the same id yields a plain
    404 to avoid an existence oracle).

    H2 design rationale: tokens MUST NOT appear in URLs (browser history,
    Referer headers, process argv). The id is a lookup key, not a
    credential.
    """
    auth_header = request.headers.get("authorization", "")
    provided = ""
    if auth_header.startswith("Bearer "):
        provided = auth_header[len("Bearer "):]
    stored_token = load_token()
    if not stored_token or not secrets.compare_digest(provided, stored_token):
        raise HTTPException(status_code=401, detail="Invalid token")
    handoff_id = create_handoff_token()
    bound_port = request.app.state.bound_port
    login_url = (
        f"http://127.0.0.1:{bound_port}/admin/api/auth/handoff/{handoff_id}"
    )
    return {"login_url": login_url}


@router.get("/handoff/{handoff_id}")
async def handoff_consume(handoff_id: str):
    """Consume a handoff id: set the session cookie and redirect to /admin/.

    Single-use; expired/replayed/unknown ids all return a plain 404 (NOT
    401, NOT 410 -- the status code MUST NOT discriminate between
    "never existed" and "already consumed", since both are normal
    post-success states from browser back/refresh).

    Logged at INFO (not WARNING) for the same reason: a replayed id is
    expected browser behavior, not a security event.
    """
    if not validate_handoff_token(handoff_id):
        logger.info("admin handoff: id not valid (expired, replayed, or unknown)")
        raise HTTPException(status_code=404, detail="Not found")
    session_id = secrets.token_urlsafe(16)
    cookie_value = create_session_cookie(session_id)
    response = RedirectResponse(url="/admin/", status_code=302)
    response.set_cookie(
        "spellbook_admin_session",
        cookie_value,
        httponly=True,
        samesite="strict",
        max_age=86400,
    )
    return response


@router.post("/ws-ticket")
async def get_ws_ticket(session_id: str = Depends(require_admin_auth)):
    """Get a short-lived ticket for WebSocket authentication."""
    ticket = create_ws_ticket()
    return {"ticket": ticket}


@router.post("/logout")
async def logout():
    """Clear session cookie."""
    response = JSONResponse({"status": "ok"})
    response.delete_cookie("spellbook_admin_session")
    return response
