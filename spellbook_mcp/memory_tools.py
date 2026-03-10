"""Memory MCP tool implementations.

Separated from server.py for testability. server.py thin wrappers call these.
"""

import glob as glob_module
import json
import os
import uuid
from typing import Any, Dict, List, Optional

from spellbook_mcp.memory_store import (
    recall_by_query,
    recall_by_file_path,
    soft_delete_memory,
    get_memory,
    update_access,
    log_raw_event,
    log_audit,
    get_unconsolidated_events,
    get_recently_consolidated_events,
    insert_memory,
    insert_link,
    mark_events_consolidated,
    search_memories_by_topic,
    delete_raw_events_by_topic,
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
) -> Dict[str, Any]:
    """Store client-synthesized memories and mark source events consolidated.

    Args:
        db_path: Database path.
        memories_json: JSON string of memory objects matching MEMORY_STORE_SCHEMA.
        event_ids_str: Comma-separated event IDs to mark consolidated.
        namespace: Project namespace.

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


def _grep_files_for_topic(
    file_paths: List[str],
    query: str,
) -> List[Dict[str, Any]]:
    """Search a list of files for lines matching query (case-insensitive).

    Returns list of dicts with path, matched_lines, total_lines, match_ratio.
    """
    results: List[Dict[str, Any]] = []
    query_lower = query.lower()
    for fpath in file_paths:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        matched = [
            line.strip() for line in lines if query_lower in line.lower()
        ]
        if matched:
            total = len(lines)
            results.append({
                "path": fpath,
                "matched_lines": matched[:10],  # Cap preview at 10 lines
                "match_count": len(matched),
                "total_lines": total,
                "match_ratio": len(matched) / total if total > 0 else 0.0,
            })
    return results


def do_memory_purge_topic(
    db_path: str,
    topic: str,
    namespace: str,
    config_dir: str = "",
    claude_projects_dir: str = "",
    understanding_dir: str = "",
    auto_memory_dir: str = "",
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Sweep all 4 memory storage layers for topic matches.

    Searches memories (SQLite FTS5), raw_events (SQLite LIKE), understanding
    docs (markdown files), and auto-memory files (Claude project memory).

    Args:
        db_path: Database path.
        topic: Search term/topic to purge.
        namespace: Project namespace (encoded path).
        config_dir: Spellbook config dir (~/.local/spellbook). Used to derive
            understanding_dir if understanding_dir is not provided.
        claude_projects_dir: Claude projects dir (~/.claude/projects). Used to
            derive auto_memory_dir if auto_memory_dir is not provided.
        understanding_dir: Direct path to understanding docs directory. Overrides
            config_dir-based resolution.
        auto_memory_dir: Direct path to auto-memory directory. Overrides
            claude_projects_dir-based resolution.
        dry_run: If True, return findings without deleting. If False, delete.

    Returns:
        Dict with matches across all layers, total_found, dry_run flag,
        and deleted counts when dry_run=False.
    """
    if not topic.strip():
        return {"status": "error", "error": "Query cannot be empty"}

    deleted: Dict[str, int] = {
        "memories": 0,
        "raw_events": 0,
        "understanding_docs": 0,
        "auto_memory_files": 0,
    }

    # Layer 1: SQLite memories table (FTS5)
    matching_memories = search_memories_by_topic(
        db_path=db_path, query=topic, namespace=namespace,
    )
    if not dry_run:
        for mem in matching_memories:
            soft_delete_memory(db_path=db_path, memory_id=mem["id"])
        deleted["memories"] = len(matching_memories)

    # Layer 2: SQLite raw_events table
    raw_result = delete_raw_events_by_topic(
        db_path=db_path, query=topic, namespace=namespace, dry_run=dry_run,
    )
    if not dry_run:
        deleted["raw_events"] = raw_result.get("deleted", 0)

    # Layer 3: Understanding docs
    understanding_matches: List[Dict[str, Any]] = []
    # Resolve understanding directory: explicit param > config_dir-based
    resolved_understanding_dir = understanding_dir
    if not resolved_understanding_dir and config_dir:
        resolved_understanding_dir = os.path.join(
            config_dir, "docs", namespace, "understanding",
        )
    if resolved_understanding_dir and os.path.isdir(resolved_understanding_dir):
        md_files = glob_module.glob(
            os.path.join(resolved_understanding_dir, "*.md"),
        )
        understanding_matches = _grep_files_for_topic(
            file_paths=md_files, query=topic,
        )
        if not dry_run:
            for match in understanding_matches:
                try:
                    os.remove(match["path"])
                    deleted["understanding_docs"] += 1
                    log_audit(
                        db_path,
                        "purge_topic_understanding",
                        details={
                            "path": match["path"],
                            "topic": topic,
                        },
                    )
                except OSError:
                    pass  # Permission error or already removed

    # Layer 4: Auto-memory files
    auto_memory_matches: List[Dict[str, Any]] = []
    auto_memory_deleted: List[Dict[str, Any]] = []
    auto_memory_flagged: List[Dict[str, Any]] = []

    # Resolve auto-memory directory: explicit param > claude_projects_dir-based
    if auto_memory_dir and os.path.isdir(auto_memory_dir):
        memory_files = glob_module.glob(
            os.path.join(auto_memory_dir, "*.md"),
        )
        auto_memory_matches = _grep_files_for_topic(
            file_paths=memory_files, query=topic,
        )
    elif claude_projects_dir and os.path.isdir(claude_projects_dir):
        memory_files = glob_module.glob(
            os.path.join(claude_projects_dir, "*", "memory", "*.md"),
        )
        auto_memory_matches = _grep_files_for_topic(
            file_paths=memory_files, query=topic,
        )

    if not dry_run:
        for match in auto_memory_matches:
            # Only delete files where >50% of lines match the topic
            if match["match_ratio"] > 0.5:
                try:
                    os.remove(match["path"])
                    deleted["auto_memory_files"] += 1
                    auto_memory_deleted.append({
                        "path": match["path"],
                        "match_ratio": round(match["match_ratio"], 2),
                    })
                    log_audit(
                        db_path,
                        "purge_topic_auto_memory",
                        details={
                            "path": match["path"],
                            "topic": topic,
                            "match_ratio": match["match_ratio"],
                        },
                    )
                except OSError:
                    pass  # Permission error or already removed
            else:
                # Files with <=50% match are flagged for manual review
                auto_memory_flagged.append({
                    "path": match["path"],
                    "matched_lines": match["matched_lines"],
                    "match_ratio": round(match["match_ratio"], 2),
                })

    total_found = (
        len(matching_memories)
        + raw_result["matched"]
        + len(understanding_matches)
        + len(auto_memory_matches)
    )

    result: Dict[str, Any] = {
        "memories": matching_memories,
        "raw_events": raw_result["events"],
        "understanding_docs": [
            {"path": m["path"], "matched_lines": m["matched_lines"]}
            for m in understanding_matches
        ],
        "auto_memory": {
            "files": [
                {
                    "path": m["path"],
                    "matched_lines": m["matched_lines"],
                    "match_ratio": round(m["match_ratio"], 2),
                    "would_auto_delete": m["match_ratio"] > 0.5,
                }
                for m in auto_memory_matches
            ],
            "deleted": auto_memory_deleted,
            "flagged_for_review": auto_memory_flagged,
        },
        "total_found": total_found,
        "dry_run": dry_run,
        "topic": topic,
        "namespace": namespace,
    }

    if not dry_run:
        result["deleted"] = deleted
        log_audit(
            db_path,
            "purge_topic",
            details={
                "topic": topic,
                "namespace": namespace,
                "deleted": deleted,
                "total_found": total_found,
            },
        )

    return result
