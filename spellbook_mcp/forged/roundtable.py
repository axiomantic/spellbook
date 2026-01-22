"""Roundtable MCP tools for Forged autonomous development system.

This module provides roundtable validation using tarot archetypes.
Each archetype brings a unique perspective to validate stage completion:

- Magician: Technical precision, implementation quality
- Priestess: Hidden knowledge, edge cases, what's not being said
- Hermit: Deep analysis, thorough understanding
- Fool: Naive questions, challenging assumptions
- Chariot: Forward momentum, actionable progress
- Justice: Synthesis/resolution, final arbitration
- Lovers: Integration, how pieces work together
- Hierophant: Standards, best practices, conventions
- Emperor: Constraints, boundaries, resources
- Queen: User needs, stakeholder value
"""

from pathlib import Path
from typing import Optional

from spellbook_mcp.forged.artifacts import read_artifact
from spellbook_mcp.forged.models import VALID_STAGES, Feedback
from spellbook_mcp.forged.verdict_parsing import (
    VALID_ROUNDTABLE_VERDICTS,
    ParsedVerdict,
    parse_roundtable_response,
)


# =============================================================================
# Archetype Definitions
# =============================================================================

ROUNDTABLE_ARCHETYPES: dict[str, dict[str, str]] = {
    "Magician": {
        "description": "Master of technical craft and implementation",
        "focus": "Technical precision, code quality, implementation correctness",
        "questions": "Is the implementation sound? Are there technical flaws?",
    },
    "Priestess": {
        "description": "Keeper of hidden knowledge and intuition",
        "focus": "Hidden knowledge, edge cases, unstated assumptions",
        "questions": "What's not being said? What edge cases are missed?",
    },
    "Hermit": {
        "description": "Seeker of deep understanding through solitary reflection",
        "focus": "Deep analysis, thorough understanding, root causes",
        "questions": "Have we truly understood the problem? Is this the right approach?",
    },
    "Fool": {
        "description": "Bearer of naive wisdom and fresh perspectives",
        "focus": "Naive questions, challenging assumptions, simplicity",
        "questions": "Why is this so complicated? What if we did something simpler?",
    },
    "Chariot": {
        "description": "Driver of progress and directed action",
        "focus": "Forward momentum, actionable progress, unblocking",
        "questions": "What's blocking progress? How do we move forward?",
    },
    "Justice": {
        "description": "Arbiter of balance and synthesis",
        "focus": "Synthesis, resolution, fair weighing of perspectives",
        "questions": "How do we balance these concerns? What's the right decision?",
    },
    "Lovers": {
        "description": "Weaver of connections and integration",
        "focus": "Integration, how pieces work together, relationships",
        "questions": "How does this fit with the rest? Are the interfaces clean?",
    },
    "Hierophant": {
        "description": "Guardian of standards and established wisdom",
        "focus": "Standards, best practices, conventions, patterns",
        "questions": "Does this follow established patterns? Are best practices used?",
    },
    "Emperor": {
        "description": "Ruler of boundaries and resources",
        "focus": "Constraints, boundaries, resources, scope",
        "questions": "Are we within scope? Do we have the resources? What are the limits?",
    },
    "Queen": {
        "description": "Voice of the user and stakeholder value",
        "focus": "User needs, stakeholder value, practical outcomes",
        "questions": "Does this serve the user? Will stakeholders be satisfied?",
    },
}

# Default archetypes by stage
_DEFAULT_ARCHETYPES_BY_STAGE: dict[str, list[str]] = {
    "DISCOVER": ["Fool", "Queen", "Priestess", "Justice"],
    "DESIGN": ["Hermit", "Hierophant", "Lovers", "Justice"],
    "PLAN": ["Emperor", "Chariot", "Magician", "Justice"],
    "IMPLEMENT": ["Magician", "Hermit", "Hierophant", "Justice"],
    "COMPLETE": ["Magician", "Queen", "Justice"],
    "ESCALATED": ["Justice"],
}


