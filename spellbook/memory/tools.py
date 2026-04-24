"""Memory MCP tool implementations.

File-based memory system wrappers. The do_memory_* functions delegate to
spellbook.memory.filestore. SQLite event logging (do_log_event) is preserved
for hooks and REST endpoints.
"""

import json
import logging
import os
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from spellbook.core.db import get_db_path as _get_db_path
from spellbook.memory.consolidation import build_consolidation_prompt
from spellbook.memory.filestore import (
    forget_memory,
    recall_memories,
    store_memory,
    verify_memory,
)
from spellbook.memory.models import Citation
from spellbook.memory.requirements import (
    MemorySystemNotAvailable,
    ensure_memory_system_available,
)
from spellbook.memory.store import (
    get_memory,
    get_unconsolidated_events,
    log_raw_event,
    soft_delete_memory,
)
from spellbook.memory.sync_pipeline import memory_sync as _run_sync_pipeline

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker-LLM recall-error propagation
# ---------------------------------------------------------------------------
#
# ``_MEMORY_RECALL_ERROR`` ferries a ``<worker-llm-error>`` XML string from
# deep inside ``spellbook.memory.search_qmd.search_memories`` (the rerank
# branch) up to the MCP tool boundary (``do_memory_recall``) without
# changing any function's return type. A ``ContextVar`` (not a module-level
# global) is required because multiple ``memory_recall`` calls may run
# concurrently under async MCP, and the value must be isolated per call.
#
# Lifecycle:
#   1. ``do_memory_recall`` resets the ContextVar to ``None`` on entry so
#      stale errors from a previous call cannot leak.
#   2. ``search_memories`` sets the ContextVar when a worker rerank call
#      raises ``WorkerLLMError``; results still come from the baseline
#      ranking (the error is never raised out of ``search_memories``).
#   3. ``do_memory_recall`` reads the ContextVar before returning and, when
#      non-``None``, attaches it to the response dict under the key
#      ``worker_llm_error``. When ``None``, the key is omitted so the
#      orchestrator sees no field and takes no action.
_MEMORY_RECALL_ERROR: ContextVar[str | None] = ContextVar(
    "_MEMORY_RECALL_ERROR", default=None
)


def get_last_memory_recall_error() -> str | None:
    """Public accessor for the worker-LLM recall-error marker.

    Callers that want to inspect the most recent ``memory_recall`` worker
    failure without importing the ``ContextVar`` directly use this helper.
    Returns the ``<worker-llm-error>`` XML string that was stored by
    ``search_memories`` during the most recent ``do_memory_recall``, or
    ``None`` when the last recall succeeded or has not yet run.
    """
    return _MEMORY_RECALL_ERROR.get()


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


# ---------------------------------------------------------------------------
# Memory directory resolution
# ---------------------------------------------------------------------------


def _get_memory_dir(namespace: str, scope: str = "project") -> str:
    """Resolve the root memory directory for a namespace and scope.

    Args:
        namespace: Project path or namespace identifier.
        scope: "project" or "global".

    Returns:
        Absolute path to the memory directory.
    """
    if scope == "global":
        return os.path.expanduser("~/.local/spellbook/memories/_global")
    # project-encoded path: strip leading /, replace / with -
    project_encoded = namespace.replace("/", "-").lstrip("-")
    return os.path.expanduser(f"~/.local/spellbook/memories/{project_encoded}")


# ---------------------------------------------------------------------------
# New file-based tool functions
# ---------------------------------------------------------------------------


