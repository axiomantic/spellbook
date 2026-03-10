"""Memory MCP tool implementations.

Separated from server.py for testability. server.py thin wrappers call these.
"""

import json
import uuid
from typing import Any, Dict, List, Optional

from spellbook_mcp.memory_store import (
    recall_by_query,
    recall_by_file_path,
    soft_delete_memory,
    get_memory,
    update_access,
    log_raw_event,
    get_unconsolidated_events,
    get_recently_consolidated_events,
    insert_memory,
    insert_link,
    mark_events_consolidated,
)
from spellbook_mcp.memory_consolidation import (
    build_consolidation_prompt,
    parse_llm_response,
    compute_bibliographic_coupling,
)


MEMORY_STORE_SCHEMA = {
    "type": "object",
    "required": ["memories"],
    "properties": {
        "memories": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["content"],
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The synthesized memory content. Non-empty.",
                    },
                    "memory_type": {
                        "type": "string",
                        "enum": ["fact", "rule", "antipattern", "preference", "decision"],
                        "default": "fact",
                        "description": "Category of the memory.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 20,
                        "description": "Keywords for retrieval. Max 20.",
                    },
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["file_path"],
                            "properties": {
                                "file_path": {"type": "string"},
                                "line_range": {"type": "string"},
                                "snippet": {"type": "string"},
                            },
                        },
                        "description": "Source file references.",
                    },
                },
            },
        },
    },
}


def do_memory_recall(
    db_path: str,
    query: str,
    namespace: str,
    limit: int = 10,
    file_path: Optional[str] = None,
    branch: str = "",
    repo_path: str = "",
) -> Dict[str, Any]:
    """Recall memories by query or file path.

    Args:
        db_path: Database path.
        query: FTS5 search query. Empty string returns recent+important.
        namespace: Project namespace for scoping.
        limit: Max results.
        file_path: If provided, search by cited file path instead of FTS5.
        branch: Current git branch for branch-weighted scoring.
        repo_path: Git repo root path for ancestry checks.

    Returns:
        Dict with 'memories' list and metadata.
    """
    if file_path:
        results = recall_by_file_path(
            db_path, file_path, namespace, limit,
            branch=branch, repo_path=repo_path,
        )
    else:
        results = recall_by_query(
            db_path, query, namespace, limit,
            branch=branch, repo_path=repo_path,
        )

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
    branch: str = "",
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
        branch: Git branch name (default: empty).

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
        branch=branch,
    )
    return {"status": "logged", "event_id": event_id}


def do_get_unconsolidated(
    db_path: str,
    namespace: str = "",
    limit: int = 50,
    include_consolidated: bool = False,
) -> Dict[str, Any]:
    """Get unconsolidated events for client-side synthesis.

    Args:
        db_path: Database path.
        namespace: Project namespace for scoping. Empty string means all.
        limit: Max events to return.
        include_consolidated: If true, also return recently consolidated events.

    Returns:
        Dict with events, count, consolidation_prompt, and response_schema.
    """
    ns = namespace if namespace else None
    events = get_unconsolidated_events(db_path, limit=limit, namespace=ns)

    if include_consolidated:
        consolidated = get_recently_consolidated_events(
            db_path, limit=limit, namespace=ns,
        )
        # Merge, dedup by event ID, respect total limit
        seen_ids = {e["id"] for e in events}
        for e in consolidated:
            if e["id"] not in seen_ids and len(events) < limit:
                events.append(e)
                seen_ids.add(e["id"])

    if not events:
        return {
            "events": [],
            "count": 0,
            "consolidation_prompt": "",
            "response_schema": json.dumps(MEMORY_STORE_SCHEMA),
        }

    prompt = build_consolidation_prompt(events)

    return {
        "events": events,
        "count": len(events),
        "consolidation_prompt": prompt,
        "response_schema": json.dumps(MEMORY_STORE_SCHEMA),
    }


def do_store_memories(
    db_path: str,
    memories_json: str,
    event_ids_str: str = "",
    namespace: str = "",
    branch: str = "",
) -> Dict[str, Any]:
    """Store client-synthesized memories and mark source events consolidated.

    Args:
        db_path: Database path.
        memories_json: JSON string of memory objects matching MEMORY_STORE_SCHEMA.
        event_ids_str: Comma-separated event IDs to mark consolidated.
        namespace: Project namespace.
        branch: Git branch name to associate with stored memories.

    Returns:
        Dict with status, memories_created, events_consolidated, memory_ids.
    """
    # Parse memories JSON
    try:
        data = json.loads(memories_json)
    except (json.JSONDecodeError, TypeError) as e:
        return {"status": "error", "error": f"Invalid JSON: {e}"}

    # Accept both {"memories": [...]} and bare list [...]
    if not isinstance(data, (list, dict)):
        return {"status": "error", "error": "Expected JSON object or array"}

    # Validate and parse using parse_llm_response for consistency
    if isinstance(data, list):
        validated = parse_llm_response(json.dumps({"memories": data}))
    else:
        validated = parse_llm_response(memories_json)

    if not validated:
        return {
            "status": "error",
            "error": "No valid memories found. Each memory must have non-empty 'content'.",
        }

    # Validate memory_type values
    valid_types = {"fact", "rule", "antipattern", "preference", "decision"}
    for mem in validated:
        if mem["memory_type"] not in valid_types:
            mem["memory_type"] = "fact"
        # Cap tags at 20
        if len(mem.get("tags", [])) > 20:
            mem["tags"] = mem["tags"][:20]

    # Parse event IDs
    event_ids: List[int] = []
    if event_ids_str:
        for eid_str in event_ids_str.split(","):
            eid_str = eid_str.strip()
            if eid_str:
                try:
                    event_ids.append(int(eid_str))
                except ValueError:
                    pass  # Silently ignore non-integer IDs

    # Insert memories
    created_ids: List[str] = []
    for mem in validated:
        mem_id = insert_memory(
            db_path=db_path,
            content=mem["content"],
            memory_type=mem["memory_type"],
            namespace=namespace,
            tags=mem["tags"],
            citations=mem["citations"],
            extra_meta={"source": "client_llm"},
            branch=branch,
        )
        created_ids.append(mem_id)

    # Compute bibliographic coupling for new memories
    for mem_id in created_ids:
        links = compute_bibliographic_coupling(db_path, mem_id)
        for link in links:
            insert_link(
                db_path, mem_id, link["other_id"],
                "bibliographic", link["weight"],
            )

    # Mark events consolidated (scoped to namespace to prevent cross-project marking)
    events_consolidated = 0
    if event_ids:
        batch_id = str(uuid.uuid4())
        events_consolidated = mark_events_consolidated(
            db_path, event_ids, batch_id, namespace=namespace or None,
        )

    return {
        "status": "success",
        "memories_created": len(created_ids),
        "events_consolidated": events_consolidated,
        "memory_ids": created_ids,
    }
