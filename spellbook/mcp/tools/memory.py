"""MCP tools for memory operations."""

import asyncio

from fastmcp import Context

from spellbook.mcp.server import mcp
from spellbook_mcp.branch_ancestry import get_current_branch
from spellbook_mcp.db import get_db_path
from spellbook_mcp.injection import inject_recovery_context
from spellbook_mcp.memory_consolidation import consolidate_batch, should_consolidate
from spellbook_mcp.memory_tools import (
    do_get_unconsolidated,
    do_memory_forget,
    do_memory_recall,
    do_store_memories,
)
from spellbook_mcp.path_utils import (
    encode_cwd,
    get_project_path_from_context,
    resolve_repo_root,
)


@mcp.tool()
@inject_recovery_context
async def memory_recall(
    ctx: Context,
    query: str = "",
    namespace: str = "",
    limit: int = 10,
    file_path: str = "",
) -> dict:
    """Search and retrieve project memories.

    Query memories by keyword search or file path. Empty query returns
    the most recent and important memories.

    Args:
        query: FTS5 search query (keywords). Empty = recent+important.
        namespace: Project namespace. Auto-detected if empty.
        limit: Maximum memories to return (default 10).
        file_path: If provided, find memories citing this file path.

    Returns:
        Dict with 'memories' list, count, query, and namespace.
    """
    db_path = str(get_db_path())
    project_path = await get_project_path_from_context(ctx)
    if not namespace:
        if project_path:
            namespace = encode_cwd(project_path)
        else:
            return {"error": "Could not determine project namespace", "memories": []}

    # Detect current branch for branch-weighted scoring
    repo_path = resolve_repo_root(project_path) if project_path else ""
    branch = get_current_branch(repo_path) if repo_path else ""

    return do_memory_recall(
        db_path=db_path,
        query=query,
        namespace=namespace,
        limit=limit,
        file_path=file_path if file_path else None,
        branch=branch,
        repo_path=repo_path,
    )


@mcp.tool()
@inject_recovery_context
async def memory_forget(ctx: Context, memory_id: str) -> dict:
    """Soft-delete a memory by ID. Memory is recoverable for 30 days.

    Args:
        memory_id: The UUID of the memory to forget.

    Returns:
        Dict with status ('deleted' or 'not_found').
    """
    db_path = str(get_db_path())
    result = do_memory_forget(db_path=db_path, memory_id=memory_id)
    try:
        from spellbook_mcp.admin.events import Event, Subsystem, event_bus

        await event_bus.publish(
            Event(
                subsystem=Subsystem.MEMORY,
                event_type="memory.deleted",
                data={"memory_id": memory_id},
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
async def memory_consolidate(ctx: Context, namespace: str = "") -> dict:
    """Trigger memory consolidation: extract structured memories from raw events.

    Checks if enough unconsolidated events have accumulated, then runs
    the consolidation pipeline (heuristic strategies, dedup, bibliographic coupling).

    Args:
        namespace: Project namespace. Auto-detected if empty.

    Returns:
        Dict with status, events_consolidated, and memories_created.
    """
    db_path = str(get_db_path())
    if not namespace:
        project_path = await get_project_path_from_context(ctx)
        if project_path:
            namespace = encode_cwd(project_path)
        else:
            return {"error": "Could not determine project namespace"}

    if not should_consolidate(db_path):
        return {
            "status": "below_threshold",
            "message": "Not enough unconsolidated events to trigger consolidation.",
        }

    # Run synchronous consolidation in a thread to avoid blocking the event loop
    result = await asyncio.to_thread(consolidate_batch, db_path, namespace)
    return result


@mcp.tool()
@inject_recovery_context
async def memory_get_unconsolidated(
    ctx: Context,
    namespace: str = "",
    limit: int = 50,
    include_consolidated: bool = False,
) -> dict:
    """Get raw events for client-side memory synthesis.

    Returns unconsolidated events with a pre-built consolidation prompt and
    response schema. Use with memory_store_memories for two-tool synthesis:
    1. Call memory_get_unconsolidated to get events + prompt
    2. Process the prompt with your LLM
    3. Call memory_store_memories with the synthesized memories

    Args:
        namespace: Project namespace. Auto-detected if empty.
        limit: Maximum events to return (default 50).
        include_consolidated: If true, also return events consolidated in last 24h.

    Returns:
        Dict with events, count, consolidation_prompt, and response_schema.
    """
    db_path = str(get_db_path())
    if not namespace:
        project_path = await get_project_path_from_context(ctx)
        if project_path:
            namespace = encode_cwd(project_path)
        else:
            return {"error": "Could not determine project namespace", "events": []}

    return do_get_unconsolidated(
        db_path=db_path,
        namespace=namespace,
        limit=limit,
        include_consolidated=include_consolidated,
    )


@mcp.tool()
@inject_recovery_context
async def memory_store_memories(
    ctx: Context,
    memories: str,
    event_ids: str = "",
    namespace: str = "",
) -> dict:
    """Store client-synthesized memories from raw events.

    Accepts memories as a JSON string (output from client LLM processing
    the consolidation_prompt from memory_get_unconsolidated).

    Args:
        memories: JSON string of memory objects. Format:
            {"memories": [{"content": "...", "memory_type": "fact", "tags": [...]}]}
        event_ids: Comma-separated event IDs to mark as consolidated.
        namespace: Project namespace. Auto-detected if empty.

    Returns:
        Dict with status, memories_created, events_consolidated, memory_ids.
    """
    db_path = str(get_db_path())
    project_path = await get_project_path_from_context(ctx)
    if not namespace:
        if project_path:
            namespace = encode_cwd(project_path)
        else:
            return {"error": "Could not determine project namespace"}

    # Detect current branch
    branch = get_current_branch(project_path) if project_path else ""

    result = do_store_memories(
        db_path=db_path,
        memories_json=memories,
        event_ids_str=event_ids,
        namespace=namespace,
        branch=branch,
    )
    try:
        from spellbook_mcp.admin.events import Event, Subsystem, event_bus

        await event_bus.publish(
            Event(
                subsystem=Subsystem.MEMORY,
                event_type="memory.created",
                data={
                    "namespace": namespace,
                    "count": result.get("memories_created", 0),
                },
                namespace=namespace,
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result
