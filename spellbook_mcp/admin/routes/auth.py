"""Auth routes for the admin web interface.

Handles exchange token creation, callback-based session cookie setting,
WebSocket ticket generation, and logout.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from spellbook_mcp.auth import load_token
from spellbook_mcp.admin.auth import (
    create_exchange_token,
    create_session_cookie,
    create_ws_ticket,
    require_admin_auth,
    validate_exchange_token,
)

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


@router.post("/exchange")
async def exchange_token(request: Request):
    """Exchange MCP bearer token for a one-time browser auth token."""
    body = await request.json()
    mcp_token = body.get("token", "")
    stored_token = load_token()
    if not stored_token or not secrets.compare_digest(mcp_token, stored_token):
        raise HTTPException(status_code=401, detail="Invalid token")
    exchange = create_exchange_token()
    return {"exchange_token": exchange}


@router.get("/callback")
async def auth_callback(auth: str):
    """Consume exchange token and set session cookie."""
    if not validate_exchange_token(auth):
        raise HTTPException(
            status_code=401, detail="Invalid or expired exchange token"
        )
    session_id = secrets.token_urlsafe(16)
    cookie_value = create_session_cookie(session_id)
    response = RedirectResponse(url="/admin/")
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