def do_memory_store(
    content: str,
    type: str = "project",
    kind: Optional[str] = None,
    citations: Optional[List[Dict[str, str]]] = None,
    tags: Optional[List[str]] = None,
    scope: str = "project",
    branch: Optional[str] = None,
    namespace: str = "",
) -> Dict[str, Any]:
    """Store a single memory as a markdown file.

    Args:
        content: Memory body text.
        type: Memory category (project, user, feedback, reference).
        kind: Knowledge classification (fact, rule, convention, etc.).
        citations: List of citation dicts with 'file' and optional 'symbol'.
        tags: Freeform tags.
        scope: "project" or "global".
        branch: Git branch where memory was created.
        namespace: Project namespace for directory resolution.

    Returns:
        Dict with status, path, and content_hash.
    """
    try:
        ensure_memory_system_available()
    except MemorySystemNotAvailable as e:
        return {"error": str(e), "status": "unavailable"}

    memory_dir = _get_memory_dir(namespace, scope)

    # Parse citations from dicts to Citation objects
    citation_objects: List[Citation] = []
    if citations:
        for c in citations:
            citation_objects.append(Citation(
                file=c.get("file", ""),
                symbol=c.get("symbol"),
                symbol_type=c.get("symbol_type"),
            ))

    mf = store_memory(
        content=content,
        type=type,
        kind=kind,
        citations=citation_objects,
        tags=tags or [],
        scope=scope,
        branch=branch,
        memory_dir=memory_dir,
    )

    return {
        "status": "stored",
        "path": mf.path,
        "content_hash": mf.frontmatter.content_hash,
    }


def do_memory_recall(
    query: str = "",
    namespace: str = "",
    limit: int = 10,
    file_path: Optional[str] = None,
    scope: str = "project",
    tags: Optional[List[str]] = None,
    branch: str = "",
    # Legacy params kept for backward compat with MCP tool registration
    db_path: str = "",
    repo_path: str = "",
) -> Dict[str, Any]:
    """Search memories using the new filestore.

    Falls back through QMD -> grep search.

    Args:
        query: Search query text. Empty returns recent/all.
        namespace: Project namespace.
        limit: Maximum results.
        file_path: Filter by citation file path.
        scope: "project", "global", or "all".
        tags: Filter by tags.
        branch: Current git branch for scoring.
        db_path: Ignored (legacy). Kept for backward compat.
        repo_path: Ignored (legacy). Kept for backward compat.

    Returns:
        Dict with memories list, count, query, and namespace.
    """
    # Clear any stale worker-LLM error marker from a prior call on this
    # task/context before delegating. Populated by
    # ``search_qmd.search_memories`` on worker rerank failure (D7).
    _MEMORY_RECALL_ERROR.set(None)

    try:
        ensure_memory_system_available()
    except MemorySystemNotAvailable as e:
        return {"error": str(e), "status": "unavailable"}

    memory_dirs: List[str] = []

    if scope in ("project", "all"):
        memory_dirs.append(_get_memory_dir(namespace, "project"))
    if scope in ("global", "all"):
        memory_dirs.append(_get_memory_dir(namespace, "global"))

    # Use the first directory as the primary for recall_memories
    # (recall_memories expects a single dir)
    results = []
    for mdir in memory_dirs:
        if os.path.isdir(mdir):
            results.extend(
                recall_memories(
                    query=query,
                    memory_dir=mdir,
                    scope=None,  # Already filtered by directory
                    tags=tags,
                    file_path=file_path,
                    limit=limit,
                    branch=branch or None,
                )
            )

    # Sort by score descending and limit
    results.sort(key=lambda r: r.score, reverse=True)
    results = results[:limit]

    memories = []
    for r in results:
        memories.append({
            "content": r.memory.content.strip(),
            "score": r.score,
            "path": r.memory.path,
            "type": r.memory.frontmatter.type,
            "kind": r.memory.frontmatter.kind,
            "tags": r.memory.frontmatter.tags,
            "scope": r.memory.frontmatter.scope,
            "match_context": r.match_context,
        })

    response: Dict[str, Any] = {
        "memories": memories,
        "count": len(memories),
        "query": query,
        "namespace": namespace,
    }
    # D7: surface worker-LLM rerank failures without raising.
    recall_error = _MEMORY_RECALL_ERROR.get()
    if recall_error:
        response["worker_llm_error"] = recall_error
    return response


