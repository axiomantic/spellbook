"""Query operations for the fractal thinking system.

Provides read-only query functions for inspecting fractal exploration
graphs, including snapshots, branches, open questions, convergence
points, contradictions, and saturation status.
"""

import json

from spellbook_mcp.fractal.schema import get_fractal_connection


def _graph_exists(cursor, graph_id):
    """Check if a graph exists. Returns the row or None."""
    cursor.execute(
        "SELECT id, seed, intensity, checkpoint_mode, status, metadata_json "
        "FROM graphs WHERE id = ?",
        (graph_id,),
    )
    return cursor.fetchone()


def _row_to_node(row):
    """Convert a node database row to a dict with parsed metadata.

    Expected column order: id, parent_id, node_type, text, owner,
    depth, status, metadata_json, created_at.
    """
    return {
        "node_id": row[0],
        "parent_id": row[1],
        "node_type": row[2],
        "text": row[3],
        "owner": row[4],
        "depth": row[5],
        "status": row[6],
        "metadata": json.loads(row[7]),
        "created_at": row[8],
    }


_NODE_COLUMNS = (
    "id, parent_id, node_type, text, owner, depth, status, "
    "metadata_json, created_at"
)

# Same columns but table-qualified for use in queries with JOINs or subqueries
_NODE_COLUMNS_QUALIFIED = (
    "n.id, n.parent_id, n.node_type, n.text, n.owner, n.depth, n.status, "
    "n.metadata_json, n.created_at"
)


def _fetch_nodes(cursor, graph_id):
    """Fetch all nodes for a graph, returning list of dicts with parsed metadata."""
    cursor.execute(
        f"SELECT {_NODE_COLUMNS} FROM nodes WHERE graph_id = ?",
        (graph_id,),
    )
    return [_row_to_node(row) for row in cursor.fetchall()]


def _fetch_edges(cursor, graph_id):
    """Fetch all edges for a graph, returning list of dicts with parsed metadata."""
    cursor.execute(
        "SELECT from_node, to_node, edge_type, metadata_json "
        "FROM edges WHERE graph_id = ?",
        (graph_id,),
    )
    edges = []
    for row in cursor.fetchall():
        edges.append({
            "from_node": row[0],
            "to_node": row[1],
            "edge_type": row[2],
            "metadata": json.loads(row[3]),
        })
    return edges


def get_snapshot(graph_id, db_path=None):
    """Return full graph snapshot including all nodes, edges, and metadata.

    Args:
        graph_id: ID of the graph to snapshot
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, seed, intensity, status, nodes, edges, metadata
        or dict with "error" key if graph not found
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    graph_row = _graph_exists(cursor, graph_id)
    if graph_row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    nodes = _fetch_nodes(cursor, graph_id)
    edges = _fetch_edges(cursor, graph_id)

    return {
        "graph_id": graph_id,
        "seed": graph_row[1],
        "intensity": graph_row[2],
        "status": graph_row[4],
        "nodes": nodes,
        "edges": edges,
        "metadata": json.loads(graph_row[5]),
    }


def get_branch(graph_id, node_id, db_path=None):
    """Return subtree rooted at node_id using recursive CTE.

    Args:
        graph_id: ID of the graph containing the node
        node_id: ID of the root node of the desired subtree
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with nodes and edges within the subtree
        or dict with "error" key if graph or node not found
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    graph_row = _graph_exists(cursor, graph_id)
    if graph_row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    # Check that the node exists in this graph
    cursor.execute(
        "SELECT id FROM nodes WHERE id = ? AND graph_id = ?",
        (node_id, graph_id),
    )
    if cursor.fetchone() is None:
        return {"error": f"Node '{node_id}' not found in graph '{graph_id}'."}

    # Recursive CTE to get subtree
    cursor.execute(
        """
        WITH RECURSIVE subtree AS (
            SELECT id, parent_id, node_type, text, owner, depth, status,
                   metadata_json, created_at
            FROM nodes
            WHERE id = ? AND graph_id = ?
            UNION ALL
            SELECT n.id, n.parent_id, n.node_type, n.text, n.owner, n.depth,
                   n.status, n.metadata_json, n.created_at
            FROM nodes n
            JOIN subtree s ON n.parent_id = s.id
            WHERE n.graph_id = ?
        )
        SELECT * FROM subtree
        """,
        (node_id, graph_id, graph_id),
    )

    nodes = []
    node_ids = set()
    for row in cursor.fetchall():
        node_ids.add(row[0])
        nodes.append(_row_to_node(row))

    # Fetch edges where both endpoints are in the subtree
    all_edges = _fetch_edges(cursor, graph_id)
    subtree_edges = [
        e for e in all_edges
        if e["from_node"] in node_ids and e["to_node"] in node_ids
    ]

    return {
        "graph_id": graph_id,
        "nodes": nodes,
        "edges": subtree_edges,
    }


