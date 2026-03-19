"""MCP tools for Forge workflow (autonomous development)."""

import re
from pathlib import Path

from spellbook.mcp.server import mcp
from spellbook_mcp.config_tools import get_spellbook_dir
from spellbook_mcp.forged.iteration_tools import (
    forge_iteration_advance as do_forge_iteration_advance,
    forge_iteration_return as do_forge_iteration_return,
    forge_iteration_start as do_forge_iteration_start,
)
from spellbook_mcp.forged.project_tools import (
    forge_feature_update as do_forge_feature_update,
    forge_project_init as do_forge_project_init,
    forge_project_status as do_forge_project_status,
    forge_select_skill as do_forge_select_skill,
)
from spellbook_mcp.forged.roundtable import (
    process_roundtable_response as do_process_roundtable_response,
    roundtable_convene as do_roundtable_convene,
    roundtable_debate as do_roundtable_debate,
)
from spellbook_mcp.injection import inject_recovery_context


def _extract_section(content: str, section_name: str) -> str | None:
    """Extract a named section from skill content.

    Tries XML-style tags first: <SECTION>...</SECTION>
    Then tries markdown headers: ## Section Name ... (until next ##)

    Args:
        content: Full skill content
        section_name: Name of section to extract

    Returns:
        Extracted section content, or None if not found
    """
    # Try XML-style tags first: <SECTION>...</SECTION>
    pattern = f"<{section_name}>(.*?)</{section_name}>"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try markdown headers: ## Section Name ... (until next ## or end)
    pattern = f"##\\s+{section_name}[^#]*?(?=##|$)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(0).strip()

    return None


