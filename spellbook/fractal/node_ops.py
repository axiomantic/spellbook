"""Node-level operations for the fractal thinking system.

Provides async functions for creating, updating, and managing nodes within
fractal exploration graphs using SQLAlchemy ORM models.
"""

import json
import uuid

from sqlalchemy import select, func, and_, text

from spellbook.db.fractal_models import FractalEdge, FractalGraph, FractalNode
from spellbook.fractal.models import (
    INTENSITY_BUDGETS,
    VALID_NODE_TYPES,
    VALID_SATURATION_REASONS,
)
from spellbook.fractal.schema import get_async_fractal_session


async def add_node(graph_id, parent_id, node_type, text, owner=None, metadata_json=None, db_path=None):
    """Add a new node to a fractal graph.

    Args:
        graph_id: ID of the graph to add the node to
        parent_id: ID of the parent node (None for root-level nodes)
        node_type: Type of node ("question" or "answer")
        text: The question or answer text
        owner: Optional agent that owns this node
        metadata_json: Optional JSON string of additional metadata
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with node_id, graph_id, parent_id, depth, node_type, status

    Raises:
        ValueError: If graph_id doesn't exist, node_type is invalid,
                    or parent_id doesn't exist
    """
    if node_type not in VALID_NODE_TYPES:
        raise ValueError(
            f"Invalid node_type '{node_type}'. "
            f"Must be one of: {VALID_NODE_TYPES}"
        )

    async with get_async_fractal_session(db_path) as session:
        # Validate graph exists and is active
        result = await session.execute(
            select(FractalGraph.status, FractalGraph.intensity).where(
                FractalGraph.id == graph_id
            )
        )
        row = result.one_or_none()
        if row is None:
            raise ValueError(f"Graph '{graph_id}' not found.")

        graph_status, intensity = row
        if graph_status != "active":
            raise ValueError(
                f"Cannot add node to graph with status '{graph_status}'. "
                f"Graph must be 'active'."
            )

        max_depth = INTENSITY_BUDGETS[intensity]["max_depth"]

        # Calculate depth and validate parent
        depth = 0
        parent_node_type = None
        parent_status = None
        if parent_id is not None:
            parent_result = await session.execute(
                select(FractalNode.depth, FractalNode.node_type, FractalNode.status).where(
                    and_(FractalNode.id == parent_id, FractalNode.graph_id == graph_id)
                )
            )
            parent_row = parent_result.one_or_none()
            if parent_row is None:
                raise ValueError(f"Parent node '{parent_id}' not found in graph '{graph_id}'.")
            depth = parent_row[0] + 1
            parent_node_type = parent_row[1]
            parent_status = parent_row[2]

        if depth >= max_depth:
            raise ValueError(
                f"Depth {depth} would exceed max_depth {max_depth} "
                f"for intensity '{intensity}'"
            )

        node_id = str(uuid.uuid4())

        new_node = FractalNode(
            id=node_id,
            graph_id=graph_id,
            parent_id=parent_id,
            node_type=node_type,
            text=text,
            owner=owner,
            depth=depth,
            status="open",
            metadata_json=metadata_json or "{}",
        )
        session.add(new_node)
        # Flush to persist the node before adding edges that reference it
        await session.flush()

        # Create parent_child edge if parent_id provided
        if parent_id is not None:
            edge = FractalEdge(
                graph_id=graph_id,
                from_node=parent_id,
                to_node=node_id,
                edge_type="parent_child",
            )
            session.add(edge)

            # Auto-transition: if adding answer to open/claimed question parent, mark parent as answered
            if node_type == "answer":
                if parent_node_type == "question" and parent_status in ("open", "claimed"):
                    parent_node_result = await session.execute(
                        select(FractalNode).where(FractalNode.id == parent_id)
                    )
                    parent_node = parent_node_result.scalar_one()
                    parent_node.status = "answered"
                    parent_node.answered_at = func.datetime("now")

    return {
        "node_id": node_id,
        "graph_id": graph_id,
        "parent_id": parent_id,
        "depth": depth,
        "node_type": node_type,
        "status": "open",
    }


