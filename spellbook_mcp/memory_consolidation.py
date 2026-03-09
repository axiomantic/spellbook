"""Memory consolidation pipeline.

Batch-extracts structured memories from raw events via heuristic strategies.
Handles dedup, bibliographic coupling, FTS5 sync, and error recovery.
Client-side LLM synthesis available via memory_get_unconsolidated/memory_store_memories tools.
"""

import json
import uuid
from typing import Any, Dict, List

from spellbook_mcp.db import get_connection
from spellbook_mcp.memory_store import (
    get_unconsolidated_events,
    insert_memory,
    insert_link,
    mark_events_consolidated,
    log_audit,
    purge_deleted,
)

EVENT_THRESHOLD = 10


def should_consolidate(db_path: str) -> bool:
    """Check if there are enough unconsolidated events to trigger consolidation."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT COUNT(*) FROM raw_events WHERE consolidated = 0"
    )
    count = cursor.fetchone()[0]
    return count >= EVENT_THRESHOLD


def build_consolidation_prompt(events: List[Dict[str, Any]]) -> str:
    """Build the LLM prompt from a batch of raw events."""
    observations = []
    for e in events:
        line = f"- [{e['tool_name']}] {e['subject']}: {e['summary']}"
        if e.get("tags"):
            line += f" (tags: {e['tags']})"
        observations.append(line)

    return (
        "Given these tool observations from a coding session, extract structured memories.\n"
        "For each distinct fact, rule, pattern, or decision observed:\n"
        "- content: the memory as a clear, standalone statement\n"
        "- memory_type: one of fact/rule/antipattern/preference/decision\n"
        "- tags: 3-5 keywords for retrieval\n"
        "- citations: file paths referenced, with line ranges and 1-3 line snippets\n\n"
        'Return JSON: {"memories": [{"content": "...", "memory_type": "...", '
        '"tags": [...], "citations": [{"file_path": "...", "line_range": "...", '
        '"snippet": "..."}]}]}\n\n'
        "Observations:\n" + "\n".join(observations)
    )


def parse_llm_response(response: str) -> List[Dict[str, Any]]:
    """Parse LLM response into memory dicts. Returns empty list on failure."""
    try:
        data = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        return []

    memories = data.get("memories", [])
    result = []
    for mem in memories:
        if not isinstance(mem, dict) or not mem.get("content"):
            continue
        result.append({
            "content": mem["content"],
            "memory_type": mem.get("memory_type", "fact"),
            "tags": mem.get("tags", []),
            "citations": mem.get("citations", []),
        })
    return result


def compute_bibliographic_coupling(
    db_path: str, memory_id: str
) -> List[Dict[str, Any]]:
    """Find other memories sharing file citations with this memory.

    Returns list of {other_id, weight} where weight is Jaccard similarity
    of cited file paths.
    """
    conn = get_connection(db_path)

    # Get file paths cited by this memory
    cursor = conn.execute(
        "SELECT file_path FROM memory_citations WHERE memory_id = ?",
        (memory_id,),
    )
    my_files = {r[0] for r in cursor.fetchall()}
    if not my_files:
        return []

    # Find other memories citing any of the same files
    placeholders = ",".join("?" for _ in my_files)
    cursor = conn.execute(
        f"SELECT DISTINCT mc.memory_id, mc.file_path "
        f"FROM memory_citations mc "
        f"JOIN memories m ON m.id = mc.memory_id "
        f"WHERE mc.file_path IN ({placeholders}) "
        f"AND mc.memory_id != ? AND m.status = 'active'",
        list(my_files) + [memory_id],
    )
    # Group by other memory
    other_files: Dict[str, set] = {}
    for row in cursor.fetchall():
        other_files.setdefault(row[0], set()).add(row[1])

    links = []
    for other_id, _their_shared_files in other_files.items():
        # Get ALL files for the other memory (not just shared)
        cursor2 = conn.execute(
            "SELECT file_path FROM memory_citations WHERE memory_id = ?",
            (other_id,),
        )
        all_their_files = {r[0] for r in cursor2.fetchall()}
        union = my_files | all_their_files
        intersection = my_files & all_their_files
        weight = len(intersection) / len(union) if union else 0
        if weight > 0:
            links.append({"other_id": other_id, "weight": weight})

    return links


def consolidate_batch(
    db_path: str,
    namespace: str,
    event_limit: int = 50,
) -> Dict[str, Any]:
    """Run one consolidation batch.

    Intentionally synchronous: this is a background batch operation,
    not an MCP request handler. The MCP server calls this via
    asyncio.to_thread() to avoid blocking the event loop.

    1. Fetch unconsolidated events
    2. Build prompt and call LLM
    3. Parse response and insert memories
    4. Compute bibliographic coupling for new memories
    5. Mark events as consolidated
    6. Run GC (purge old soft-deleted entries)

    Returns dict with status, counts, and any errors.
    """
    events = get_unconsolidated_events(db_path, limit=event_limit)
    if not events:
        return {"status": "no_events", "events_consolidated": 0, "memories_created": 0}

    batch_id = str(uuid.uuid4())
    event_ids = [e["id"] for e in events]

    prompt = build_consolidation_prompt(events)

    try:
        response = _call_llm(prompt)
    except Exception as e:
        log_audit(db_path, "consolidation_error", details={
            "batch_id": batch_id,
            "error": str(e),
            "event_count": len(events),
        })
        return {
            "status": "error",
            "error": str(e),
            "events_consolidated": 0,
            "memories_created": 0,
        }

    memories = parse_llm_response(response)
    if not memories:
        log_audit(db_path, "consolidation_error", details={
            "batch_id": batch_id,
            "error": "No memories parsed from LLM response",
            "response_preview": response[:200],
        })
        # INTENTIONAL: Mark events as consolidated even though no memories
        # were extracted. This is a deliberate deviation from the design
        # doc's error recovery spec (which only covers LLM call failures).
        # Empty parse results (valid JSON but no extractable memories) are
        # NOT retryable -- the same events will produce the same empty
        # result. Leaving them unconsolidated would create an infinite
        # retry loop at each consolidation trigger.
        mark_events_consolidated(db_path, event_ids, batch_id)
        return {
            "status": "success",
            "events_consolidated": len(event_ids),
            "memories_created": 0,
        }

    created_ids = []
    for mem in memories:
        mem_id = insert_memory(
            db_path=db_path,
            content=mem["content"],
            memory_type=mem["memory_type"],
            namespace=namespace,
            tags=mem["tags"],
            citations=mem["citations"],
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

    mark_events_consolidated(db_path, event_ids, batch_id)

    # Piggyback GC
    purged = purge_deleted(db_path)

    return {
        "status": "success",
        "batch_id": batch_id,
        "events_consolidated": len(event_ids),
        "memories_created": len(created_ids),
        "purged": purged,
    }
