"""Memory browser routes for the admin interface (file-based memory).

Reads markdown memory files with YAML frontmatter from the configured
memory root (default: ``~/.local/spellbook/memories``). No SQLAlchemy,
no ORM, no consolidation trigger. Writes are not exposed through the
admin UI; use the MCP tools for mutation.

Endpoints:
- ``GET /api/memories`` -- offset-paginated list, sorted by ``created`` desc
- ``GET /api/memories/search?q=...`` -- delegate to QMD search
- ``GET /api/memories/{path:path}`` -- single memory by relative path
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from spellbook.admin.auth import require_admin_auth
from spellbook.memory import memory_index
from spellbook.memory.filestore import read_memory
from spellbook.memory.models import Citation, MemoryFile, MemoryFrontmatter
from spellbook.memory.search_qmd import search_memories
from spellbook.memory.utils import iter_memory_files

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memory"])


# ---------------------------------------------------------------------------
# Memory root resolution
# ---------------------------------------------------------------------------


def _resolve_memory_root() -> str:
    """Return the absolute path to the memory files root.

    Tests monkeypatch this function to point at a tmp directory.
    """
    return os.path.expanduser("~/.local/spellbook/memories")


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_citation(c: Citation) -> dict[str, Any]:
    return {
        "file": c.file,
        "symbol": c.symbol,
        "symbol_type": c.symbol_type,
    }


def _serialize_frontmatter(fm: MemoryFrontmatter) -> dict[str, Any]:
    return {
        "type": fm.type,
        "kind": fm.kind,
        "tags": list(fm.tags),
        "citations": [_serialize_citation(c) for c in fm.citations],
        "confidence": fm.confidence,
        "created": fm.created.isoformat() if isinstance(fm.created, date) else fm.created,
        "last_verified": (
            fm.last_verified.isoformat()
            if isinstance(fm.last_verified, date)
            else fm.last_verified
        ),
    }


def _serialize_memory(rel_id: str, mf: MemoryFile) -> dict[str, Any]:
    payload = {"id": rel_id, **_serialize_frontmatter(mf.frontmatter)}
    payload["body"] = mf.content.strip()
    return payload


def _error_response(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message}}, status_code=status
    )


def _resolve_within_root(root: str, rel_path: str) -> Optional[str]:
    """Return the absolute path if ``rel_path`` resolves inside ``root``.

    Returns ``None`` if the path escapes the root or does not exist as a file.
    """
    real_root = os.path.realpath(root)
    abs_candidate = os.path.realpath(os.path.join(real_root, rel_path))
    if not (abs_candidate == real_root or abs_candidate.startswith(real_root + os.sep)):
        return None
    if not os.path.isfile(abs_candidate):
        return None
    return abs_candidate


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@dataclass
class _LoadedMemory:
    rel_id: str
    mf: MemoryFile


def _load_all_memories(root: str) -> list[_LoadedMemory]:
    """Walk ``root`` and return all parseable memory files."""
    real_root = os.path.realpath(root)
    loaded: list[_LoadedMemory] = []
    if not os.path.isdir(real_root):
        return loaded
    for abs_path in iter_memory_files(real_root):
        try:
            mf = read_memory(abs_path)
        except (ValueError, OSError) as e:
            logger.debug("Skipping unparseable memory %s: %s", abs_path, e)
            continue
        rel_id = os.path.relpath(abs_path, real_root).replace(os.sep, "/")
        loaded.append(_LoadedMemory(rel_id=rel_id, mf=mf))
    return loaded


def _sort_by_created_desc(mems: list[_LoadedMemory]) -> list[_LoadedMemory]:
    """Sort by frontmatter.created desc, placing missing dates last."""
    min_date = date.min

    def _key(lm: _LoadedMemory) -> date:
        created = lm.mf.frontmatter.created
        return created if isinstance(created, date) else min_date

    return sorted(mems, key=_key, reverse=True)


@router.get("/search")
async def search_memories_endpoint(
    q: str = Query(..., description="Search query (required)"),
    limit: int = Query(10, ge=1, le=100),
    _session: str = Depends(require_admin_auth),
):
    """Search memories via QMD and return ranked results."""
    root = _resolve_memory_root()
    results = await asyncio.to_thread(
        search_memories,
        query=q,
        memory_dirs=[root],
        limit=limit,
    )

    items: list[dict[str, Any]] = []
    real_root = os.path.realpath(root)
    for r in results:
        abs_path = os.path.realpath(r.memory.path)
        # Compute a stable id relative to the memory root when possible.
        if abs_path == real_root or abs_path.startswith(real_root + os.sep):
            rel_id = os.path.relpath(abs_path, real_root).replace(os.sep, "/")
        else:
            rel_id = r.memory.path
        payload = _serialize_memory(rel_id, r.memory)
        payload["score"] = r.score
        payload["match_context"] = r.match_context
        items.append(payload)

    return {"query": q, "total": len(items), "items": items}


@router.get("")
async def list_memories(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    _session: str = Depends(require_admin_auth),
):
    """List memories sorted by ``created`` descending, offset-paginated.

    Backed by the :mod:`spellbook.memory.memory_index` sidecar. Only fields
    stored in the index are surfaced: ``id`` (rel path), ``type``, ``kind``,
    ``created``, ``content_hash``. Hit the detail endpoint for full
    frontmatter and body.
    """
    root = _resolve_memory_root()

    def _collect() -> tuple[list[dict[str, Any]], int]:
        # Self-heal after external modification (throttled internally).
        try:
            memory_index.rebuild_if_stale(root)
        except OSError as e:
            logger.warning("memory-index rebuild_if_stale failed: %s", e)
        entries = memory_index.list_entries(root)
        total = len(entries)
        window = entries[offset : offset + limit]
        items = [
            {
                "id": e["rel_path"],
                "type": e.get("type"),
                "kind": e.get("kind"),
                "created": e.get("created"),
                "content_hash": e.get("content_hash"),
            }
            for e in window
        ]
        return items, total

    items, total = await asyncio.to_thread(_collect)
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{path:path}")
async def get_memory(
    path: str,
    _session: str = Depends(require_admin_auth),
):
    """Return a single memory identified by its path relative to memory root."""
    root = _resolve_memory_root()
    abs_path = _resolve_within_root(root, path)
    if abs_path is None:
        return _error_response(
            "MEMORY_NOT_FOUND", f"Memory '{path}' not found", 404
        )
    try:
        mf = await asyncio.to_thread(read_memory, abs_path)
    except (ValueError, OSError) as e:
        logger.warning("Failed to parse memory %s: %s", abs_path, e)
        return _error_response(
            "MEMORY_NOT_FOUND", f"Memory '{path}' not found", 404
        )
    rel_id = os.path.relpath(abs_path, os.path.realpath(root)).replace(os.sep, "/")
    return _serialize_memory(rel_id, mf)
