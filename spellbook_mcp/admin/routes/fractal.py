"""Fractal graph explorer API routes.

Provides graph listing, detail, node/edge queries, and pre-formatted
Cytoscape.js data for the interactive graph visualization.
"""

import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from spellbook_mcp.admin.auth import require_admin_auth
from spellbook_mcp.admin.db import query_fractal_db

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
               n.parent_id, n.metadata_json, n.created_at
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
               n.parent_id, n.owner
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
                "label": n["text"][:80] if n["text"] else "",
                "type": node_type,
                "status": status,
                "depth": n["depth"],
                "parent_id": n["parent_id"],
                "owner": n["owner"],
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
