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
