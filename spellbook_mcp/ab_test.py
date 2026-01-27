"""A/B test management for skill version experiments."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ExperimentStatus(str, Enum):
    """Valid experiment lifecycle states."""

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class OutcomeType(str, Enum):
    """Valid skill outcome types."""

    COMPLETED = "completed"
    ABANDONED = "abandoned"
    SUPERSEDED = "superseded"
    SESSION_ENDED = "session_ended"


class ABTestErrorCode(str, Enum):
    """Error codes for A/B test operations."""

    EXPERIMENT_NOT_FOUND = "EXPERIMENT_NOT_FOUND"
    EXPERIMENT_EXISTS = "EXPERIMENT_EXISTS"
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"
    CONCURRENT_EXPERIMENT = "CONCURRENT_EXPERIMENT"
    INVALID_VARIANTS = "INVALID_VARIANTS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"


class ABTestError(Exception):
    """Base exception for A/B test operations."""

    def __init__(
        self,
        code: ABTestErrorCode,
        message: str,
        recoverable: bool = False,
        context: Optional[dict] = None,
    ):
        super().__init__(message)
        self.code = code
        self.recoverable = recoverable
        self.context = context or {}

    def user_message(self) -> str:
        """Return formatted message for display to user."""
        return f"[{self.code.value}] {self.args[0]}"

    def to_mcp_response(self) -> dict:
        """Convert to MCP tool error response format."""
        return {
            "success": False,
            "error": self.code.value,
            "message": str(self),
            "recoverable": self.recoverable,
            "details": self.context,
        }


class ExperimentNotFoundError(ABTestError):
    """Experiment with given ID does not exist."""

    def __init__(self, experiment_id: str):
        super().__init__(
            code=ABTestErrorCode.EXPERIMENT_NOT_FOUND,
            message=f"Experiment not found: {experiment_id}",
            recoverable=False,
            context={"experiment_id": experiment_id},
        )


class ExperimentExistsError(ABTestError):
    """Experiment with given name already exists."""

    def __init__(self, name: str, existing_id: Optional[str] = None):
        context = {"name": name}
        if existing_id:
            context["existing_id"] = existing_id
        super().__init__(
            code=ABTestErrorCode.EXPERIMENT_EXISTS,
            message=f"Experiment already exists: {name}",
            recoverable=False,
            context=context,
        )


class InvalidStatusTransitionError(ABTestError):
    """Invalid experiment status transition requested."""

    def __init__(self, current: str, requested: str, experiment_id: Optional[str] = None):
        context = {"current_status": current, "requested_status": requested}
        if experiment_id:
            context["experiment_id"] = experiment_id
        super().__init__(
            code=ABTestErrorCode.INVALID_STATUS_TRANSITION,
            message=f"Cannot transition from '{current}' to '{requested}'",
            recoverable=False,
            context=context,
        )


class ConcurrentExperimentError(ABTestError):
    """Another experiment for this skill is already active."""

    def __init__(self, skill_name: str, active_experiment_id: str):
        super().__init__(
            code=ABTestErrorCode.CONCURRENT_EXPERIMENT,
            message=f"Active experiment already exists for skill '{skill_name}': {active_experiment_id}",
            recoverable=True,
            context={
                "skill_name": skill_name,
                "active_experiment_id": active_experiment_id,
            },
        )


class InvalidVariantsError(ABTestError):
    """Variant configuration is invalid."""

    def __init__(self, reason: str, variants: Optional[list] = None):
        context = {"reason": reason}
        if variants:
            context["variants_provided"] = len(variants)
        super().__init__(
            code=ABTestErrorCode.INVALID_VARIANTS,
            message=f"Invalid variants: {reason}",
            recoverable=True,
            context=context,
        )


class ValidationError(ABTestError):
    """Generic validation error for input parameters."""

    def __init__(self, field_name: str, reason: str, value: Optional[str] = None):
        context = {"field": field_name, "reason": reason}
        if value is not None:
            context["value"] = value
        super().__init__(
            code=ABTestErrorCode.VALIDATION_ERROR,
            message=f"Validation error for '{field_name}': {reason}",
            recoverable=True,
            context=context,
        )


@dataclass
class Variant:
    """A single variant within an experiment."""

    id: str
    experiment_id: str
    variant_name: str
    skill_version: Optional[str]
    weight: int
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not 0 <= self.weight <= 100:
            raise ValueError(f"weight must be 0-100, got {self.weight}")
        if not self.variant_name:
            raise ValueError("variant_name cannot be empty")


@dataclass
class Experiment:
    """Top-level experiment definition."""

    id: str
    name: str
    skill_name: str
    status: ExperimentStatus = ExperimentStatus.CREATED
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    variants: list[Variant] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.skill_name:
            raise ValueError("skill_name cannot be empty")

    def validate_variants(self) -> None:
        """Validate variant configuration."""
        if len(self.variants) < 2:
            raise InvalidVariantsError("At least 2 variants required")

        total_weight = sum(v.weight for v in self.variants)
        if total_weight != 100:
            raise InvalidVariantsError(
                f"Variant weights must sum to 100, got {total_weight}"
            )

        has_control = any(v.skill_version is None for v in self.variants)
        if not has_control:
            raise InvalidVariantsError(
                "At least one variant must have skill_version=None (control)"
            )


@dataclass
class Assignment:
    """Sticky session-to-variant mapping."""

    id: int
    experiment_id: str
    session_id: str
    variant_id: str
    assigned_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VariantMetrics:
    """Computed metrics for a single variant."""

    variant_id: str
    variant_name: str
    skill_version: Optional[str]
    sessions_assigned: int
    outcomes: dict[str, int]
    completion_rate: float
    abandonment_rate: float
    avg_tokens_used: float
    avg_corrections: float
    avg_retries: float


# Valid status transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    "created": {"active"},
    "active": {"paused", "completed"},
    "paused": {"active", "completed"},
    "completed": set(),
}


def validate_status_transition(current: str, target: str) -> None:
    """Validate experiment status transition is allowed."""
    if target not in VALID_TRANSITIONS.get(current, set()):
        raise InvalidStatusTransitionError(current, target)


import uuid


def experiment_create(
    name: str,
    skill_name: str,
    variants: list[dict],
    description: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Create a new experiment with defined variants.

    Args:
        name: Human-readable unique identifier (1-100 chars, alphanumeric with hyphens/underscores)
        skill_name: Target skill name
        variants: List of variant dicts with 'name', optional 'skill_version', and 'weight'
        description: Optional experiment description
        db_path: Path to database (defaults to standard location)

    Returns:
        Dict with experiment details including generated IDs

    Raises:
        ExperimentExistsError: If name already taken
        InvalidVariantsError: If variants are invalid
        ValidationError: If name format is invalid
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    # Validate name format
    if not name or len(name) > 100:
        raise ValidationError("name", "must be 1-100 characters", name)

    # Generate IDs
    experiment_id = str(uuid.uuid4())

    # Build Variant objects for validation
    variant_objects = []
    for v in variants:
        variant_id = str(uuid.uuid4())
        variant_objects.append(
            Variant(
                id=variant_id,
                experiment_id=experiment_id,
                variant_name=v.get("name", ""),
                skill_version=v.get("skill_version"),
                weight=v.get("weight", 0),
            )
        )

    # Create and validate experiment
    experiment = Experiment(
        id=experiment_id,
        name=name,
        skill_name=skill_name,
        description=description,
        variants=variant_objects,
    )
    experiment.validate_variants()

    conn = get_connection(db_path)

    # Check for existing experiment with same name
    cursor = conn.execute(
        "SELECT id FROM experiments WHERE name = ?", (name,)
    )
    existing = cursor.fetchone()
    if existing:
        raise ExperimentExistsError(name, existing[0])

    # Insert experiment
    conn.execute(
        """
        INSERT INTO experiments (id, name, skill_name, status, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            experiment.id,
            experiment.name,
            experiment.skill_name,
            experiment.status.value,
            experiment.description,
            experiment.created_at.isoformat(),
        ),
    )

    # Insert variants
    for v in variant_objects:
        conn.execute(
            """
            INSERT INTO experiment_variants (id, experiment_id, variant_name, skill_version, weight, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (v.id, v.experiment_id, v.variant_name, v.skill_version, v.weight, v.created_at.isoformat()),
        )

    conn.commit()

    return {
        "success": True,
        "experiment_id": experiment.id,
        "name": experiment.name,
        "skill_name": experiment.skill_name,
        "status": experiment.status.value,
        "variants": [
            {
                "id": v.id,
                "name": v.variant_name,
                "skill_version": v.skill_version,
                "weight": v.weight,
            }
            for v in variant_objects
        ],
    }


def experiment_start(experiment_id: str, db_path: Optional[str] = None) -> dict:
    """Activate an experiment for variant assignment.

    Args:
        experiment_id: UUID of experiment to start
        db_path: Path to database (defaults to standard location)

    Returns:
        Dict with experiment status and started_at timestamp

    Raises:
        ExperimentNotFoundError: If experiment doesn't exist
        InvalidStatusTransitionError: If experiment not in created/paused status
        ConcurrentExperimentError: If another experiment for the skill is active
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)

    # Get experiment
    cursor = conn.execute(
        "SELECT name, skill_name, status, started_at FROM experiments WHERE id = ?",
        (experiment_id,),
    )
    row = cursor.fetchone()

    if row is None:
        raise ExperimentNotFoundError(experiment_id)

    name, skill_name, current_status, existing_started_at = row

    # Validate status transition
    validate_status_transition(current_status, "active")

    # Check for concurrent active experiment for same skill
    cursor = conn.execute(
        """
        SELECT id FROM experiments
        WHERE skill_name = ? AND status = 'active' AND id != ?
        """,
        (skill_name, experiment_id),
    )
    active_experiment = cursor.fetchone()
    if active_experiment:
        raise ConcurrentExperimentError(skill_name, active_experiment[0])

    # Set started_at only if first activation
    started_at = existing_started_at
    if started_at is None:
        started_at = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE experiments SET status = 'active', started_at = ? WHERE id = ?",
            (started_at, experiment_id),
        )
    else:
        conn.execute(
            "UPDATE experiments SET status = 'active' WHERE id = ?",
            (experiment_id,),
        )

    conn.commit()

    return {
        "success": True,
        "experiment_id": experiment_id,
        "status": "active",
        "started_at": started_at,
    }
