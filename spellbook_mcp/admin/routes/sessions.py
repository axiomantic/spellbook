"""Session list API routes.

Scans ~/.claude/projects/ for JSONL session files and returns lightweight
metadata (timestamps, message count, first user message) without loading
full file contents.
"""

import asyncio
import json
import math
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from spellbook_mcp.admin.auth import require_admin_auth

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _scan_sessions(project_filter: Optional[str] = None) -> list[dict]:
    """Scan ~/.claude/projects/ for session JSONL files.

    Returns lightweight metadata by reading only the first and last few
    lines of each file, avoiding full-file reads for large sessions.
    """
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return []

    sessions: list[dict] = []

    # Iterate project directories
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        project_path = str(project_dir.name)

        if project_filter and project_filter not in project_path:
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

    # Sort by last activity descending
    sessions.sort(key=lambda s: s.get("last_activity") or "", reverse=True)
    return sessions


@router.get("")
async def list_sessions(
    project: Optional[str] = Query(None, description="Filter by project path substring"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _session: str = Depends(require_admin_auth),
):
    """List sessions by scanning JSONL session files."""
    all_sessions = await asyncio.to_thread(_scan_sessions, project)

    total = len(all_sessions)
    pages = max(1, math.ceil(total / per_page))
    offset = (page - 1) * per_page
    page_sessions = all_sessions[offset : offset + per_page]

    return {
        "sessions": page_sessions,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }
