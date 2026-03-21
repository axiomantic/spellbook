"""Query operations for the fractal thinking system.

Provides async read-only query functions for inspecting fractal exploration
graphs, including snapshots, branches, open questions, convergence
points, contradictions, and saturation status. Uses SQLAlchemy ORM models.
"""

import json

from sqlalchemy import select, func, and_, text

from spellbook.db.fractal_models import FractalEdge, FractalGraph, FractalNode
from spellbook.fractal.schema import get_async_fractal_session


def _row_to_node(node):
    """Convert a FractalNode ORM instance to a dict with parsed metadata."""
    return {
        "node_id": node.id,
        "parent_id": node.parent_id,
        "node_type": node.node_type,
        "text": node.text,
        "owner": node.owner,
        "depth": node.depth,
        "status": node.status,
        "metadata": json.loads(node.metadata_json) if node.metadata_json else {},
        "created_at": node.created_at,
    }


def _edge_to_dict(edge):
    """Convert a FractalEdge ORM instance to a dict with parsed metadata."""
    return {
        "from_node": edge.from_node,
        "to_node": edge.to_node,
        "edge_type": edge.edge_type,
        "metadata": json.loads(edge.metadata_json) if edge.metadata_json else {},
    }


async def get_snapshot(graph_id, db_path=None):
    """Return full graph snapshot including all nodes, edges, and metadata.

    Args:
        graph_id: ID of the graph to snapshot
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, seed, intensity, status, nodes, edges, metadata
        or dict with "error" key if graph not found
    """
    async with get_async_fractal_session(db_path) as session:
        graph_result = await session.execute(
            select(FractalGraph).where(FractalGraph.id == graph_id)
        )
        graph = graph_result.scalar_one_or_none()
        if graph is None:
            return {"error": f"Graph '{graph_id}' not found."}

        node_result = await session.execute(
            select(FractalNode).where(FractalNode.graph_id == graph_id)
        )
        nodes = [_row_to_node(n) for n in node_result.scalars().all()]

        edge_result = await session.execute(
            select(FractalEdge).where(FractalEdge.graph_id == graph_id)
        )
        edges = [_edge_to_dict(e) for e in edge_result.scalars().all()]

        return {
            "graph_id": graph_id,
            "seed": graph.seed,
            "intensity": graph.intensity,
            "status": graph.status,
            "nodes": nodes,
            "edges": edges,
            "metadata": json.loads(graph.metadata_json) if graph.metadata_json else {},
        }


async def get_branch(graph_id, node_id, db_path=None):
    """Return subtree rooted at node_id using recursive CTE.

    Args:
        graph_id: ID of the graph containing the node
        node_id: ID of the root node of the desired subtree
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with nodes and edges within the subtree
        or dict with "error" key if graph or node not found
    """
    async with get_async_fractal_session(db_path) as session:
        # Check graph exists
        graph_result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if graph_result.scalar_one_or_none() is None:
            return {"error": f"Graph '{graph_id}' not found."}

        # Check that the node exists in this graph
        node_check = await session.execute(
            select(FractalNode.id).where(
                and_(FractalNode.id == node_id, FractalNode.graph_id == graph_id)
            )
        )
        if node_check.scalar_one_or_none() is None:
            return {"error": f"Node '{node_id}' not found in graph '{graph_id}'."}

        # Recursive CTE to get subtree - use raw SQL for the recursive query
        subtree_result = await session.execute(
            text("""
                WITH RECURSIVE subtree AS (
                    SELECT id, parent_id, node_type, text, owner, depth, status,
                           metadata_json, created_at
                    FROM nodes
                    WHERE id = :node_id AND graph_id = :graph_id
                    UNION ALL
                    SELECT n.id, n.parent_id, n.node_type, n.text, n.owner, n.depth,
                           n.status, n.metadata_json, n.created_at
                    FROM nodes n
                    JOIN subtree s ON n.parent_id = s.id
                    WHERE n.graph_id = :graph_id
                )
                SELECT * FROM subtree
            """),
            {"node_id": node_id, "graph_id": graph_id},
        )

        nodes = []
        node_ids = set()
        for row in subtree_result.all():
            node_ids.add(row[0])
            nodes.append({
                "node_id": row[0],
                "parent_id": row[1],
                "node_type": row[2],
                "text": row[3],
                "owner": row[4],
                "depth": row[5],
                "status": row[6],
                "metadata": json.loads(row[7]) if row[7] else {},
                "created_at": row[8],
            })

        # Fetch all edges for the graph, then filter to subtree
        edge_result = await session.execute(
            select(FractalEdge).where(FractalEdge.graph_id == graph_id)
        )
        all_edges = [_edge_to_dict(e) for e in edge_result.scalars().all()]
        subtree_edges = [
            e for e in all_edges
            if e["from_node"] in node_ids and e["to_node"] in node_ids
        ]

        return {
            "graph_id": graph_id,
            "nodes": nodes,
            "edges": subtree_edges,
        }