# =============================================================================
# Utility Functions
# =============================================================================


def get_default_archetypes(stage: str) -> list[str]:
    """Get default archetypes for a stage.

    Args:
        stage: Workflow stage (must be in VALID_STAGES)

    Returns:
        List of archetype names appropriate for the stage

    Raises:
        ValueError: If stage is not a valid stage
    """
    if stage not in VALID_STAGES:
        raise ValueError(f"Invalid stage '{stage}'. Must be one of: {VALID_STAGES}")

    return _DEFAULT_ARCHETYPES_BY_STAGE.get(stage, ["Justice"])


def has_conflict(verdicts: dict[str, str]) -> bool:
    """Check if there is conflict among verdicts.

    Conflict exists when there are both APPROVE and ITERATE verdicts.
    ABSTAIN verdicts are ignored for conflict detection.

    Args:
        verdicts: Dict mapping archetype names to verdict strings

    Returns:
        True if conflicting verdicts exist, False otherwise
    """
    active_verdicts = {
        v for v in verdicts.values() if v in ("APPROVE", "ITERATE")
    }
    return len(active_verdicts) > 1


def determine_consensus(
    verdicts: dict[str, str], current_stage: str
) -> tuple[bool, Optional[str]]:
    """Determine consensus and return stage if iteration needed.

    Args:
        verdicts: Dict mapping archetype names to verdict strings
        current_stage: The current workflow stage

    Returns:
        Tuple of (consensus_reached, return_to_stage)
        - consensus_reached: True if all active verdicts are APPROVE
        - return_to_stage: Stage to return to if ITERATE, else None
    """
    if not verdicts:
        return True, None

    # Filter out ABSTAIN verdicts
    active_verdicts = [
        v for v in verdicts.values() if v in ("APPROVE", "ITERATE")
    ]

    if not active_verdicts:
        # All abstained
        return True, None

    # Check if any ITERATE
    if "ITERATE" in active_verdicts:
        # Determine which stage to return to based on current stage
        return_to = _determine_return_stage(current_stage)
        return False, return_to

    # All active verdicts are APPROVE
    return True, None


def _determine_return_stage(current_stage: str) -> str:
    """Determine which stage to return to on ITERATE.

    Generally returns the same stage for iteration, but can be
    customized for stage-specific logic.

    Args:
        current_stage: The current workflow stage

    Returns:
        Stage to return to for iteration
    """
    # For now, return to the same stage to iterate on current work
    # Could be enhanced to return to earlier stages based on feedback
    return current_stage


# =============================================================================
# Prompt Building
# =============================================================================


def build_roundtable_prompt(
    feature_name: str,
    stage: str,
    artifact_content: str,
    archetypes: Optional[list[str]] = None,
) -> str:
    """Build the roundtable prompt for convening archetypes.

    Args:
        feature_name: Name of the feature being developed
        stage: Current workflow stage
        artifact_content: Content of the artifact to review
        archetypes: List of archetype names to include (defaults to stage defaults)

    Returns:
        Complete prompt string for LLM
    """
    if archetypes is None:
        archetypes = get_default_archetypes(stage) if stage in VALID_STAGES else ["Justice"]

    # Build archetype instructions
    archetype_sections = []
    for name in archetypes:
        if name in ROUNDTABLE_ARCHETYPES:
            info = ROUNDTABLE_ARCHETYPES[name]
            archetype_sections.append(
                f"**{name}** ({info['description']})\n"
                f"Focus: {info['focus']}\n"
                f"Consider: {info['questions']}"
            )

    archetype_instructions = "\n\n".join(archetype_sections)

    prompt = f"""# Roundtable Convene: {feature_name}

## Stage: {stage}

You are convening a roundtable of tarot archetypes to validate the completion
of the {stage} stage for feature "{feature_name}".

## Participating Archetypes

{archetype_instructions}

## Artifact to Review

```
{artifact_content}
```

## Instructions

Each archetype should provide their perspective on the artifact, then render
a verdict. Use this format for each archetype:

**ArchetypeName**: [Archetype's perspective and analysis]

Concerns:
- [Any concerns, one per line with bullet]

Suggestions:
- [Any suggestions for improvement]

Verdict: [APPROVE | ITERATE | ABSTAIN]
Severity: [blocking | important | minor] (only if ITERATE)

## Verdict Meanings

- **APPROVE**: The artifact meets requirements for this stage
- **ITERATE**: The artifact needs revision before proceeding
- **ABSTAIN**: The archetype has no relevant input for this artifact

## Begin Roundtable

Each archetype speaks in turn. End with a summary of verdicts.
"""
    return prompt


