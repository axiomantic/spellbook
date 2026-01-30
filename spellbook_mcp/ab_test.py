"""A/B test management for skill version experiments."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
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
    assigned_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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
        started_at = datetime.now(UTC).isoformat()
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


def experiment_pause(experiment_id: str, db_path: Optional[str] = None) -> dict:
    """Pause an active experiment without completing it.

    Args:
        experiment_id: UUID of experiment to pause
        db_path: Path to database (defaults to standard location)

    Returns:
        Dict with experiment status

    Raises:
        ExperimentNotFoundError: If experiment doesn't exist
        InvalidStatusTransitionError: If experiment not in active status
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)

    cursor = conn.execute(
        "SELECT status FROM experiments WHERE id = ?", (experiment_id,)
    )
    row = cursor.fetchone()

    if row is None:
        raise ExperimentNotFoundError(experiment_id)

    current_status = row[0]
    validate_status_transition(current_status, "paused")

    conn.execute(
        "UPDATE experiments SET status = 'paused' WHERE id = ?",
        (experiment_id,),
    )
    conn.commit()

    return {
        "success": True,
        "experiment_id": experiment_id,
        "status": "paused",
    }


def experiment_complete(experiment_id: str, db_path: Optional[str] = None) -> dict:
    """Mark experiment as completed and freeze data.

    Args:
        experiment_id: UUID of experiment to complete
        db_path: Path to database (defaults to standard location)

    Returns:
        Dict with experiment status and completed_at timestamp

    Raises:
        ExperimentNotFoundError: If experiment doesn't exist
        InvalidStatusTransitionError: If experiment not in active/paused status
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)

    cursor = conn.execute(
        "SELECT status FROM experiments WHERE id = ?", (experiment_id,)
    )
    row = cursor.fetchone()

    if row is None:
        raise ExperimentNotFoundError(experiment_id)

    current_status = row[0]
    validate_status_transition(current_status, "completed")

    completed_at = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE experiments SET status = 'completed', completed_at = ? WHERE id = ?",
        (completed_at, experiment_id),
    )
    conn.commit()

    return {
        "success": True,
        "experiment_id": experiment_id,
        "status": "completed",
        "completed_at": completed_at,
    }


def experiment_status(experiment_id: str, db_path: Optional[str] = None) -> dict:
    """Get current status and summary metrics for an experiment.

    Args:
        experiment_id: UUID of experiment
        db_path: Path to database (defaults to standard location)

    Returns:
        Dict with experiment details, variant counts, and metrics

    Raises:
        ExperimentNotFoundError: If experiment doesn't exist
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)

    # Get experiment
    cursor = conn.execute(
        """
        SELECT id, name, skill_name, status, description, created_at, started_at, completed_at
        FROM experiments WHERE id = ?
        """,
        (experiment_id,),
    )
    row = cursor.fetchone()

    if row is None:
        raise ExperimentNotFoundError(experiment_id)

    exp_id, name, skill_name, status, description, created_at, started_at, completed_at = row

    # Get variants with counts
    cursor = conn.execute(
        """
        SELECT ev.id, ev.variant_name, ev.skill_version, ev.weight,
               COUNT(DISTINCT va.session_id) as sessions_assigned,
               COUNT(DISTINCT so.id) as outcomes_recorded
        FROM experiment_variants ev
        LEFT JOIN variant_assignments va ON ev.id = va.variant_id
        LEFT JOIN skill_outcomes so ON ev.id = so.experiment_variant_id
        WHERE ev.experiment_id = ?
        GROUP BY ev.id
        """,
        (experiment_id,),
    )

    variants = []
    total_sessions = 0
    total_outcomes = 0

    for v_row in cursor.fetchall():
        v_id, v_name, v_version, v_weight, sessions, outcomes = v_row
        variants.append({
            "id": v_id,
            "name": v_name,
            "skill_version": v_version,
            "weight": v_weight,
            "sessions_assigned": sessions,
            "outcomes_recorded": outcomes,
        })
        total_sessions += sessions
        total_outcomes += outcomes

    return {
        "success": True,
        "experiment": {
            "id": exp_id,
            "name": name,
            "skill_name": skill_name,
            "status": status,
            "description": description,
            "created_at": created_at,
            "started_at": started_at,
            "completed_at": completed_at,
        },
        "variants": variants,
        "total_sessions": total_sessions,
        "total_outcomes": total_outcomes,
    }


