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
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.events import (
    CANVAS_DECISION_SUBMITTED,
    Event,
    Subsystem,
    event_bus,
)
from spellbook.canvas import store as canvas_store
from spellbook.canvas.decision_contract import (
    SUBMISSION_SCHEMA_VERSION,
    DecisionCode,
)

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
    # Projected pending decision (§3.0 project_decision_for_detail); additive,
    # None when absent. await_binding/free_text are never included (DA-2/§8.3).
    decision: Optional[dict] = None


class CanvasErrorBody(BaseModel):
    code: str
    message: str


class CanvasErrorResponse(BaseModel):
    error: CanvasErrorBody


class SubmitRequest(BaseModel):
    """Operator's decision submission (design §5.1). The browser sends only
    the choice/approval ``value`` and an optional note; it does NOT send
    identity — the route reconstructs ``await_binding`` from stored meta."""

    decision_id: str
    value: str  # choice value OR "approved"/"declined"
    free_text: Optional[str] = Field(default=None, max_length=4000)


class SubmitResponse(BaseModel):
    status: str  # "accepted"
    decision_id: str
    # ISO-8601 string (NOT a ``datetime``) so the wire value is byte-identical
    # to the persisted inbox item's ``submitted_at`` (§3.3) — both come from a
    # single ``datetime.isoformat()`` call in the handler. A ``datetime`` field
    # would re-serialize via Pydantic ("...Z") and diverge from the disk form
    # ("...+00:00") even for the same instant.
    submitted_at: str


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
                    "message": "Name must match ^[a-z0-9][a-z0-9_-]{0,63}$",
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


# ---------------------------------------------------------------------------
# POST /api/canvas/{name}/decision/submit (design §5.1, §5.2, §7)
# ---------------------------------------------------------------------------


def _submit_error(code: DecisionCode, message: str, status: int) -> JSONResponse:
    """Build the shared ``{"error": {"code", "message"}}`` envelope
    (``CanvasErrorResponse`` shape). ``code`` is the ``DecisionCode`` value
    verbatim — one vocabulary across store/tool/route (§3.0, RT-4)."""
    return JSONResponse(
        {"error": {"code": code.value, "message": message}},
        status_code=status,
    )


@router.post(
    "/{name}/decision/submit",
    response_model=SubmitResponse,
    responses={
        400: {"model": CanvasErrorResponse},
        404: {"model": CanvasErrorResponse},
        409: {"model": CanvasErrorResponse},
    },
)
async def submit_decision(
    name: str,
    body: SubmitRequest,
    _session: str = Depends(require_admin_auth),
) -> SubmitResponse | JSONResponse:
    """Submit the operator's answer to a canvas's pending decision (§5.1).

    First-wins: the inbox file is the kernel-atomic claim key (§3.6.1), so a
    second tab / double-click loses the race and gets ``409 already_decided``.
    Value validation happens INSIDE ``claim_submission`` via the single
    ``validate_submission_value`` (§3.0, RT-4) — this route never re-validates,
    so the two layers cannot drift.
    """
    # 1. Name regex is the single source of truth (mirror the GET route).
    if not canvas_store.NAME_RE.match(name):
        return _submit_error(
            DecisionCode.INVALID_NAME,
            "Name must match ^[a-z0-9][a-z0-9_-]{0,63}$",
            400,
        )

    # 2. Load the authoritative meta. The browser never sends identity; the
    #    route reconstructs ``await_binding`` from the stored decision (§5.1
    #    step 2) so ``claim_submission``'s binding check (DA-2) passes.
    meta = canvas_store.read_meta(name)
    if (
        meta is None
        or meta.decision is None
        or meta.decision.decision_id != body.decision_id
    ):
        return _submit_error(
            DecisionCode.NO_SUCH_DECISION,
            f"No pending decision '{body.decision_id}' on canvas '{name}'",
            404,
        )

    # 3. Build the SubmissionItem (§3.3). ``submitted_at`` is generated once and
    #    used for both the persisted item and the response.
    binding = meta.decision.await_binding
    submitted_at = datetime.now(timezone.utc).isoformat()
    item = {
        "schema_version": SUBMISSION_SCHEMA_VERSION,
        "decision_id": body.decision_id,
        "canvas": name,
        "kind": meta.decision.kind,
        "value": body.value,
        "free_text": body.free_text,
        "await_binding": {
            "session_id": binding.session_id,
            "await_token": binding.await_token,
        },
        "submitted_at": submitted_at,
        "consumed": False,
    }

    # 4. Atomic first-wins claim; value validation happens inside (RT-4).
    result = canvas_store.claim_submission(name, body.decision_id, item)

    if result == DecisionCode.ACCEPTED:
        # 5. Publish the canvas-keyed invalidation hint (§7, finding #6: no
        #    session_id / namespace). ``value`` rides the bus, never free_text.
        await event_bus.publish(
            Event(
                subsystem=Subsystem.CANVAS,
                event_type=CANVAS_DECISION_SUBMITTED,
                data={
                    "canvas": name,
                    "decision_id": body.decision_id,
                    "value": body.value,
                },
            )
        )
        return SubmitResponse(
            status="accepted",
            decision_id=body.decision_id,
            submitted_at=submitted_at,
        )

    # 6. Map every other DecisionCode to its HTTP status (§5.2). Code string is
    #    the enum value verbatim; only the status and message differ.
    builder = _SUBMIT_ERROR_MAP.get(result)
    if builder is None:
        # Defensive: claim_submission's contract (§3.6.1) only returns the
        # mapped codes, so this is unreachable on the current store. Surface
        # loudly rather than mis-respond if the store's vocabulary ever widens.
        logger.error("Unmapped claim_submission result: %s", result)
        return _submit_error(
            result, f"Submission rejected ({result.value})", 409
        )
    return builder(name, body.decision_id, body.value)


# DecisionCode → (JSONResponse builder) for the non-ACCEPTED claim outcomes
# (§5.2). Each entry closes over the exact message + HTTP status for that code.
# Builder signature: (name, decision_id, value) -> JSONResponse.
_SUBMIT_ERROR_MAP = {
    DecisionCode.ALREADY_DECIDED: lambda name, did, value: _submit_error(
        DecisionCode.ALREADY_DECIDED,
        f"Decision '{did}' was already submitted",
        409,
    ),
    DecisionCode.NO_SUCH_DECISION: lambda name, did, value: _submit_error(
        DecisionCode.NO_SUCH_DECISION,
        f"No pending decision '{did}' on canvas '{name}'",
        404,
    ),
    DecisionCode.CANVAS_CLOSED: lambda name, did, value: _submit_error(
        DecisionCode.CANVAS_CLOSED,
        f"Canvas '{name}' is closed",
        409,
    ),
    DecisionCode.CANCELLED: lambda name, did, value: _submit_error(
        DecisionCode.CANCELLED,
        f"Decision '{did}' was cancelled",
        409,
    ),
    DecisionCode.INVALID_VALUE: lambda name, did, value: _submit_error(
        DecisionCode.INVALID_VALUE,
        f"Value '{value}' is not valid for this decision",
        400,
    ),
    DecisionCode.BINDING_MISMATCH: lambda name, did, value: _submit_error(
        DecisionCode.BINDING_MISMATCH,
        f"Submission binding does not match decision '{did}'",
        409,
    ),
    DecisionCode.INVALID_NAME: lambda name, did, value: _submit_error(
        DecisionCode.INVALID_NAME,
        "Name must match ^[a-z0-9][a-z0-9_-]{0,63}$",
        400,
    ),
}