async def update_node(graph_id, node_id, metadata_json, db_path=None):
    """Update a node's metadata and optionally create relationship edges.

    Shallow-merges new metadata into existing metadata (top-level key overwrite, not deep merge).
    If metadata contains "convergence_with" or "contradiction_with" keys
    (lists of node_ids), creates the corresponding edges.

    Args:
        graph_id: ID of the graph containing the node
        node_id: ID of the node to update
        metadata_json: JSON string of metadata to merge
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with node_id, metadata (merged dict), edges_created (int)

    Raises:
        ValueError: If graph or node doesn't exist, or edge targets don't exist
    """
    async with get_async_fractal_session(db_path) as session:
        # Validate graph exists
        graph_result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if graph_result.scalar_one_or_none() is None:
            raise ValueError(f"Graph '{graph_id}' not found.")

        # Validate node exists
        node_result = await session.execute(
            select(FractalNode).where(
                and_(FractalNode.id == node_id, FractalNode.graph_id == graph_id)
            )
        )
        node = node_result.scalar_one_or_none()
        if node is None:
            raise ValueError(f"Node '{node_id}' not found in graph '{graph_id}'.")

        # Merge metadata
        existing_meta = json.loads(node.metadata_json)
        try:
            new_meta = json.loads(metadata_json)
        except json.JSONDecodeError:
            raise ValueError("Invalid metadata_json: must be valid JSON string")
        existing_meta.update(new_meta)

        edges_created = 0

        # Handle convergence_with side effect
        convergence_targets = new_meta.get("convergence_with", [])
        for target_id in convergence_targets:
            target_result = await session.execute(
                select(FractalNode.id).where(
                    and_(FractalNode.id == target_id, FractalNode.graph_id == graph_id)
                )
            )
            if target_result.scalar_one_or_none() is None:
                raise ValueError(f"Node '{target_id}' not found in graph '{graph_id}'.")
            edge = FractalEdge(
                graph_id=graph_id,
                from_node=node_id,
                to_node=target_id,
                edge_type="convergence",
            )
            session.add(edge)
            edges_created += 1

        # Handle contradiction_with side effect
        contradiction_targets = new_meta.get("contradiction_with", [])
        for target_id in contradiction_targets:
            target_result = await session.execute(
                select(FractalNode.id).where(
                    and_(FractalNode.id == target_id, FractalNode.graph_id == graph_id)
                )
            )
            if target_result.scalar_one_or_none() is None:
                raise ValueError(f"Node '{target_id}' not found in graph '{graph_id}'.")
            edge = FractalEdge(
                graph_id=graph_id,
                from_node=node_id,
                to_node=target_id,
                edge_type="contradiction",
            )
            session.add(edge)
            edges_created += 1

        # Persist merged metadata
        node.metadata_json = json.dumps(existing_meta)

    return {
        "node_id": node_id,
        "metadata": existing_meta,
        "edges_created": edges_created,
    }


async def mark_saturated(graph_id, node_id, reason, db_path=None):
    """Mark a node as saturated with a given reason.

    Args:
        graph_id: ID of the graph containing the node
        node_id: ID of the node to mark as saturated
        reason: Saturation reason (must be in VALID_SATURATION_REASONS)
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with node_id, status ("saturated"), reason

    Raises:
        ValueError: If graph/node don't exist, reason is invalid,
                    or node status doesn't allow transition
    """
    if reason not in VALID_SATURATION_REASONS:
        raise ValueError(
            f"Invalid saturation reason '{reason}'. "
            f"Must be one of: {VALID_SATURATION_REASONS}"
        )

    async with get_async_fractal_session(db_path) as session:
        # Validate graph exists
        graph_result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if graph_result.scalar_one_or_none() is None:
            raise ValueError(f"Graph '{graph_id}' not found.")

        # Validate node exists and check current status
        node_result = await session.execute(
            select(FractalNode).where(
                and_(FractalNode.id == node_id, FractalNode.graph_id == graph_id)
            )
        )
        node = node_result.scalar_one_or_none()
        if node is None:
            raise ValueError(f"Node '{node_id}' not found in graph '{graph_id}'.")

        current_status = node.status
        if current_status not in ("open", "claimed", "answered"):
            raise ValueError(
                f"Cannot saturate node with status '{current_status}'. "
                f"Node must be 'open', 'claimed', or 'answered'."
            )

        # Update metadata with saturation reason
        existing_meta = json.loads(node.metadata_json)
        existing_meta["saturation_reason"] = reason

        # Update node
        node.status = "saturated"
        node.metadata_json = json.dumps(existing_meta)

    return {
        "node_id": node_id,
        "status": "saturated",
        "reason": reason,
    }


