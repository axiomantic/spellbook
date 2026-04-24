"""MCP tools for miscellaneous operations.

Includes: workflow state persistence.
"""

__all__ = [
    "workflow_state_save",
    "workflow_state_load",
    "workflow_state_update",
]

import json
from datetime import datetime, timezone

from spellbook.mcp.server import mcp
from spellbook.sessions.injection import inject_recovery_context


def _deep_merge(base: dict, updates: dict) -> dict:
    """Recursively merge updates into base dict."""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            # For lists, append new items (useful for skill_stack, subagents)
            result[key] = result[key] + value
        else:
            result[key] = value
    return result


# ============================================================================
# Workflow State Tools
# ============================================================================


@mcp.tool()
@inject_recovery_context
def workflow_state_save(
    project_path: str,
    state: dict,
    trigger: str = "manual",
) -> dict:
    """
    Persist workflow state to database.

    Called by plugin on session.compacting hook or manually via /handoff.
    Overwrites previous state for project (only latest matters).

    Args:
        project_path: Absolute path to project directory
        state: WorkflowState dict (from handoff Section 1.20)
        trigger: "manual" | "auto" | "checkpoint"

    Returns:
        {"success": True/False, "project_path": str, "trigger": str, "error": str?}
    """
    from spellbook.core.db import get_connection
    from spellbook.sessions.resume import validate_workflow_state

    validation = validate_workflow_state(state)
    if not validation["valid"]:
        high_or_above = [f for f in validation["findings"] if f.get("severity") in ("HIGH", "CRITICAL")]
        if high_or_above:
            messages = [f.get("message", "unknown") for f in high_or_above]
            return {"success": False, "project_path": project_path, "trigger": trigger, "error": f"Workflow state failed validation: {'; '.join(messages)}"}

    try:
        conn = get_connection()
        cursor = conn.cursor()

        state_json = json.dumps(state)
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT OR REPLACE INTO workflow_state
                (project_path, state_json, trigger, created_at, updated_at)
            VALUES
                (?, ?, ?, COALESCE(
                    (SELECT created_at FROM workflow_state WHERE project_path = ?),
                    ?
                ), ?)
            """,
            (project_path, state_json, trigger, project_path, now, now),
        )
        conn.commit()

        return {
            "success": True,
            "project_path": project_path,
            "trigger": trigger,
        }
    except Exception as e:
        return {
            "success": False,
            "project_path": project_path,
            "trigger": trigger,
            "error": str(e),
        }


@mcp.tool()
@inject_recovery_context
def workflow_state_load(
    project_path: str,
    max_age_hours: float = 24.0,
) -> dict:
    """
    Load persisted workflow state for project.

    Returns None-like response if no state exists or state is too old.
    Called by plugin on session.created to check for resumable work.

    Args:
        project_path: Absolute path to project directory
        max_age_hours: Maximum age of state to consider valid (default 24h)

    Returns:
        {
            "success": True/False,
            "found": True/False,
            "state": dict | None,  # The WorkflowState if found and fresh
            "age_hours": float | None,
            "trigger": str | None,
            "error": str?
        }
    """
    from spellbook.core.db import get_connection

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT state_json, trigger, updated_at
            FROM workflow_state
            WHERE project_path = ?
            """,
            (project_path,),
        )
        row = cursor.fetchone()

        if row is None:
            return {
                "success": True,
                "found": False,
                "state": None,
                "age_hours": None,
                "trigger": None,
            }

        state_json, trigger, updated_at_str = row

        # Parse updated_at timestamp
        # Handle both ISO format with Z and without timezone
        if updated_at_str.endswith("Z"):
            updated_at_str = updated_at_str[:-1] + "+00:00"
        if "+" not in updated_at_str and updated_at_str.count(":") < 3:
            # No timezone info, assume UTC
            updated_at = datetime.fromisoformat(updated_at_str).replace(
                tzinfo=timezone.utc
            )
        else:
            updated_at = datetime.fromisoformat(updated_at_str)

        now = datetime.now(timezone.utc)
        age_hours = (now - updated_at).total_seconds() / 3600.0

        if age_hours > max_age_hours:
            return {
                "success": True,
                "found": False,
                "state": None,
                "age_hours": age_hours,
                "trigger": trigger,
            }

        state = json.loads(state_json)

        import logging as _logging
        _logger = _logging.getLogger(__name__)
        from spellbook.sessions.resume import validate_workflow_state
        validation = validate_workflow_state(state)
        if not validation["valid"]:
            _logger.warning(
                "Loaded workflow state for %s failed validation: %s",
                project_path,
                [f.get("message", "unknown") for f in validation["findings"]],
            )
            return {
                "success": True,
                "found": False,
                "state": None,
                "age_hours": age_hours,
                "trigger": trigger,
                "rejected": True,
                "rejection_reason": "State failed validation",
                "finding_count": len(validation["findings"]),
            }

        return {
            "success": True,
            "found": True,
            "state": state,
            "age_hours": age_hours,
            "trigger": trigger,
        }
    except Exception as e:
        return {
            "success": False,
            "found": False,
            "state": None,
            "age_hours": None,
            "trigger": None,
            "error": str(e),
        }


@mcp.tool()
@inject_recovery_context
def workflow_state_update(
    project_path: str,
    updates: dict,
) -> dict:
    """
    Incrementally update workflow state.

    Called by plugin on tool.execute.after to track:
    - Skill invocations (add to skill_stack)
    - Subagent spawns (add to subagents)
    - Todo changes

    Args:
        project_path: Absolute path to project directory
        updates: Partial WorkflowState dict to merge

    Returns:
        {"success": True/False, "project_path": str, "error": str?}
    """
    from spellbook.core.db import get_connection

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Load existing state (if any)
        cursor.execute(
            """
            SELECT state_json
            FROM workflow_state
            WHERE project_path = ?
            """,
            (project_path,),
        )
        row = cursor.fetchone()

        if row is None:
            # No existing state, create new with updates as base
            base_state = {}
        else:
            base_state = json.loads(row[0])

        # Validate incoming updates before merging
        from spellbook.sessions.resume import validate_workflow_state

        pre_validation = validate_workflow_state(updates)
        if not pre_validation["valid"]:
            return {
                "success": False,
                "project_path": project_path,
                "error": "Updates failed validation",
                "findings": [
                    f.get("message", "unknown")
                    for f in pre_validation["findings"]
                ],
            }

        # Deep merge updates into existing state
        merged_state = _deep_merge(base_state, updates)

        # Validate merged result (catches payloads that become dangerous after merge)
        post_validation = validate_workflow_state(merged_state)
        if not post_validation["valid"]:
            return {
                "success": False,
                "project_path": project_path,
                "error": "Merged state failed validation",
                "findings": [
                    f.get("message", "unknown")
                    for f in post_validation["findings"]
                ],
                "state": base_state,
            }

        state_json = json.dumps(merged_state)
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT OR REPLACE INTO workflow_state
                (project_path, state_json, trigger, created_at, updated_at)
            VALUES
                (?, ?, 'auto', COALESCE(
                    (SELECT created_at FROM workflow_state WHERE project_path = ?),
                    ?
                ), ?)
            """,
            (project_path, state_json, project_path, now, now),
        )
        conn.commit()

        return {
            "success": True,
            "project_path": project_path,
        }
    except Exception as e:
        return {
            "success": False,
            "project_path": project_path,
            "error": str(e),
        }


