"""Memory MCP tool implementations.

Separated from server.py for testability. server.py thin wrappers call these.
"""

from typing import Any, Dict, Optional

from spellbook_mcp.memory_store import (
    recall_by_query,
    recall_by_file_path,
    soft_delete_memory,
    get_memory,
    update_access,
    log_raw_event,
)


def do_memory_recall(
    db_path: str,
    query: str,
    namespace: str,
    limit: int = 10,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Recall memories by query or file path.

    Args:
        db_path: Database path.
        query: FTS5 search query. Empty string returns recent+important.
        namespace: Project namespace for scoping.
        limit: Max results.
        file_path: If provided, search by cited file path instead of FTS5.

    Returns:
        Dict with 'memories' list and metadata.
    """
    if file_path:
        results = recall_by_file_path(db_path, file_path, namespace, limit)
    else:
        results = recall_by_query(db_path, query, namespace, limit)

    # Update access for returned memories
    for mem in results:
        update_access(db_path, mem["id"])

    return {
        "memories": results,
        "count": len(results),
        "query": query,
        "namespace": namespace,
    }


def do_memory_forget(
    db_path: str,
    memory_id: str,
) -> Dict[str, Any]:
    """Soft-delete a memory by ID.

    Args:
        db_path: Database path.
        memory_id: The memory ID to forget.

    Returns:
        Dict with status ('deleted' or 'not_found') and memory_id.
    """
    mem = get_memory(db_path, memory_id)
    if mem is None:
        return {"status": "not_found", "memory_id": memory_id}

    soft_delete_memory(db_path, memory_id)
    return {
        "status": "deleted",
        "memory_id": memory_id,
        "message": f"Memory soft-deleted. Will be purged after 30 days. "
                   f"Content preview: {mem['content'][:80]}...",
    }


def do_log_event(
    db_path: str,
    session_id: str,
    project: str,
    tool_name: str,
    subject: str,
    summary: str,
    tags: str = "",
    event_type: str = "tool_use",
) -> Dict[str, Any]:
    """Log a raw observation event (called by hooks via REST endpoint).

    Args:
        db_path: Database path.
        session_id: Session identifier.
        project: Project namespace (project-encoded path).
        tool_name: Name of the tool used.
        subject: Primary subject (usually file path).
        summary: One-line summary of what happened.
        tags: Comma-separated keywords.
        event_type: Event type (default: tool_use).

    Returns:
        Dict with status and event_id.
    """
    event_id = log_raw_event(
        db_path=db_path,
        session_id=session_id,
        project=project,
        event_type=event_type,
        tool_name=tool_name,
        subject=subject,
        summary=summary,
        tags=tags,
    )
    return {"status": "logged", "event_id": event_id}
