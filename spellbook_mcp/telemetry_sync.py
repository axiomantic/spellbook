"""Telemetry synchronization for A/B test integration."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TelemetryAggregate:
    """Aggregated telemetry metrics for a skill."""

    skill_name: str
    total_invocations: int
    total_completions: int
    total_abandonments: int
    avg_tokens_used: float
    avg_corrections: float

    @property
    def completion_rate(self) -> float:
        """Calculate completion rate."""
        if self.total_invocations == 0:
            return 0.0
        return self.total_completions / self.total_invocations


def sync_outcomes_to_experiments(db_path: Optional[str] = None) -> dict:
    """Link skill outcomes to experiment variants based on session assignments.

    For outcomes without an experiment_variant_id, looks up the session's
    variant assignment and links them.

    Args:
        db_path: Path to database (defaults to standard location)

    Returns:
        Dict with count of outcomes synced
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)

    # Find outcomes without variant assignment where session has one
    cursor = conn.execute(
        """
        SELECT so.id, va.variant_id
        FROM skill_outcomes so
        JOIN variant_assignments va ON so.session_id = va.session_id
        JOIN experiment_variants ev ON va.variant_id = ev.id
        JOIN experiments e ON ev.experiment_id = e.id
        WHERE so.experiment_variant_id IS NULL
          AND so.skill_name = e.skill_name
        """
    )

    updates = cursor.fetchall()

    for outcome_id, variant_id in updates:
        conn.execute(
            "UPDATE skill_outcomes SET experiment_variant_id = ? WHERE id = ?",
            (variant_id, outcome_id),
        )

    conn.commit()

    return {
        "success": True,
        "outcomes_synced": len(updates),
    }
