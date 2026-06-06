"""MCP tools for the canvas feature.

Seven tools matching design §4:

- ``canvas_open`` — create or re-attach to a named canvas
- ``canvas_write`` — write markdown content to a canvas page
- ``canvas_close`` — mark a canvas closed (does not delete files)
- ``canvas_list`` — read-only listing of all canvases
- ``canvas_decision_open`` — declare the single pending decision on a canvas
- ``canvas_decision_await`` — block until the operator submits (bounded long-poll)
- ``canvas_decision_cancel`` — retract a pending decision

Event publishing diverges from ``memory.py`` (which uses
``except Exception: pass``): canvas wants observability on publish
failures, so this module uses ``logger.warning(..., exc_info=True)``.
Tool results are unaffected by publish failures.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets

from fastmcp import Context

from spellbook.admin.events import (
    CANVAS_DECISION_CANCELLED,
    CANVAS_DECISION_CONSUMED,
    CANVAS_DECISION_OPENED,
    CANVAS_DECISION_SUBMITTED,
    Event,
    Subsystem,
    event_bus,
)
from spellbook.canvas import store as canvas_store
from spellbook.canvas.decision_contract import DecisionCode
from spellbook.core.config import get_env
from spellbook.mcp.server import mcp
from spellbook.mcp.tools.sessions import _get_session_id

logger = logging.getLogger(__name__)


# Map a non-ACCEPTED DecisionCode to the {"error", "code"} envelope the
# decision MCP tools return. The ``code`` is the DecisionCode wire string
# (§3.0), so callers branch on a closed vocabulary (RT-4).
_DECISION_ERROR_MESSAGES = {
    DecisionCode.INVALID_NAME: "invalid canvas name",
    DecisionCode.INVALID_DECISION_ID: "invalid decision_id",
    DecisionCode.NOT_FOUND: "canvas not found",
    DecisionCode.CANVAS_CLOSED: "canvas is closed",
    DecisionCode.DECISION_EXISTS: "a pending decision already exists on this canvas",
    DecisionCode.INVALID_KIND: "kind must be 'choice' or 'approve'",
    DecisionCode.INVALID_OPTIONS: "options invalid: at most 20, each value/label <=200 chars",
    DecisionCode.NO_SUCH_DECISION: "no such decision",
}


def _decision_error(code: DecisionCode) -> dict:
    """Build the ``{"error", "code"}`` envelope for a non-ACCEPTED code."""
    return {
        "error": _DECISION_ERROR_MESSAGES.get(code, code.value),
        "code": code.value,
    }


# Long-poll window bounds (design §6). The harness HTTP-client timeout floor is
# an EMPIRICAL UNKNOWN (§6 escalation) — UNVERIFIED at implementation time; no
# live timing probe was feasible in the test environment. 20s is the
# conservative ceiling kept below the unmeasured floor. It is a clamp bound, not
# a contract value, so it can be raised later without a contract change if a
# probe ever measures the floor >> 20s. Do NOT raise it speculatively.
_AWAIT_TIMEOUT_FLOOR = 1
_AWAIT_TIMEOUT_CEILING = 20


def _clamp_timeout(timeout_s: int) -> int:
    """Clamp the long-poll window to ``1..20`` (design §6).

    Pure module-level helper so the bound is asserted directly and is
    harness-independent. ``canvas_decision_await`` calls this first thing.
    """
    return max(_AWAIT_TIMEOUT_FLOOR, min(_AWAIT_TIMEOUT_CEILING, timeout_s))


def _canvas_url(name: str) -> str:
    """Construct the admin URL for a canvas page.

    Mirrors the host/port precedent at ``spellbook/admin/cli.py:33`` and
    ``spellbook/mcp/server.py:240-241`` so the URL respects operator env
    overrides without hard-coding 127.0.0.1:8765.
    """
    host = get_env("HOST", "127.0.0.1")
    port = int(get_env("PORT", "8765"))
    return f"http://{host}:{port}/admin/canvas/{name}"


async def _publish_canvas_event(event_type: str, data: dict) -> None:
    """Publish a canvas event, swallowing all errors with a warning.

    Tool callers must never break on publish failures. Defense-in-depth
    only; in current behavior ``event_bus.publish`` does not raise.
    """
    try:
        await event_bus.publish(
            Event(subsystem=Subsystem.CANVAS, event_type=event_type, data=data)
        )
    except Exception:
        logger.warning(
            "event_bus.publish failed for %s", event_type, exc_info=True
        )


@mcp.tool()
async def canvas_open(ctx: Context, name: str, title: str = "") -> dict:
    """Open (create or re-attach to) a named canvas.

    Idempotent: if the canvas already exists, returns its current metadata
    without modifying files. If it doesn't exist, creates the directory tree
    (pages/, inbox/, meta.json) and returns the new metadata.

    Threat model: canvas content is TRUSTED-LOCAL-AGENT output. Agents MUST
    NOT write unsanitized external content (chat transcripts, fetched web
    pages, untrusted MCP tool outputs) into a canvas. Raw HTML is permitted
    via rehype-raw and executes under the admin's auth context — a script
    tag is a session-takeover primitive.

    Args:
        name: Canvas name. Must match ^[a-z0-9][a-z0-9_-]{0,63}$.
        title: Human-readable title. Defaults to `name` if empty.

    Returns:
        dict with one of:
        - {"status": "opened", "name": str, "title": str, "url": str,
           "created_at": str, "last_updated": str, "created": bool}
          (created=True if newly created, False if pre-existing)
        - {"error": str, "code": str} where code in {"invalid_name"}
    """
    try:
        meta, created, reopened = canvas_store.open_canvas(name, title=title)
    except ValueError as e:
        return {"error": str(e), "code": "invalid_name"}

    await _publish_canvas_event(
        "canvas.opened",
        {"canvas": name, "created": created, "reopened": reopened},
    )
    return {
        "status": "opened",
        "name": meta.name,
        "title": meta.title,
        "url": _canvas_url(meta.name),
        "created_at": meta.created_at.isoformat(),
        "last_updated": meta.last_updated.isoformat(),
        "created": created,
    }


@mcp.tool()
async def canvas_write(
    ctx: Context,
    canvas: str,
    content: str,
    page: str = "index.md",
) -> dict:
    """Write markdown content to a canvas page, replacing existing content.

    Last-write-wins: this replaces the whole page atomically. Concurrent
    writes to the same canvas from different sessions can clobber each
    other. Use distinct canvas names per concurrent workflow.

    Threat model: TRUSTED-LOCAL-AGENT only. Do NOT write unsanitized external
    content (chat transcripts, fetched web pages, untrusted MCP tool
    outputs). Raw HTML is rendered via rehype-raw and executes under the
    admin's auth context.

    Args:
        canvas: Canvas name. Must match ^[a-z0-9][a-z0-9_-]{0,63}$ and
            already be opened (canvas_open) or this is a no-op error.
        content: Markdown content. Custom shortcodes (<diagram>, <chart>,
            <callout>, <tabs>, <choice>, <approve>) supported. Raw HTML
            permitted. Max 1 MB UTF-8.
        page: Page filename within pages/. MVP only supports "index.md".
            Pass through unchanged; v2 enables multi-page.

    Returns:
        dict with one of:
        - {"status": "written", "canvas": str, "page": str, "bytes": int,
           "last_updated": str, "url": str}
        - {"error": str, "code": str} where code in {"invalid_name",
           "not_found", "closed", "page_too_large", "invalid_content",
           "queue_overflow"}
    """
    # Validate name. canvas_store.NAME_RE is the single source of truth.
    if not canvas_store.NAME_RE.match(canvas):
        return {"error": f"invalid canvas name: {canvas!r}", "code": "invalid_name"}

    # Read existing meta to enforce open/closed semantics.
    meta = canvas_store.read_meta(canvas)
    if meta is None:
        return {"error": f"canvas {canvas!r} not found", "code": "not_found"}
    if meta.closed:
        return {"error": f"canvas {canvas!r} is closed", "code": "closed"}

    # Delegate write; store raises ValueError with code prefix on each
    # error path (invalid_content, page_too_large).
    try:
        nbytes = canvas_store.write_page(canvas, content, page=page)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("page_too_large"):
            code = "page_too_large"
        elif msg.startswith("invalid_content"):
            code = "invalid_content"
        else:
            # Shouldn't reach: name was already validated above.
            code = "invalid_name"
        return {"error": msg, "code": code}

    # Bump meta.last_updated and persist.
    from datetime import datetime, timezone

    bumped = meta.model_copy(update={"last_updated": datetime.now(timezone.utc)})
    canvas_store.write_meta(canvas, bumped)

    await _publish_canvas_event(
        "canvas.updated",
        {"canvas": canvas, "page": page, "bytes": nbytes},
    )
    return {
        "status": "written",
        "canvas": canvas,
        "page": page,
        "bytes": nbytes,
        "last_updated": bumped.last_updated.isoformat(),
        "url": _canvas_url(canvas),
    }


@mcp.tool()
async def canvas_close(ctx: Context, name: str) -> dict:
    """Mark a canvas closed. Does NOT delete files; the directory remains
    on disk and can be removed manually if desired.

    Args:
        name: Canvas name.

    Returns:
        - {"status": "closed", "name": str, "last_updated": str}
        - {"error": str, "code": str} where code in {"invalid_name", "not_found"}
    """
    if not canvas_store.NAME_RE.match(name):
        return {"error": f"invalid canvas name: {name!r}", "code": "invalid_name"}
    closed_meta = canvas_store.close_canvas(name)
    if closed_meta is None:
        return {"error": f"canvas {name!r} not found", "code": "not_found"}
    await _publish_canvas_event("canvas.closed", {"canvas": name})
    return {
        "status": "closed",
        "name": name,
        "last_updated": closed_meta.last_updated.isoformat(),
    }


@mcp.tool()
async def canvas_list(ctx: Context) -> dict:
    """List all canvases on disk with their metadata.

    Symmetric recovery: regenerates meta.json with defaults if missing
    or corrupt, so a canvas always appears in the list with at least
    the inferred name + timestamps.

    Returns:
        {"canvases": [
            {"name": str, "title": str, "created_at": str,
             "last_updated": str, "closed": bool, "url": str}
        ], "count": int}
    """
    items = canvas_store.list_canvases()
    enriched = [{**item, "url": _canvas_url(item["name"])} for item in items]
    return {"canvases": enriched, "count": len(enriched)}


_NO_SESSION_IDENTITY_ERROR = (
    "No session identity: this context has no MCP session id, so a decision "
    "binding cannot be established. Call canvas_decision_open from the session "
    "main context."
)


async def _notify_decision_ready(prompt: str, url: str, session_id: str) -> None:
    """Fire-and-forget operator summons on decision open (RT-11, §7).

    Reuses the existing ``spellbook.notifications`` machinery. A notify failure
    MUST NOT block or fail the declare — this is the one sanctioned narrow
    except, scoped to the fire-and-forget notify only.
    """
    try:
        from spellbook.notifications.notify import send_notification

        summary = prompt if len(prompt) <= 80 else prompt[:77] + "..."
        await send_notification(
            body=f"Decision ready: {summary} — {url}",
            session_id=session_id,
        )
    except Exception:
        logger.warning("decision-ready notification failed", exc_info=True)


@mcp.tool()
async def canvas_decision_open(
    ctx: Context,
    canvas: str,
    decision_id: str,
    kind: str,
    prompt: str,
    options: list[dict] | None = None,
) -> dict:
    """Declare the single pending decision on a canvas and make its
    <choice>/<approve> control LIVE in the browser.

    Use when: you have rendered (or are about to render via canvas_write) a
    decision page and want the operator to answer IN THE BROWSER. Pair with
    canvas_decision_await to block until they answer.

    Do NOT use when: the question is a quick yes/no with no context to show
    (use AskUserQuestion in the terminal), or the operator chose the inline
    terminal decision surface (see canvas-decision skill / feature-config 0.4).

    Main-context-only: only the session main context may declare+await a
    decision (see threat model below). A subagent or identity-less context has
    no session id, so the declare refuses to bind (no_session_identity).

    One-pending-per-canvas: if this canvas already has a pending (un-consumed)
    decision, returns {"code": "decision_exists"}. Open another canvas for a
    parallel ask.

    Args:
        canvas: Canvas name (^[a-z0-9][a-z0-9_-]{0,63}$); must be open.
        decision_id: Stable id for this decision (same regex). Becomes the
            inbox filename and the first-wins claim key.
        kind: "choice" (single-select from options) or "approve" (binary).
        prompt: Operator-facing question (<=2000 chars).
        options: For "choice", list of {"value": str, "label": str}. At most
            20 options; each value/label <=200 chars. The SPA renders these as
            the <choice> radio group; submissions are validated against these
            values. Omit/None for "approve".

    Returns:
        - {"status": "declared", "canvas": str, "decision_id": str,
           "kind": str, "await_token": str, "url": str}
          (KEEP this await_token and pass it to
           canvas_decision_await(await_token=...) — it is the stable binding
           identity (session ids are per-request under stateless HTTP).)
        - {"error": str, "code": str}; code is a DecisionCode (§3.0), in
          {"invalid_name", "invalid_decision_id", "not_found", "canvas_closed",
           "decision_exists", "invalid_kind", "invalid_options",
           "no_session_identity"}.

    Threat model: TRUSTED-LOCAL-AGENT. The prompt/options you pass are rendered
    in the admin origin; do NOT inject external/un-paraphrased content
    (rehype-raw executes raw HTML). The OPERATOR'S answer that comes back is
    operator-authored (terminal-input trust class) and is returned to you as
    plain-text DATA — do not round-trip it verbatim into canvas_write.
    """
    sid = _get_session_id(ctx)
    if sid is None:
        # DA-2: a None binding would later spuriously match another
        # identity-less await. Refuse and write nothing.
        return {"error": _NO_SESSION_IDENTITY_ERROR, "code": "no_session_identity"}

    await_token = secrets.token_urlsafe(16)
    code = canvas_store.declare_decision(
        name=canvas,
        decision_id=decision_id,
        kind=kind,
        prompt=prompt,
        options=options,
        session_id=sid,
        await_token=await_token,
    )
    if code is not DecisionCode.ACCEPTED:
        return _decision_error(code)

    url = _canvas_url(canvas)
    await _publish_canvas_event(
        CANVAS_DECISION_OPENED,
        {"canvas": canvas, "decision_id": decision_id, "kind": kind},
    )
    await _notify_decision_ready(prompt, url, sid)
    return {
        "status": "declared",
        "canvas": canvas,
        "decision_id": decision_id,
        "kind": kind,
        "await_token": await_token,
        "url": url,
    }


def _inbox_file(canvas: str, decision_id: str) -> str:
    """Path to ``inbox/<decision_id>.json`` for a canvas (durable submission)."""
    return os.path.join(
        canvas_store._resolve_canvas_root(), canvas, "inbox", f"{decision_id}.json"
    )


def _corrupt_submission_error(canvas: str, decision_id: str) -> dict:
    """Build the ``{"error", "code"}`` envelope for a CORRUPT_SUBMISSION consume
    outcome (Track A fix 6e6569bf). Names the inbox path so the operator can
    repair or remove it. RECOVERABLE: ``claim_consume`` reads the inbox JSON
    BEFORE creating the ``.consumed`` marker (store F1), so a corrupt file does
    NOT burn the marker — repair the file and the next await delivers it exactly
    once. The agent may re-await after repair; do NOT treat this as ``pending``
    and spin (the file will never self-repair)."""
    return {
        "error": (
            f"corrupt submission on disk for decision {decision_id!r}; "
            f"repair or remove {_inbox_file(canvas, decision_id)} and re-await"
        ),
        "code": DecisionCode.CORRUPT_SUBMISSION.value,
    }


async def _try_consume(canvas: str, decision_id: str) -> dict | None:
    """Attempt the atomic consume step (§4.2 step 3 / §3.6.2).

    Returns the await result dict when the consume resolves (submitted,
    already-consumed, or corrupt-submission), or ``None`` when there is no
    submission to consume yet (caller falls through to the event wait).
    """
    consume = canvas_store.claim_consume(canvas, decision_id)
    if consume.result is DecisionCode.CONSUMED_NOW:
        await _publish_canvas_event(
            CANVAS_DECISION_CONSUMED,
            {"canvas": canvas, "decision_id": decision_id},
        )
        payload = consume.payload or {}
        return {
            "status": "submitted",
            "value": payload.get("value"),
            "free_text": payload.get("free_text"),
            "kind": payload.get("kind"),
            "submitted_at": payload.get("submitted_at"),
        }
    if consume.result is DecisionCode.ALREADY_CONSUMED:
        return {"status": "consumed"}
    if consume.result is DecisionCode.CORRUPT_SUBMISSION:
        # Recoverable: marker NOT burned. Surface immediately so the agent can
        # repair and re-await rather than spinning on an un-repairable file.
        return _corrupt_submission_error(canvas, decision_id)
    # NO_SUBMISSION → no file after all; caller waits for the event.
    return None


@mcp.tool()
async def canvas_decision_await(
    ctx: Context,
    canvas: str,
    decision_id: str,
    timeout_s: int = 15,
    await_token: str | None = None,
) -> dict:
    """Wait up to timeout_s for the operator's submission to this decision,
    then return it — or a 'pending' sentinel if they have not answered yet.

    Bounded long-poll: this call blocks for AT MOST timeout_s. If the operator
    submits within the window, returns the submission immediately (<2s typical,
    event-driven). If the window elapses with no submission, returns
    {"status": "pending"} and YOU CALL IT AGAIN in a loop. Looping preserves
    'wait indefinitely' as a BEHAVIOR while keeping each HTTP request well under
    the harness client timeout (the daemon runs stateless_http=True; a single
    indefinite block is not viable — see design §6).

    PASS THE await_token: canvas_decision_open returns an ``await_token``. Pass
    it back here as the ``await_token`` argument. It is the PRIMARY, robust
    identity binding: only the declaring caller holds it (bearer-style), and it
    is stable across requests. Under stateless_http=True the daemon assigns a
    FRESH ctx.session_id to every HTTP request, so the declaring session's id at
    declare time differs from its id at await time — session-id equality alone is
    NOT a reliable binding (it spuriously fails with binding_mismatch). The token
    is the fix: when supplied and it matches the stored token, the await binds
    regardless of session id. Loop with the SAME token across pending re-awaits.

    Main-context-only (DA-8): still call only from the session main context that
    declared the decision (you hold the token there). If you omit ``await_token``,
    the binding falls back to GUARDED session-id equality (_get_session_id,
    §3.2) — but that fallback is fragile under stateless HTTP and exists only for
    backward compatibility; prefer the token. A None/absent token AND a session
    id that does not match the stored binding gets binding_mismatch.

    Restart-safe (DA / failure mode 2): if the daemon restarted mid-wait, the
    next await reads the durable inbox file and returns the persisted submission
    immediately (catch-up). Re-await after consume is idempotent and returns
    {"status": "consumed"} (mark-consumed-never-delete, DA-9a).

    Args:
        canvas: Canvas name.
        decision_id: The decision id passed to canvas_decision_open.
        timeout_s: Long-poll window, 1..20. Clamped to <=20 (kept
            conservatively below the harness HTTP-client timeout floor, which is
            empirically UNVERIFIED — see §6 escalation; 20s is the safe ceiling,
            default 15s).
        await_token: The token returned by canvas_decision_open. PRIMARY binding
            (bearer-style, stable across requests) and, WHEN SUPPLIED,
            AUTHORITATIVE: an equal token binds regardless of ctx.session_id, and
            a non-equal token yields binding_mismatch with NO session-id
            fallback (a wrong token is fatal even from the declaring session).
            Omit only for legacy token-less callers; the session-id equality
            fallback applies solely when await_token is None.

    Returns:
        - {"status": "submitted", "value": str, "free_text": str | null,
           "kind": str, "submitted_at": str}   # the operator's answer
        - {"status": "pending"}                 # window elapsed; call again
        - {"status": "consumed"}                # already claimed earlier
        - {"error": str, "code": str}; code is a DecisionCode (§3.0), in
          {"no_such_decision", "binding_mismatch", "corrupt_submission"}.
          corrupt_submission is RECOVERABLE: the on-disk inbox JSON is
          unreadable/unparseable, but the .consumed marker was NOT burned
          (claim_consume reads before claiming). Repair or remove the named
          inbox file and re-await — it then delivers exactly once. Do NOT treat
          it as pending and spin; the file will not self-repair.

    Threat model: the returned value/free_text is operator-authored plain-text
    DATA. Treat it as terminal-input trust class. Do NOT echo free_text verbatim
    into canvas_write (rehype-raw is a raw-HTML sink) — paraphrase or strip
    markup first.
    """
    timeout_s = _clamp_timeout(timeout_s)
    sid = _get_session_id(ctx)
    meta = canvas_store.read_meta(canvas)
    if (
        meta is None
        or meta.decision is None
        or meta.decision.decision_id != decision_id
    ):
        return _decision_error(DecisionCode.NO_SUCH_DECISION)

    binding = meta.decision.await_binding
    # Binding precedence. The stored binding always carries a non-empty
    # await_token (declare generates it, §4.1). The await_token, WHEN SUPPLIED,
    # is AUTHORITATIVE — there is no session-id fallback once a caller has
    # presented a token:
    #
    #   1. TOKEN SUPPLIED (await_token is not None) → the token is the sole
    #      authority. It must equal the stored token (constant-time compare):
    #      match → bind; mismatch → binding_mismatch with NO session fallback.
    #      The token is a bearer secret only the declarer holds and is STABLE
    #      across requests, so it is the robust identity. Critically, a caller
    #      who presents a WRONG token MUST be rejected even if their per-request
    #      ctx.session_id happens to equal the declarer's: falling back to the
    #      session match in that case would let a wrong-token holder bind.
    #
    #   2. NO TOKEN (await_token is None, legacy token-less call) → fall back to
    #      non-null session-id equality. Preserves pre-token callers and still
    #      rejects a genuinely foreign caller. Fragile under stateless_http=True,
    #      where ctx.session_id is a fresh uuid per HTTP request (see root
    #      cause) — kept only for backward compatibility.
    if await_token is not None:
        bound = (
            isinstance(await_token, str)
            and isinstance(binding.await_token, str)
            and secrets.compare_digest(await_token, binding.await_token)
        )
    else:
        bound = (
            sid is not None
            and sid == binding.session_id
            and bool(binding.await_token)
        )
    if not bound:
        return _decision_error(DecisionCode.BINDING_MISMATCH)

    if meta.decision.status == "consumed":
        return {"status": "consumed"}

    # Step 3: atomic consume if a submission is already on disk (catch-up).
    if os.path.isfile(_inbox_file(canvas, decision_id)):
        resolved = await _try_consume(canvas, decision_id)
        if resolved is not None:
            return resolved

    # Step 4: subscribe, re-check disk once (closes the subscribe/submit race),
    # then wait for the submitted event filtered to this (canvas, decision_id).
    subscriber_id = f"canvas-await-{canvas}-{decision_id}-{secrets.token_hex(8)}"
    try:
        queue = await event_bus.subscribe(subscriber_id)
        if os.path.isfile(_inbox_file(canvas, decision_id)):
            resolved = await _try_consume(canvas, decision_id)
            if resolved is not None:
                return resolved
        deadline = asyncio.get_running_loop().time() + timeout_s
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return {"status": "pending"}
            try:
                event = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                return {"status": "pending"}
            if (
                event.event_type == CANVAS_DECISION_SUBMITTED
                and event.data.get("canvas") == canvas
                and event.data.get("decision_id") == decision_id
            ):
                resolved = await _try_consume(canvas, decision_id)
                if resolved is not None:
                    return resolved
                # Spurious wake (no file yet): keep waiting within the window.
    finally:
        await event_bus.unsubscribe(subscriber_id)


@mcp.tool()
async def canvas_decision_cancel(
    ctx: Context, canvas: str, decision_id: str
) -> dict:
    """Retract a pending decision (operator-side control goes inert).

    Sets meta.decision.status="cancelled". Idempotent. Use when you no longer
    need the answer (e.g. the path changed). A cancelled decision rejects late
    submissions with DecisionCode.CANCELLED (the route maps it to 409, §5.2).
    Publishes canvas.decision.cancelled (§7, same loop).

    Args:
        canvas: Canvas name.
        decision_id: The decision id passed to canvas_decision_open.

    Returns:
        - {"status": "cancelled"}
        - {"error": str, "code": "no_such_decision"} when no matching decision.
    """
    code = canvas_store.cancel_decision(canvas, decision_id)
    if code is DecisionCode.NO_SUCH_DECISION:
        return _decision_error(code)
    await _publish_canvas_event(
        CANVAS_DECISION_CANCELLED,
        {"canvas": canvas, "decision_id": decision_id},
    )
    return {"status": "cancelled"}
