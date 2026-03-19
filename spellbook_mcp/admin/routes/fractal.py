"""Fractal graph explorer API routes.

Provides graph listing, detail, node/edge queries, and pre-formatted
Cytoscape.js data for the interactive graph visualization.
"""

import asyncio
import json
import math
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from spellbook.admin.auth import require_admin_auth
from spellbook.admin.db import query_fractal_db
from spellbook.admin.events import Event, Subsystem, event_bus
from spellbook.admin.routes.schemas import GraphStatusUpdateRequest
from spellbook.fractal.graph_ops import delete_graph, update_graph_status

router = APIRouter(prefix="/fractal", tags=["fractal"])


def _error_response(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


@router.get("/graphs")
async def list_graphs(
    status: Optional[str] = Query(None, description="Filter by graph status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _session: str = Depends(require_admin_auth),
):
    """List fractal graphs with pagination and optional status filter."""
    where_clauses = []
    params: list = []

    if status:
        where_clauses.append("g.status = ?")
        params.append(status)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    count_result = await query_fractal_db(
        f"SELECT COUNT(*) as cnt FROM graphs g WHERE {where_sql}",
        tuple(params),
    )
    total = count_result[0]["cnt"] if count_result else 0
    pages = max(1, math.ceil(total / per_page))
    offset = (page - 1) * per_page

    rows = await query_fractal_db(
        f"""
        SELECT g.id, g.seed, g.intensity, g.status, g.created_at,
               COUNT(n.id) as total_nodes
        FROM graphs g
        LEFT JOIN nodes n ON g.id = n.graph_id
        WHERE {where_sql}
        GROUP BY g.id
        ORDER BY g.created_at DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [per_page, offset]),
    )

    return {
        "graphs": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.get("/graphs/{graph_id}")
async def get_graph(
    graph_id: str,
    _session: str = Depends(require_admin_auth),
):
    """Get fractal graph detail with metadata and node count."""
    rows = await query_fractal_db(
        """
        SELECT g.*, COUNT(n.id) as total_nodes
        FROM graphs g
        LEFT JOIN nodes n ON g.id = n.graph_id
        WHERE g.id = ?
        GROUP BY g.id
        """,
        (graph_id,),
    )
    if not rows:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    return rows[0]


@router.delete("/graphs/{graph_id}")
async def delete_graph_endpoint(
    graph_id: str,
    _session: str = Depends(require_admin_auth),
):
    """Delete a fractal graph and all its nodes/edges."""
    result = await asyncio.to_thread(delete_graph, graph_id)

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
    _session: str = Depends(require_admin_auth),
):
    """Update the status of a fractal graph."""
    result = await asyncio.to_thread(update_graph_status, graph_id, body.status, body.reason)

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
    _session: str = Depends(require_admin_auth),
):
    """Get nodes for a fractal graph, optionally depth-limited."""
    # Verify graph exists
    graph = await query_fractal_db(
        "SELECT id FROM graphs WHERE id = ?", (graph_id,)
    )
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    params: list = [graph_id]
    depth_clause = ""
    if max_depth is not None:
        depth_clause = " AND n.depth <= ?"
        params.append(max_depth)

    nodes = await query_fractal_db(
        f"""
        SELECT n.id, n.node_type, n.text, n.owner, n.depth, n.status,
               n.parent_id, n.metadata_json, n.created_at,
               n.session_id, n.claimed_at, n.answered_at, n.synthesized_at
        FROM nodes n
        WHERE n.graph_id = ?{depth_clause}
        ORDER BY n.depth, n.created_at
        """,
        tuple(params),
    )

    return {"nodes": nodes, "count": len(nodes)}


@router.get("/graphs/{graph_id}/edges")
async def get_graph_edges(
    graph_id: str,
    _session: str = Depends(require_admin_auth),
):
    """Get edges for a fractal graph."""
    graph = await query_fractal_db(
        "SELECT id FROM graphs WHERE id = ?", (graph_id,)
    )
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    edges = await query_fractal_db(
        """
        SELECT e.id, e.from_node as source, e.to_node as target,
               e.edge_type, e.metadata_json, e.created_at
        FROM edges e
        WHERE e.graph_id = ?
        ORDER BY e.created_at
        """,
        (graph_id,),
    )

    return {"edges": edges, "count": len(edges)}


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
    _session: str = Depends(require_admin_auth),
):
    """Get pre-formatted Cytoscape.js data for graph visualization.

    Returns {elements: {nodes, edges}, stats} format.
    Nodes and edges include `data` and `classes` fields for Cytoscape.
    """
    # Verify graph exists
    graph = await query_fractal_db(
        "SELECT id FROM graphs WHERE id = ?", (graph_id,)
    )
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    # Fetch nodes
    node_params: list = [graph_id]
    depth_clause = ""
    if max_depth is not None:
        depth_clause = " AND n.depth <= ?"
        node_params.append(max_depth)

    raw_nodes = await query_fractal_db(
        f"""
        SELECT n.id, n.node_type, n.text, n.depth, n.status,
               n.parent_id, n.owner,
               n.session_id, n.claimed_at, n.answered_at, n.synthesized_at
        FROM nodes n
        WHERE n.graph_id = ?{depth_clause}
        ORDER BY n.depth, n.created_at
        """,
        tuple(node_params),
    )

    # Fetch edges (only between nodes we have)
    raw_edges = await query_fractal_db(
        """
        SELECT e.from_node as source, e.to_node as target, e.edge_type
        FROM edges e
        WHERE e.graph_id = ?
        """,
        (graph_id,),
    )

    # Build node set for filtering edges
    node_ids = {n["id"] for n in raw_nodes}

    # Transform to Cytoscape format
    cyto_nodes = []
    status_counts = {"saturated": 0, "pending": 0}
    max_node_depth = 0

    for n in raw_nodes:
        status = n["status"]
        node_type = n["node_type"]

        # Build classes string for styling
        classes_parts = [node_type, status]
        classes = " ".join(classes_parts)

        cyto_nodes.append({
            "data": {
                "id": n["id"],
                "label": _make_node_label(n["text"]),
                "text": n["text"] or "",
                "type": node_type,
                "status": status,
                "depth": n["depth"],
                "parent_id": n["parent_id"],
                "owner": n["owner"],
                "session_id": n["session_id"],
                "claimed_at": n["claimed_at"],
                "answered_at": n["answered_at"],
                "synthesized_at": n["synthesized_at"],
            },
            "classes": classes,
        })

        if status == "saturated":
            status_counts["saturated"] += 1
        elif status in ("open", "claimed"):
            status_counts["pending"] += 1

        if n["depth"] > max_node_depth:
            max_node_depth = n["depth"]

    cyto_edges = []
    convergence_count = 0
    contradiction_count = 0

    for e in raw_edges:
        # Only include edges where both endpoints are in our node set
        if e["source"] in node_ids and e["target"] in node_ids:
            edge_type = e["edge_type"]
            cyto_edges.append({
                "data": {
                    "source": e["source"],
                    "target": e["target"],
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
    _session: str = Depends(require_admin_auth),
):
    """Get convergence clusters for a fractal graph."""
    graph = await query_fractal_db(
        "SELECT id FROM graphs WHERE id = ?", (graph_id,)
    )
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    # Find convergence edges and their connected nodes
    edges = await query_fractal_db(
        """
        SELECT e.from_node, e.to_node, e.metadata_json,
               n1.text as from_text, n1.depth as from_depth,
               n2.text as to_text, n2.depth as to_depth
        FROM edges e
        JOIN nodes n1 ON e.from_node = n1.id
        JOIN nodes n2 ON e.to_node = n2.id
        WHERE e.graph_id = ? AND e.edge_type = 'convergence'
        """,
        (graph_id,),
    )

    # Group convergence edges into clusters (simplified: each edge is a cluster)
    clusters = []
    for edge in edges:
        clusters.append({
            "nodes": [
                {"node_id": edge["from_node"], "text": edge["from_text"], "depth": edge["from_depth"]},
                {"node_id": edge["to_node"], "text": edge["to_text"], "depth": edge["to_depth"]},
            ],
            "insight": "",
            "edge_count": 1,
        })

    return {"clusters": clusters, "count": len(clusters)}


@router.get("/graphs/{graph_id}/contradictions")
async def get_contradictions(
    graph_id: str,
    _session: str = Depends(require_admin_auth),
):
    """Get contradiction pairs for a fractal graph."""
    graph = await query_fractal_db(
        "SELECT id FROM graphs WHERE id = ?", (graph_id,)
    )
    if not graph:
        return _error_response("GRAPH_NOT_FOUND", f"Graph '{graph_id}' not found", 404)

    edges = await query_fractal_db(
        """
        SELECT e.from_node, e.to_node, e.metadata_json,
               n1.text as from_text, n2.text as to_text
        FROM edges e
        JOIN nodes n1 ON e.from_node = n1.id
        JOIN nodes n2 ON e.to_node = n2.id
        WHERE e.graph_id = ? AND e.edge_type = 'contradiction'
        """,
        (graph_id,),
    )

    pairs = []
    for edge in edges:
        pairs.append({
            "node_a": {"node_id": edge["from_node"], "text": edge["from_text"]},
            "node_b": {"node_id": edge["to_node"], "text": edge["to_text"]},
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
    _session: str = Depends(require_admin_auth),
):
    """Get the chat log for a fractal node's work session."""
    rows = await query_fractal_db(
        "SELECT session_id, claimed_at, answered_at, synthesized_at FROM nodes WHERE id = ? AND graph_id = ?",
        (node_id, graph_id),
    )
    if not rows:
        # Fallback: try without graph_id constraint (handles stale frontend state)
        rows = await query_fractal_db(
            "SELECT session_id, claimed_at, answered_at, synthesized_at FROM nodes WHERE id = ?",
            (node_id,),
        )
    if not rows:
        return _error_response("NODE_NOT_FOUND", f"Node '{node_id}' not found", 404)

    node = rows[0]
    session_id = node["session_id"]
    claimed_at = node["claimed_at"]
    answered_at = node["answered_at"]
    synthesized_at = node["synthesized_at"]

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
