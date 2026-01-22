"""Iteration MCP tools for Forged autonomous development workflow.

This module provides tools for managing the iteration cycle of autonomous
feature development, including stage transitions with token-based workflow
enforcement.

Token System:
- Tokens are generated on stage entry
- Required for advance/return operations
- Invalidated on transition to prevent replay
- Prevents skipping stages in the workflow

Stage Flow:
    DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE
                  ^                    |
                  |____ (feedback) ____|

    ESCALATED: Terminal state for unresolvable issues
"""

import json
import os
from datetime import datetime
from typing import Optional
from uuid import uuid4

from spellbook_mcp.forged.models import VALID_STAGES, Feedback, IterationState
from spellbook_mcp.forged.schema import get_forged_connection, init_forged_schema


# Stages that can be returned to (not terminal states)
_RETURNABLE_STAGES = ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT"]

# Stage progression order (index determines next stage)
_STAGE_ORDER = ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]


def _get_project_path() -> str:
    """Get current project path from working directory.

    Returns:
        Absolute path to current working directory
    """
    return os.getcwd()


def _generate_token() -> str:
    """Generate a unique workflow token.

    Returns:
        UUID string for token
    """
    return str(uuid4())


def _validate_token(conn, token: str, feature_name: str) -> dict:
    """Validate a workflow token.

    Args:
        conn: Database connection
        token: Token to validate
        feature_name: Expected feature name

    Returns:
        Dict with validation result:
        - valid: bool
        - error: Optional error message
        - stage: Current stage if valid
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT feature_name, stage, invalidated_at
        FROM forge_tokens
        WHERE id = ?
        """,
        (token,),
    )
    row = cursor.fetchone()

    if row is None:
        return {"valid": False, "error": "Invalid token: not found"}

    db_feature, stage, invalidated_at = row

    if invalidated_at is not None:
        return {"valid": False, "error": "Token expired: already used"}

    if db_feature != feature_name:
        return {
            "valid": False,
            "error": f"Token feature mismatch: token for '{db_feature}' cannot be used for '{feature_name}'",
        }

    return {"valid": True, "stage": stage}


def _invalidate_token(conn, token: str) -> None:
    """Mark a token as invalidated.

    Args:
        conn: Database connection
        token: Token to invalidate
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE forge_tokens
        SET invalidated_at = datetime('now')
        WHERE id = ?
        """,
        (token,),
    )
    conn.commit()


def _invalidate_feature_tokens(conn, feature_name: str) -> None:
    """Invalidate all tokens for a feature.

    Args:
        conn: Database connection
        feature_name: Feature to invalidate tokens for
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE forge_tokens
        SET invalidated_at = datetime('now')
        WHERE feature_name = ? AND invalidated_at IS NULL
        """,
        (feature_name,),
    )
    conn.commit()


