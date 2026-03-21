"""MCP tools for fractal thinking."""

__all__ = [
    "fractal_create_graph",
    "fractal_resume_graph",
    "fractal_delete_graph",
    "fractal_update_graph_status",
    "fractal_add_node",
    "fractal_update_node",
    "fractal_mark_saturated",
    "fractal_get_snapshot",
    "fractal_get_branch",
    "fractal_get_open_questions",
    "fractal_query_convergence",
    "fractal_query_contradictions",
    "fractal_get_saturation_status",
    "fractal_claim_work",
    "fractal_synthesize_node",
    "fractal_get_claimable_work",
    "fractal_get_ready_to_synthesize",
]

from spellbook.mcp.server import mcp
from spellbook.fractal.graph_ops import (
    create_graph as do_fractal_create_graph,
    delete_graph as do_fractal_delete_graph,
    resume_graph as do_fractal_resume_graph,
    update_graph_status as do_fractal_update_graph_status,
)
from spellbook.fractal.node_ops import (
    add_node as do_fractal_add_node,
    claim_work as do_fractal_claim_work,
    mark_saturated as do_fractal_mark_saturated,
    synthesize_node as do_fractal_synthesize_node,
    update_node as do_fractal_update_node,
)
from spellbook.fractal.query_ops import (
    get_branch as do_fractal_get_branch,
    get_claimable_work as do_fractal_get_claimable_work,
    get_open_questions as do_fractal_get_open_questions,
    get_ready_to_synthesize as do_fractal_get_ready_to_synthesize,
    get_saturation_status as do_fractal_get_saturation_status,
    get_snapshot as do_fractal_get_snapshot,
    query_contradictions as do_fractal_query_contradictions,
    query_convergence as do_fractal_query_convergence,
)
from spellbook.sessions.injection import inject_recovery_context


@mcp.tool()
@inject_recovery_context
async def fractal_create_graph(seed: str, intensity: str, checkpoint_mode: str, metadata: str = None):
    """Create a new fractal thinking graph with a seed question."""
    result = await do_fractal_create_graph(seed=seed, intensity=intensity, checkpoint_mode=checkpoint_mode, metadata_json=metadata)
    try:
        from spellbook.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.FRACTAL,
                event_type="fractal.graph_created",
                data={
                    "graph_id": result.get("graph_id"),
                    "seed": seed[:200],
                    "intensity": intensity,
                },
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
async def fractal_resume_graph(graph_id: str):
    """Resume a paused fractal graph or retrieve snapshot of an active one."""
    return await do_fractal_resume_graph(graph_id=graph_id)


@mcp.tool()
@inject_recovery_context
async def fractal_delete_graph(graph_id: str):
    """Delete a fractal thinking graph and all its nodes/edges."""
    result = await do_fractal_delete_graph(graph_id=graph_id)
    try:
        from spellbook.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.FRACTAL,
                event_type="fractal.graph_deleted",
                data={"graph_id": graph_id},
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
async def fractal_update_graph_status(graph_id: str, status: str, reason: str = None):
    """Update the status of a fractal thinking graph."""
    return await do_fractal_update_graph_status(graph_id=graph_id, status=status, reason=reason)


@mcp.tool()
@inject_recovery_context
async def fractal_add_node(graph_id: str, parent_id: str, node_type: str, text: str, owner: str = None, metadata: str = None):
    """Add a new node to a fractal thinking graph."""
    try:
        result = await do_fractal_add_node(graph_id=graph_id, parent_id=parent_id, node_type=node_type, text=text, owner=owner, metadata_json=metadata)
    except ValueError as e:
        return {"error": str(e)}
    try:
        from spellbook.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.FRACTAL,
                event_type="fractal.node_added",
                data={
                    "graph_id": graph_id,
                    "node_id": result.get("node_id"),
                    "node_type": node_type,
                    "parent_id": parent_id,
                },
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
async def fractal_update_node(graph_id: str, node_id: str, metadata: str):
    """Update a node's metadata in a fractal thinking graph."""
    try:
        return await do_fractal_update_node(graph_id=graph_id, node_id=node_id, metadata_json=metadata)
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
@inject_recovery_context
async def fractal_mark_saturated(graph_id: str, node_id: str, reason: str):
    """Mark a node as saturated in a fractal thinking graph."""
    try:
        result = await do_fractal_mark_saturated(graph_id=graph_id, node_id=node_id, reason=reason)
    except ValueError as e:
        return {"error": str(e)}
    try:
        from spellbook.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.FRACTAL,
                event_type="fractal.node_saturated",
                data={
                    "graph_id": graph_id,
                    "node_id": node_id,
                    "reason": reason[:200],
                },
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
async def fractal_get_snapshot(graph_id: str):
    """Get a full snapshot of a fractal thinking graph."""
    return await do_fractal_get_snapshot(graph_id=graph_id)


@mcp.tool()
@inject_recovery_context
async def fractal_get_branch(graph_id: str, node_id: str):
    """Get a subtree rooted at a specific node in a fractal thinking graph."""
    return await do_fractal_get_branch(graph_id=graph_id, node_id=node_id)


@mcp.tool()
@inject_recovery_context
async def fractal_get_open_questions(graph_id: str):
    """Get all open questions in a fractal thinking graph."""
    return await do_fractal_get_open_questions(graph_id=graph_id)


@mcp.tool()
@inject_recovery_context
async def fractal_query_convergence(graph_id: str):
    """Find convergence points in a fractal thinking graph."""
    return await do_fractal_query_convergence(graph_id=graph_id)


@mcp.tool()
@inject_recovery_context
async def fractal_query_contradictions(graph_id: str):
    """Find contradictions in a fractal thinking graph."""
    return await do_fractal_query_contradictions(graph_id=graph_id)


@mcp.tool()
@inject_recovery_context
async def fractal_get_saturation_status(graph_id: str):
    """Get saturation status of branches in a fractal thinking graph."""
    return await do_fractal_get_saturation_status(graph_id=graph_id)


@mcp.tool()
@inject_recovery_context
async def fractal_claim_work(graph_id: str, worker_id: str, session_id: str = ""):
    """Atomically claim the next available question node for a worker. Returns node data with branch affinity preference, or graph_done status. Pass session_id (Claude Code session UUID) for chat log linking in the admin UI."""
    try:
        return await do_fractal_claim_work(
            graph_id=graph_id, worker_id=worker_id,
            session_id=session_id or None,
        )
    except ValueError as e:
        return {"error": str(e)}


@mcp.tool()
@inject_recovery_context
async def fractal_synthesize_node(graph_id: str, node_id: str, synthesis_text: str):
    """Mark a node as synthesized with synthesis text. Validates all child questions are complete."""
    try:
        result = await do_fractal_synthesize_node(graph_id=graph_id, node_id=node_id, synthesis_text=synthesis_text)
    except ValueError as e:
        return {"error": str(e)}
    try:
        from spellbook.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.FRACTAL,
                event_type="fractal.node_synthesized",
                data={
                    "graph_id": graph_id,
                    "node_id": node_id,
                },
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
async def fractal_get_claimable_work(graph_id: str, worker_id: str = None):
    """Preview available work in a fractal graph with optional branch affinity ordering."""
    return await do_fractal_get_claimable_work(graph_id=graph_id, worker_id=worker_id)


@mcp.tool()
@inject_recovery_context
async def fractal_get_ready_to_synthesize(graph_id: str):
    """Find nodes ready for bottom-up synthesis (all child questions complete)."""
    return await do_fractal_get_ready_to_synthesize(graph_id=graph_id)