def _build_debate_prompt(
    feature_name: str,
    conflicting_verdicts: dict[str, str],
    artifact_content: str,
) -> str:
    """Build prompt for Justice to moderate debate.

    Args:
        feature_name: Name of the feature
        conflicting_verdicts: Dict of archetype -> verdict
        artifact_content: Content of the artifact

    Returns:
        Prompt string for debate moderation
    """
    verdicts_summary = "\n".join(
        f"- **{archetype}**: {verdict}"
        for archetype, verdict in conflicting_verdicts.items()
    )

    prompt = f"""# Roundtable Debate: {feature_name}

## Conflict Detected

The roundtable has conflicting verdicts that require resolution:

{verdicts_summary}

## Artifact Under Review

```
{artifact_content}
```

## Justice Moderates

As **Justice**, you must synthesize the perspectives and render a binding
decision. Consider:

1. The weight of concerns raised by those voting ITERATE
2. The validity of approval from those voting APPROVE
3. The overall quality and completeness of the artifact
4. What best serves the project moving forward

Provide your analysis and then render a binding verdict.

## Response Format

**Justice**: [Analysis of the conflicting perspectives]

Reasoning: [Why you reached this decision]

Binding Decision: [APPROVE | ITERATE]
"""
    return prompt


# =============================================================================
# Main Functions
# =============================================================================


def roundtable_convene(
    feature_name: str,
    stage: str,
    artifact_path: str,
    archetypes: Optional[list[str]] = None,
) -> dict:
    """Convene roundtable to validate stage completion.

    This is the primary entry point for roundtable validation. It reads
    the artifact, builds a prompt for the selected archetypes, and returns
    a structure ready for LLM processing.

    Note: This function generates the prompt and structure but does not
    invoke an LLM directly. The caller is responsible for LLM invocation.

    Args:
        feature_name: Name of the feature being developed
        stage: Current workflow stage (must be in VALID_STAGES)
        artifact_path: Path to the artifact file to validate
        archetypes: List of archetype names to include (optional)

    Returns:
        Dict with:
        - consensus: bool (True if all APPROVE, initially False)
        - verdicts: dict[archetype, verdict] (empty initially)
        - feedback: list[Feedback] (empty initially)
        - return_to: str | None (stage to return to)
        - dialogue: str (the generated prompt for LLM)
        - error: str | None (error message if artifact not found)

    Raises:
        ValueError: If stage is not a valid stage
    """
    # Validate stage
    if stage not in VALID_STAGES:
        raise ValueError(f"Invalid stage '{stage}'. Must be one of: {VALID_STAGES}")

    # Read artifact
    artifact_content = read_artifact(artifact_path)

    if artifact_content is None:
        return {
            "consensus": False,
            "verdicts": {},
            "feedback": [
                Feedback(
                    source="roundtable",
                    stage=stage,
                    return_to=stage,
                    critique=f"Artifact not found: {artifact_path}",
                    evidence=f"Path does not exist: {artifact_path}",
                    suggestion="Ensure the artifact file exists before convening roundtable",
                    severity="blocking",
                    iteration=0,
                ).to_dict()
            ],
            "return_to": stage,
            "dialogue": "",
            "error": f"Artifact not found: {artifact_path}",
        }

    # Get archetypes
    if archetypes is None:
        archetypes = get_default_archetypes(stage)

    # Build prompt
    dialogue = build_roundtable_prompt(
        feature_name=feature_name,
        stage=stage,
        artifact_content=artifact_content,
        archetypes=archetypes,
    )

    # Return structure for caller to process with LLM
    # The caller should:
    # 1. Send dialogue to LLM
    # 2. Parse response with parse_roundtable_response()
    # 3. Update verdicts and consensus based on parsed results
    return {
        "consensus": False,  # Will be updated after LLM response
        "verdicts": {},  # Will be populated after LLM response
        "feedback": [],  # Will be populated after LLM response
        "return_to": None,  # Will be set if ITERATE
        "dialogue": dialogue,
        "archetypes": archetypes,  # Included for reference
    }


