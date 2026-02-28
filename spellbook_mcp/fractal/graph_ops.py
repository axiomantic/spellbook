"""Graph-level operations for the fractal thinking system.

Provides functions for creating, resuming, deleting, and updating
fractal exploration graphs.
"""

import json
import uuid

from spellbook_mcp.fractal.models import (
    INTENSITY_BUDGETS,
    VALID_INTENSITIES,
    validate_checkpoint_mode,
)
from spellbook_mcp.fractal.schema import get_fractal_connection

# Valid status transitions: {from_status: [allowed_to_statuses]}
VALID_TRANSITIONS = {
    "active": ["completed", "paused", "error", "budget_exhausted"],
    "paused": ["active"],
    "budget_exhausted": ["active", "completed"],
}

# Terminal states that cannot be resumed
TERMINAL_STATES = ["completed", "error", "budget_exhausted"]


def create_graph(seed, intensity, checkpoint_mode, metadata_json=None, db_path=None):
    """Create a new fractal exploration graph with a root question node.

    Args:
        seed: The initial question to explore
        intensity: Exploration intensity ("pulse", "explore", "deep")
        checkpoint_mode: When to pause for human review
        metadata_json: Optional JSON string of metadata to store
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

    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO graphs (id, seed, intensity, checkpoint_mode, metadata_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (graph_id, seed, intensity, checkpoint_mode, metadata_json),
    )
    cursor.execute(
        "INSERT INTO nodes (id, graph_id, node_type, text, depth, status) "
        "VALUES (?, ?, 'question', ?, 0, 'open')",
        (root_node_id, graph_id, seed),
    )
    conn.commit()

    return {
        "graph_id": graph_id,
        "root_node_id": root_node_id,
        "intensity": intensity,
        "checkpoint_mode": checkpoint_mode,
        "budget": INTENSITY_BUDGETS[intensity],
        "status": "active",
    }


def resume_graph(graph_id, db_path=None):
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
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, seed, intensity, checkpoint_mode, status, metadata_json "
        "FROM graphs WHERE id = ?",
        (graph_id,),
    )
    row = cursor.fetchone()

    if row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    current_status = row[4]

    if current_status in TERMINAL_STATES:
        return {
            "error": f"Cannot resume graph in '{current_status}' state. "
            f"Terminal states are: {TERMINAL_STATES}"
        }

    if current_status == "paused":
        cursor.execute(
            "UPDATE graphs SET status = 'active', updated_at = datetime('now') "
            "WHERE id = ?",
            (graph_id,),
        )
        conn.commit()
        current_status = "active"

    # Fetch nodes
    cursor.execute(
        "SELECT id, graph_id, parent_id, node_type, text, owner, depth, status, "
        "metadata_json, created_at FROM nodes WHERE graph_id = ?",
        (graph_id,),
    )
    nodes = []
    for node_row in cursor.fetchall():
        nodes.append({
            "id": node_row[0],
            "graph_id": node_row[1],
            "parent_id": node_row[2],
            "node_type": node_row[3],
            "text": node_row[4],
            "owner": node_row[5],
            "depth": node_row[6],
            "status": node_row[7],
            "metadata": json.loads(node_row[8]) if node_row[8] else {},
            "created_at": node_row[9],
        })

    # Fetch edges
    cursor.execute(
        "SELECT id, graph_id, from_node, to_node, edge_type, metadata_json, "
        "created_at FROM edges WHERE graph_id = ?",
        (graph_id,),
    )
    edges = []
    for edge_row in cursor.fetchall():
        edges.append({
            "id": edge_row[0],
            "graph_id": edge_row[1],
            "from_node": edge_row[2],
            "to_node": edge_row[3],
            "edge_type": edge_row[4],
            "metadata": json.loads(edge_row[5]) if edge_row[5] else {},
            "created_at": edge_row[6],
        })

    return {
        "graph_id": graph_id,
        "seed": row[1],
        "status": current_status,
        "intensity": row[2],
        "checkpoint_mode": row[3],
        "metadata": json.loads(row[5]) if row[5] else {},
        "nodes": nodes,
        "edges": edges,
    }


def delete_graph(graph_id, db_path=None):
    """Delete a fractal exploration graph and all its nodes/edges via CASCADE.

    Args:
        graph_id: ID of the graph to delete
        db_path: Path to database file (defaults to standard location)

    Returns:
        dict with deleted=True and graph_id, or dict with "error" key if not found
    """
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    # Check existence first
    cursor.execute("SELECT id FROM graphs WHERE id = ?", (graph_id,))
    if cursor.fetchone() is None:
        return {"error": f"Graph '{graph_id}' not found."}

    cursor.execute("DELETE FROM graphs WHERE id = ?", (graph_id,))
    conn.commit()

    return {"deleted": True, "graph_id": graph_id}


def update_graph_status(graph_id, status, reason=None, db_path=None):
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
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT status, metadata_json FROM graphs WHERE id = ?",
        (graph_id,),
    )
    row = cursor.fetchone()

    if row is None:
        return {"error": f"Graph '{graph_id}' not found."}

    previous_status = row[0]
    current_metadata = row[1] or "{}"

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

    cursor.execute(
        "UPDATE graphs SET status = ?, metadata_json = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (status, current_metadata, graph_id),
    )
    conn.commit()

    return {
        "graph_id": graph_id,
        "status": status,
        "previous_status": previous_status,
    }