async def get_open_questions(graph_id, db_path=None):
    """Return nodes where node_type='question' AND status='open'.

    Args:
        graph_id: ID of the graph to query
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, open_questions list, and count
        or dict with "error" key if graph not found
    """
    async with get_async_fractal_session(db_path) as session:
        graph_result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if graph_result.scalar_one_or_none() is None:
            return {"error": f"Graph '{graph_id}' not found."}

        node_result = await session.execute(
            select(FractalNode).where(
                and_(
                    FractalNode.graph_id == graph_id,
                    FractalNode.node_type == "question",
                    FractalNode.status == "open",
                )
            )
        )
        open_questions = [_row_to_node(n) for n in node_result.scalars().all()]

        return {
            "graph_id": graph_id,
            "open_questions": open_questions,
            "count": len(open_questions),
        }


async def query_convergence(graph_id, db_path=None):
    """Find all convergence edges and group by convergence cluster.

    Args:
        graph_id: ID of the graph to query
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, convergence_points list, and count
        or dict with "error" key if graph not found
    """
    async with get_async_fractal_session(db_path) as session:
        graph_result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if graph_result.scalar_one_or_none() is None:
            return {"error": f"Graph '{graph_id}' not found."}

        edge_result = await session.execute(
            select(FractalEdge).where(
                and_(
                    FractalEdge.graph_id == graph_id,
                    FractalEdge.edge_type == "convergence",
                )
            )
        )
        edges = edge_result.scalars().all()

        # Build convergence clusters using union-find approach
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

        edge_node_ids = set()
        for edge in edges:
            from_node, to_node = edge.from_node, edge.to_node
            edge_node_ids.add(from_node)
            edge_node_ids.add(to_node)
            union(from_node, to_node)

        # Group nodes by cluster root
        clusters = {}
        for nid in edge_node_ids:
            root = find(nid)
            if root not in clusters:
                clusters[root] = set()
            clusters[root].add(nid)

        # For each cluster, find the convergence_insight from any member's metadata
        convergence_points = []
        for cluster_nodes in clusters.values():
            insight = None
            for nid in cluster_nodes:
                node_result = await session.execute(
                    select(FractalNode.metadata_json).where(FractalNode.id == nid)
                )
                node_row = node_result.scalar_one_or_none()
                if node_row:
                    meta = json.loads(node_row)
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


async def query_contradictions(graph_id, db_path=None):
    """Find all contradiction edges and extract tension metadata.

    Args:
        graph_id: ID of the graph to query
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, contradictions list, and count
        or dict with "error" key if graph not found
    """
    async with get_async_fractal_session(db_path) as session:
        graph_result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if graph_result.scalar_one_or_none() is None:
            return {"error": f"Graph '{graph_id}' not found."}

        edge_result = await session.execute(
            select(FractalEdge).where(
                and_(
                    FractalEdge.graph_id == graph_id,
                    FractalEdge.edge_type == "contradiction",
                )
            )
        )
        edges = edge_result.scalars().all()

        contradictions = []
        for edge in edges:
            from_node, to_node = edge.from_node, edge.to_node
            nodes = sorted([from_node, to_node])

            # Look for contradiction_tension in either node's metadata
            tension = None
            for nid in [from_node, to_node]:
                node_result = await session.execute(
                    select(FractalNode.metadata_json).where(FractalNode.id == nid)
                )
                node_row = node_result.scalar_one_or_none()
                if node_row:
                    meta = json.loads(node_row)
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


