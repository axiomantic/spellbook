"""Graph-level operations for the fractal thinking system.

Provides async functions for creating, resuming, deleting, and updating
fractal exploration graphs using SQLAlchemy ORM models.
"""

import json
import uuid

from sqlalchemy import delete, select, func

from spellbook.db.fractal_models import FractalEdge, FractalGraph, FractalNode
from spellbook.fractal.models import (
    INTENSITY_BUDGETS,
    VALID_INTENSITIES,
    validate_checkpoint_mode,
)
from spellbook.fractal.schema import get_async_fractal_session

# Valid status transitions: {from_status: [allowed_to_statuses]}
VALID_TRANSITIONS = {
    "active": ["completed", "paused", "error", "budget_exhausted"],
    "paused": ["active"],
    "budget_exhausted": ["active", "completed"],
}

# Terminal states that cannot be resumed
TERMINAL_STATES = ["completed", "error", "budget_exhausted"]


async def create_graph(seed, intensity, checkpoint_mode, metadata_json=None, project_dir=None, db_path=None):
    """Create a new fractal exploration graph with a root question node.

    Args:
        seed: The initial question to explore
        intensity: Exploration intensity ("pulse", "explore", "deep")
        checkpoint_mode: When to pause for human review
        metadata_json: Optional JSON string of metadata to store
        project_dir: Optional project directory path associated with this graph
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, root_node_id, intensity, checkpoint_mode, budget, status
        or dict with "error" key if validation fails
    """
    if intensity not in VALID_INTENSITIES:
        return {
            "error": f"Invalid intensity '{intensity}'. "
            f"Must be one of: {VALID_INTENSITIES}"
        }

    if not validate_checkpoint_mode(checkpoint_mode):
        return {"error": f"Invalid checkpoint_mode '{checkpoint_mode}'."}

    if metadata_json is None:
        metadata_json = "{}"

    graph_id = str(uuid.uuid4())
    root_node_id = str(uuid.uuid4())

    async with get_async_fractal_session(db_path) as session:
        graph = FractalGraph(
            id=graph_id,
            seed=seed,
            intensity=intensity,
            checkpoint_mode=checkpoint_mode,
            metadata_json=metadata_json,
            project_dir=project_dir,
        )
        session.add(graph)

        root_node = FractalNode(
            id=root_node_id,
            graph_id=graph_id,
            node_type="question",
            text=seed,
            depth=0,
            status="open",
        )
        session.add(root_node)

    return {
        "graph_id": graph_id,
        "root_node_id": root_node_id,
        "intensity": intensity,
        "checkpoint_mode": checkpoint_mode,
        "budget": INTENSITY_BUDGETS[intensity],
        "status": "active",
    }


async def resume_graph(graph_id, db_path=None):
    """Resume a fractal exploration graph.

    If the graph is paused, transitions it to active. If already active,
    returns the current state as a no-op. Rejects terminal states.

    Args:
        graph_id: ID of the graph to resume
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph snapshot (graph_id, seed, status, intensity, nodes, edges)
        or dict with "error" key if graph not found or in terminal state
    """
    async with get_async_fractal_session(db_path) as session:
        result = await session.execute(
            select(FractalGraph).where(FractalGraph.id == graph_id)
        )
        graph = result.scalar_one_or_none()

        if graph is None:
            return {"error": f"Graph '{graph_id}' not found."}

        current_status = graph.status

        if current_status in TERMINAL_STATES:
            return {
                "error": f"Cannot resume graph in '{current_status}' state. "
                f"Terminal states are: {TERMINAL_STATES}"
            }

        if current_status == "paused":
            graph.status = "active"
            graph.updated_at = func.datetime("now")
            current_status = "active"

        # Fetch nodes
        node_result = await session.execute(
            select(FractalNode).where(FractalNode.graph_id == graph_id)
        )
        node_rows = node_result.scalars().all()
        nodes = []
        for node in node_rows:
            nodes.append({
                "id": node.id,
                "graph_id": node.graph_id,
                "parent_id": node.parent_id,
                "node_type": node.node_type,
                "text": node.text,
                "owner": node.owner,
                "depth": node.depth,
                "status": node.status,
                "metadata": json.loads(node.metadata_json) if node.metadata_json else {},
                "created_at": node.created_at,
            })

        # Fetch edges
        edge_result = await session.execute(
            select(FractalEdge).where(FractalEdge.graph_id == graph_id)
        )
        edge_rows = edge_result.scalars().all()
        edges = []
        for edge in edge_rows:
            edges.append({
                "id": edge.id,
                "graph_id": edge.graph_id,
                "from_node": edge.from_node,
                "to_node": edge.to_node,
                "edge_type": edge.edge_type,
                "metadata": json.loads(edge.metadata_json) if edge.metadata_json else {},
                "created_at": edge.created_at,
            })

        return {
            "graph_id": graph_id,
            "seed": graph.seed,
            "status": current_status,
            "intensity": graph.intensity,
            "checkpoint_mode": graph.checkpoint_mode,
            "metadata": json.loads(graph.metadata_json) if graph.metadata_json else {},
            "nodes": nodes,
            "edges": edges,
        }


async def delete_graph(graph_id, db_path=None):
    """Delete a fractal exploration graph and all its nodes/edges via CASCADE.

    Args:
        graph_id: ID of the graph to delete
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with deleted=True and graph_id, or dict with "error" key if not found
    """
    async with get_async_fractal_session(db_path) as session:
        # Check existence first
        result = await session.execute(
            select(FractalGraph.id).where(FractalGraph.id == graph_id)
        )
        if result.scalar_one_or_none() is None:
            return {"error": f"Graph '{graph_id}' not found."}

        # Use SQL DELETE to let database CASCADE handle related rows
        await session.execute(
            delete(FractalGraph).where(FractalGraph.id == graph_id)
        )

    return {"deleted": True, "graph_id": graph_id}


async def update_graph_status(graph_id, status, reason=None, db_path=None):
    """Update the status of a fractal exploration graph.

    Validates status transitions according to VALID_TRANSITIONS.
    Optionally stores a reason in metadata_json.

    Args:
        graph_id: ID of the graph to update
        status: New status to set
        reason: Optional reason for the status change
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with graph_id, status, previous_status
        or dict with "error" key if invalid transition or not found
    """
    async with get_async_fractal_session(db_path) as session:
        result = await session.execute(
            select(FractalGraph).where(FractalGraph.id == graph_id)
        )
        graph = result.scalar_one_or_none()

        if graph is None:
            return {"error": f"Graph '{graph_id}' not found."}

        previous_status = graph.status
        current_metadata = graph.metadata_json or "{}"

        # Validate transition
        allowed = VALID_TRANSITIONS.get(previous_status, [])
        if status not in allowed:
            return {
                "error": f"Invalid transition from '{previous_status}' to '{status}'. "
                f"Allowed transitions from '{previous_status}': {allowed}"
            }

        # Store reason in metadata if provided
        if reason is not None:
            metadata = json.loads(current_metadata)
            metadata["status_reason"] = reason
            current_metadata = json.dumps(metadata)

        graph.status = status
        graph.metadata_json = current_metadata
        graph.updated_at = func.datetime("now")

    return {
        "graph_id": graph_id,
        "status": status,
        "previous_status": previous_status,
    }