def experiment_list(
    status: Optional[str] = None,
    skill_name: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """List experiments with optional status filter.

    Args:
        status: Filter by experiment status
        skill_name: Filter by target skill
        db_path: Path to database (defaults to standard location)

    Returns:
        Dict with list of experiments and total count
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)

    query = """
        SELECT e.id, e.name, e.skill_name, e.status, e.created_at,
               COUNT(DISTINCT ev.id) as variants_count,
               COUNT(DISTINCT va.session_id) as total_sessions
        FROM experiments e
        LEFT JOIN experiment_variants ev ON e.id = ev.experiment_id
        LEFT JOIN variant_assignments va ON e.id = va.experiment_id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND e.status = ?"
        params.append(status)

    if skill_name:
        query += " AND e.skill_name = ?"
        params.append(skill_name)

    query += " GROUP BY e.id ORDER BY e.created_at DESC"

    cursor = conn.execute(query, params)

    experiments = []
    for row in cursor.fetchall():
        exp_id, name, s_name, exp_status, created_at, variants_count, total_sessions = row
        experiments.append({
            "id": exp_id,
            "name": name,
            "skill_name": s_name,
            "status": exp_status,
            "created_at": created_at,
            "variants_count": variants_count,
            "total_sessions": total_sessions,
        })

    return {
        "success": True,
        "experiments": experiments,
        "total": len(experiments),
    }


import hashlib


def get_skill_version_for_session(
    skill_name: str,
    session_id: str,
    db_path: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Determine which skill version a session should receive.

    Args:
        skill_name: Name of skill being invoked
        session_id: Claude session ID
        db_path: Path to database (defaults to standard location)

    Returns:
        (experiment_id, variant_id, skill_version)
        All None if no active experiment for this skill.
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)

    # Find active or paused experiment for this skill
    cursor = conn.execute(
        """
        SELECT id, status FROM experiments
        WHERE skill_name = ? AND status IN ('active', 'paused')
        ORDER BY status = 'active' DESC
        LIMIT 1
        """,
        (skill_name,),
    )
    experiment = cursor.fetchone()

    if not experiment:
        return None, None, None

    experiment_id, status = experiment

    # Check for existing assignment
    cursor = conn.execute(
        """
        SELECT va.variant_id, ev.skill_version
        FROM variant_assignments va
        JOIN experiment_variants ev ON va.variant_id = ev.id
        WHERE va.experiment_id = ? AND va.session_id = ?
        """,
        (experiment_id, session_id),
    )
    assignment = cursor.fetchone()

    if assignment:
        return experiment_id, assignment[0], assignment[1]

    # No existing assignment
    if status == "paused":
        # Paused experiments do not create new assignments
        return None, None, None

    # Active experiment: create new assignment
    variant_id, skill_version = _assign_variant(experiment_id, session_id, conn)

    return experiment_id, variant_id, skill_version


def _assign_variant(
    experiment_id: str,
    session_id: str,
    conn,
) -> tuple[str, Optional[str]]:
    """Assign session to variant using deterministic hash.

    Args:
        experiment_id: UUID of experiment
        session_id: Session to assign
        conn: Database connection

    Returns:
        (variant_id, skill_version)
    """
    # Get variants with weights
    cursor = conn.execute(
        """
        SELECT id, skill_version, weight FROM experiment_variants
        WHERE experiment_id = ?
        ORDER BY variant_name
        """,
        (experiment_id,),
    )
    variants = cursor.fetchall()

    # Deterministic assignment based on hash
    hash_input = f"{experiment_id}:{session_id}".encode()
    hash_value = int(hashlib.sha256(hash_input).hexdigest(), 16) % 100

    cumulative = 0
    selected_variant_id = None
    selected_skill_version = None

    for variant_id, skill_version, weight in variants:
        cumulative += weight
        if hash_value < cumulative:
            selected_variant_id = variant_id
            selected_skill_version = skill_version
            break

    # Fallback to last variant (should not reach if weights sum to 100)
    if selected_variant_id is None:
        selected_variant_id = variants[-1][0]
        selected_skill_version = variants[-1][1]

    # Persist assignment
    conn.execute(
        """
        INSERT INTO variant_assignments (experiment_id, session_id, variant_id)
        VALUES (?, ?, ?)
        """,
        (experiment_id, session_id, selected_variant_id),
    )
    conn.commit()

    return selected_variant_id, selected_skill_version


def experiment_results(experiment_id: str, db_path: Optional[str] = None) -> dict:
    """Compare variant performance with detailed metrics.

    Args:
        experiment_id: UUID of experiment
        db_path: Path to database (defaults to standard location)

    Returns:
        Dict with per-variant metrics and comparison

    Raises:
        ExperimentNotFoundError: If experiment doesn't exist
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)

    # Get experiment
    cursor = conn.execute(
        """
        SELECT name, skill_name, status, created_at, started_at
        FROM experiments WHERE id = ?
        """,
        (experiment_id,),
    )
    row = cursor.fetchone()

    if row is None:
        raise ExperimentNotFoundError(experiment_id)

    name, skill_name, status, created_at, started_at = row

    # Calculate duration
    duration_days = None
    if started_at:
        start = datetime.fromisoformat(started_at)
        duration_days = (datetime.now(UTC) - start).days

    # Get per-variant metrics
    cursor = conn.execute(
        """
        SELECT ev.id, ev.variant_name, ev.skill_version,
               COUNT(DISTINCT va.session_id) as sessions,
               SUM(CASE WHEN so.outcome = 'completed' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN so.outcome = 'abandoned' THEN 1 ELSE 0 END) as abandoned,
               SUM(CASE WHEN so.outcome = 'superseded' THEN 1 ELSE 0 END) as superseded,
               SUM(CASE WHEN so.outcome = 'session_ended' THEN 1 ELSE 0 END) as session_ended,
               AVG(so.tokens_used) as avg_tokens,
               AVG(so.corrections) as avg_corrections,
               AVG(so.retries) as avg_retries
        FROM experiment_variants ev
        LEFT JOIN variant_assignments va ON ev.id = va.variant_id
        LEFT JOIN skill_outcomes so ON ev.id = so.experiment_variant_id
        WHERE ev.experiment_id = ?
        GROUP BY ev.id
        """,
        (experiment_id,),
    )

    results = {}
    for v_row in cursor.fetchall():
        (
            v_id, v_name, v_version, sessions, completed, abandoned,
            superseded, session_ended, avg_tokens, avg_corrections, avg_retries
        ) = v_row

        total_outcomes = (completed or 0) + (abandoned or 0) + (superseded or 0) + (session_ended or 0)
        completion_rate = (completed or 0) / total_outcomes if total_outcomes > 0 else 0
        abandonment_rate = (abandoned or 0) / total_outcomes if total_outcomes > 0 else 0

        results[v_name] = {
            "variant_id": v_id,
            "skill_version": v_version,
            "sessions": sessions or 0,
            "outcomes": {
                "completed": completed or 0,
                "abandoned": abandoned or 0,
                "superseded": superseded or 0,
                "session_ended": session_ended or 0,
            },
            "metrics": {
                "completion_rate": round(completion_rate, 3),
                "abandonment_rate": round(abandonment_rate, 3),
                "avg_tokens_used": round(avg_tokens or 0, 0),
                "avg_corrections": round(avg_corrections or 0, 1),
                "avg_retries": round(avg_retries or 0, 1),
            },
        }

    # Build comparison
    # Note: For A/B/n tests with multiple treatment variants, this comparison
    # only evaluates control vs the best-performing treatment. For comprehensive
    # multi-variant analysis, examine the per-variant metrics in results directly.
    comparison = {}
    variant_names = list(results.keys())
    if len(variant_names) >= 2 and "control" in results:
        control = results["control"]
        control_cr = control["metrics"]["completion_rate"]
        
        # Find the best-performing treatment variant
        treatment_variants = [(n, results[n]) for n in variant_names if n != "control"]
        if treatment_variants:
            # Sort by completion rate descending to get best treatment
            treatment_variants.sort(
                key=lambda x: x[1]["metrics"]["completion_rate"],
                reverse=True
            )
            treatment_name, treatment = treatment_variants[0]
            treatment_cr = treatment["metrics"]["completion_rate"]

            comparison = {
                "completion_rate_delta": round(treatment_cr - control_cr, 3),
                "token_efficiency_delta": round(
                    (treatment["metrics"]["avg_tokens_used"] or 0) - (control["metrics"]["avg_tokens_used"] or 0), 0
                ),
                "correction_rate_delta": round(
                    (treatment["metrics"]["avg_corrections"] or 0) - (control["metrics"]["avg_corrections"] or 0), 1
                ),
                "preliminary_winner": treatment_name if treatment_cr > control_cr else "control",
                # For A/B/n tests, indicate which treatment was compared
                "compared_treatment": treatment_name if len(treatment_variants) > 1 else None,
            }

    return {
        "success": True,
        "experiment_id": experiment_id,
        "name": name,
        "skill_name": skill_name,
        "status": status,
        "duration_days": duration_days,
        "results": results,
        "comparison": comparison,
    }