async def claim_work(graph_id, worker_id, db_path=None, session_id=None):
    """Atomically claim the next available open question node for a worker.

    Uses branch affinity to prefer sibling nodes of those already owned by
    the same worker, then prefers shallower nodes, then older nodes.

    Args:
        graph_id: ID of the graph to claim work from
        worker_id: ID of the worker claiming work
        db_path: Path to database file (defaults to standard location)
        session_id: Optional Claude Code session ID for chat log linking

    Returns:
        dict with node data and graph_done flag:
        - If work claimed: node_id, text, depth, parent_id, metadata, graph_done=False
        - If no open work but claimed nodes exist: node_id=None, graph_done=False
        - If no open and no claimed work: node_id=None, graph_done=True

    Raises:
        ValueError: If graph doesn't exist or is not active
    """
    async with get_async_fractal_session(db_path) as session:
        # Validate graph exists and is active
        graph_result = await session.execute(
            select(FractalGraph.status).where(FractalGraph.id == graph_id)
        )
        row = graph_result.one_or_none()
        if row is None:
            raise ValueError(f"Graph '{graph_id}' not found.")

        graph_status = row[0]
        if graph_status != "active":
            raise ValueError(
                f"Cannot claim work from graph with status '{graph_status}'. "
                f"Graph must be 'active'."
            )

        # Find the best candidate node to claim using raw SQL for the complex ORDER BY
        candidate_result = await session.execute(
            text("""
                SELECT n.id FROM nodes n
                WHERE n.graph_id = :graph_id AND n.node_type = 'question' AND n.status = 'open'
                ORDER BY
                    CASE WHEN EXISTS (
                        SELECT 1 FROM nodes sibling
                        WHERE sibling.parent_id = n.parent_id
                        AND sibling.owner = :worker_id
                    ) THEN 0 ELSE 1 END,
                    n.depth ASC,
                    n.created_at ASC
                LIMIT 1
            """),
            {"worker_id": worker_id, "graph_id": graph_id},
        )
        candidate = candidate_result.one_or_none()

        if candidate is None:
            # No open question nodes available -- check if there is in-flight work
            claimed_result = await session.execute(
                select(func.count()).select_from(FractalNode).where(
                    and_(
                        FractalNode.graph_id == graph_id,
                        FractalNode.status == "claimed",
                    )
                )
            )
            claimed_count = claimed_result.scalar()

            if claimed_count > 0:
                return {"node_id": None, "graph_done": False}
            else:
                return {"node_id": None, "graph_done": True}

        candidate_id = candidate[0]

        # Atomically claim the node
        node_result = await session.execute(
            select(FractalNode).where(FractalNode.id == candidate_id)
        )
        node = node_result.scalar_one()
        node.owner = worker_id
        node.status = "claimed"
        node.claimed_at = func.datetime("now")
        node.session_id = session_id

        # We need to flush to persist the changes before reading back
        await session.flush()

        return {
            "node_id": node.id,
            "text": node.text,
            "depth": node.depth,
            "parent_id": node.parent_id,
            "metadata": json.loads(node.metadata_json) if node.metadata_json else {},
            "graph_done": False,
        }


async def synthesize_node(graph_id, node_id, synthesis_text, db_path=None):
    """Mark a node as synthesized with synthesis text stored in metadata.

    Args:
        graph_id: ID of the graph containing the node
        node_id: ID of the node to synthesize
        synthesis_text: The synthesis text to store in metadata
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with node_id and status ("synthesized")

    Raises:
        ValueError: If graph/node don't exist, node status doesn't allow
                    synthesis, or child question nodes are not yet done
    """
    async with get_async_fractal_session(db_path) as session:
        # Validate graph exists and is active
        graph_result = await session.execute(
            select(FractalGraph.status).where(FractalGraph.id == graph_id)
        )
        row = graph_result.one_or_none()
        if row is None:
            raise ValueError(f"Graph '{graph_id}' not found.")

        graph_status = row[0]
        if graph_status != "active":
            raise ValueError(
                f"Cannot synthesize node in graph with status '{graph_status}'. "
                f"Graph must be 'active'."
            )

        # Validate node exists and check status
        node_result = await session.execute(
            select(FractalNode).where(
                and_(FractalNode.id == node_id, FractalNode.graph_id == graph_id)
            )
        )
        node = node_result.scalar_one_or_none()
        if node is None:
            raise ValueError(f"Node '{node_id}' not found in graph '{graph_id}'.")

        current_status = node.status
        if current_status not in ("answered", "claimed"):
            raise ValueError(
                f"Cannot synthesize node with status '{current_status}'. "
                f"Node must be 'answered' or 'claimed'."
            )

        # Validate all child question nodes are synthesized or saturated
        incomplete_result = await session.execute(
            select(func.count()).select_from(FractalNode).where(
                and_(
                    FractalNode.parent_id == node_id,
                    FractalNode.graph_id == graph_id,
                    FractalNode.node_type == "question",
                    FractalNode.status.not_in(["synthesized", "saturated"]),
                )
            )
        )
        incomplete_children = incomplete_result.scalar()

        # Check if node actually has children
        total_result = await session.execute(
            select(func.count()).select_from(FractalNode).where(
                and_(
                    FractalNode.parent_id == node_id,
                    FractalNode.graph_id == graph_id,
                    FractalNode.node_type == "question",
                )
            )
        )
        total_children = total_result.scalar()

        if incomplete_children > 0 and total_children > 0:
            raise ValueError(
                f"Cannot synthesize node '{node_id}': "
                f"{incomplete_children} child question node(s) not yet complete."
            )

        # Update metadata with synthesis text
        existing_meta = json.loads(node.metadata_json) if node.metadata_json else {}
        existing_meta["synthesis"] = synthesis_text

        # Update node status and metadata
        node.status = "synthesized"
        node.synthesized_at = func.datetime("now")
        node.metadata_json = json.dumps(existing_meta)

    return {
        "node_id": node_id,
        "status": "synthesized",
    }