def do_memory_forget(
    memory_id_or_query: str = "",
    namespace: str = "",
    archive: bool = True,
    # Legacy params
    db_path: str = "",
    memory_id: str = "",
) -> Dict[str, Any]:
    """Archive or delete a memory file.

    Args:
        memory_id_or_query: Absolute path to the memory file.
        namespace: Project namespace.
        archive: If True, move to .archive/. If False, permanently delete.
        db_path: Ignored (legacy).
        memory_id: Legacy param. If provided and memory_id_or_query is empty,
                   falls back to old SQLite deletion.

    Returns:
        Dict with status.
    """
    try:
        ensure_memory_system_available()
    except MemorySystemNotAvailable as e:
        return {"error": str(e), "status": "unavailable"}

    # Legacy fallback: if called with old memory_id param (UUID)
    if not memory_id_or_query and memory_id:
        db = str(_get_db_path()) if not db_path else db_path
        mem = get_memory(db, memory_id)
        if mem is None:
            return {"status": "not_found", "memory_id": memory_id}
        soft_delete_memory(db, memory_id)
        return {
            "status": "deleted",
            "memory_id": memory_id,
            "message": f"Memory soft-deleted. Will be purged after 30 days. "
                       f"Content preview: {mem['content'][:80]}...",
        }

    memory_dir = _get_memory_dir(namespace, "project")
    found = forget_memory(memory_id_or_query, memory_dir, archive=archive)

    if not found:
        return {"status": "not_found", "path": memory_id_or_query}

    status = "archived" if archive else "deleted"
    return {"status": status, "path": memory_id_or_query}


def do_memory_sync(
    namespace: str = "",
    project_root: str = "",
    changed_files: Optional[List[str]] = None,
    base_ref: str = "main",
) -> Dict[str, Any]:
    """Run sync pipeline phases 1-3, return plan for calling LLM.

    Args:
        namespace: Project namespace.
        project_root: Root of the git repository.
        changed_files: List of changed file paths.
        base_ref: Base git ref for diff (default: main).

    Returns:
        Dict with status, factcheck_items, prompt_template, and stats.
    """
    try:
        ensure_memory_system_available()
    except MemorySystemNotAvailable as e:
        return {"error": str(e), "status": "unavailable"}

    memory_dir = _get_memory_dir(namespace, "project")
    if changed_files is None:
        changed_files = []

    plan = _run_sync_pipeline(
        project_root=project_root,
        memory_dir=memory_dir,
        changed_files=changed_files,
        diff_text="",
    )

    # Serialize factcheck items
    factcheck_items = []
    for item in plan.factcheck_items:
        factcheck_items.append({
            "memory_path": item.memory_path,
            "memory_content": item.memory_content,
            "prompt": item.prompt,
        })

    return {
        "status": "plan_ready",
        "factcheck_items": factcheck_items,
        "prompt_template": plan.prompt_template,
        "phase4_instructions": plan.phase4_instructions,
        "stats": {**plan.stats, "base_ref": base_ref},
    }


def do_memory_verify(
    memory_path: str,
    namespace: str = "",
    project_root: str = "",
) -> Dict[str, Any]:
    """Fact-check a single memory, return context for calling LLM.

    Args:
        memory_path: Absolute path to the memory file.
        namespace: Project namespace.
        project_root: Root of the project for citation checks.

    Returns:
        Dict with status, cited_files_exist, cited_symbols_exist, and memory_content.
    """
    try:
        ensure_memory_system_available()
    except MemorySystemNotAvailable as e:
        return {"error": str(e), "status": "unavailable"}

    ctx = verify_memory(memory_path, project_root)

    return {
        "status": "context_ready",
        "memory_content": ctx.memory.content,
        "memory_path": memory_path,
        "cited_files_exist": ctx.cited_files_exist,
        "cited_symbols_exist": ctx.cited_symbols_exist,
    }


def do_memory_review_events(
    namespace: Optional[str] = None,
    limit: int = 50,
    db_path: str = "",
) -> Dict[str, Any]:
    """Return pending raw events for LLM synthesis.

    Args:
        namespace: Project namespace for scoping.
        limit: Max events to return.
        db_path: Explicit database path. If empty, uses _get_db_path().

    Returns:
        Dict with events, count, consolidation_prompt, and response_schema.
    """
    try:
        ensure_memory_system_available()
    except MemorySystemNotAvailable as e:
        return {"error": str(e), "status": "unavailable"}

    if not db_path:
        db_path = str(_get_db_path())
    events = get_unconsolidated_events(db_path, limit=limit, namespace=namespace)

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


# ---------------------------------------------------------------------------
# SQLite event logging (preserved for hooks/REST)
# ---------------------------------------------------------------------------


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
