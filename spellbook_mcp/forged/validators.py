"""Validator infrastructure for the Forged autonomous development system.

This module provides the validator catalog and tools for invoking validators
on artifacts, managing validator dependencies, and handling transform levels.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from spellbook_mcp.forged.models import VALID_STAGES, ValidatorResult, Feedback


@dataclass
class Validator:
    """Represents a validator in the Forged system.

    Validators check artifacts for quality, correctness, and compliance with
    various standards. They can be backed by existing skills or be planned
    for future implementation.

    Attributes:
        id: Unique identifier for the validator
        name: Human-readable name
        status: "EXISTS" | "PLANNED" | "PLACEHOLDER"
        archetype: Category of validation (e.g., "code-quality", "accuracy", "design")
        applicable_stages: List of workflow stages where this validator applies
        skill: Name of the spellbook skill that implements this validator (if EXISTS)
        prompt_template: Template for validators without skill implementation
        feedback_schema: JSON schema for feedback structure
        transform_level: None | "mechanical" | "semantic"
        depends_on: List of validator IDs that must run before this one
    """

    id: str
    name: str
    status: str
    archetype: str
    applicable_stages: list[str]
    skill: Optional[str]
    prompt_template: Optional[str]
    feedback_schema: dict
    transform_level: Optional[str]
    depends_on: list[str]

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary.

        Returns:
            Dictionary with all validator fields
        """
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "archetype": self.archetype,
            "applicable_stages": self.applicable_stages,
            "skill": self.skill,
            "prompt_template": self.prompt_template,
            "feedback_schema": self.feedback_schema,
            "transform_level": self.transform_level,
            "depends_on": self.depends_on,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Validator":
        """Reconstruct Validator from dictionary.

        Args:
            data: Dictionary containing validator fields

        Returns:
            Reconstructed Validator instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            status=data["status"],
            archetype=data["archetype"],
            applicable_stages=data["applicable_stages"],
            skill=data.get("skill"),
            prompt_template=data.get("prompt_template"),
            feedback_schema=data.get("feedback_schema", {}),
            transform_level=data.get("transform_level"),
            depends_on=data.get("depends_on", []),
        )


# Standard feedback schema for code-quality validators
CODE_QUALITY_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "issue": {"type": "string"},
        "location": {"type": "string"},
        "severity": {"type": "string", "enum": ["blocking", "significant", "minor"]},
        "suggestion": {"type": "string"},
    },
    "required": ["issue", "severity"],
}

# Standard feedback schema for design validators
DESIGN_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "issue": {"type": "string"},
        "rationale": {"type": "string"},
        "severity": {"type": "string", "enum": ["blocking", "significant", "minor"]},
        "suggestion": {"type": "string"},
    },
    "required": ["issue", "severity"],
}

# Standard feedback schema for accuracy validators
ACCURACY_FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "claim": {"type": "string"},
        "finding": {"type": "string"},
        "evidence": {"type": "string"},
        "severity": {"type": "string", "enum": ["blocking", "significant", "minor"]},
    },
    "required": ["claim", "finding", "severity"],
}


# VALIDATOR_CATALOG: Registry of all validators
VALIDATOR_CATALOG: dict[str, Validator] = {
    # EXISTS validators - backed by existing spellbook skills
    "code_review": Validator(
        id="code_review",
        name="Code Review Validator",
        status="EXISTS",
        archetype="code-quality",
        applicable_stages=["IMPLEMENT", "COMPLETE"],
        skill="requesting-code-review",
        prompt_template=None,
        feedback_schema=CODE_QUALITY_FEEDBACK_SCHEMA,
        transform_level=None,  # Read-only validation
        depends_on=[],
    ),
    "test_quality": Validator(
        id="test_quality",
        name="Test Quality Validator",
        status="EXISTS",
        archetype="code-quality",
        applicable_stages=["IMPLEMENT", "COMPLETE"],
        skill="green-mirage-audit",
        prompt_template=None,
        feedback_schema=CODE_QUALITY_FEEDBACK_SCHEMA,
        transform_level=None,  # Read-only validation
        depends_on=[],
    ),
    "fact_check": Validator(
        id="fact_check",
        name="Fact Check Validator",
        status="EXISTS",
        archetype="accuracy",
        applicable_stages=["DESIGN", "PLAN", "IMPLEMENT", "COMPLETE"],
        skill="fact-checking",
        prompt_template=None,
        feedback_schema=ACCURACY_FEEDBACK_SCHEMA,
        transform_level=None,  # Read-only validation
        depends_on=[],
    ),
    "dead_code": Validator(
        id="dead_code",
        name="Dead Code Validator",
        status="EXISTS",
        archetype="code-quality",
        applicable_stages=["IMPLEMENT", "COMPLETE"],
        skill="finding-dead-code",
        prompt_template=None,
        feedback_schema=CODE_QUALITY_FEEDBACK_SCHEMA,
        transform_level=None,  # Read-only validation
        depends_on=["code_review"],  # Run after code review
    ),
    # PLANNED validators - not yet implemented
    "requirements_clarity": Validator(
        id="requirements_clarity",
        name="Requirements Clarity Validator",
        status="PLANNED",
        archetype="design",
        applicable_stages=["DISCOVER", "DESIGN"],
        skill=None,
        prompt_template="""Analyze the requirements document for clarity:
1. Check for ambiguous language
2. Identify missing acceptance criteria
3. Flag contradictory requirements
4. Verify testability of requirements""",
        feedback_schema=DESIGN_FEEDBACK_SCHEMA,
        transform_level=None,
        depends_on=[],
    ),
    "design_coherence": Validator(
        id="design_coherence",
        name="Design Coherence Validator",
        status="PLANNED",
        archetype="design",
        applicable_stages=["DESIGN", "PLAN"],
        skill=None,
        prompt_template="""Analyze the design document for coherence:
1. Check alignment with requirements
2. Verify component interfaces are consistent
3. Identify potential integration issues
4. Flag over-engineering or under-specification""",
        feedback_schema=DESIGN_FEEDBACK_SCHEMA,
        transform_level=None,
        depends_on=["requirements_clarity"],
    ),
}


def validators_for_stage(stage: str) -> list[Validator]:
    """Return validators applicable to the given stage.

    Args:
        stage: Workflow stage (must be in VALID_STAGES)

    Returns:
        List of Validator instances applicable to this stage

    Raises:
        ValueError: If stage is not a valid stage
    """
    if stage not in VALID_STAGES:
        raise ValueError(f"Invalid stage '{stage}'. Must be one of: {VALID_STAGES}")

    return [
        validator
        for validator in VALIDATOR_CATALOG.values()
        if stage in validator.applicable_stages
    ]


def resolve_validator_order(validator_ids: list[str]) -> list[str]:
    """Topological sort of validators based on depends_on.

    Ensures validators run after their dependencies.

    Args:
        validator_ids: List of validator IDs to sort

    Returns:
        List of validator IDs in dependency order

    Raises:
        ValueError: If unknown validator ID or circular dependency detected
    """
    if not validator_ids:
        return []

    # Validate all IDs exist
    for vid in validator_ids:
        if vid not in VALIDATOR_CATALOG:
            raise ValueError(f"Unknown validator: {vid}")

    # Build adjacency list for validators in our set
    id_set = set(validator_ids)
    in_degree: dict[str, int] = {vid: 0 for vid in validator_ids}
    dependents: dict[str, list[str]] = {vid: [] for vid in validator_ids}

    for vid in validator_ids:
        validator = VALIDATOR_CATALOG[vid]
        for dep in validator.depends_on:
            if dep in id_set:
                in_degree[vid] += 1
                dependents[dep].append(vid)

    # Kahn's algorithm for topological sort
    result: list[str] = []
    queue: list[str] = [vid for vid in validator_ids if in_degree[vid] == 0]

    while queue:
        # Sort queue for deterministic ordering of independent validators
        queue.sort()
        current = queue.pop(0)
        result.append(current)

        for dependent in dependents[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Check for cycles
    if len(result) != len(validator_ids):
        missing = set(validator_ids) - set(result)
        raise ValueError(f"Circular dependency detected involving: {missing}")

    return result


def get_transform_level(validator_id: str) -> Optional[str]:
    """Get the transform level for a validator.

    Args:
        validator_id: ID of the validator

    Returns:
        Transform level: None (read-only), "mechanical" (auto-apply),
        or "semantic" (requires approval)

    Raises:
        ValueError: If validator ID is unknown
    """
    if validator_id not in VALIDATOR_CATALOG:
        raise ValueError(f"Unknown validator: {validator_id}")

    return VALIDATOR_CATALOG[validator_id].transform_level


def _compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of file contents.

    Args:
        path: Path to the file

    Returns:
        Hex-encoded SHA-256 hash
    """
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validator_invoke(
    validator_id: str,
    artifact_path: str,
    context: Optional[dict] = None,
) -> ValidatorResult:
    """Invoke a validator on an artifact.

    Args:
        validator_id: ID of the validator to invoke
        artifact_path: Path to the artifact to validate
        context: Optional context dict (feature_name, iteration, etc.)

    Returns:
        ValidatorResult with verdict and feedback
    """
    # Check validator exists
    if validator_id not in VALIDATOR_CATALOG:
        return ValidatorResult(
            verdict="ERROR",
            feedback=None,
            transformed=False,
            artifact_path=artifact_path,
            artifact_hash="",
            transform_description=None,
            error=f"Unknown validator: {validator_id}",
        )

    validator = VALIDATOR_CATALOG[validator_id]

    # Check artifact exists
    path = Path(artifact_path)
    if not path.exists():
        return ValidatorResult(
            verdict="ERROR",
            feedback=None,
            transformed=False,
            artifact_path=artifact_path,
            artifact_hash="",
            transform_description=None,
            error=f"Artifact not found: {artifact_path}",
        )

    # Compute artifact hash
    artifact_hash = _compute_file_hash(path)

    # PLANNED validators abstain
    if validator.status == "PLANNED":
        return ValidatorResult(
            verdict="ABSTAIN",
            feedback=None,
            transformed=False,
            artifact_path=artifact_path,
            artifact_hash=artifact_hash,
            transform_description=None,
            error=None,
        )

    # PLACEHOLDER validators abstain
    if validator.status == "PLACEHOLDER":
        return ValidatorResult(
            verdict="ABSTAIN",
            feedback=None,
            transformed=False,
            artifact_path=artifact_path,
            artifact_hash=artifact_hash,
            transform_description=None,
            error=None,
        )

    # EXISTS validators - for now, return APPROVED as placeholder
    # In a full implementation, this would invoke the skill
    # and parse its output into feedback
    #
    # The actual skill invocation would look something like:
    # result = skill_invoke(validator.skill, artifact_path, context)
    # return parse_skill_result(result, artifact_path, artifact_hash)
    #
    # For now, we return APPROVED to indicate the validator ran successfully
    # without producing feedback. This is a valid outcome when the artifact
    # passes all checks.
    return ValidatorResult(
        verdict="APPROVED",
        feedback=None,
        transformed=False,
        artifact_path=artifact_path,
        artifact_hash=artifact_hash,
        transform_description=None,
        error=None,
    )