async def get_saturation_status(graph_id, db_path=None):
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
    async with get_async_fractal_session(db_path) as session:
        graph_result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if graph_result.scalar_one_or_none() is None:
            return {"error": f"Graph '{graph_id}' not found."}

        # Get top-level branches (depth=1 nodes)
        branch_result = await session.execute(
            select(FractalNode).where(
                and_(FractalNode.graph_id == graph_id, FractalNode.depth == 1)
            )
        )
        branch_nodes = branch_result.scalars().all()

        branches = []
        for branch in branch_nodes:
            branch_meta = json.loads(branch.metadata_json) if branch.metadata_json else {}

            saturated = branch.status in ("saturated", "synthesized")
            saturation_reason = branch_meta.get("saturation_reason")

            # Count open questions in this branch's subtree using recursive CTE
            open_count_result = await session.execute(
                text("""
                    WITH RECURSIVE subtree AS (
                        SELECT id, node_type, status
                        FROM nodes
                        WHERE id = :branch_id AND graph_id = :graph_id
                        UNION ALL
                        SELECT n.id, n.node_type, n.status
                        FROM nodes n
                        JOIN subtree s ON n.parent_id = s.id
                        WHERE n.graph_id = :graph_id
                    )
                    SELECT COUNT(*) FROM subtree
                    WHERE node_type = 'question' AND status = 'open'
                """),
                {"branch_id": branch.id, "graph_id": graph_id},
            )
            open_count = open_count_result.scalar()

            branches.append({
                "node_id": branch.id,
                "text": branch.text,
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


async def get_claimable_work(graph_id, worker_id=None, db_path=None):
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
    async with get_async_fractal_session(db_path) as session:
        graph_result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if graph_result.scalar_one_or_none() is None:
            return {"error": f"Graph '{graph_id}' not found."}

        if worker_id is not None:
            # Use raw SQL for the complex ORDER BY with subquery
            node_result = await session.execute(
                text("""
                    SELECT id, parent_id, node_type, text, owner, depth, status,
                           metadata_json, created_at
                    FROM nodes n
                    WHERE n.graph_id = :graph_id AND n.node_type = 'question' AND n.status = 'open'
                    ORDER BY
                        CASE WHEN EXISTS (
                            SELECT 1 FROM nodes sibling
                            WHERE sibling.parent_id = n.parent_id
                            AND sibling.owner = :worker_id
                        ) THEN 0 ELSE 1 END,
                        n.depth ASC,
                        n.created_at ASC
                """),
                {"worker_id": worker_id, "graph_id": graph_id},
            )
            claimable = []
            for row in node_result.all():
                claimable.append({
                    "node_id": row[0],
                    "parent_id": row[1],
                    "node_type": row[2],
                    "text": row[3],
                    "owner": row[4],
                    "depth": row[5],
                    "status": row[6],
                    "metadata": json.loads(row[7]) if row[7] else {},
                    "created_at": row[8],
                })
        else:
            node_result = await session.execute(
                select(FractalNode).where(
                    and_(
                        FractalNode.graph_id == graph_id,
                        FractalNode.node_type == "question",
                        FractalNode.status == "open",
                    )
                ).order_by(FractalNode.depth.asc(), FractalNode.created_at.asc())
            )
            claimable = [_row_to_node(n) for n in node_result.scalars().all()]

        return {
            "graph_id": graph_id,
            "claimable": claimable,
            "count": len(claimable),
        }


async def get_ready_to_synthesize(graph_id, db_path=None):
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
    async with get_async_fractal_session(db_path) as session:
        graph_result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if graph_result.scalar_one_or_none() is None:
            return {"error": f"Graph '{graph_id}' not found."}

        # Use raw SQL for the complex subquery conditions
        ready_result = await session.execute(
            text("""
                SELECT id, parent_id, node_type, text, owner, depth, status,
                       metadata_json, created_at
                FROM nodes n
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
            """),
            {"graph_id": graph_id},
        )

        ready_nodes = []
        for row in ready_result.all():
            ready_nodes.append({
                "node_id": row[0],
                "parent_id": row[1],
                "node_type": row[2],
                "text": row[3],
                "owner": row[4],
                "depth": row[5],
                "status": row[6],
                "metadata": json.loads(row[7]) if row[7] else {},
                "created_at": row[8],
            })

        return {
            "graph_id": graph_id,
            "ready_nodes": ready_nodes,
            "count": len(ready_nodes),
        }
