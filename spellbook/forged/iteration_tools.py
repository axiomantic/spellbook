"""Iteration MCP tools for workflow enforcement and orchestration.

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

Uses SQLAlchemy ORM (ForgeToken, IterationState, ForgeReflection) with
async sessions.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from spellbook.db.forged_models import (
    ForgeToken,
    ForgeReflection,
    IterationState as IterationStateORM,
)
from spellbook.forged.models import VALID_STAGES
from spellbook.forged.project_tools import _load_project_graph


# Stages that can be returned to (not terminal states)
_RETURNABLE_STAGES = ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT"]

# Stage progression order (index determines next stage)
_STAGE_ORDER = ["DISCOVER", "DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"]


def _get_project_path() -> str:
    """Get current project path from working directory."""
    return os.getcwd()


def _generate_token() -> str:
    """Generate a unique workflow token."""
    return str(uuid4())


async def _validate_token(
    session: AsyncSession, token: str, feature_name: str
) -> dict:
    """Validate a workflow token.

    Args:
        session: Async DB session
        token: Token to validate
        feature_name: Expected feature name

    Returns:
        Dict with validation result
    """
    stmt = select(ForgeToken).where(ForgeToken.id == token)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return {"valid": False, "error": "Invalid token: not found"}

    if row.invalidated_at is not None:
        return {"valid": False, "error": "Token expired: already used"}

    if row.feature_name != feature_name:
        return {
            "valid": False,
            "error": f"Token feature mismatch: token for '{row.feature_name}' cannot be used for '{feature_name}'",
        }

    return {"valid": True, "stage": row.stage}


async def _invalidate_token(session: AsyncSession, token: str) -> None:
    """Mark a token as invalidated."""
    now = datetime.now(timezone.utc).isoformat()
    stmt = (
        update(ForgeToken)
        .where(ForgeToken.id == token)
        .values(invalidated_at=now)
    )
    await session.execute(stmt)


async def _invalidate_feature_tokens(
    session: AsyncSession, feature_name: str
) -> None:
    """Invalidate all tokens for a feature."""
    now = datetime.now(timezone.utc).isoformat()
    stmt = (
        update(ForgeToken)
        .where(
            ForgeToken.feature_name == feature_name,
            ForgeToken.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )
    await session.execute(stmt)


async def _create_token(
    session: AsyncSession, feature_name: str, stage: str
) -> str:
    """Create a new workflow token."""
    token_id = _generate_token()
    now = datetime.now(timezone.utc).isoformat()
    token = ForgeToken(
        id=token_id,
        feature_name=feature_name,
        stage=stage,
        created_at=now,
    )
    session.add(token)
    await session.flush()
    return token_id


async def _get_iteration_state(
    session: AsyncSession, project_path: str, feature_name: str
) -> Optional[dict]:
    """Get existing iteration state for a feature."""
    stmt = select(IterationStateORM).where(
        IterationStateORM.project_path == project_path,
        IterationStateORM.feature_name == feature_name,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return None

    return {
        "iteration_number": row.iteration_number,
        "current_stage": row.current_stage,
        "accumulated_knowledge": json.loads(row.accumulated_knowledge) if row.accumulated_knowledge else {},
        "feedback_history": json.loads(row.feedback_history) if row.feedback_history else [],
        "artifacts_produced": json.loads(row.artifacts_produced) if row.artifacts_produced else [],
        "preferences": json.loads(row.preferences) if row.preferences else {},
    }


async def _save_iteration_state(
    session: AsyncSession,
    project_path: str,
    feature_name: str,
    iteration_number: int,
    current_stage: str,
    accumulated_knowledge: dict,
    feedback_history: list,
    artifacts_produced: list,
    preferences: dict,
) -> None:
    """Save or update iteration state via ORM merge."""
    now = datetime.now(timezone.utc).isoformat()

    # Check if exists
    stmt = select(IterationStateORM).where(
        IterationStateORM.project_path == project_path,
        IterationStateORM.feature_name == feature_name,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.iteration_number = iteration_number
        existing.current_stage = current_stage
        existing.accumulated_knowledge = json.dumps(accumulated_knowledge)
        existing.feedback_history = json.dumps(feedback_history)
        existing.artifacts_produced = json.dumps(artifacts_produced)
        existing.preferences = json.dumps(preferences)
        existing.updated_at = now
    else:
        state = IterationStateORM(
            project_path=project_path,
            feature_name=feature_name,
            iteration_number=iteration_number,
            current_stage=current_stage,
            accumulated_knowledge=json.dumps(accumulated_knowledge),
            feedback_history=json.dumps(feedback_history),
            artifacts_produced=json.dumps(artifacts_produced),
            preferences=json.dumps(preferences),
            created_at=now,
            updated_at=now,
        )
        session.add(state)

    await session.flush()


def _get_next_stage(current_stage: str) -> Optional[str]:
    """Get the next stage in the workflow."""
    if current_stage not in _STAGE_ORDER:
        return None
    idx = _STAGE_ORDER.index(current_stage)
    if idx >= len(_STAGE_ORDER) - 1:
        return None
    return _STAGE_ORDER[idx + 1]


def _check_dependencies(project_path: str, feature_name: str) -> dict:
    """Check if all dependencies for a feature are COMPLETE.

    Reads the project graph JSON to find the feature's depends_on list,
    then checks each dependency's status.

    Args:
        project_path: Project path
        feature_name: Feature to check dependencies for

    Returns:
        Dict with:
        - blocked: bool (True if any dependency is not COMPLETE)
        - details: list of {name, status, blocking} per dependency
    """
    project_graph = _load_project_graph(project_path)
    if project_graph is None:
        return {"blocked": False, "details": []}

    # Find this feature's node in the project graph
    feature_node = None
    for node_id, node in project_graph.features.items():
        if node.id == feature_name or node.name == feature_name:
            feature_node = node
            break

    if feature_node is None:
        return {"blocked": False, "details": []}

    depends_on = feature_node.depends_on
    if not depends_on:
        return {"blocked": False, "details": []}

    details = []
    blocked = False

    for dep_name in depends_on:
        # Look up each dependency's status in the project graph
        dep_node = None
        for node_id, node in project_graph.features.items():
            if node.id == dep_name or node.name == dep_name:
                dep_node = node
                break

        if dep_node is None:
            details.append({
                "name": dep_name,
                "status": "NOT_FOUND",
                "blocking": True,
            })
            blocked = True
        else:
            dep_status = dep_node.status
            if dep_status != "complete":
                details.append({
                    "name": dep_name,
                    "status": dep_status,
                    "blocking": True,
                })
                blocked = True
            else:
                details.append({
                    "name": dep_name,
                    "status": "complete",
                    "blocking": False,
                })

    return {"blocked": blocked, "details": details}


async def forge_iteration_start(
    feature_name: str,
    starting_stage: str = "DISCOVER",
    preferences: Optional[dict] = None,
    project_path: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> dict:
    """Start or resume an iteration cycle for a feature.

    Creates initial state for a new feature or loads existing state.
    Returns a token for the current stage that must be used in subsequent
    advance/return calls.

    Args:
        feature_name: Name of the feature being developed
        starting_stage: Initial stage (default: DISCOVER)
        preferences: Optional user preferences to store
        project_path: Project path (defaults to cwd)
        session: Optional async session (injected for testing)

    Returns:
        Dict containing status, feature_name, current_stage,
        iteration_number, token, and optionally error.
    """
    # Validate starting stage
    if starting_stage not in VALID_STAGES:
        return {
            "status": "error",
            "error": f"Invalid stage: '{starting_stage}'. Must be one of: {VALID_STAGES}",
        }

    if project_path is None:
        project_path = _get_project_path()

    # Check dependencies before allowing start
    dep_status = _check_dependencies(project_path, feature_name)
    if dep_status["blocked"]:
        return {
            "status": "blocked",
            "error": "Dependencies not yet complete",
            "feature_name": feature_name,
            "dependencies": dep_status["details"],
        }

    async def _do(s: AsyncSession) -> dict:
        # Invalidate any existing tokens for this feature
        await _invalidate_feature_tokens(s, feature_name)

        # Check for existing state
        existing = await _get_iteration_state(s, project_path, feature_name)

        if existing:
            # Resume existing feature
            token = await _create_token(s, feature_name, existing["current_stage"])
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
        await _save_iteration_state(
            session=s,
            project_path=project_path,
            feature_name=feature_name,
            iteration_number=1,
            current_stage=starting_stage,
            accumulated_knowledge={},
            feedback_history=[],
            artifacts_produced=[],
            preferences=preferences or {},
        )

        token = await _create_token(s, feature_name, starting_stage)

        return {
            "status": "started",
            "feature_name": feature_name,
            "current_stage": starting_stage,
            "iteration_number": 1,
            "token": token,
        }

    if session is not None:
        return await _do(session)

    from spellbook.db import get_forged_session

    async with get_forged_session() as s:
        return await _do(s)


async def forge_iteration_advance(
    feature_name: str,
    current_token: str,
    evidence: Optional[dict] = None,
    project_path: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> dict:
    """Advance to next stage after consensus.

    Validates the token, transitions to the next stage, and returns
    a new token for the next operation.

    Args:
        feature_name: Name of the feature being developed
        current_token: Token from previous operation
        evidence: Optional evidence/knowledge to store from current stage
        project_path: Project path (defaults to cwd)
        session: Optional async session (injected for testing)

    Returns:
        Dict containing status, previous_stage, current_stage,
        iteration_number, token, and optionally error.
    """
    if project_path is None:
        project_path = _get_project_path()

    async def _do(s: AsyncSession) -> dict:
        # Validate token
        validation = await _validate_token(s, current_token, feature_name)
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
        state = await _get_iteration_state(s, project_path, feature_name)
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
        await _invalidate_token(s, current_token)

        # Save updated state
        await _save_iteration_state(
            session=s,
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
        new_token = await _create_token(s, feature_name, next_stage)

        return {
            "status": "advanced",
            "previous_stage": current_stage,
            "current_stage": next_stage,
            "iteration_number": state["iteration_number"],
            "token": new_token,
        }

    if session is not None:
        return await _do(session)

    from spellbook.db import get_forged_session

    async with get_forged_session() as s:
        return await _do(s)


async def forge_iteration_return(
    feature_name: str,
    current_token: str,
    return_to: str,
    feedback: list,
    reflection: Optional[str] = None,
    project_path: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> dict:
    """Return to earlier stage with feedback.

    Increments the iteration counter, stores feedback, and returns
    to the specified earlier stage.

    Args:
        feature_name: Name of the feature being developed
        current_token: Token from previous operation
        return_to: Stage to return to
        feedback: List of feedback dicts
        reflection: Optional lesson learned
        project_path: Project path (defaults to cwd)
        session: Optional async session (injected for testing)

    Returns:
        Dict containing status, previous_stage, current_stage,
        iteration_number, token, and optionally error.
    """
    if project_path is None:
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

    # Require at least one feedback item
    if not feedback:
        return {
            "status": "error",
            "error": "Feedback is required when returning to an earlier stage.",
        }

    async def _do(s: AsyncSession) -> dict:
        # Validate token
        validation = await _validate_token(s, current_token, feature_name)
        if not validation["valid"]:
            return {"status": "error", "error": validation["error"]}

        current_stage = validation["stage"]

        # Get current state
        state = await _get_iteration_state(s, project_path, feature_name)
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
        await _invalidate_token(s, current_token)

        # Save updated state
        await _save_iteration_state(
            session=s,
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
            validator = feedback[0].get("source", "unknown")
            now = datetime.now(timezone.utc).isoformat()
            ref = ForgeReflection(
                feature_name=feature_name,
                validator=validator,
                iteration=state["iteration_number"],
                failure_description=feedback[0].get("critique", ""),
                lesson_learned=reflection,
                status="PENDING",
                created_at=now,
            )
            s.add(ref)
            await s.flush()

        # Create new token
        new_token = await _create_token(s, feature_name, return_to)

        return {
            "status": "returned",
            "previous_stage": current_stage,
            "current_stage": return_to,
            "iteration_number": new_iteration,
            "token": new_token,
        }

    if session is not None:
        return await _do(session)

    from spellbook.db import get_forged_session

    async with get_forged_session() as s:
        return await _do(s)
