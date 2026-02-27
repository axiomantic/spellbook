"""Node-level operations for the fractal thinking system.

Provides functions for creating, updating, and managing nodes within
fractal exploration graphs.
"""

import json
import uuid

from spellbook_mcp.fractal.models import (
    INTENSITY_BUDGETS,
    VALID_NODE_TYPES,
    VALID_SATURATION_REASONS,
)
from spellbook_mcp.fractal.schema import get_fractal_connection


def add_node(graph_id, parent_id, node_type, text, owner=None, metadata_json=None, db_path=None):
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

    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    # Validate graph exists and is active
    cursor.execute(
        "SELECT status, intensity FROM graphs WHERE id = ?",
        (graph_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"Graph '{graph_id}' not found.")

    graph_status = row[0]
    if graph_status != "active":
        raise ValueError(
            f"Cannot add node to graph with status '{graph_status}'. "
            f"Graph must be 'active'."
        )

    intensity = row[1]
    max_depth = INTENSITY_BUDGETS[intensity]["max_depth"]

    # Calculate depth and validate parent
    depth = 0
    if parent_id is not None:
        cursor.execute(
            "SELECT depth, node_type, status FROM nodes WHERE id = ? AND graph_id = ?",
            (parent_id, graph_id),
        )
        parent_row = cursor.fetchone()
        if parent_row is None:
            raise ValueError(f"Parent node '{parent_id}' not found in graph '{graph_id}'.")
        depth = parent_row[0] + 1

    if depth >= max_depth:
        raise ValueError(
            f"Depth {depth} would exceed max_depth {max_depth} "
            f"for intensity '{intensity}'"
        )

    node_id = str(uuid.uuid4())

    cursor.execute(
        "INSERT INTO nodes (id, graph_id, parent_id, node_type, text, owner, depth, status, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
        (node_id, graph_id, parent_id, node_type, text, owner, depth, metadata_json or "{}"),
    )

    # Create parent_child edge if parent_id provided
    if parent_id is not None:
        cursor.execute(
            "INSERT INTO edges (graph_id, from_node, to_node, edge_type) "
            "VALUES (?, ?, ?, 'parent_child')",
            (graph_id, parent_id, node_id),
        )

        # Auto-transition: if adding answer to open question parent, mark parent as answered
        if node_type == "answer":
            parent_node_type = parent_row[1]
            parent_status = parent_row[2]
            if parent_node_type == "question" and parent_status == "open":
                cursor.execute(
                    "UPDATE nodes SET status = 'answered' WHERE id = ?",
                    (parent_id,),
                )

    conn.commit()

    return {
        "node_id": node_id,
        "graph_id": graph_id,
        "parent_id": parent_id,
        "depth": depth,
        "node_type": node_type,
        "status": "open",
    }


def update_node(graph_id, node_id, metadata_json, db_path=None):
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
    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    # Validate graph exists
    cursor.execute("SELECT id FROM graphs WHERE id = ?", (graph_id,))
    if cursor.fetchone() is None:
        raise ValueError(f"Graph '{graph_id}' not found.")

    # Validate node exists
    cursor.execute(
        "SELECT metadata_json FROM nodes WHERE id = ? AND graph_id = ?",
        (node_id, graph_id),
    )
    node_row = cursor.fetchone()
    if node_row is None:
        raise ValueError(f"Node '{node_id}' not found in graph '{graph_id}'.")

    # Merge metadata
    existing_meta = json.loads(node_row[0])
    try:
        new_meta = json.loads(metadata_json)
    except json.JSONDecodeError:
        raise ValueError("Invalid metadata_json: must be valid JSON string")
    existing_meta.update(new_meta)

    edges_created = 0

    # Handle convergence_with side effect
    convergence_targets = new_meta.get("convergence_with", [])
    for target_id in convergence_targets:
        cursor.execute(
            "SELECT id FROM nodes WHERE id = ? AND graph_id = ?",
            (target_id, graph_id),
        )
        if cursor.fetchone() is None:
            raise ValueError(f"Node '{target_id}' not found in graph '{graph_id}'.")
        cursor.execute(
            "INSERT INTO edges (graph_id, from_node, to_node, edge_type) "
            "VALUES (?, ?, ?, 'convergence')",
            (graph_id, node_id, target_id),
        )
        edges_created += 1

    # Handle contradiction_with side effect
    contradiction_targets = new_meta.get("contradiction_with", [])
    for target_id in contradiction_targets:
        cursor.execute(
            "SELECT id FROM nodes WHERE id = ? AND graph_id = ?",
            (target_id, graph_id),
        )
        if cursor.fetchone() is None:
            raise ValueError(f"Node '{target_id}' not found in graph '{graph_id}'.")
        cursor.execute(
            "INSERT INTO edges (graph_id, from_node, to_node, edge_type) "
            "VALUES (?, ?, ?, 'contradiction')",
            (graph_id, node_id, target_id),
        )
        edges_created += 1

    # Persist merged metadata
    cursor.execute(
        "UPDATE nodes SET metadata_json = ? WHERE id = ?",
        (json.dumps(existing_meta), node_id),
    )

    conn.commit()

    return {
        "node_id": node_id,
        "metadata": existing_meta,
        "edges_created": edges_created,
    }


def mark_saturated(graph_id, node_id, reason, db_path=None):
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

    conn = get_fractal_connection(db_path)
    cursor = conn.cursor()

    # Validate graph exists
    cursor.execute("SELECT id FROM graphs WHERE id = ?", (graph_id,))
    if cursor.fetchone() is None:
        raise ValueError(f"Graph '{graph_id}' not found.")

    # Validate node exists and check current status
    cursor.execute(
        "SELECT status, metadata_json FROM nodes WHERE id = ? AND graph_id = ?",
        (node_id, graph_id),
    )
    node_row = cursor.fetchone()
    if node_row is None:
        raise ValueError(f"Node '{node_id}' not found in graph '{graph_id}'.")

    current_status = node_row[0]
    if current_status not in ("open", "answered"):
        raise ValueError(
            f"Cannot saturate node with status '{current_status}'. "
            f"Node must be 'open' or 'answered'."
        )

    # Update metadata with saturation reason
    existing_meta = json.loads(node_row[1])
    existing_meta["saturation_reason"] = reason

    # Update node
    cursor.execute(
        "UPDATE nodes SET status = 'saturated', metadata_json = ? WHERE id = ?",
        (json.dumps(existing_meta), node_id),
    )

    conn.commit()

    return {
        "node_id": node_id,
        "status": "saturated",
        "reason": reason,
    }