def roundtable_debate(
    feature_name: str,
    conflicting_verdicts: dict[str, str],
    artifact_path: str,
) -> dict:
    """Moderate debate when archetypes disagree.

    Justice archetype synthesizes conflicting perspectives and
    renders a binding decision.

    Note: This function generates the prompt but does not invoke
    an LLM directly. The caller is responsible for LLM invocation.

    Args:
        feature_name: Name of the feature
        conflicting_verdicts: Dict mapping archetype names to verdicts
        artifact_path: Path to the artifact under debate

    Returns:
        Dict with:
        - binding_decision: str (the verdict from Justice)
        - reasoning: str (explanation of the decision)
        - moderator: str ("Justice")
        - dialogue: str (the generated prompt)
        - error: str | None (if artifact not found)
    """
    # Read artifact
    artifact_content = read_artifact(artifact_path)

    if artifact_content is None:
        return {
            "binding_decision": "ABSTAIN",
            "reasoning": f"Cannot debate: artifact not found at {artifact_path}",
            "moderator": "Justice",
            "dialogue": "",
            "error": f"Artifact not found: {artifact_path}",
        }

    # Build debate prompt
    dialogue = _build_debate_prompt(
        feature_name=feature_name,
        conflicting_verdicts=conflicting_verdicts,
        artifact_content=artifact_content,
    )

    # Return structure for caller to process with LLM
    # The caller should:
    # 1. Send dialogue to LLM
    # 2. Parse response to extract binding decision and reasoning
    return {
        "binding_decision": "ABSTAIN",  # Will be updated after LLM response
        "reasoning": "",  # Will be populated after LLM response
        "moderator": "Justice",
        "dialogue": dialogue,
    }


def process_roundtable_response(
    response: str,
    stage: str,
    iteration: int = 1,
) -> dict:
    """Process an LLM response from roundtable convene.

    This helper parses the LLM response and returns a complete
    result structure.

    Args:
        response: Raw LLM response text
        stage: The workflow stage
        iteration: Current iteration number

    Returns:
        Dict with consensus, verdicts, feedback, return_to
    """
    parsed_verdicts = parse_roundtable_response(response)

    # Build verdicts dict
    verdicts = {pv.archetype: pv.verdict for pv in parsed_verdicts}

    # Determine consensus
    consensus, return_to = determine_consensus(verdicts, stage)

    # Build feedback from ITERATE verdicts
    feedback = []
    for pv in parsed_verdicts:
        if pv.verdict == "ITERATE":
            for concern in pv.concerns:
                feedback.append(
                    Feedback(
                        source=f"roundtable:{pv.archetype}",
                        stage=stage,
                        return_to=stage,
                        critique=concern,
                        evidence=f"Raised by {pv.archetype}",
                        suggestion=pv.suggestions[0] if pv.suggestions else "",
                        severity=pv.severity or "significant",
                        iteration=iteration,
                    ).to_dict()
                )

    return {
        "consensus": consensus,
        "verdicts": verdicts,
        "feedback": feedback,
        "return_to": return_to,
        "parsed_verdicts": [pv.to_dict() for pv in parsed_verdicts],
    }