def _create_token(conn, feature_name: str, stage: str) -> str:
    """Create a new workflow token.

    Args:
        conn: Database connection
        feature_name: Feature name
        stage: Current stage

    Returns:
        New token ID
    """
    token = _generate_token()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO forge_tokens (id, feature_name, stage)
        VALUES (?, ?, ?)
        """,
        (token, feature_name, stage),
    )
    conn.commit()
    return token


def _get_iteration_state(conn, project_path: str, feature_name: str) -> Optional[dict]:
    """Get existing iteration state for a feature.

    Args:
        conn: Database connection
        project_path: Project path
        feature_name: Feature name

    Returns:
        State dict or None if not found
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT iteration_number, current_stage, accumulated_knowledge,
               feedback_history, artifacts_produced, preferences
        FROM iteration_state
        WHERE project_path = ? AND feature_name = ?
        """,
        (project_path, feature_name),
    )
    row = cursor.fetchone()

    if row is None:
        return None

    return {
        "iteration_number": row[0],
        "current_stage": row[1],
        "accumulated_knowledge": json.loads(row[2]) if row[2] else {},
        "feedback_history": json.loads(row[3]) if row[3] else [],
        "artifacts_produced": json.loads(row[4]) if row[4] else [],
        "preferences": json.loads(row[5]) if row[5] else {},
    }


def _save_iteration_state(
    conn,
    project_path: str,
    feature_name: str,
    iteration_number: int,
    current_stage: str,
    accumulated_knowledge: dict,
    feedback_history: list,
    artifacts_produced: list,
    preferences: dict,
) -> None:
    """Save or update iteration state.

    Args:
        conn: Database connection
        project_path: Project path
        feature_name: Feature name
        iteration_number: Current iteration number
        current_stage: Current workflow stage
        accumulated_knowledge: Accumulated knowledge dict
        feedback_history: List of feedback dicts
        artifacts_produced: List of artifact paths
        preferences: User preferences dict
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO iteration_state
        (project_path, feature_name, iteration_number, current_stage,
         accumulated_knowledge, feedback_history, artifacts_produced, preferences,
         created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                COALESCE((SELECT created_at FROM iteration_state WHERE project_path = ? AND feature_name = ?), datetime('now')),
                datetime('now'))
        """,
        (
            project_path,
            feature_name,
            iteration_number,
            current_stage,
            json.dumps(accumulated_knowledge),
            json.dumps(feedback_history),
            json.dumps(artifacts_produced),
            json.dumps(preferences),
            project_path,
            feature_name,
        ),
    )
    conn.commit()


def _get_next_stage(current_stage: str) -> Optional[str]:
    """Get the next stage in the workflow.

    Args:
        current_stage: Current stage name

    Returns:
        Next stage name, or None if at terminal stage
    """
    if current_stage not in _STAGE_ORDER:
        return None
    idx = _STAGE_ORDER.index(current_stage)
    if idx >= len(_STAGE_ORDER) - 1:
        return None
    return _STAGE_ORDER[idx + 1]


def forge_iteration_start(
    feature_name: str,
    starting_stage: str = "DISCOVER",
    preferences: Optional[dict] = None,
) -> dict:
    """Start or resume an iteration cycle for a feature.

    Creates initial state for a new feature or loads existing state.
    Returns a token for the current stage that must be used in subsequent
    advance/return calls.

    Args:
        feature_name: Name of the feature being developed
        starting_stage: Initial stage (default: DISCOVER)
        preferences: Optional user preferences to store

    Returns:
        Dict containing:
        - status: "started" | "resumed" | "error"
        - feature_name: The feature name
        - current_stage: Current workflow stage
        - iteration_number: Current iteration count
        - token: Workflow token for next operation
        - error: Error message if status is "error"
    """
    # Validate starting stage
    if starting_stage not in VALID_STAGES:
        return {
            "status": "error",
            "error": f"Invalid stage: '{starting_stage}'. Must be one of: {VALID_STAGES}",
        }

    conn = get_forged_connection()
    project_path = _get_project_path()

    # Ensure schema is initialized
    init_forged_schema()

    # Invalidate any existing tokens for this feature
    _invalidate_feature_tokens(conn, feature_name)

    # Check for existing state
    existing = _get_iteration_state(conn, project_path, feature_name)

    if existing:
        # Resume existing feature
        token = _create_token(conn, feature_name, existing["current_stage"])
        return {
            "status": "resumed",
            "feature_name": feature_name,
            "current_stage": existing["current_stage"],
            "iteration_number": existing["iteration_number"],
            "token": token,
            "accumulated_knowledge": existing["accumulated_knowledge"],
            "feedback_history": existing["feedback_history"],
        }

    # Create new iteration state
    _save_iteration_state(
        conn=conn,
        project_path=project_path,
        feature_name=feature_name,
        iteration_number=1,
        current_stage=starting_stage,
        accumulated_knowledge={},
        feedback_history=[],
        artifacts_produced=[],
        preferences=preferences or {},
    )

    token = _create_token(conn, feature_name, starting_stage)

    return {
        "status": "started",
        "feature_name": feature_name,
        "current_stage": starting_stage,
        "iteration_number": 1,
        "token": token,
    }


def forge_iteration_advance(
    feature_name: str,
    current_token: str,
    evidence: Optional[dict] = None,
) -> dict:
    """Advance to next stage after consensus.

    Validates the token, transitions to the next stage, and returns
    a new token for the next operation.

    Args:
        feature_name: Name of the feature being developed
        current_token: Token from previous operation
        evidence: Optional evidence/knowledge to store from current stage

    Returns:
        Dict containing:
        - status: "advanced" | "error"
        - previous_stage: Stage before advancement
        - current_stage: New current stage
        - token: New workflow token
        - error: Error message if status is "error"
    """
    conn = get_forged_connection()
    project_path = _get_project_path()

    # Validate token
    validation = _validate_token(conn, current_token, feature_name)
    if not validation["valid"]:
        return {"status": "error", "error": validation["error"]}

    current_stage = validation["stage"]

    # Cannot advance from COMPLETE
    if current_stage == "COMPLETE":
        return {
            "status": "error",
            "error": "Cannot advance from COMPLETE stage. Feature is already finished.",
        }

    # Cannot advance from ESCALATED
    if current_stage == "ESCALATED":
        return {
            "status": "error",
            "error": "Cannot advance from ESCALATED stage. Human intervention required.",
        }

    # Get next stage
    next_stage = _get_next_stage(current_stage)
    if next_stage is None:
        return {
            "status": "error",
            "error": f"Cannot advance from {current_stage}. No next stage defined.",
        }

    # Get current state
    state = _get_iteration_state(conn, project_path, feature_name)
    if state is None:
        return {
            "status": "error",
            "error": f"No iteration state found for feature '{feature_name}'",
        }

    # Update accumulated knowledge with evidence
    accumulated_knowledge = state["accumulated_knowledge"]
    if evidence:
        stage_key = f"{current_stage.lower()}_evidence"
        accumulated_knowledge[stage_key] = evidence

    # Invalidate current token
    _invalidate_token(conn, current_token)

    # Save updated state
    _save_iteration_state(
        conn=conn,
        project_path=project_path,
        feature_name=feature_name,
        iteration_number=state["iteration_number"],
        current_stage=next_stage,
        accumulated_knowledge=accumulated_knowledge,
        feedback_history=state["feedback_history"],
        artifacts_produced=state["artifacts_produced"],
        preferences=state["preferences"],
    )

    # Create new token
    new_token = _create_token(conn, feature_name, next_stage)

    return {
        "status": "advanced",
        "previous_stage": current_stage,
        "current_stage": next_stage,
        "iteration_number": state["iteration_number"],
        "token": new_token,
    }


def forge_iteration_return(
    feature_name: str,
    current_token: str,
    return_to: str,
    feedback: list,
    reflection: Optional[str] = None,
) -> dict:
    """Return to earlier stage with feedback.

    Increments the iteration counter, stores feedback, and returns
    to the specified earlier stage.

    Args:
        feature_name: Name of the feature being developed
        current_token: Token from previous operation
        return_to: Stage to return to
        feedback: List of feedback dicts with structure:
            - source: Validator name
            - critique: Issue description
            - evidence: Supporting evidence
            - suggestion: Recommended fix
            - severity: "blocking" | "significant" | "minor"
        reflection: Optional lesson learned

    Returns:
        Dict containing:
        - status: "returned" | "error"
        - previous_stage: Stage before return
        - current_stage: Stage returned to
        - iteration_number: New iteration count
        - token: New workflow token
        - error: Error message if status is "error"
    """
    conn = get_forged_connection()
    project_path = _get_project_path()

    # Validate return_to stage
    if return_to not in VALID_STAGES:
        return {
            "status": "error",
            "error": f"Invalid stage: '{return_to}'. Must be one of: {VALID_STAGES}",
        }

    # Cannot return to terminal stages
    if return_to not in _RETURNABLE_STAGES:
        return {
            "status": "error",
            "error": f"Cannot return to '{return_to}'. Only returnable stages are: {_RETURNABLE_STAGES}",
        }

    # Validate token
    validation = _validate_token(conn, current_token, feature_name)
    if not validation["valid"]:
        return {"status": "error", "error": validation["error"]}

    current_stage = validation["stage"]

    # Require at least one feedback item
    if not feedback:
        return {
            "status": "error",
            "error": "Feedback is required when returning to an earlier stage.",
        }

    # Get current state
    state = _get_iteration_state(conn, project_path, feature_name)
    if state is None:
        return {
            "status": "error",
            "error": f"No iteration state found for feature '{feature_name}'",
        }

    # Build feedback objects and add to history
    new_iteration = state["iteration_number"] + 1
    feedback_history = state["feedback_history"]

    for fb in feedback:
        feedback_obj = {
            "source": fb.get("source", "unknown"),
            "stage": current_stage,
            "return_to": return_to,
            "critique": fb.get("critique", ""),
            "evidence": fb.get("evidence", ""),
            "suggestion": fb.get("suggestion", ""),
            "severity": fb.get("severity", "minor"),
            "iteration": state["iteration_number"],
        }
        feedback_history.append(feedback_obj)

    # Invalidate current token
    _invalidate_token(conn, current_token)

    # Save updated state
    _save_iteration_state(
        conn=conn,
        project_path=project_path,
        feature_name=feature_name,
        iteration_number=new_iteration,
        current_stage=return_to,
        accumulated_knowledge=state["accumulated_knowledge"],
        feedback_history=feedback_history,
        artifacts_produced=state["artifacts_produced"],
        preferences=state["preferences"],
    )

    # Create reflection record if provided
    if reflection and feedback:
        cursor = conn.cursor()
        # Use the first feedback item's source as the validator
        validator = feedback[0].get("source", "unknown")
        cursor.execute(
            """
            INSERT INTO reflections
            (feature_name, validator, iteration, failure_description, lesson_learned, status)
            VALUES (?, ?, ?, ?, ?, 'PENDING')
            """,
            (
                feature_name,
                validator,
                state["iteration_number"],
                feedback[0].get("critique", ""),
                reflection,
            ),
        )
        conn.commit()

    # Create new token
    new_token = _create_token(conn, feature_name, return_to)

    return {
        "status": "returned",
        "previous_stage": current_stage,
        "current_stage": return_to,
        "iteration_number": new_iteration,
        "token": new_token,
    }
