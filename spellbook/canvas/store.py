"""Filesystem store for canvases.

Per design §3, a canvas is a named directory tree under
``~/.local/spellbook/canvas/<name>/`` with this layout::

    <name>/
      pages/
        index.md      # agent-written markdown; MVP = single page
      inbox/              # submission items + .consumed markers (decision write-back)
      meta.json       # CanvasMeta metadata

Writes are atomic (tempfile + ``os.replace``) mirroring the
``agent2agent`` precedent. Reads regenerate missing or corrupt ``meta.json``
with default-derived metadata so a canvas always surfaces in
``canvas_list`` with at least an inferred title + timestamps.

Threat model: canvas content is TRUSTED-LOCAL-AGENT output only. Agents
MUST NOT write unsanitized external content (chat transcripts, fetched
web pages, untrusted MCP tool outputs, user-pasted strings) into a
canvas. ``rehype-raw`` is an explicit escape hatch — raw HTML renders
under the admin's auth context, so a script tag is a session-takeover
primitive.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Callable, NamedTuple, Optional

from pydantic import BaseModel, Field

from spellbook.canvas.decision_contract import (
    DecisionCode,
    SUBMISSION_SCHEMA_VERSION,
    project_decision_for_detail,
    validate_submission_value,
)


NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-_]{0,63}$")


class DecisionOption(BaseModel):
    """One selectable option for ``kind == "choice"`` (RT-12 bounds)."""

    value: str = Field(..., max_length=200)
    label: str = Field(..., max_length=200)


class AwaitBinding(BaseModel):
    """Who is allowed to claim this decision (DA-2 routing identity).

    ``session_id`` is the MCP ``ctx.session_id`` of the awaiting main
    context, obtained via the GUARDED accessor (``_get_session_id``) —
    never ``ctx.session_id`` unguarded. ``await_token`` is a per-declare
    random nonce; the await match (§4.2 step 1) requires NON-NULL
    ``session_id`` equality AND ``await_token`` equality, so a stale
    daemon's resurrected await cannot steal a decision declared by a
    different daemon for the same canvas name.

    ``await_token`` is DAEMON-INTERNAL: persisted in ``meta.json`` and never
    sent to or by the browser. The POST handler reconstructs the binding
    from the stored decision; the browser cannot know the token.
    """

    session_id: str  # non-null by construction (declare rejects None, §4.1)
    await_token: str  # secrets.token_urlsafe(16), generated at declare time


class PendingDecision(BaseModel):
    """The single pending decision on a canvas (one-at-a-time).

    Lives in ``meta.json`` so it is authoritative over the page body and
    survives ``canvas_write``. Cleared (set back to ``None``) when the
    decision is resolved (submission claimed) or explicitly cancelled.
    """

    decision_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-_]{0,63}$")
    kind: str  # "choice" | "approve" (matches the shortcode that renders it)
    prompt: str = Field(..., max_length=2000)
    # JSON-serializable option list for "choice"; None for "approve".
    # Bounded (RT-12): at most 20 options; each option's value/label <=200.
    options: Optional[list[DecisionOption]] = Field(default=None, max_length=20)
    # Identity binding for multi-daemon safety (DA-2).
    await_binding: AwaitBinding
    status: str = "pending"  # "pending" | "submitted" | "consumed" | "cancelled"
    created_at: datetime
    payload_schema_version: int = SUBMISSION_SCHEMA_VERSION  # §3.4


class CanvasMeta(BaseModel):
    """Canvas metadata persisted as ``meta.json``.

    Authoritative source for canvas title and timestamps. Used by
    ``canvas_list`` and the admin frontend. Symmetric recovery: if the
    file is missing or corrupt, both ``canvas_open`` and ``canvas_list``
    regenerate it with defaults inferred from the canvas directory.
    """

    name: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-_]{0,63}$")
    title: str = Field(..., max_length=200)
    created_at: datetime
    last_updated: datetime
    closed: bool = False
    schema_version: int = 2  # was 1; bump signals decision-capable
    decision: Optional[PendingDecision] = None  # NEW, default None


def _resolve_canvas_root() -> str:
    """Return ``~/.local/spellbook/canvas/``.

    Tests monkeypatch this to redirect to a tmp directory.

    Uses ``os.path.join`` (not a slash-literal subpath) so the result has
    consistent native separators on every platform. Mixed-separator paths
    are accepted by the OS but break naive suffix / prefix checks downstream.
    """
    return os.path.join(os.path.expanduser("~"), ".local", "spellbook", "canvas")


def _max_page_bytes() -> int:
    """Maximum bytes accepted by ``write_page``.

    Read at call time (not import time) so tests can flip the limit via
    ``monkeypatch.setenv``. A malformed env var (non-integer or
    non-positive) is logged and ignored; the default 1 MB applies. This
    prevents a typo in operator config from breaking every
    ``canvas_write`` call with an opaque ``ValueError``.
    """
    default = 1 * 1024 * 1024
    raw = os.environ.get("SPELLBOOK_CANVAS_MAX_PAGE_BYTES")
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logging.getLogger(__name__).warning(
            "SPELLBOOK_CANVAS_MAX_PAGE_BYTES=%r is not an integer; "
            "falling back to %d bytes (default).",
            raw,
            default,
        )
        return default
    if value <= 0:
        logging.getLogger(__name__).warning(
            "SPELLBOOK_CANVAS_MAX_PAGE_BYTES=%r must be positive; "
            "falling back to %d bytes (default).",
            raw,
            default,
        )
        return default
    return value


def _canvas_dir(name: str) -> str:
    """Return the absolute canvas directory for ``name``.

    Raises:
        ValueError: ``name`` fails the regex OR the resolved path escapes
            the canvas root (path-traversal guard: the realpath of the
            candidate must equal the canvas root or sit beneath it).
    """
    if not NAME_RE.match(name):
        raise ValueError(f"invalid_name: {name!r} does not match {NAME_RE.pattern}")
    root = _resolve_canvas_root()
    real_root = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(real_root, name))
    if not (candidate == real_root or candidate.startswith(real_root + os.sep)):
        raise ValueError(f"invalid_name: {name!r} escapes canvas root")
    return candidate


def _atomic_write(path: str, content: bytes) -> None:
    """Atomic file write via tempfile + ``os.replace``.

    Mirrors ``skills/agent2agent/scripts/agent2agent.py:_atomic_write_text``.
    On any error, the temp file is removed and the original (if any) is
    untouched.
    """
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _meta_path(canvas_dir: str) -> str:
    return os.path.join(canvas_dir, "meta.json")


def _page_path(canvas_dir: str, page: str = "index.md") -> str:
    return os.path.join(canvas_dir, "pages", page)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _mtime_dt(path: str) -> Optional[datetime]:
    try:
        ts = os.path.getmtime(path)
    except OSError:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _regenerate_meta(name: str, canvas_dir: str) -> CanvasMeta:
    """Build default metadata for a canvas whose ``meta.json`` is
    missing or corrupt.

    Timestamps are inferred from ``pages/index.md`` mtime when available,
    falling back to current time.
    """
    page = _page_path(canvas_dir)
    mtime = _mtime_dt(page) or _now_utc()
    return CanvasMeta(
        name=name,
        title=name,
        created_at=mtime,
        last_updated=mtime,
        closed=False,
    )


def read_meta(name: str) -> Optional[CanvasMeta]:
    """Read ``meta.json`` for ``name``.

    Returns ``None`` only when the canvas directory itself is missing.
    If the directory exists but ``meta.json`` is missing or corrupt,
    regenerates and returns the default-derived metadata WITHOUT
    persisting (callers persist when appropriate).
    """
    try:
        canvas_dir = _canvas_dir(name)
    except ValueError:
        return None
    if not os.path.isdir(canvas_dir):
        return None
    meta_p = _meta_path(canvas_dir)
    if os.path.isfile(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return CanvasMeta.model_validate(raw)
        except (OSError, ValueError):
            # Corrupt — fall through to regenerate.
            pass
    return _regenerate_meta(name, canvas_dir)


def write_meta(name: str, meta: CanvasMeta) -> None:
    """Atomically persist ``meta`` for ``name``."""
    canvas_dir = _canvas_dir(name)
    os.makedirs(canvas_dir, exist_ok=True)
    payload = meta.model_dump_json().encode("utf-8")
    _atomic_write(_meta_path(canvas_dir), payload)


def write_page(name: str, content: str, page: str = "index.md") -> int:
    """Atomically write ``content`` to ``pages/<page>`` and bump ``last_updated``.

    Args:
        name: Canvas name (must match :data:`NAME_RE`).
        content: UTF-8 string content.
        page: Page filename; MVP only accepts ``"index.md"``.

    Returns:
        Bytes written.

    Raises:
        ValueError: name regex fails, ``page != "index.md"``, content
            exceeds :func:`_max_page_bytes`, or content is not encodable
            as UTF-8. The message starts with the error code from §13
            (``invalid_name``, ``invalid_content``, ``page_too_large``).
    """
    canvas_dir = _canvas_dir(name)  # raises ValueError on invalid name
    if page != "index.md":
        raise ValueError(f"invalid_content: page {page!r} not supported in MVP")
    try:
        encoded = content.encode("utf-8")
    except UnicodeEncodeError as e:
        raise ValueError(f"invalid_content: content not UTF-8 encodable ({e})") from e
    limit = _max_page_bytes()
    if len(encoded) > limit:
        raise ValueError(f"page_too_large: {len(encoded)} > {limit}")
    _atomic_write(_page_path(canvas_dir, page), encoded)
    return len(encoded)


def read_canvas(name: str) -> Optional[dict]:
    """Return the full canvas payload or ``None`` when not found.

    Payload shape (matches ``CanvasDetailResponse`` in
    ``spellbook.admin.routes.canvas``)::

        {
            "name": str,
            "title": str,
            "created_at": str (ISO 8601),
            "last_updated": str (ISO 8601),
            "closed": bool,
            "page": "index.md",
            "content": str,
            "bytes": int,
            "decision": dict | None,  # projected pending decision (§3.0)
        }

    Path-traversal and other invalid names are rejected at the
    ``_canvas_dir`` boundary and surface here as ``None``.
    """
    try:
        canvas_dir = _canvas_dir(name)
    except ValueError:
        return None
    if not os.path.isdir(canvas_dir):
        return None
    meta = read_meta(name)
    if meta is None:
        return None
    page = _page_path(canvas_dir)
    if os.path.isfile(page):
        with open(page, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""
    # Persist regenerated meta if it wasn't there (symmetric recovery).
    if not os.path.isfile(_meta_path(canvas_dir)):
        write_meta(name, meta)
    return {
        "name": meta.name,
        "title": meta.title,
        "created_at": meta.created_at.isoformat(),
        "last_updated": meta.last_updated.isoformat(),
        "closed": meta.closed,
        "page": "index.md",
        "content": content,
        "bytes": len(content.encode("utf-8")),
        "decision": project_decision_for_detail(meta.decision),
    }


def list_canvases() -> list[dict]:
    """List all canvases under the canvas root, sorted by
    ``last_updated`` desc.

    Symmetric recovery: regenerates missing or corrupt ``meta.json`` with
    defaults inferred from ``pages/index.md`` mtime.
    """
    root = _resolve_canvas_root()
    if not os.path.isdir(root):
        return []
    items: list[dict] = []
    for entry in os.listdir(root):
        path = os.path.join(root, entry)
        if not os.path.isdir(path):
            continue
        if not NAME_RE.match(entry):
            continue
        meta = read_meta(entry)
        if meta is None:
            continue
        # Persist regenerated meta if it wasn't there.
        if not os.path.isfile(_meta_path(path)):
            try:
                write_meta(entry, meta)
            except OSError:
                pass
        items.append(
            {
                "name": meta.name,
                "title": meta.title,
                "created_at": meta.created_at.isoformat(),
                "last_updated": meta.last_updated.isoformat(),
                "closed": meta.closed,
            }
        )
    items.sort(key=lambda i: i["last_updated"], reverse=True)
    return items


def open_canvas(name: str, title: str = "") -> tuple[CanvasMeta, bool, bool]:
    """Create or re-attach to a canvas.

    Returns:
        ``(meta, created, reopened)``:
        - ``created`` is True when the canvas directory did not exist
          before this call.
        - ``reopened`` is True when an existing canvas with ``closed=True``
          was reopened.
        - The two are mutually exclusive; both False indicates an
          idempotent reattach to an already-open canvas.

    Raises:
        ValueError: name regex fails (``invalid_name``).
    """
    canvas_dir = _canvas_dir(name)
    pages_dir = os.path.join(canvas_dir, "pages")
    inbox_dir = os.path.join(canvas_dir, "inbox")
    page_p = _page_path(canvas_dir)
    meta_p = _meta_path(canvas_dir)

    dir_existed_before = os.path.isdir(canvas_dir)

    # Always ensure the directory tree exists (idempotent).
    os.makedirs(pages_dir, exist_ok=True)
    os.makedirs(inbox_dir, exist_ok=True)
    if not os.path.isfile(page_p):
        _atomic_write(page_p, b"")

    created = False
    reopened = False

    existing = None
    if dir_existed_before and os.path.isfile(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                existing = CanvasMeta.model_validate_json(f.read())
        except (OSError, ValueError):
            existing = None

    now = _now_utc()
    if existing is not None:
        if existing.closed:
            existing = existing.model_copy(
                update={"closed": False, "last_updated": now}
            )
            reopened = True
            write_meta(name, existing)
        meta = existing
    else:
        # Either fresh canvas (created=True) or directory existed with
        # missing/corrupt meta (regenerate; report created=True only
        # when the dir is genuinely new).
        created = not dir_existed_before
        effective_title = title or name
        if dir_existed_before:
            # Regenerate from existing page mtime when possible.
            mtime = _mtime_dt(page_p) or now
            meta = CanvasMeta(
                name=name,
                title=effective_title,
                created_at=mtime,
                last_updated=mtime,
                closed=False,
            )
        else:
            meta = CanvasMeta(
                name=name,
                title=effective_title,
                created_at=now,
                last_updated=now,
                closed=False,
            )
        write_meta(name, meta)

    return meta, created, reopened


def close_canvas(name: str) -> Optional[CanvasMeta]:
    """Mark a canvas closed. Returns the updated meta or ``None`` if the
    canvas is missing. Does not delete files."""
    try:
        canvas_dir = _canvas_dir(name)
    except ValueError:
        return None
    meta_p = _meta_path(canvas_dir)
    if not os.path.isfile(meta_p):
        return None
    try:
        with open(meta_p, "r", encoding="utf-8") as f:
            meta = CanvasMeta.model_validate_json(f.read())
    except (OSError, ValueError):
        return None
    closed_meta = meta.model_copy(
        update={"closed": True, "last_updated": _now_utc()}
    )
    write_meta(name, closed_meta)
    return closed_meta


# ---------------------------------------------------------------------------
# Decision lifecycle (design §3.2, §3.6, §4)
# ---------------------------------------------------------------------------

_DECISION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-_]{0,63}$")
_VALID_KINDS = {"choice", "approve"}
# A decision blocks a fresh declare only while it is still live; resolved or
# retracted decisions free the canvas for a new one.
_LIVE_STATUSES = {"pending", "submitted"}


# Test seam (code-review F2): invoked inside ``_merge_decision`` AFTER the fresh
# re-read of meta but BEFORE the merge-write, so a test can deterministically
# interleave a concurrent meta mutation into the read-modify-write window
# without sleeps. Production default is ``None`` (no-op).
_DECISION_MERGE_HOOK: Optional["Callable[[str], None]"] = None


def _set_decision_merge_hook(hook: "Optional[Callable[[str], None]]") -> None:
    """Install (or clear, with ``None``) the decision-merge interleave hook.

    Test-only seam for code-review F2. Production code never calls this.
    """
    global _DECISION_MERGE_HOOK
    _DECISION_MERGE_HOOK = hook


def _merge_decision(
    name: str,
    mutate: "Callable[[Optional[PendingDecision]], Optional[PendingDecision]]",
) -> None:
    """Re-read ``meta.json`` and write back ONLY the decision field (merge
    semantics, code-review F2).

    Reads the freshest meta on disk, computes the new decision from the
    freshly-read decision via ``mutate``, then writes a copy that updates ONLY
    ``decision`` and ``last_updated`` — every other field (title, closed,
    schema_version, etc.) is preserved from the fresh read, so a concurrent
    ``canvas_write``/title update landing in the read-modify-write window is
    not clobbered.

    ``mutate`` receives the freshly-read ``meta.decision`` (which may differ
    from what the caller first read — e.g. a cancel may have landed) and
    returns the decision to persist. This is what makes the LAST atomic writer
    win per the source-of-truth doctrine (§3.6): ``meta.decision.status`` is
    derived/best-effort; delivery truth lives in the O_EXCL marker + inbox
    file, not here.

    No-op if the canvas's meta cannot be re-read (directory vanished).
    """
    fresh = read_meta(name)
    if fresh is None:
        return
    # Fire the interleave hook at most once per merge, and clear it for the
    # duration so a hook that itself performs decision writes (e.g. a racing
    # cancel) does not re-enter this branch and recurse.
    global _DECISION_MERGE_HOOK
    hook = _DECISION_MERGE_HOOK
    if hook is not None:
        _DECISION_MERGE_HOOK = None
        try:
            hook(name)
        finally:
            _DECISION_MERGE_HOOK = hook
        # Re-read so the hook's concurrent write is the one we merge into.
        fresh = read_meta(name)
        if fresh is None:
            return
    new_decision = mutate(fresh.decision)
    # Never regress last_updated below the freshly-read value: a decision-status
    # write must not roll back a concurrent canvas_write's newer timestamp
    # (code-review F2). max() keeps the field monotonic.
    next_updated = max(fresh.last_updated, _now_utc())
    write_meta(
        name,
        fresh.model_copy(
            update={"decision": new_decision, "last_updated": next_updated}
        ),
    )


def declare_decision(
    name: str,
    decision_id: str,
    kind: str,
    prompt: str,
    options: Optional[list[dict]],
    session_id: str,
    await_token: str,
) -> DecisionCode:
    """Declare the single pending decision on a canvas (§4.1 effect).

    Writes an authoritative ``meta.decision``. ``session_id`` is non-null by
    contract: the None-identity guard lives in the MCP tool (Task B2), not
    here.

    Returns a :class:`DecisionCode`:
        - ``ACCEPTED`` on success.
        - ``INVALID_NAME`` / ``INVALID_DECISION_ID`` on regex failure.
        - ``NOT_FOUND`` when the canvas does not exist.
        - ``CANVAS_CLOSED`` when the canvas is closed.
        - ``DECISION_EXISTS`` when a live (pending/submitted) decision is
          already present.
        - ``INVALID_KIND`` when ``kind`` is not ``"choice"`` or ``"approve"``.
        - ``INVALID_OPTIONS`` when a ``choice`` has >20 options or any
          ``value``/``label`` exceeds 200 chars.
    """
    if not NAME_RE.match(name):
        return DecisionCode.INVALID_NAME
    if not _DECISION_ID_RE.match(decision_id):
        return DecisionCode.INVALID_DECISION_ID
    meta = read_meta(name)
    if meta is None:
        return DecisionCode.NOT_FOUND
    if meta.closed:
        return DecisionCode.CANVAS_CLOSED
    if meta.decision is not None and meta.decision.status in _LIVE_STATUSES:
        return DecisionCode.DECISION_EXISTS
    if kind not in _VALID_KINDS:
        return DecisionCode.INVALID_KIND

    decision_options: Optional[list[DecisionOption]] = None
    if kind == "choice":
        raw_options = options or []
        if len(raw_options) > 20:
            return DecisionCode.INVALID_OPTIONS
        built: list[DecisionOption] = []
        for opt in raw_options:
            # Structural validation BEFORE any len()/.get() (Gemini round-5 F1):
            # a non-dict element, or a missing/None/non-str value|label, must
            # return INVALID_OPTIONS — never crash with AttributeError/TypeError
            # and escape the closed DecisionCode vocabulary. An empty-string
            # value is also rejected: a choice option with no value can never be
            # submitted against (validate_submission_value matches on o.value).
            if not isinstance(opt, dict):
                return DecisionCode.INVALID_OPTIONS
            value = opt.get("value")
            label = opt.get("label")
            if not isinstance(value, str) or not isinstance(label, str):
                return DecisionCode.INVALID_OPTIONS
            if not value or not label:
                return DecisionCode.INVALID_OPTIONS
            if len(value) > 200 or len(label) > 200:
                return DecisionCode.INVALID_OPTIONS
            built.append(DecisionOption(value=value, label=label))
        decision_options = built

    decision = PendingDecision(
        decision_id=decision_id,
        kind=kind,
        prompt=prompt,
        options=decision_options,
        await_binding=AwaitBinding(session_id=session_id, await_token=await_token),
        status="pending",
        created_at=_now_utc(),
    )
    # Merge into the freshest meta so a concurrent canvas_write/title update is
    # not clobbered (code-review F2). The live-decision guard above used the
    # initial read; a racing declare is still bounded by the one-at-a-time
    # contract enforced at the MCP-tool layer.
    _merge_decision(name, lambda _current: decision)
    return DecisionCode.ACCEPTED


def _inbox_path(canvas_dir: str, decision_id: str) -> str:
    return os.path.join(canvas_dir, "inbox", f"{decision_id}.json")


def claim_submission(name: str, decision_id: str, item: dict) -> DecisionCode:
    """Atomically create ``inbox/<decision_id>.json``, first-writer-wins
    (§3.6.1, DA-3).

    Does NOT use :func:`_atomic_write` (tempfile + ``os.replace`` overwrites
    the final path, which would defeat first-wins). Opens the FINAL path
    directly with ``os.open(path, O_CREAT | O_EXCL | O_WRONLY)``. On success:
    write the full bytes through an ``os.fdopen(fd, "wb")`` wrapper (so a
    short write cannot truncate the payload), ``os.fsync`` before close, return
    ``ACCEPTED``. On ``FileExistsError`` (a prior submission already won):
    ``ALREADY_DECIDED``.

    Durability / claim-release (Gemini round-4): if write/flush/fsync raises
    after the O_EXCL create (disk full, interruption), the partial/empty file is
    unlinked (best-effort) before the exception propagates, RELEASING the
    first-wins claim. The submit side has no CORRUPT_SUBMISSION recovery (unlike
    consume), so a failed write must not leave a corrupt payload that burns the
    claim forever — a retry must be able to win cleanly.

    The value is validated (``validate_submission_value``, §3.0) BEFORE the
    claim, so an invalid value never lands an inbox file. The item is also
    checked for JSON-serializability up front (code-review F3): a
    non-serializable item returns ``INVALID_VALUE`` rather than raising
    ``TypeError`` after partial work.

    Source-of-truth doctrine (§3.6, code-review F2): the O_EXCL inbox file is
    the authoritative claim. The ``meta.decision.status="submitted"`` flip is a
    derived, best-effort projection written via :func:`_merge_decision` (re-read
    + merge), so a concurrent ``canvas_write`` or ``cancel`` is never clobbered;
    the LAST atomic meta writer wins for the status field.

    Returns a :class:`DecisionCode`:
        - ``ACCEPTED`` / ``ALREADY_DECIDED`` (claim outcome).
        - ``NO_SUCH_DECISION`` when no decision is recorded.
        - ``CANVAS_CLOSED`` / ``CANCELLED`` (terminal canvas/decision state).
        - ``BINDING_MISMATCH`` when ``item["await_binding"]`` does not match
          the stored binding (DA-2).
        - ``INVALID_VALUE`` when the value is not allowed for the kind OR the
          item is not JSON-serializable.
    """
    try:
        canvas_dir = _canvas_dir(name)
    except ValueError:
        return DecisionCode.INVALID_NAME
    meta = read_meta(name)
    if meta is None or meta.decision is None or meta.decision.decision_id != decision_id:
        return DecisionCode.NO_SUCH_DECISION
    if meta.closed:
        return DecisionCode.CANVAS_CLOSED
    decision = meta.decision
    if decision.status == "cancelled":
        return DecisionCode.CANCELLED
    stored = decision.await_binding
    supplied = item.get("await_binding") or {}
    if (
        supplied.get("session_id") != stored.session_id
        or supplied.get("await_token") != stored.await_token
    ):
        return DecisionCode.BINDING_MISMATCH
    if not validate_submission_value(decision, item.get("value", "")):
        return DecisionCode.INVALID_VALUE
    # Validate serializability BEFORE the O_EXCL claim (code-review F3) so a
    # non-serializable item never burns the first-wins slot nor raises.
    try:
        payload = json.dumps(item).encode("utf-8")
    except (TypeError, ValueError):
        return DecisionCode.INVALID_VALUE

    inbox_path = _inbox_path(canvas_dir, decision_id)
    os.makedirs(os.path.dirname(inbox_path), exist_ok=True)
    try:
        fd = os.open(inbox_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return DecisionCode.ALREADY_DECIDED
    # Wrap the O_EXCL fd in a file object so the FULL payload is written
    # (a bare os.write may short-write and silently truncate); fsync before
    # close preserves the durability guarantee, and os.fdopen's context
    # manager closes the fd on every path (including the fsync error path).
    #
    # If write/flush/fsync raises (disk full, interruption), the O_EXCL file
    # already exists on disk holding a partial/empty payload. Leaving it there
    # would permanently burn the first-wins claim: every subsequent valid
    # submission would see the path and return ALREADY_DECIDED, and the submit
    # side has no recovery path (unlike consume's CORRUPT_SUBMISSION). So on any
    # failure, unlink the partial file (best-effort) to RELEASE the claim before
    # re-raising — a failed write must not consume the slot.
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        try:
            os.unlink(inbox_path)
        except OSError:
            pass
        raise
    # Flip status to submitted (best-effort, derived). Merge into the freshest
    # meta so a concurrent update is preserved and the last atomic writer wins.
    # Only advance pending->submitted: a terminal status (cancelled/consumed)
    # that landed concurrently must NOT be resurrected (code-review F2).
    def _to_submitted(
        current: Optional[PendingDecision],
    ) -> Optional[PendingDecision]:
        base = current or decision
        if base.status != "pending":
            return base
        return base.model_copy(update={"status": "submitted"})

    _merge_decision(name, _to_submitted)
    return DecisionCode.ACCEPTED


def cancel_decision(name: str, decision_id: str) -> DecisionCode:
    """Retract a pending decision: set ``status="cancelled"`` (§4.4).

    Idempotent. Returns ``CANCELLED`` on success (including re-cancel) or
    ``NO_SUCH_DECISION`` when no matching decision exists.

    Source-of-truth doctrine (§3.6, code-review F2): the status write goes
    through :func:`_merge_decision` (re-read + merge), so a concurrent
    ``canvas_write`` / title update is preserved. ``meta.decision.status`` is a
    derived, best-effort projection; cancel is a terminal retraction and the
    last atomic meta writer wins.
    """
    meta = read_meta(name)
    if meta is None or meta.decision is None or meta.decision.decision_id != decision_id:
        return DecisionCode.NO_SUCH_DECISION
    _merge_decision(
        name,
        lambda current: (current or meta.decision).model_copy(
            update={"status": "cancelled"}
        ),
    )
    return DecisionCode.CANCELLED


class ConsumeResult(NamedTuple):
    """Outcome of :func:`claim_consume`.

    ``payload`` carries the submission item dict only on ``CONSUMED_NOW``;
    it is ``None`` for ``ALREADY_CONSUMED`` and ``NO_SUBMISSION``.
    """

    result: DecisionCode
    payload: Optional[dict]


def claim_consume(name: str, decision_id: str) -> ConsumeResult:
    """Atomically claim delivery of a submitted decision, first-consumer-wins
    (§3.6.2, RT-1).

    Precondition: ``inbox/<decision_id>.json`` exists (a submission landed);
    otherwise returns ``NO_SUBMISSION``.

    Order (code-review F1): read AND parse the inbox JSON BEFORE attempting the
    O_EXCL marker create. A corrupt/partial inbox file therefore returns
    ``CORRUPT_SUBMISSION`` WITHOUT burning the ``.consumed`` marker, so the
    payload stays recoverable — repair the inbox file and ``claim_consume``
    again delivers it exactly once. (Burning the marker first would make a
    corrupt payload undeliverable forever.)

    Claim: ``os.open(inbox/<decision_id>.consumed, O_CREAT|O_EXCL|O_WRONLY)``.
        - success -> THIS caller owns delivery. Set
          ``meta.decision.status="consumed"`` (best-effort, derived; written via
          :func:`_merge_decision` so a concurrent meta update is preserved —
          code-review F2), return ``CONSUMED_NOW`` with the submission payload.
        - ``FileExistsError`` -> another await already consumed it. Return
          ``ALREADY_CONSUMED`` (no payload).

    Source-of-truth doctrine (§3.6): the ``.consumed`` marker create is the
    single atomic delivery decision point; ``meta.decision.status`` is a derived
    projection, not the truth. The inbox JSON persists (never deleted) for
    human/debug inspection.

    Returns:
        - ``CONSUMED_NOW`` (with payload) / ``ALREADY_CONSUMED`` / ``NO_SUBMISSION``.
        - ``CORRUPT_SUBMISSION`` (no payload, no marker) when the inbox JSON
          cannot be read or parsed.
    """
    try:
        canvas_dir = _canvas_dir(name)
    except ValueError:
        return ConsumeResult(DecisionCode.NO_SUBMISSION, None)
    inbox_path = _inbox_path(canvas_dir, decision_id)
    if not os.path.isfile(inbox_path):
        return ConsumeResult(DecisionCode.NO_SUBMISSION, None)
    # F1: read + parse the payload BEFORE the marker. On failure, do NOT create
    # the marker — the submission must remain recoverable after repair.
    try:
        with open(inbox_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return ConsumeResult(DecisionCode.CORRUPT_SUBMISSION, None)
    marker_path = os.path.join(canvas_dir, "inbox", f"{decision_id}.consumed")
    try:
        fd = os.open(marker_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return ConsumeResult(DecisionCode.ALREADY_CONSUMED, None)
    os.close(fd)
    # Best-effort consumed-status projection; merge so concurrent meta survives.
    _merge_decision(
        name,
        lambda current: current.model_copy(update={"status": "consumed"})
        if current is not None and current.decision_id == decision_id
        else current,
    )
    return ConsumeResult(DecisionCode.CONSUMED_NOW, payload)


def peek_decision(name: str, decision_id: str) -> dict:
    """Non-consuming read of a decision's state (§4.3, RT-9).

    Never flips ``consumed`` and never creates the ``.consumed`` marker.
    Returns ``{"status": <status>, "kind": <kind>}`` when a matching decision
    exists, else ``{"status": "none"}``.
    """
    meta = read_meta(name)
    if meta is None or meta.decision is None or meta.decision.decision_id != decision_id:
        return {"status": "none"}
    return {"status": meta.decision.status, "kind": meta.decision.kind}
