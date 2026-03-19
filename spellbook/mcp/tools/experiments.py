"""MCP tools for A/B testing experiments."""

from spellbook.mcp.server import mcp
from spellbook.experiments.ab_test import (
    ABTestError,
    experiment_complete as do_experiment_complete,
    experiment_create as do_experiment_create,
    experiment_list as do_experiment_list,
    experiment_pause as do_experiment_pause,
    experiment_results as do_experiment_results,
    experiment_start as do_experiment_start,
    experiment_status as do_experiment_status,
)
from spellbook.sessions.injection import inject_recovery_context


@mcp.tool()
@inject_recovery_context
def experiment_create(
    name: str,
    skill_name: str,
    variants: list,
    description: str = None,
) -> dict:
    """Create a new A/B test experiment with defined variants.

    Args:
        name: Human-readable unique identifier (1-100 chars)
        skill_name: Target skill to test (e.g., "develop")
        variants: List of variant dicts with:
            - name: Variant name (e.g., "control", "treatment")
            - skill_version: Optional version string (None for control)
            - weight: Assignment weight (0-100, all must sum to 100)
        description: Optional experiment description

    Returns:
        {
            "success": True,
            "experiment_id": "uuid",
            "name": str,
            "skill_name": str,
            "status": "created",
            "variants": [{id, name, skill_version, weight}, ...]
        }

    Errors:
        - EXPERIMENT_EXISTS: Name already taken
        - INVALID_VARIANTS: Weights don't sum to 100 or no control variant
    """
    try:
        return do_experiment_create(
            name=name,
            skill_name=skill_name,
            variants=variants,
            description=description,
        )
    except ABTestError as e:
        return e.to_mcp_response()


@mcp.tool()
@inject_recovery_context
def experiment_start(experiment_id: str) -> dict:
    """Activate an experiment for variant assignment.

    Sessions invoking the skill will be deterministically assigned to variants.

    Args:
        experiment_id: UUID of experiment to start

    Returns:
        {"success": True, "experiment_id": str, "status": "active", "started_at": str}

    Errors:
        - EXPERIMENT_NOT_FOUND: Invalid experiment_id
        - INVALID_STATUS_TRANSITION: Experiment not in created/paused status
        - CONCURRENT_EXPERIMENT: Another experiment for this skill is active
    """
    try:
        return do_experiment_start(experiment_id)
    except ABTestError as e:
        return e.to_mcp_response()


@mcp.tool()
@inject_recovery_context
def experiment_pause(experiment_id: str) -> dict:
    """Pause an active experiment.

    No new variant assignments will be made. Existing assignments continue
    tracking outcomes.

    Args:
        experiment_id: UUID of experiment to pause

    Returns:
        {"success": True, "experiment_id": str, "status": "paused"}
    """
    try:
        return do_experiment_pause(experiment_id)
    except ABTestError as e:
        return e.to_mcp_response()


@mcp.tool()
@inject_recovery_context
def experiment_complete(experiment_id: str) -> dict:
    """Mark experiment as completed and freeze data.

    No further assignments or outcome modifications.

    Args:
        experiment_id: UUID of experiment to complete

    Returns:
        {"success": True, "experiment_id": str, "status": "completed", "completed_at": str}
    """
    try:
        return do_experiment_complete(experiment_id)
    except ABTestError as e:
        return e.to_mcp_response()


@mcp.tool()
@inject_recovery_context
def experiment_status(experiment_id: str) -> dict:
    """Get current status and summary metrics for an experiment.

    Args:
        experiment_id: UUID of experiment

    Returns:
        {
            "success": True,
            "experiment": {id, name, skill_name, status, description, timestamps},
            "variants": [{id, name, skill_version, weight, sessions_assigned, outcomes_recorded}],
            "total_sessions": int,
            "total_outcomes": int
        }
    """
    try:
        return do_experiment_status(experiment_id)
    except ABTestError as e:
        return e.to_mcp_response()


@mcp.tool()
@inject_recovery_context
def experiment_list(
    status: str = None,
    skill_name: str = None,
) -> dict:
    """List experiments with optional filters.

    Args:
        status: Filter by status (created, active, paused, completed)
        skill_name: Filter by target skill

    Returns:
        {
            "success": True,
            "experiments": [{id, name, skill_name, status, created_at, variants_count, total_sessions}],
            "total": int
        }
    """
    return do_experiment_list(status=status, skill_name=skill_name)


@mcp.tool()
@inject_recovery_context
def experiment_results(experiment_id: str) -> dict:
    """Compare variant performance with detailed metrics.

    Args:
        experiment_id: UUID of experiment

    Returns:
        {
            "success": True,
            "experiment_id": str,
            "name": str,
            "skill_name": str,
            "status": str,
            "duration_days": int,
            "results": {
                "control": {variant_id, skill_version, sessions, outcomes, metrics},
                "treatment": {...}
            },
            "comparison": {
                completion_rate_delta, token_efficiency_delta,
                correction_rate_delta, preliminary_winner
            }
        }
    """
    try:
        return do_experiment_results(experiment_id)
    except ABTestError as e:
        return e.to_mcp_response()
