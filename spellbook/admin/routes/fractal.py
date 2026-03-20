"""Fractal graph explorer API routes.

Provides graph listing, detail, node/edge queries, and pre-formatted
Cytoscape.js data for the interactive graph visualization.

Uses SQLAlchemy ORM models for database access via the fractal_db
dependency.
"""

import asyncio
import json
import math
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.events import Event, Subsystem, event_bus
from spellbook.admin.routes.list_helpers import build_list_response, validate_sort_order
from spellbook.admin.routes.schemas import GraphStatusUpdateRequest
from spellbook.db import fractal_db
from spellbook.db.fractal_models import FractalEdge, FractalGraph, FractalNode
from spellbook.db.helpers import apply_sorting
from spellbook.fractal.graph_ops import delete_graph, update_graph_status

router = APIRouter(prefix="/fractal", tags=["fractal"])

GRAPH_SORT_WHITELIST = {"created_at", "updated_at", "seed", "status"}


def _error_response(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


@router.get("/graphs")
async def list_graphs(
    status: Optional[str] = Query(None, description="Filter by graph status"),
    project_dir: Optional[str] = Query(None, description="Filter by project directory"),
    search: Optional[str] = Query(None, description="Search by seed text"),
    sort: Optional[str] = Query(
        "created_at",
        description="Sort field",
    ),
    order: Optional[str] = Query(
        "desc",
        description="Sort order: asc or desc",
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(fractal_db),
    _auth: str = Depends(require_admin_auth),
):
    """List fractal graphs with pagination, filtering, and sorting."""
    # Build filter conditions
    filters = []
    if status:
        filters.append(FractalGraph.status == status)
    if project_dir:
        filters.append(FractalGraph.project_dir == project_dir)
    if search:
        filters.append(FractalGraph.seed.contains(search))

    # Count query
    count_query = select(func.count()).select_from(FractalGraph)
    for f in filters:
        count_query = count_query.where(f)
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()
    pages = max(1, math.ceil(total / per_page))
    offset = (page - 1) * per_page

    # Data query with LEFT JOIN for node count
    node_count = func.count(FractalNode.id).label("node_count")
    data_query = (
        select(FractalGraph, node_count)
        .outerjoin(FractalNode, FractalGraph.id == FractalNode.graph_id)
        .group_by(FractalGraph.id)
    )
    for f in filters:
        data_query = data_query.where(f)

    # Apply sorting
    sort_order = validate_sort_order(order or "desc")
    data_query = apply_sorting(
        data_query,
        FractalGraph,
        sort or "created_at",
        sort_order,
        GRAPH_SORT_WHITELIST,
    )
    data_query = data_query.limit(per_page).offset(offset)

    result = await session.execute(data_query)
    rows = result.all()

    items = []
    for graph, node_count_val in rows:
        d = graph.to_dict()
        d["total_nodes"] = node_count_val
        items.append(d)

    return build_list_response(items, total, page, per_page)


@router.get("/graphs/{graph_id}")
async def get_graph(
    graph_id: str,
    session: AsyncSession = Depends(fractal_db),
    _auth: str = Depends(require_admin_auth),
):
    """Get fractal graph detail with metadata and node count."""
    result = await session.execute(
        select(FractalGraph).where(FractalGraph.id == graph_id)
    )
    graph = result.scalars().first()
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    # Get node count
    count_result = await session.execute(
        select(func.count()).select_from(FractalNode).where(
            FractalNode.graph_id == graph_id
        )
    )
    total_nodes = count_result.scalar_one()

    d = graph.to_dict()
    d["total_nodes"] = total_nodes
    return d


@router.delete("/graphs/{graph_id}")
async def delete_graph_endpoint(
    graph_id: str,
    _auth: str = Depends(require_admin_auth),
):
    """Delete a fractal graph and all its nodes/edges."""
    result = await delete_graph(graph_id)

    if "error" in result:
        return _error_response("GRAPH_NOT_FOUND", "Graph not found", 404)

    await event_bus.publish(
        Event(
            subsystem=Subsystem.FRACTAL,
            event_type="fractal.graph_deleted",
            data={"graph_id": graph_id},
        )
    )

    return result


@router.patch("/graphs/{graph_id}/status")
async def update_graph_status_endpoint(
    graph_id: str,
    body: GraphStatusUpdateRequest,
    _auth: str = Depends(require_admin_auth),
):
    """Update the status of a fractal graph."""
    result = await update_graph_status(graph_id, body.status, body.reason)

    if "error" in result:
        error_msg = result["error"]
        if "not found" in error_msg.lower():
            return _error_response("GRAPH_NOT_FOUND", "Graph not found", 404)
        return _error_response("INVALID_TRANSITION", error_msg, 400)

    await event_bus.publish(
        Event(
            subsystem=Subsystem.FRACTAL,
            event_type="fractal.graph_updated",
            data={"graph_id": graph_id, "status": body.status},
        )
    )

    return result


@router.get("/graphs/{graph_id}/nodes")
async def get_graph_nodes(
    graph_id: str,
    max_depth: Optional[int] = Query(None, ge=0, description="Maximum depth to return"),
    session: AsyncSession = Depends(fractal_db),
    _auth: str = Depends(require_admin_auth),
):
    """Get nodes for a fractal graph, optionally depth-limited."""
    # Verify graph exists
    result = await session.execute(
        select(FractalGraph).where(FractalGraph.id == graph_id)
    )
    graph = result.scalars().first()
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    query = (
        select(FractalNode)
        .where(FractalNode.graph_id == graph_id)
        .order_by(FractalNode.depth, FractalNode.created_at)
    )
    if max_depth is not None:
        query = query.where(FractalNode.depth <= max_depth)

    result = await session.execute(query)
    nodes = result.scalars().all()

    return {"nodes": [n.to_dict() for n in nodes], "count": len(nodes)}


@router.get("/graphs/{graph_id}/edges")
async def get_graph_edges(
    graph_id: str,
    session: AsyncSession = Depends(fractal_db),
    _auth: str = Depends(require_admin_auth),
):
    """Get edges for a fractal graph."""
    result = await session.execute(
        select(FractalGraph).where(FractalGraph.id == graph_id)
    )
    graph = result.scalars().first()
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    result = await session.execute(
        select(FractalEdge)
        .where(FractalEdge.graph_id == graph_id)
        .order_by(FractalEdge.created_at)
    )
    edges = result.scalars().all()

    return {"edges": [e.to_dict() for e in edges], "count": len(edges)}


def _make_node_label(text: str | None) -> str:
    """Extract first line of text for node label, stripping trailing colon."""
    if not text:
        return ""
    first_line = text.split("\n", 1)[0].strip()
    if first_line.endswith(":"):
        first_line = first_line[:-1].strip()
    if len(first_line) > 80:
        first_line = first_line[:77] + "..."
    return first_line


@router.get("/graphs/{graph_id}/cytoscape")
async def get_cytoscape_data(
    graph_id: str,
    max_depth: Optional[int] = Query(None, ge=0, description="Maximum depth"),
    session: AsyncSession = Depends(fractal_db),
    _auth: str = Depends(require_admin_auth),
):
    """Get pre-formatted Cytoscape.js data for graph visualization.

    Returns {elements: {nodes, edges}, stats} format.
    Nodes and edges include `data` and `classes` fields for Cytoscape.
    """
    # Verify graph exists
    result = await session.execute(
        select(FractalGraph).where(FractalGraph.id == graph_id)
    )
    graph = result.scalars().first()
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    # Fetch nodes
    node_query = (
        select(FractalNode)
        .where(FractalNode.graph_id == graph_id)
        .order_by(FractalNode.depth, FractalNode.created_at)
    )
    if max_depth is not None:
        node_query = node_query.where(FractalNode.depth <= max_depth)

    result = await session.execute(node_query)
    raw_nodes = result.scalars().all()

    # Fetch edges
    result = await session.execute(
        select(FractalEdge).where(FractalEdge.graph_id == graph_id)
    )
    raw_edges = result.scalars().all()

    # Build node set for filtering edges
    node_ids = {n.id for n in raw_nodes}

    # Transform to Cytoscape format
    cyto_nodes = []
    status_counts = {"saturated": 0, "pending": 0}
    max_node_depth = 0

    for n in raw_nodes:
        node_status = n.status
        node_type = n.node_type

        # Build classes string for styling
        classes = f"{node_type} {node_status}"

        cyto_nodes.append({
            "data": {
                "id": n.id,
                "label": _make_node_label(n.text),
                "text": n.text or "",
                "type": node_type,
                "status": node_status,
                "depth": n.depth,
                "parent_id": n.parent_id,
                "owner": n.owner,
                "session_id": n.session_id,
                "claimed_at": n.claimed_at,
                "answered_at": n.answered_at,
                "synthesized_at": n.synthesized_at,
            },
            "classes": classes,
        })

        if node_status == "saturated":
            status_counts["saturated"] += 1
        elif node_status in ("open", "claimed"):
            status_counts["pending"] += 1

        if n.depth > max_node_depth:
            max_node_depth = n.depth

    cyto_edges = []
    convergence_count = 0
    contradiction_count = 0

    for e in raw_edges:
        # Only include edges where both endpoints are in our node set
        if e.from_node in node_ids and e.to_node in node_ids:
            edge_type = e.edge_type
            cyto_edges.append({
                "data": {
                    "source": e.from_node,
                    "target": e.to_node,
                    "type": edge_type,
                },
                "classes": edge_type,
            })
            if edge_type == "convergence":
                convergence_count += 1
            elif edge_type == "contradiction":
                contradiction_count += 1

    return {
        "elements": {
            "nodes": cyto_nodes,
            "edges": cyto_edges,
        },
        "stats": {
            "total_nodes": len(cyto_nodes),
            "saturated": status_counts["saturated"],
            "pending": status_counts["pending"],
            "max_depth": max_node_depth,
            "convergences": convergence_count,
            "contradictions": contradiction_count,
        },
    }


@router.get("/graphs/{graph_id}/convergence")
async def get_convergence(
    graph_id: str,
    session: AsyncSession = Depends(fractal_db),
    _auth: str = Depends(require_admin_auth),
):
    """Get convergence clusters for a fractal graph."""
    result = await session.execute(
        select(FractalGraph).where(FractalGraph.id == graph_id)
    )
    graph = result.scalars().first()
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    # Alias for the two node joins
    from_node = FractalNode.__table__.alias("n1")
    to_node = FractalNode.__table__.alias("n2")

    # Find convergence edges and their connected nodes
    conv_query = (
        select(
            FractalEdge,
            from_node.c.text.label("from_text"),
            from_node.c.depth.label("from_depth"),
            to_node.c.text.label("to_text"),
            to_node.c.depth.label("to_depth"),
        )
        .join(from_node, FractalEdge.from_node == from_node.c.id)
        .join(to_node, FractalEdge.to_node == to_node.c.id)
        .where(FractalEdge.graph_id == graph_id)
        .where(FractalEdge.edge_type == "convergence")
    )

    result = await session.execute(conv_query)
    rows = result.all()

    clusters = []
    for edge, from_text, from_depth, to_text, to_depth in rows:
        clusters.append({
            "nodes": [
                {"node_id": edge.from_node, "text": from_text, "depth": from_depth},
                {"node_id": edge.to_node, "text": to_text, "depth": to_depth},
            ],
            "insight": "",
            "edge_count": 1,
        })

    return {"clusters": clusters, "count": len(clusters)}


@router.get("/graphs/{graph_id}/contradictions")
async def get_contradictions(
    graph_id: str,
    session: AsyncSession = Depends(fractal_db),
    _auth: str = Depends(require_admin_auth),
):
    """Get contradiction pairs for a fractal graph."""
    result = await session.execute(
        select(FractalGraph).where(FractalGraph.id == graph_id)
    )
    graph = result.scalars().first()
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    from_node = FractalNode.__table__.alias("n1")
    to_node = FractalNode.__table__.alias("n2")

    contra_query = (
        select(
            FractalEdge,
            from_node.c.text.label("from_text"),
            to_node.c.text.label("to_text"),
        )
        .join(from_node, FractalEdge.from_node == from_node.c.id)
        .join(to_node, FractalEdge.to_node == to_node.c.id)
        .where(FractalEdge.graph_id == graph_id)
        .where(FractalEdge.edge_type == "contradiction")
    )

    result = await session.execute(contra_query)
    rows = result.all()

    pairs = []
    for edge, from_text, to_text in rows:
        pairs.append({
            "node_a": {"node_id": edge.from_node, "text": from_text},
            "node_b": {"node_id": edge.to_node, "text": to_text},
            "tension": "",
        })

    return {"pairs": pairs, "count": len(pairs)}


def _find_jsonl_file(session_id: str) -> Path | None:
    """Search for a session JSONL file across all project directories.

    Session files can be at the top level (regular sessions) or nested
    in subagents/ directories (worker sessions from Task tool dispatch).
    """
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return None
    filename = f"{session_id}.jsonl"
    for match in projects_dir.glob(f"**/{filename}"):
        return match
    return None


def _parse_jsonl_messages(
    jsonl_path: Path,
    start_time: str | None,
    end_time: str | None,
) -> list[dict]:
    """Parse JSONL file and extract user/assistant messages within a time window."""
    messages = []
    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")
            if entry_type not in ("user", "assistant"):
                continue

            timestamp = entry.get("timestamp")
            if not timestamp:
                continue

            # Filter by time window
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue

            message = entry.get("message", {})
            content = message.get("content")
            if content is None:
                continue

            if entry_type == "user":
                # User messages: content is a string or list of tool_result blocks
                if isinstance(content, str):
                    messages.append({
                        "role": "user",
                        "content": content,
                        "timestamp": timestamp,
                    })
                elif isinstance(content, list):
                    # User messages can contain tool_result blocks
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tool_content = block.get("content", "")
                            if isinstance(tool_content, list):
                                tool_content = "\n".join(
                                    b.get("text", "") for b in tool_content
                                    if isinstance(b, dict) and b.get("type") == "text"
                                )
                            if tool_content:
                                messages.append({
                                    "role": "tool_result",
                                    "content": tool_content[:2000],
                                    "tool_use_id": block.get("tool_use_id", ""),
                                    "timestamp": timestamp,
                                })
            else:
                # Assistant messages: content is a list of blocks
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type")
                    if block_type == "thinking":
                        thinking = block.get("thinking", "")
                        if thinking:
                            messages.append({
                                "role": "thinking",
                                "content": thinking,
                                "timestamp": timestamp,
                            })
                    elif block_type == "text":
                        text = block.get("text", "")
                        if text:
                            messages.append({
                                "role": "assistant",
                                "content": text,
                                "timestamp": timestamp,
                            })
                    elif block_type == "tool_use":
                        messages.append({
                            "role": "tool_use",
                            "content": block.get("name", "unknown_tool"),
                            "tool_use_id": block.get("id", ""),
                            "timestamp": timestamp,
                        })

    return messages


@router.get("/graphs/{graph_id}/nodes/{node_id}/chat-log")
async def get_node_chat_log(
    graph_id: str,
    node_id: str,
    session: AsyncSession = Depends(fractal_db),
    _auth: str = Depends(require_admin_auth),
):
    """Get the chat log for a fractal node's work session."""
    result = await session.execute(
        select(FractalNode).where(
            FractalNode.id == node_id,
            FractalNode.graph_id == graph_id,
        )
    )
    node = result.scalars().first()

    if not node:
        # Fallback: try without graph_id constraint (handles stale frontend state)
        result = await session.execute(
            select(FractalNode).where(FractalNode.id == node_id)
        )
        node = result.scalars().first()

    if not node:
        return _error_response("NODE_NOT_FOUND", f"Node '{node_id}' not found", 404)

    session_id = node.session_id
    claimed_at = node.claimed_at
    answered_at = node.answered_at
    synthesized_at = node.synthesized_at

    if not session_id:
        return {
            "messages": [],
            "node_id": node_id,
            "session_id": None,
            "note": "No session ID recorded for this node",
        }

    # Find the JSONL file
    jsonl_path = await asyncio.to_thread(_find_jsonl_file, session_id)
    if jsonl_path is None:
        return {
            "messages": [],
            "node_id": node_id,
            "session_id": session_id,
            "note": f"Session file not found for session '{session_id}'",
        }

    # Determine the end of the time window: use the later of synthesized_at and answered_at
    end_time = None
    if synthesized_at and answered_at:
        end_time = max(synthesized_at, answered_at)
    elif synthesized_at:
        end_time = synthesized_at
    elif answered_at:
        end_time = answered_at

    messages = await asyncio.to_thread(_parse_jsonl_messages, jsonl_path, claimed_at, end_time)

    return {
        "messages": messages,
        "node_id": node_id,
        "session_id": session_id,
        "claimed_at": claimed_at,
        "synthesized_at": synthesized_at,
    }
