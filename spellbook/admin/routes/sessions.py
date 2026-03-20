"""Session list API routes.

Scans ~/.claude/projects/ for JSONL session files and returns lightweight
metadata (timestamps, message count, first user message) without loading
full file contents.
"""

import asyncio
import json
import math
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.routes.list_helpers import build_list_response, validate_sort_order

router = APIRouter(prefix="/sessions", tags=["sessions"])


_SORT_WHITELIST = {"last_activity", "created_at", "message_count", "size_bytes"}


def _scan_sessions(
    project_filter: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "last_activity",
    order: str = "desc",
) -> list[dict]:
    """Scan ~/.claude/projects/ for session JSONL files.

    Returns lightweight metadata by reading only the first and last few
    lines of each file, avoiding full-file reads for large sessions.
    """
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return []

    sessions: list[dict] = []

    # Parse comma-separated project filters (OR logic)
    project_filters: list[str] = []
    if project_filter:
        project_filters = [p.strip() for p in project_filter.split(",") if p.strip()]

    # Iterate project directories
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        project_path = str(project_dir.name)

        if project_filters and not any(pf in project_path for pf in project_filters):
            continue

        # Find JSONL files (top-level only, skip subagents/)
        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                stat = jsonl_file.stat()
                if stat.st_size == 0:
                    continue

                session_id = jsonl_file.stem
                first_user_msg = None
                first_timestamp = None
                last_timestamp = None
                message_count = 0
                slug = None
                custom_title = None

                with open(jsonl_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        message_count += 1

                        if entry.get("slug") and not slug:
                            slug = entry["slug"]

                        ts = entry.get("timestamp")
                        if ts:
                            if first_timestamp is None:
                                first_timestamp = ts
                            last_timestamp = ts

                        if entry.get("customTitle"):
                            custom_title = entry["customTitle"]

                        if (
                            first_user_msg is None
                            and entry.get("type") == "user"
                        ):
                            content = entry.get("message", {}).get("content", "")
                            if isinstance(content, str):
                                first_user_msg = content[:200]
                            elif isinstance(content, list):
                                # Extract text from content blocks
                                for block in content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        first_user_msg = block.get("text", "")[:200]
                                        break

                sessions.append({
                    "id": session_id,
                    "project": project_path,
                    "slug": slug,
                    "custom_title": custom_title,
                    "first_user_message": first_user_msg,
                    "created_at": first_timestamp,
                    "last_activity": last_timestamp,
                    "message_count": message_count,
                    "size_bytes": stat.st_size,
                })
            except (OSError, PermissionError):
                continue

    # Apply free-text search filter (case-insensitive substring match)
    if search:
        search_lower = search.lower()
        sessions = [
            s for s in sessions
            if search_lower in (s.get("first_user_message") or "").lower()
            or search_lower in (s.get("slug") or "").lower()
            or search_lower in (s.get("custom_title") or "").lower()
        ]

    # Validate and apply sort
    sort_field = sort if sort in _SORT_WHITELIST else "last_activity"
    sort_order = validate_sort_order(order)
    reverse = sort_order == "desc"

    # Use appropriate default for missing values based on field type
    if sort_field in ("message_count", "size_bytes"):
        sessions.sort(key=lambda s: s.get(sort_field) or 0, reverse=reverse)
    else:
        sessions.sort(key=lambda s: s.get(sort_field) or "", reverse=reverse)

    return sessions


@router.get("")
async def list_sessions(
    project: Optional[str] = Query(None, description="Filter by project path substring (comma-separated for multiple)"),
    search: Optional[str] = Query(None, description="Free-text search across title, slug, and first message"),
    sort: str = Query("last_activity", description="Sort field"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _session: str = Depends(require_admin_auth),
):
    """List sessions by scanning JSONL session files."""
    all_sessions = await asyncio.to_thread(
        _scan_sessions, project, search, sort, order
    )

    total = len(all_sessions)
    offset = (page - 1) * per_page
    page_sessions = all_sessions[offset : offset + per_page]

    return build_list_response(page_sessions, total, page, per_page)


def _validate_path_segment(segment: str) -> bool:
    """Reject path traversal attempts in URL parameters."""
    return (
        ".." not in segment
        and "/" not in segment
        and "\\" not in segment
        and "\x00" not in segment
    )


def _decode_project_path(project: str) -> str:
    """Reverse project-encoding: dashes to slashes, prepend /.

    NOTE: This is lossy -- paths containing literal dashes will be
    incorrectly decoded (e.g. "my-project" becomes "/my/project").
    This is a pre-existing limitation matching the frontend's
    decodeProjectPath behavior.
    """
    return "/" + project.replace("-", "/")


def _normalize_message(entry: dict, line_number: int) -> dict:
    """Extract a consistent shape from heterogeneous JSONL entry types."""
    msg_type = entry.get("type", "unknown")
    timestamp = entry.get("timestamp")

    content = ""
    if msg_type in ("user", "assistant"):
        raw_content = entry.get("message", {}).get("content", "")
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            content = "\n".join(
                block.get("text", "")
                for block in raw_content
                if isinstance(block, dict) and block.get("type") == "text"
            )
    elif msg_type == "custom-title":
        content = entry.get("customTitle", "")
    elif msg_type == "progress":
        # NOTE: progress.message is a plain string, unlike user/assistant/system
        # where .message.content is string-or-list-of-blocks.
        content = entry.get("message", "")
    elif msg_type == "system":
        raw_content = entry.get("message", {}).get("content", "")
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            content = "\n".join(
                block.get("text", "")
                for block in raw_content
                if isinstance(block, dict) and block.get("type") == "text"
            )
    else:
        content = json.dumps(entry, default=str)[:500]

    is_compact = (
        msg_type == "user"
        and entry.get("message", {}).get("isCompactSummary", False)
    )

    return {
        "line_number": line_number,
        "type": msg_type,
        "timestamp": timestamp,
        "content": content,
        "is_compact_summary": is_compact,
        "raw": entry,
    }


def _read_session_metadata(file_path: Path) -> dict:
    """Extract metadata from a single JSONL session file.

    Reads the file to extract timestamps, message count, slug,
    custom title, and first user message (untruncated).
    """
    first_user_msg = None
    first_timestamp = None
    last_timestamp = None
    message_count = 0
    slug = None
    custom_title = None

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            message_count += 1

            if entry.get("slug") and not slug:
                slug = entry["slug"]

            ts = entry.get("timestamp")
            if ts:
                if first_timestamp is None:
                    first_timestamp = ts
                last_timestamp = ts

            if entry.get("customTitle"):
                custom_title = entry["customTitle"]

            if (
                first_user_msg is None
                and entry.get("type") == "user"
            ):
                raw_content = entry.get("message", {}).get("content", "")
                if isinstance(raw_content, str):
                    first_user_msg = raw_content
                elif isinstance(raw_content, list):
                    for block in raw_content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            first_user_msg = block.get("text", "")
                            break

    stat = file_path.stat()
    return {
        "id": file_path.stem,
        "project": file_path.parent.name,
        "project_decoded": _decode_project_path(file_path.parent.name),
        "slug": slug,
        "custom_title": custom_title,
        "created_at": first_timestamp,
        "last_activity": last_timestamp,
        "message_count": message_count,
        "size_bytes": stat.st_size,
        "first_user_message": first_user_msg,
    }


def _read_messages_page(file_path: Path, page: int, per_page: int) -> dict:
    """Read a page of messages using sequential enumeration."""
    offset = (page - 1) * per_page
    messages: list[dict] = []
    total_lines = 0

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1

            # Past the target page -- just count remaining lines
            if len(messages) >= per_page:
                continue

            # Before the target page -- skip
            if total_lines <= offset:
                continue

            # Within the target page -- parse and collect
            try:
                entry = json.loads(line)
                messages.append(_normalize_message(entry, total_lines))
            except json.JSONDecodeError:
                messages.append({
                    "line_number": total_lines,
                    "type": "error",
                    "timestamp": None,
                    "content": "[Malformed JSONL line]",
                    "is_compact_summary": False,
                    "raw": None,
                })

    pages = max(1, math.ceil(total_lines / per_page))
    return {
        "messages": messages,
        "total_lines": total_lines,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.get("/{project}/{session_id}")
async def get_session_detail(
    project: str,
    session_id: str,
    _session: str = Depends(require_admin_auth),
):
    """Get full metadata for a single session."""
    if not _validate_path_segment(project) or not _validate_path_segment(session_id):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "BAD_REQUEST", "message": "Invalid path segment"}},
        )

    base_dir = (Path.home() / ".claude" / "projects").resolve()
    project_dir = base_dir / project
    if not project_dir.exists() or not project_dir.is_dir():
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Project not found"}},
        )

    file_path = (project_dir / f"{session_id}.jsonl").resolve()
    if not file_path.is_relative_to(base_dir):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "BAD_REQUEST", "message": "Invalid path"}},
        )

    if not file_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Session not found"}},
        )

    result = await asyncio.to_thread(_read_session_metadata, file_path)
    return JSONResponse(result)


@router.get("/{project}/{session_id}/messages")
async def get_session_messages(
    project: str,
    session_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=200),
    _session: str = Depends(require_admin_auth),
):
    """Get paginated messages from a session JSONL file."""
    if not _validate_path_segment(project) or not _validate_path_segment(session_id):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "BAD_REQUEST", "message": "Invalid path segment"}},
        )

    base_dir = (Path.home() / ".claude" / "projects").resolve()
    project_dir = base_dir / project
    if not project_dir.exists() or not project_dir.is_dir():
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Project not found"}},
        )

    file_path = (project_dir / f"{session_id}.jsonl").resolve()
    if not file_path.is_relative_to(base_dir):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "BAD_REQUEST", "message": "Invalid path"}},
        )

    if not file_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Session not found"}},
        )

    result = await asyncio.to_thread(_read_messages_page, file_path, page, per_page)
    return JSONResponse(result)
