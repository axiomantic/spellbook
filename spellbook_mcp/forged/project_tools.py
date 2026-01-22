"""MCP tools for Forged project management.

This module provides MCP tool functions for managing projects, features,
and skill invocations in the Forged autonomous development system.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from spellbook_mcp.forged.artifacts import (
    artifact_base_path,
    get_project_encoded,
    read_artifact,
    write_artifact,
)
from spellbook_mcp.forged.models import IterationState
from spellbook_mcp.forged.project_graph import (
    CyclicDependencyError,
    FeatureNode,
    MissingDependencyError,
    ProjectGraph,
    SkillInvocation,
    compute_dependency_order,
)
from spellbook_mcp.forged.skill_selection import select_skill


def _get_project_graph_path(project_path: str) -> str:
    """Get path to project graph JSON file.

    Args:
        project_path: Absolute path to project directory

    Returns:
        Path to project graph JSON file
    """
    project_encoded = get_project_encoded(project_path)
    base = Path.home() / ".local" / "spellbook" / "docs" / project_encoded / "forged"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "project-graph.json")


def _load_project_graph(project_path: str) -> Optional[ProjectGraph]:
    """Load project graph from storage.

    Args:
        project_path: Absolute path to project directory

    Returns:
        ProjectGraph if found, None otherwise
    """
    graph_path = _get_project_graph_path(project_path)
    content = read_artifact(graph_path)
    if content is None:
        return None
    try:
        data = json.loads(content)
        return ProjectGraph.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def _save_project_graph(project_path: str, graph: ProjectGraph) -> bool:
    """Save project graph to storage.

    Args:
        project_path: Absolute path to project directory
        graph: ProjectGraph to save

    Returns:
        True on success
    """
    graph_path = _get_project_graph_path(project_path)
    content = json.dumps(graph.to_dict(), indent=2)
    return write_artifact(graph_path, content)


def _get_invocations_path(project_path: str) -> str:
    """Get path to skill invocations JSON file.

    Args:
        project_path: Absolute path to project directory

    Returns:
        Path to skill invocations JSON file
    """
    project_encoded = get_project_encoded(project_path)
    base = Path.home() / ".local" / "spellbook" / "docs" / project_encoded / "forged"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "skill-invocations.json")


def _load_invocations(project_path: str) -> list[SkillInvocation]:
    """Load skill invocations from storage.

    Args:
        project_path: Absolute path to project directory

    Returns:
        List of SkillInvocation objects
    """
    invocations_path = _get_invocations_path(project_path)
    content = read_artifact(invocations_path)
    if content is None:
        return []
    try:
        data = json.loads(content)
        return [SkillInvocation.from_dict(inv) for inv in data]
    except (json.JSONDecodeError, KeyError):
        return []


def _save_invocations(project_path: str, invocations: list[SkillInvocation]) -> bool:
    """Save skill invocations to storage.

    Args:
        project_path: Absolute path to project directory
        invocations: List of SkillInvocation objects to save

    Returns:
        True on success
    """
    invocations_path = _get_invocations_path(project_path)
    data = [inv.to_dict() for inv in invocations]
    content = json.dumps(data, indent=2)
    return write_artifact(invocations_path, content)


def forge_project_init(
    project_path: str,
    project_name: str,
    features: list[dict],
) -> dict[str, Any]:
    """Initialize a new project graph.

    Creates a project graph from feature definitions, validates dependencies,
    and computes topological sort for execution order.

    Args:
        project_path: Absolute path to project directory
        project_name: Human-readable project name
        features: List of feature definitions with id, name, description,
                  depends_on, and estimated_complexity

    Returns:
        Dictionary with success status and graph or error message
    """
    # Convert feature definitions to FeatureNode objects
    feature_nodes: dict[str, FeatureNode] = {}

    for feat_def in features:
        node = FeatureNode(
            id=feat_def["id"],
            name=feat_def["name"],
            description=feat_def["description"],
            depends_on=feat_def.get("depends_on", []),
            status="pending",
            estimated_complexity=feat_def.get("estimated_complexity", "medium"),
            assigned_skill=None,
            artifacts=[],
        )
        feature_nodes[node.id] = node

    # Compute dependency order (validates dependencies and detects cycles)
    try:
        dependency_order = compute_dependency_order(feature_nodes)
    except MissingDependencyError as e:
        return {
            "success": False,
            "error": f"Missing dependency: {e}",
        }
    except CyclicDependencyError as e:
        return {
            "success": False,
            "error": f"Cyclic dependency detected: {e}",
        }

    # Create and save project graph
    graph = ProjectGraph(
        project_name=project_name,
        features=feature_nodes,
        dependency_order=dependency_order,
        current_feature=None,
        completed_features=[],
    )

    _save_project_graph(project_path, graph)

    return {
        "success": True,
        "graph": graph.to_dict(),
    }


def forge_project_status(project_path: str) -> dict[str, Any]:
    """Get current project status.

    Returns the project graph with progress information.

    Args:
        project_path: Absolute path to project directory

    Returns:
        Dictionary with success status, graph, and progress info
    """
    graph = _load_project_graph(project_path)
    if graph is None:
        return {
            "success": False,
            "error": f"No project graph found for {project_path}",
        }

    # Calculate progress
    total_features = len(graph.features)
    completed_features = len(graph.completed_features)
    completion_percentage = (
        (completed_features / total_features * 100)
        if total_features > 0
        else 0.0
    )

    return {
        "success": True,
        "graph": graph.to_dict(),
        "progress": {
            "total_features": total_features,
            "completed_features": completed_features,
            "completion_percentage": completion_percentage,
        },
    }


def forge_feature_update(
    project_path: str,
    feature_id: str,
    status: Optional[str] = None,
    assigned_skill: Optional[str] = None,
    artifacts: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Update a feature's status and/or artifacts.

    Args:
        project_path: Absolute path to project directory
        feature_id: ID of feature to update
        status: New status (pending, in_progress, complete, blocked)
        assigned_skill: Skill assigned to this feature
        artifacts: List of artifact paths to add

    Returns:
        Dictionary with success status and updated feature
    """
    graph = _load_project_graph(project_path)
    if graph is None:
        return {
            "success": False,
            "error": f"No project graph found for {project_path}",
        }

    if feature_id not in graph.features:
        return {
            "success": False,
            "error": f"Feature '{feature_id}' not found in project",
        }

    feature = graph.features[feature_id]

    # Update status
    if status is not None:
        feature.status = status

        # Update current_feature tracking
        if status == "in_progress":
            graph.current_feature = feature_id
        elif status == "complete":
            if feature_id not in graph.completed_features:
                graph.completed_features.append(feature_id)
            if graph.current_feature == feature_id:
                graph.current_feature = None

    # Update assigned skill
    if assigned_skill is not None:
        feature.assigned_skill = assigned_skill

    # Add artifacts
    if artifacts is not None:
        for artifact in artifacts:
            if artifact not in feature.artifacts:
                feature.artifacts.append(artifact)

    _save_project_graph(project_path, graph)

    return {
        "success": True,
        "feature": feature.to_dict(),
    }


