"""Admin HTTP routes for the canvas feature.

Two endpoints mounted at ``/api/canvas`` by ``spellbook.admin.app``:

- ``GET /api/canvas`` — list all canvases (read-only).
- ``GET /api/canvas/{name}`` — fetch a single canvas detail.

Writes go through MCP tools, not these routes. Both endpoints share
the existing HMAC-cookie auth dependency (``require_admin_auth``); no
new auth surface is introduced. Error envelope matches design §13.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from spellbook.admin.auth import require_admin_auth
from spellbook.canvas import store as canvas_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic response models (design §5.1)
# ---------------------------------------------------------------------------


class CanvasListItem(BaseModel):
    name: str
    title: str
    created_at: datetime
    last_updated: datetime
    closed: bool


class CanvasListResponse(BaseModel):
    canvases: list[CanvasListItem]
    count: int


class CanvasDetailResponse(BaseModel):
    name: str
    title: str
    created_at: datetime
    last_updated: datetime
    closed: bool
    page: str  # "index.md" in MVP
    content: str  # raw markdown
    bytes: int


class CanvasErrorBody(BaseModel):
    code: str
    message: str


class CanvasErrorResponse(BaseModel):
    error: CanvasErrorBody


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


router = APIRouter(prefix="/canvas", tags=["canvas"])


@router.get("", response_model=CanvasListResponse)
async def list_canvases(
    _session: str = Depends(require_admin_auth),
) -> CanvasListResponse:
    """List all canvases sorted by ``last_updated`` desc."""
    items = canvas_store.list_canvases()
    return CanvasListResponse(
        canvases=[CanvasListItem(**i) for i in items],
        count=len(items),
    )


@router.get(
    "/{name}",
    response_model=CanvasDetailResponse,
    responses={
        400: {"model": CanvasErrorResponse},
        404: {"model": CanvasErrorResponse},
    },
)
async def get_canvas(
    name: str,
    _session: str = Depends(require_admin_auth),
):
    """Get a single canvas by name with its page content."""
    # Use the store's regex as the single source of truth (per impl plan
    # P2-8 fix) — prevents drift from the design §5.2 inlined regex.
    if not canvas_store.NAME_RE.match(name):
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_name",
                    "message": "Name must match ^[a-z0-9][a-z0-9-_]{0,63}$",
                }
            },
            status_code=400,
        )
    result = canvas_store.read_canvas(name)
    if result is None:
        return JSONResponse(
            {
                "error": {
                    "code": "not_found",
                    "message": f"Canvas '{name}' not found",
                }
            },
            status_code=404,
        )
    return CanvasDetailResponse(**result)
