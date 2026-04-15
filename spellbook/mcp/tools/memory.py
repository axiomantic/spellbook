"""MCP tools for memory operations.

Registers file-based memory tools: memory_store, memory_recall, memory_forget,
memory_sync, memory_verify, memory_review_events.
"""

__all__ = [
    "memory_recall",
    "memory_store",
    "memory_forget",
    "memory_sync",
    "memory_verify",
    "memory_review_events",
]

import json

from fastmcp import Context

from spellbook.mcp.server import mcp
from spellbook.core.branch_ancestry import get_current_branch
from spellbook.core.db import get_db_path
from spellbook.sessions.injection import inject_recovery_context
from spellbook.memory.tools import (
    do_memory_forget,
    do_memory_recall,
    do_memory_review_events,
    do_memory_store,
    do_memory_sync,
    do_memory_verify,
)
from spellbook.core.path_utils import (
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
    scope: str = "project",
    tags: str = "",
) -> dict:
    """Search and retrieve memories.

    Query memories by keyword search, file path, or tags. Empty query returns
    the most recent and important memories.

    Args:
        query: Search query (keywords). Empty = recent+important.
        namespace: Project namespace. Auto-detected if empty.
        limit: Maximum memories to return (default 10).
        file_path: If provided, find memories citing this file path.
        scope: Memory scope to search. "project" (default) searches
            current project only. "global" searches cross-project
            memories only. "all" searches both.
        tags: Comma-separated tags to filter by.

    Returns:
        Dict with 'memories' list, count, query, and namespace.
    """
    # Validate scope
    valid_scopes = {"project", "global", "all"}
    if scope not in valid_scopes:
        return {"error": f"Invalid scope '{scope}'. Must be one of: {', '.join(sorted(valid_scopes))}"}

    project_path = await get_project_path_from_context(ctx)
    if not namespace:
        if project_path:
            namespace = encode_cwd(project_path)
        else:
            return {"error": "Could not determine project namespace", "memories": []}

    # Detect current branch for branch-weighted scoring
    repo_path = resolve_repo_root(project_path) if project_path else ""
    branch = get_current_branch(repo_path) if repo_path else ""

    # Parse tags
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    return do_memory_recall(
        query=query,
        namespace=namespace,
        limit=limit,
        file_path=file_path if file_path else None,
        scope=scope,
        tags=tags_list,
        branch=branch,
    )


@mcp.tool()
@inject_recovery_context
async def memory_store(
    ctx: Context,
    content: str,
    type: str = "project",
    kind: str = "",
    citations: str = "",
    tags: str = "",
    scope: str = "project",
) -> dict:
    """Store a single memory as a markdown file.

    Args:
        content: Memory body text. Must be non-empty.
        type: Memory category: project, user, feedback, reference.
        kind: Knowledge classification: fact, rule, convention, preference, decision, antipattern.
        citations: JSON string of citation objects: [{"file": "path", "symbol": "name"}].
        tags: Comma-separated tags for categorical retrieval.
        scope: "project" (default) or "global".

    Returns:
        Dict with status, path, and content_hash.
    """
    if scope not in ("project", "global"):
        return {"error": f"Invalid scope for store. Must be 'project' or 'global', got '{scope}'"}

    project_path = await get_project_path_from_context(ctx)
    namespace = encode_cwd(project_path) if project_path else ""
    if not namespace:
        return {"error": "Could not determine project namespace"}

    branch = get_current_branch(project_path) if project_path else ""

    # Parse citations JSON
    parsed_citations = None
    if citations:
        try:
            parsed_citations = json.loads(citations)
        except (json.JSONDecodeError, TypeError):
            return {"error": "Invalid citations JSON"}

    # Parse tags
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    return do_memory_store(
        content=content,
        type=type,
        kind=kind if kind else None,
        citations=parsed_citations,
        tags=tags_list,
        scope=scope,
        branch=branch,
        namespace=namespace,
    )


@mcp.tool()
@inject_recovery_context
async def memory_forget(ctx: Context, memory_id: str, scope: str = "") -> dict:
    """Archive a memory by path or UUID. Memory is recoverable from .archive/.

    Args:
        memory_id: File path of the memory to archive, or a legacy UUID.
        scope: Optional hint. Not functionally required.

    Returns:
        Dict with status ('archived', 'deleted', or 'not_found').
    """
    # Detect if this is a file path or a legacy UUID
    if "/" in memory_id or memory_id.endswith(".md"):
        result = do_memory_forget(memory_id_or_query=memory_id)
    else:
        # Legacy UUID path
        db_path = str(get_db_path())
        result = do_memory_forget(memory_id_or_query="", memory_id=memory_id, db_path=db_path)

    try:
        from spellbook.admin.events import Event, Subsystem, event_bus

        await event_bus.publish(
            Event(
                subsystem=Subsystem.MEMORY,
                event_type="memory.deleted",
                data={"memory_id": memory_id, "scope_hint": scope},
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
async def memory_sync(
    ctx: Context,
    changed_files: str = "",
    base_ref: str = "main",
) -> dict:
    """Run memory sync pipeline: find at-risk memories and prepare fact-check context.

    Analyzes code changes against stored memories to find memories that may
    need updating. Returns a plan with fact-check prompts for LLM execution.

    Args:
        changed_files: Comma-separated list of changed file paths (relative to project root).
        base_ref: Base git ref for diff (default: main).

    Returns:
        Dict with status, factcheck_items, prompt_template, and stats.
    """
    project_path = await get_project_path_from_context(ctx)
    if not project_path:
        return {"error": "Could not determine project path"}

    namespace = encode_cwd(project_path)
    repo_path = resolve_repo_root(project_path) or project_path

    files_list = [f.strip() for f in changed_files.split(",") if f.strip()] if changed_files else []

    return do_memory_sync(
        namespace=namespace,
        project_root=repo_path,
        changed_files=files_list,
        base_ref=base_ref,
    )


@mcp.tool()
@inject_recovery_context
async def memory_verify(
    ctx: Context,
    memory_path: str,
) -> dict:
    """Fact-check a single memory against current code state.

    Checks if cited files and symbols still exist. Returns context
    for the calling LLM to determine if the memory is still accurate.

    Args:
        memory_path: Absolute path to the memory file.

    Returns:
        Dict with status, cited_files_exist, cited_symbols_exist, and memory_content.
    """
    project_path = await get_project_path_from_context(ctx)
    if not project_path:
        return {"error": "Could not determine project path"}

    namespace = encode_cwd(project_path)
    repo_path = resolve_repo_root(project_path) or project_path

    return do_memory_verify(
        memory_path=memory_path,
        namespace=namespace,
        project_root=repo_path,
    )


@mcp.tool()
@inject_recovery_context
async def memory_review_events(
    ctx: Context,
    namespace: str = "",
    limit: int = 50,
) -> dict:
    """Get raw events for client-side memory synthesis.

    Returns unconsolidated events with a pre-built consolidation prompt.
    Use with memory_store for two-tool synthesis:
    1. Call memory_review_events to get events + prompt
    2. Process the prompt with your LLM
    3. Call memory_store with each synthesized memory

    Args:
        namespace: Project namespace. Auto-detected if empty.
        limit: Maximum events to return (default 50).

    Returns:
        Dict with events, count, consolidation_prompt, and response_schema.
    """
    if not namespace:
        project_path = await get_project_path_from_context(ctx)
        if project_path:
            namespace = encode_cwd(project_path)
        else:
            return {"error": "Could not determine project namespace", "events": []}

    return do_memory_review_events(namespace=namespace, limit=limit)