def forge_select_skill(
    project_path: str,
    feature_id: str,
    stage: str,
    feedback_history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """Select the appropriate skill for current context.

    Args:
        project_path: Absolute path to project directory
        feature_id: ID of current feature
        stage: Current workflow stage
        feedback_history: Optional list of feedback dicts

    Returns:
        Dictionary with success status and selected skill
    """
    graph = _load_project_graph(project_path)
    if graph is None:
        return {
            "success": False,
            "error": f"No project graph found for {project_path}",
        }

    if feature_id not in graph.features:
        return {
            "success": False,
            "error": f"Feature '{feature_id}' not found in project",
        }

    # Build iteration state for skill selection
    from spellbook_mcp.forged.models import Feedback

    feedback_objects = []
    if feedback_history:
        for fb in feedback_history:
            feedback_objects.append(Feedback.from_dict(fb))

    context = IterationState(
        iteration_number=1,  # Will be updated from actual state if needed
        current_stage=stage,
        feedback_history=feedback_objects,
    )

    skill = select_skill(context)

    return {
        "success": True,
        "skill": skill,
        "feature_id": feature_id,
        "stage": stage,
    }


def forge_skill_complete(
    project_path: str,
    feature_id: str,
    skill_name: str,
    result: str,
    artifacts_produced: Optional[list[str]] = None,
    context_returned: Optional[dict] = None,
) -> dict[str, Any]:
    """Record skill completion and update feature state.

    Args:
        project_path: Absolute path to project directory
        feature_id: ID of feature being worked on
        skill_name: Name of the completed skill
        result: Result status (success, failure, etc.)
        artifacts_produced: Optional list of artifact paths produced
        context_returned: Optional context data returned by skill

    Returns:
        Dictionary with success status and invocation ID
    """
    graph = _load_project_graph(project_path)
    if graph is None:
        return {
            "success": False,
            "error": f"No project graph found for {project_path}",
        }

    if feature_id not in graph.features:
        return {
            "success": False,
            "error": f"Feature '{feature_id}' not found in project",
        }

    # Create skill invocation record
    invocation_id = f"inv-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    invocation = SkillInvocation(
        id=invocation_id,
        feature_id=feature_id,
        skill_name=skill_name,
        stage=graph.features[feature_id].status,
        iteration=1,  # Will be tracked properly with full state
        started_at=now,  # In reality, would be passed in
        completed_at=now,
        result=result,
        context_passed={},
        context_returned=context_returned or {},
    )

    # Load existing invocations and add new one
    invocations = _load_invocations(project_path)
    invocations.append(invocation)
    _save_invocations(project_path, invocations)

    # Update feature artifacts if provided
    if artifacts_produced:
        feature = graph.features[feature_id]
        for artifact in artifacts_produced:
            if artifact not in feature.artifacts:
                feature.artifacts.append(artifact)
        _save_project_graph(project_path, graph)

    return {
        "success": True,
        "invocation_id": invocation_id,
        "feature_id": feature_id,
        "skill_name": skill_name,
        "result": result,
    }