@mcp.tool()
@inject_recovery_context
def forge_iteration_start(
    feature_name: str,
    starting_stage: str = "DISCOVER",
    preferences: dict = None,
) -> dict:
    """
    Start or resume an iteration cycle for a feature.

    Creates initial state for a new feature or loads existing state.
    Returns a token for the current stage that must be used in subsequent
    advance/return calls.

    Args:
        feature_name: Name of the feature being developed
        starting_stage: Initial stage (default: DISCOVER). Valid stages:
                       DISCOVER, DESIGN, PLAN, IMPLEMENT, COMPLETE, ESCALATED
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
    return do_forge_iteration_start(
        feature_name=feature_name,
        starting_stage=starting_stage,
        preferences=preferences,
    )


@mcp.tool()
@inject_recovery_context
def forge_iteration_advance(
    feature_name: str,
    current_token: str,
    evidence: dict = None,
) -> dict:
    """
    Advance to next stage after consensus (APPROVE verdict).

    Validates the token, transitions to the next stage, and returns
    a new token for the next operation.

    Stage progression: DISCOVER -> DESIGN -> PLAN -> IMPLEMENT -> COMPLETE

    Args:
        feature_name: Name of the feature being developed
        current_token: Token from previous operation (required for authorization)
        evidence: Optional evidence/knowledge to store from current stage

    Returns:
        Dict containing:
        - status: "advanced" | "error"
        - previous_stage: Stage before advancement
        - current_stage: New current stage
        - token: New workflow token
        - error: Error message if status is "error"
    """
    return do_forge_iteration_advance(
        feature_name=feature_name,
        current_token=current_token,
        evidence=evidence,
    )


@mcp.tool()
@inject_recovery_context
def forge_iteration_return(
    feature_name: str,
    current_token: str,
    return_to: str,
    feedback: list,
    reflection: str = None,
) -> dict:
    """
    Return to earlier stage with feedback (ITERATE verdict).

    Increments the iteration counter, stores feedback, and returns
    to the specified earlier stage.

    Args:
        feature_name: Name of the feature being developed
        current_token: Token from previous operation (required for authorization)
        return_to: Stage to return to (must be DISCOVER, DESIGN, PLAN, or IMPLEMENT)
        feedback: List of feedback dicts with structure:
            - source: Validator name
            - critique: Issue description
            - evidence: Supporting evidence
            - suggestion: Recommended fix
            - severity: "blocking" | "significant" | "minor"
        reflection: Optional lesson learned from this iteration

    Returns:
        Dict containing:
        - status: "returned" | "error"
        - previous_stage: Stage before return
        - current_stage: Stage returned to
        - iteration_number: New iteration count (incremented)
        - token: New workflow token
        - error: Error message if status is "error"
    """
    return do_forge_iteration_return(
        feature_name=feature_name,
        current_token=current_token,
        return_to=return_to,
        feedback=feedback,
        reflection=reflection,
    )


@mcp.tool()
@inject_recovery_context
def forge_project_init(
    project_path: str,
    project_name: str,
    features: list,
) -> dict:
    """
    Initialize a new project graph with feature decomposition.

    Creates a project graph from feature definitions, validates dependencies,
    and computes topological sort for execution order.

    Args:
        project_path: Absolute path to project directory
        project_name: Human-readable project name
        features: List of feature definitions with:
            - id: Unique feature identifier
            - name: Human-readable feature name
            - description: Feature description
            - depends_on: List of feature IDs this depends on (optional)
            - estimated_complexity: "low" | "medium" | "high" (optional)

    Returns:
        Dict containing:
        - success: True if initialization succeeded
        - graph: Project graph data structure
        - error: Error message if success is False
    """
    return do_forge_project_init(
        project_path=project_path,
        project_name=project_name,
        features=features,
    )


@mcp.tool()
@inject_recovery_context
def forge_project_status(project_path: str) -> dict:
    """
    Get current project status and progress.

    Returns the project graph with progress information including
    completion percentage and feature states.

    Args:
        project_path: Absolute path to project directory

    Returns:
        Dict containing:
        - success: True if project found
        - graph: Project graph data structure
        - progress: Progress info with total_features, completed_features,
                   completion_percentage
        - error: Error message if success is False
    """
    return do_forge_project_status(project_path=project_path)


@mcp.tool()
@inject_recovery_context
def forge_feature_update(
    project_path: str,
    feature_id: str,
    status: str = None,
    assigned_skill: str = None,
    artifacts: list = None,
) -> dict:
    """
    Update a feature's status and/or artifacts.

    Args:
        project_path: Absolute path to project directory
        feature_id: ID of feature to update
        status: New status (pending, in_progress, complete, blocked)
        assigned_skill: Skill assigned to this feature
        artifacts: List of artifact paths to add

    Returns:
        Dict containing:
        - success: True if update succeeded
        - feature: Updated feature data
        - error: Error message if success is False
    """
    return do_forge_feature_update(
        project_path=project_path,
        feature_id=feature_id,
        status=status,
        assigned_skill=assigned_skill,
        artifacts=artifacts,
    )


@mcp.tool()
@inject_recovery_context
def forge_select_skill(
    project_path: str,
    feature_id: str,
    stage: str,
    feedback_history: list = None,
) -> dict:
    """
    Select the appropriate skill for current context.

    Uses stage and feedback history to recommend the best skill
    for the current development context.

    Args:
        project_path: Absolute path to project directory
        feature_id: ID of current feature
        stage: Current workflow stage
        feedback_history: Optional list of feedback dicts from prior iterations

    Returns:
        Dict containing:
        - success: True if skill selected
        - skill: Recommended skill name
        - feature_id: The feature ID
        - stage: The current stage
        - error: Error message if success is False
    """
    return do_forge_select_skill(
        project_path=project_path,
        feature_id=feature_id,
        stage=stage,
        feedback_history=feedback_history,
    )


@mcp.tool()
@inject_recovery_context
def forge_roundtable_convene(
    feature_name: str,
    stage: str,
    artifact_path: str,
    archetypes: list = None,
) -> dict:
    """
    Convene roundtable to validate stage completion.

    Generates a prompt for tarot archetype validation of the artifact.
    Each archetype brings a unique perspective:
    - Magician: Technical precision, implementation quality
    - Priestess: Hidden knowledge, edge cases
    - Hermit: Deep analysis, thorough understanding
    - Fool: Naive questions, challenging assumptions
    - Chariot: Forward momentum, actionable progress
    - Justice: Synthesis/resolution, final arbitration
    - Lovers: Integration, how pieces work together
    - Hierophant: Standards, best practices, conventions
    - Emperor: Constraints, boundaries, resources
    - Queen: User needs, stakeholder value

    Args:
        feature_name: Name of the feature being developed
        stage: Current workflow stage (DISCOVER, DESIGN, PLAN, IMPLEMENT, etc.)
        artifact_path: Path to the artifact file to validate
        archetypes: List of archetype names to include (uses stage defaults if omitted)

    Returns:
        Dict containing:
        - consensus: False (updated after processing LLM response)
        - verdicts: Empty dict (populated after processing)
        - feedback: Empty list (populated after processing)
        - return_to: None (set if ITERATE verdict)
        - dialogue: Generated prompt for LLM
        - archetypes: List of participating archetypes
        - error: Error message if artifact not found
    """
    return do_roundtable_convene(
        feature_name=feature_name,
        stage=stage,
        artifact_path=artifact_path,
        archetypes=archetypes,
    )


@mcp.tool()
@inject_recovery_context
def forge_roundtable_debate(
    feature_name: str,
    conflicting_verdicts: dict,
    artifact_path: str,
) -> dict:
    """
    Moderate debate when archetypes disagree.

    Justice archetype synthesizes conflicting perspectives and
    renders a binding decision when roundtable has mixed verdicts.

    Args:
        feature_name: Name of the feature
        conflicting_verdicts: Dict mapping archetype names to verdicts
        artifact_path: Path to the artifact under debate

    Returns:
        Dict containing:
        - binding_decision: "ABSTAIN" (updated after processing)
        - reasoning: Empty string (populated after processing)
        - moderator: "Justice"
        - dialogue: Generated prompt for LLM
        - error: Error message if artifact not found
    """
    return do_roundtable_debate(
        feature_name=feature_name,
        conflicting_verdicts=conflicting_verdicts,
        artifact_path=artifact_path,
    )


@mcp.tool()
@inject_recovery_context
def forge_process_roundtable_response(
    response: str,
    stage: str,
    iteration: int = 1,
) -> dict:
    """
    Process an LLM response from roundtable convene.

    Parses the LLM response to extract verdicts, determine consensus,
    and generate feedback items.

    Args:
        response: Raw LLM response text from roundtable convene
        stage: The workflow stage being validated
        iteration: Current iteration number (default: 1)

    Returns:
        Dict containing:
        - consensus: True if all active verdicts are APPROVE
        - verdicts: Dict mapping archetype names to verdict strings
        - feedback: List of Feedback dicts from ITERATE verdicts
        - return_to: Stage to return to if ITERATE, else None
        - parsed_verdicts: List of parsed verdict details
    """
    return do_process_roundtable_response(
        response=response,
        stage=stage,
        iteration=iteration,
    )


@mcp.tool()
@inject_recovery_context
def skill_instructions_get(
    skill_name: str,
    sections: list = None,
) -> dict:
    """
    Fetch skill instructions from SKILL.md file.

    Used to extract behavioral constraints for injection after compaction.
    If sections specified, returns only those sections.

    Args:
        skill_name: Name of the skill (e.g., "develop")
        sections: Optional list of section names to extract (e.g., ["FORBIDDEN", "REQUIRED", "ROLE"])
                  If None, returns full content.

    Returns:
        {
            "success": True/False,
            "skill_name": str,
            "path": str,  # Path to SKILL.md
            "content": str,  # Full content or extracted sections
            "sections": {  # If sections param provided
                "FORBIDDEN": "...",
                "REQUIRED": "...",
                ...
            },
            "error": str  # If success is False
        }
    """
    # Resolve skill path
    spellbook_dir = get_spellbook_dir()
    skill_path = spellbook_dir / "skills" / skill_name / "SKILL.md"

    # Check if skill exists
    if not skill_path.exists():
        return {
            "success": False,
            "skill_name": skill_name,
            "path": str(skill_path),
            "error": f"Skill not found: {skill_path}",
        }

    # Read skill content
    try:
        content = skill_path.read_text(encoding="utf-8")
    except OSError as e:
        return {
            "success": False,
            "skill_name": skill_name,
            "path": str(skill_path),
            "error": f"Failed to read skill file: {e}",
        }

    # If no sections requested, return full content
    if not sections:
        return {
            "success": True,
            "skill_name": skill_name,
            "path": str(skill_path),
            "content": content,
        }

    # Extract requested sections
    extracted_sections = {}
    for section_name in sections:
        section_content = _extract_section(content, section_name)
        if section_content is not None:
            extracted_sections[section_name] = section_content

    # Build combined content from found sections
    combined_content = "\n\n".join(
        f"## {name}\n{text}" for name, text in extracted_sections.items()
    )

    return {
        "success": True,
        "skill_name": skill_name,
        "path": str(skill_path),
        "content": combined_content,
        "sections": extracted_sections,
    }
