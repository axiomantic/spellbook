"""Filesystem store for canvases.

Per design §3, a canvas is a named directory tree under
``~/.local/spellbook/canvas/<name>/`` with this layout::

    <name>/
      pages/
        index.md      # agent-written markdown; MVP = single page
      inbox/          # reserved for v2; empty in MVP
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
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-_]{0,63}$")


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
    schema_version: int = 1


def _resolve_canvas_root() -> str:
    """Return ``~/.local/spellbook/canvas/``.

    Tests monkeypatch this to redirect to a tmp directory. Mirrors
    ``spellbook.admin.routes.memory._resolve_memory_root``.

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
        import logging

        logging.getLogger(__name__).warning(
            "SPELLBOOK_CANVAS_MAX_PAGE_BYTES=%r is not an integer; "
            "falling back to %d bytes (default).",
            raw,
            default,
        )
        return default
    if value <= 0:
        import logging

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
            the canvas root (path-traversal guard mirroring
            ``spellbook/admin/routes/memory.py``).
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