def get_open_questions(graph_id, db_path=None):
    """Return nodes where node_type='question' AND status='open'.

    Args:
        graph_id: ID of the graph to query
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, open_questions list, and count
        or dict with "error" key if graph not found
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    graph_row = _graph_exists(cursor, graph_id)
    if graph_row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    cursor.execute(
        f"SELECT {_NODE_COLUMNS} FROM nodes "
        "WHERE graph_id = ? AND node_type = 'question' AND status = 'open'",
        (graph_id,),
    )

    open_questions = [_row_to_node(row) for row in cursor.fetchall()]

    return {
        "graph_id": graph_id,
        "open_questions": open_questions,
        "count": len(open_questions),
    }


def query_convergence(graph_id, db_path=None):
    """Find all convergence edges and group by convergence cluster.

    Args:
        graph_id: ID of the graph to query
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, convergence_points list, and count
        or dict with "error" key if graph not found
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    graph_row = _graph_exists(cursor, graph_id)
    if graph_row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    cursor.execute(
        "SELECT from_node, to_node, metadata_json "
        "FROM edges WHERE graph_id = ? AND edge_type = 'convergence'",
        (graph_id,),
    )

    # Build convergence clusters using union-find approach
    # Each convergence edge connects two nodes; nodes connected
    # transitively form a cluster.
    parent_map = {}

    def find(x):
        while parent_map.get(x, x) != x:
            parent_map[x] = parent_map.get(parent_map[x], parent_map[x])
            x = parent_map[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent_map[ra] = rb

    edges = cursor.fetchall()
    # Track which nodes participate in convergence edges
    edge_node_ids = set()
    for row in edges:
        from_node, to_node = row[0], row[1]
        edge_node_ids.add(from_node)
        edge_node_ids.add(to_node)
        union(from_node, to_node)

    # Group nodes by cluster root
    clusters = {}
    for node_id in edge_node_ids:
        root = find(node_id)
        if root not in clusters:
            clusters[root] = set()
        clusters[root].add(node_id)

    # For each cluster, find the convergence_insight from any member's metadata
    convergence_points = []
    for cluster_nodes in clusters.values():
        insight = None
        for nid in cluster_nodes:
            cursor.execute(
                "SELECT metadata_json FROM nodes WHERE id = ?",
                (nid,),
            )
            node_row = cursor.fetchone()
            if node_row:
                meta = json.loads(node_row[0])
                if "convergence_insight" in meta:
                    insight = meta["convergence_insight"]
                    break

        convergence_points.append({
            "nodes": sorted(cluster_nodes),
            "insight": insight,
        })

    return {
        "graph_id": graph_id,
        "convergence_points": convergence_points,
        "count": len(convergence_points),
    }


def query_contradictions(graph_id, db_path=None):
    """Find all contradiction edges and extract tension metadata.

    Args:
        graph_id: ID of the graph to query
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, contradictions list, and count
        or dict with "error" key if graph not found
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    graph_row = _graph_exists(cursor, graph_id)
    if graph_row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    cursor.execute(
        "SELECT from_node, to_node, metadata_json "
        "FROM edges WHERE graph_id = ? AND edge_type = 'contradiction'",
        (graph_id,),
    )

    contradictions = []
    for row in cursor.fetchall():
        from_node, to_node = row[0], row[1]
        nodes = sorted([from_node, to_node])

        # Look for contradiction_tension in either node's metadata
        tension = None
        for nid in [from_node, to_node]:
            cursor.execute(
                "SELECT metadata_json FROM nodes WHERE id = ?",
                (nid,),
            )
            node_row = cursor.fetchone()
            if node_row:
                meta = json.loads(node_row[0])
                if "contradiction_tension" in meta:
                    tension = meta["contradiction_tension"]
                    break

        contradictions.append({
            "nodes": nodes,
            "tension": tension,
        })

    return {
        "graph_id": graph_id,
        "contradictions": contradictions,
        "count": len(contradictions),
    }


def get_saturation_status(graph_id, db_path=None):
    """Identify top-level branches and their saturation status.

    Top-level branches are depth=1 nodes (direct children of root).
    For each branch, reports whether it is saturated, its saturation
    reason, and the count of open questions in its subtree.

    Args:
        graph_id: ID of the graph to query
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, branches list, and all_saturated flag
        or dict with "error" key if graph not found
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    graph_row = _graph_exists(cursor, graph_id)
    if graph_row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    # Get top-level branches (depth=1 nodes)
    cursor.execute(
        "SELECT id, text, status, metadata_json "
        "FROM nodes WHERE graph_id = ? AND depth = 1",
        (graph_id,),
    )

    branches = []
    for row in cursor.fetchall():
        branch_id = row[0]
        branch_text = row[1]
        branch_status = row[2]
        branch_meta = json.loads(row[3])

        saturated = branch_status in ("saturated", "synthesized")
        saturation_reason = branch_meta.get("saturation_reason")

        # Count open questions in this branch's subtree using recursive CTE
        cursor.execute(
            """
            WITH RECURSIVE subtree AS (
                SELECT id, node_type, status
                FROM nodes
                WHERE id = ? AND graph_id = ?
                UNION ALL
                SELECT n.id, n.node_type, n.status
                FROM nodes n
                JOIN subtree s ON n.parent_id = s.id
                WHERE n.graph_id = ?
            )
            SELECT COUNT(*) FROM subtree
            WHERE node_type = 'question' AND status = 'open'
            """,
            (branch_id, graph_id, graph_id),
        )
        open_count = cursor.fetchone()[0]

        branches.append({
            "node_id": branch_id,
            "text": branch_text,
            "saturated": saturated,
            "saturation_reason": saturation_reason,
            "open_questions": open_count,
        })

    all_saturated = len(branches) > 0 and all(b["saturated"] for b in branches)
    all_complete = len(branches) > 0 and all(b["saturated"] for b in branches)

    return {
        "graph_id": graph_id,
        "branches": branches,
        "all_saturated": all_saturated,
        "all_complete": all_complete,
    }


def get_claimable_work(graph_id, worker_id=None, db_path=None):
    """Preview available work in a fractal graph with optional branch affinity ordering.

    Returns open question nodes ordered by branch affinity (if worker_id
    provided), then by depth (shallower first), then by creation time.

    Args:
        graph_id: ID of the graph to query
        worker_id: Optional worker ID for branch affinity ordering
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, claimable list, and count
        or dict with "error" key if graph not found
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    graph_row = _graph_exists(cursor, graph_id)
    if graph_row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    if worker_id is not None:
        cursor.execute(
            f"""
            SELECT {_NODE_COLUMNS_QUALIFIED} FROM nodes n
            WHERE n.graph_id = :graph_id AND n.node_type = 'question' AND n.status = 'open'
            ORDER BY
                CASE WHEN EXISTS (
                    SELECT 1 FROM nodes sibling
                    WHERE sibling.parent_id = n.parent_id
                    AND sibling.owner = :worker_id
                ) THEN 0 ELSE 1 END,
                n.depth ASC,
                n.created_at ASC
            """,
            {"worker_id": worker_id, "graph_id": graph_id},
        )
    else:
        cursor.execute(
            f"SELECT {_NODE_COLUMNS} FROM nodes "
            "WHERE graph_id = ? AND node_type = 'question' AND status = 'open' "
            "ORDER BY depth ASC, created_at ASC",
            (graph_id,),
        )

    claimable = [_row_to_node(row) for row in cursor.fetchall()]

    return {
        "graph_id": graph_id,
        "claimable": claimable,
        "count": len(claimable),
    }


def get_ready_to_synthesize(graph_id, db_path=None):
    """Find non-leaf answered nodes where all child questions are done.

    A node is ready for synthesis when:
    - It has status 'answered'
    - It has at least one child question node (not a leaf)
    - All its child question nodes have status 'synthesized' or 'saturated'

    Results are ordered deepest-first (bottom-up) so synthesis can
    proceed from leaves toward the root.

    Args:
        graph_id: ID of the graph to query
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, ready_nodes list, and count
        or dict with "error" key if graph not found
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    graph_row = _graph_exists(cursor, graph_id)
    if graph_row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    # Find nodes that have child question nodes, where ALL child question
    # nodes are in terminal states (synthesized or saturated), and the
    # parent itself is answered.
    cursor.execute(
        f"""
        SELECT {_NODE_COLUMNS_QUALIFIED} FROM nodes n
        WHERE n.graph_id = :graph_id
          AND n.status = 'answered'
          AND EXISTS (
            SELECT 1 FROM nodes child
            WHERE child.parent_id = n.id AND child.graph_id = :graph_id
            AND child.node_type = 'question'
          )
          AND NOT EXISTS (
            SELECT 1 FROM nodes child
            WHERE child.parent_id = n.id AND child.graph_id = :graph_id
            AND child.node_type = 'question'
            AND child.status NOT IN ('synthesized', 'saturated')
          )
        ORDER BY n.depth DESC, n.created_at ASC
        """,
        {"graph_id": graph_id},
    )

    ready_nodes = [_row_to_node(row) for row in cursor.fetchall()]

    return {
        "graph_id": graph_id,
        "ready_nodes": ready_nodes,
        "count": len(ready_nodes),
    }
