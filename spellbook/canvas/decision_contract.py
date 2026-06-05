"""Single source of truth for the canvas decision vocabulary.

Three layers touch decision state — the store (``store.py``), the MCP tools
(``mcp/tools/canvas.py``), and the admin route (``admin/routes/canvas.py``).
Without one owner the same concept drifts into three spellings (the earlier
draft had ``closed`` / ``canvas_closed`` / ``CANVAS_CLOSED`` for one
condition). To prevent that, all three layers import from THIS module
(design §3.0, RT-4): one closed vocabulary, one value-validation function,
one meta→detail projector.

This module deliberately does NOT import ``store`` at module top to avoid a
circular import. ``validate_submission_value`` and ``project_decision_for_detail``
reference ``PendingDecision`` by forward-string annotation only and access
attributes duck-typed.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from spellbook.canvas.store import PendingDecision


SUBMISSION_SCHEMA_VERSION = 1  # bump on a breaking submission-contract change


class DecisionCode(str, Enum):
    """Closed vocabulary shared verbatim across store ``ClaimResult``, MCP tool
    ``code`` fields, and route error envelopes. One spelling per concept.
    String values are the wire/JSON codes the SPA and agent see.
    """

    ACCEPTED = "accepted"
    ALREADY_DECIDED = "already_decided"
    NO_SUCH_DECISION = "no_such_decision"
    BINDING_MISMATCH = "binding_mismatch"
    INVALID_VALUE = "invalid_value"
    CANVAS_CLOSED = "canvas_closed"
    CANCELLED = "cancelled"
    DECISION_EXISTS = "decision_exists"
    NO_SESSION_IDENTITY = "no_session_identity"
    SCHEMA_UNSUPPORTED = "schema_unsupported"
    INVALID_NAME = "invalid_name"
    INVALID_DECISION_ID = "invalid_decision_id"
    INVALID_KIND = "invalid_kind"
    INVALID_OPTIONS = "invalid_options"
    NOT_FOUND = "not_found"
    # Consume outcomes (§3.6.2):
    CONSUMED_NOW = "consumed_now"
    ALREADY_CONSUMED = "already_consumed"
    NO_SUBMISSION = "no_submission"
    # Inbox JSON unreadable/unparseable at consume time. Recoverable: the
    # .consumed marker is NOT burned, so the payload can be delivered once the
    # corrupt inbox file is repaired (§3.6.2).
    CORRUPT_SUBMISSION = "corrupt_submission"


def validate_submission_value(decision: "Optional[PendingDecision]", value: str) -> bool:
    """The ONE value-validation function (RT-4).

    Called by ``store.claim_submission`` atomically with the O_EXCL claim
    (§3.6) so the route never validates separately and drifts.

    - For ``kind == "choice"``: ``value`` MUST be one of
      ``{o.value for o in decision.options}``.
    - For ``kind == "approve"``: ``value`` MUST be ``"approved"`` or
      ``"declined"``.

    A ``None`` or malformed ``decision`` (missing ``kind``), or any other
    kind, or a value outside the allowed set, returns ``False``.
    """
    kind = getattr(decision, "kind", None)
    if kind == "choice":
        options = getattr(decision, "options", None) or []
        return value in {o.value for o in options}
    if kind == "approve":
        return value in {"approved", "declined"}
    return False


def project_decision_for_detail(
    decision: "Optional[PendingDecision]",
) -> "Optional[dict]":
    """``meta.decision`` → the SPA-visible detail projection (RT-2/RT-4).

    Returns ``None`` when there is no decision. Strips ``await_binding``
    (server-only identity, never leaves the daemon — DA-2) and ``free_text``
    (never present here; it stays on disk). Returned dict shape::

        {"decision_id", "kind", "prompt", "options", "status"}

    where ``options`` is ``None`` for ``kind == "approve"`` or a list of
    ``{"value", "label"}`` dicts for ``kind == "choice"``.

    ``read_canvas`` (§15 step 1) and ``CanvasDetailResponse`` both serialize
    via this single projector, so the field can never disagree across the two.
    """
    if decision is None:
        return None
    if decision.options is None:
        options: Optional[list] = None
    else:
        options = [{"value": o.value, "label": o.label} for o in decision.options]
    return {
        "decision_id": decision.decision_id,
        "kind": decision.kind,
        "prompt": decision.prompt,
        "options": options,
        "status": decision.status,
    }
