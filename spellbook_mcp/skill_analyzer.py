"""Skill usage analysis tools for measuring skill performance."""

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from spellbook_mcp.session_ops import load_jsonl

from datetime import datetime

# Outcome enum values and their triggers
OUTCOME_COMPLETED = "completed"      # skill.completed=True, skill.superseded=False
OUTCOME_ABANDONED = "abandoned"      # skill.completed=False, skill.end_idx is set, not superseded
OUTCOME_SUPERSEDED = "superseded"    # skill.superseded=True
OUTCOME_SESSION_ENDED = "session_ended"  # session inactive for 5+ minutes, skill still open


def _get_tool_uses(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract tool_use blocks from Claude Code message format.

    Claude Code stores tool uses in msg.message.content[] as blocks with type=tool_use.
    """
    message = msg.get("message", {})
    content = message.get("content", [])

    if not isinstance(content, list):
        return []

    return [block for block in content if isinstance(block, dict) and block.get("type") == "tool_use"]


def _get_user_content(msg: Dict[str, Any]) -> str:
    """Extract user message content."""
    if msg.get("type") != "user":
        return ""

    message = msg.get("message", {})
    content = message.get("content", "")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and "text" in b
        )
    return ""


def _get_role(msg: Dict[str, Any]) -> str:
    """Extract message role."""
    return msg.get("message", {}).get("role", msg.get("type", ""))


def _get_claude_sessions_dir() -> Path:
    """Get Claude Code sessions directory for current project.

    Claude stores sessions in ~/.claude/projects/<encoded-path>/
    where encoded-path has a leading dash and slashes replaced with dashes.
    """
    cwd = os.getcwd()
    # Claude's encoding: leading dash, then path with slashes as dashes
    encoded = "-" + cwd.replace("/", "-").lstrip("-")
    return Path.home() / ".claude" / "projects" / encoded


# Patterns indicating user correction/dissatisfaction
CORRECTION_PATTERNS = [
    re.compile(r"\bno\b(?![tw])", re.IGNORECASE),  # "no" but not "not", "now"
    re.compile(r"\bstop\b", re.IGNORECASE),
    re.compile(r"\bwrong\b", re.IGNORECASE),
    re.compile(r"\bactually\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\b", re.IGNORECASE),
    re.compile(r"\binstead\b", re.IGNORECASE),
    re.compile(r"\bthat'?s?\s+not\b", re.IGNORECASE),
    re.compile(r"\bincorrect\b", re.IGNORECASE),
    re.compile(r"\bredo\b", re.IGNORECASE),
]


# Outcome type constants
OUTCOME_COMPLETED = "completed"
OUTCOME_ABANDONED = "abandoned"
OUTCOME_SUPERSEDED = "superseded"
OUTCOME_SESSION_ENDED = "session_ended"


from datetime import datetime as dt


@dataclass
class SkillInvocation:
    """A single skill invocation event."""

    skill: str
    version: Optional[str] = None
    start_idx: int = 0
    end_idx: Optional[int] = None
    timestamp: Optional[str] = None
    tokens_used: int = 0
    corrections: int = 0
    completed: bool = False
    superseded: bool = False
    retried: bool = False
    session_path: str = ""


@dataclass
class SkillMetrics:
    """Aggregated metrics for a skill."""

    skill: str
    version: Optional[str] = None
    invocations: int = 0
    completions: int = 0
    corrections: int = 0
    retries: int = 0
    total_tokens: int = 0
    invocation_details: List[SkillInvocation] = field(default_factory=list)

    @property
    def completion_rate(self) -> float:
        return self.completions / self.invocations if self.invocations > 0 else 0.0

    @property
    def correction_rate(self) -> float:
        return self.corrections / self.invocations if self.invocations > 0 else 0.0

    @property
    def avg_tokens(self) -> float:
        return self.total_tokens / self.invocations if self.invocations > 0 else 0.0

    @property
    def failure_score(self) -> float:
        """Higher = worse performance."""
        if self.invocations == 0:
            return 0.0
        failures = self.corrections + self.retries + (self.invocations - self.completions)
        return failures / self.invocations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill": self.skill,
            "version": self.version,
            "invocations": self.invocations,
            "completions": self.completions,
            "corrections": self.corrections,
            "retries": self.retries,
            "avg_tokens": round(self.avg_tokens),
            "completion_rate": round(self.completion_rate, 2),
            "correction_rate": round(self.correction_rate, 2),
            "failure_score": round(self.failure_score, 2),
        }


@dataclass
class SkillOutcome:
    """Persistent skill outcome record for analytics.

    Created from SkillInvocation but adds persistence-specific fields.
    """
    id: Optional[int] = None  # DB auto-increment, None before insert
    skill_name: str = ""
    skill_version: Optional[str] = None
    session_id: str = ""  # Session filename (stem), LOCAL ONLY
    project_encoded: str = ""  # Encoded project path, LOCAL ONLY
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    outcome: str = ""  # One of OUTCOME_* constants
    tokens_used: int = 0  # LOCAL ONLY (bucketed for telemetry)
    corrections: int = 0  # LOCAL ONLY (never telemetered)
    retries: int = 0
    created_at: Optional[datetime] = None

    @classmethod
    def from_invocation(
        cls,
        inv: "SkillInvocation",
        session_id: str,
        project_encoded: str,
    ) -> "SkillOutcome":
        """Convert SkillInvocation to SkillOutcome.

        Outcome decision table:
        | completed | superseded | end_idx set | => outcome        |
        |-----------|------------|-------------|-------------------|
        | True      | False      | any         | completed         |
        | True      | True       | any         | superseded        |
        | False     | True       | any         | superseded        |
        | False     | False      | True        | abandoned         |
        | False     | False      | False       | (still active)    |
        """
        if inv.superseded:
            outcome = OUTCOME_SUPERSEDED
        elif inv.completed:
            outcome = OUTCOME_COMPLETED
        elif inv.end_idx is not None:
            outcome = OUTCOME_ABANDONED
        else:
            outcome = ""  # Still active, not yet persistable as final

        start_time = None
        if inv.timestamp:
            try:
                start_time = datetime.fromisoformat(inv.timestamp)
            except (ValueError, TypeError):
                pass

        return cls(
            skill_name=inv.skill,
            skill_version=inv.version,
            session_id=session_id,
            project_encoded=project_encoded,
            start_time=start_time,
            end_time=None,  # Calculated when finalized
            duration_seconds=None,  # Calculated when finalized
            outcome=outcome,
            tokens_used=inv.tokens_used,
            corrections=inv.corrections,
            retries=1 if inv.retried else 0,
        )


@dataclass
class TelemetryAggregate:
    """Anonymous aggregate for telemetry transmission.

    Contains only bucketed, non-identifying information.
    """
    skill_name: str
    skill_version: Optional[str]
    outcome: str  # completed|abandoned|superseded|session_ended
    duration_bucket: str  # <1m|1-5m|5-15m|15-30m|30m+
    token_bucket: str     # <1k|1-5k|5-20k|20-50k|50k+
    count: int            # Minimum 5 before transmission


def _extract_version(skill_name: str, args: Optional[str]) -> Tuple[str, Optional[str]]:
    """Extract version from skill name or args.

    Returns (base_skill_name, version).
    """
    # Check for :v1, :v2 suffix
    if ":" in skill_name:
        base, version = skill_name.rsplit(":", 1)
        if version.startswith("v") and version[1:].isdigit():
            return base, version

    # Check args for version markers
    if args:
        match = re.search(r"\[v(\d+)\]|--version\s+v?(\d+)", args, re.IGNORECASE)
        if match:
            version_num = match.group(1) or match.group(2)
            return skill_name, f"v{version_num}"

    return skill_name, None


def _detect_correction(content: str) -> bool:
    """Detect if user message contains correction patterns."""
    for pattern in CORRECTION_PATTERNS:
        if pattern.search(content):
            return True
    return False


def _get_tokens_from_message(msg: Dict[str, Any]) -> int:
    """Extract token count from assistant message."""
    usage = msg.get("message", {}).get("usage", {})
    return usage.get("output_tokens", 0)


def extract_skill_invocations(messages: List[Dict[str, Any]], session_path: str = "") -> List[SkillInvocation]:
    """Extract all skill invocations from a session.

    Returns list of SkillInvocation objects with boundaries and metrics.
    """
    invocations: List[SkillInvocation] = []
    current_invocation: Optional[SkillInvocation] = None

    for idx, msg in enumerate(messages):
        msg_type = msg.get("type", "")

        # Check for compact boundary (ends current skill)
        if msg_type == "system" and msg.get("subtype") == "compact_boundary":
            if current_invocation:
                current_invocation.end_idx = idx
                current_invocation.completed = True
                invocations.append(current_invocation)
                current_invocation = None
            continue

        # Check for skill tool calls
        for call in _get_tool_uses(msg):
            if call.get("name") == "Skill":
                # End previous invocation if exists
                if current_invocation:
                    current_invocation.end_idx = idx
                    current_invocation.superseded = True
                    invocations.append(current_invocation)

                # Start new invocation
                skill_input = call.get("input", {})
                skill_name = skill_input.get("skill", "unknown")
                args = skill_input.get("args")
                base_skill, version = _extract_version(skill_name, args)

                current_invocation = SkillInvocation(
                    skill=base_skill,
                    version=version,
                    start_idx=idx,
                    timestamp=msg.get("timestamp"),
                    session_path=session_path,
                )

        # Track tokens for current invocation
        if current_invocation and msg_type == "assistant":
            current_invocation.tokens_used += _get_tokens_from_message(msg)

        # Check for user corrections
        if current_invocation and _get_role(msg) == "user":
            content = _get_user_content(msg)
            if _detect_correction(content):
                current_invocation.corrections += 1

    # Close final invocation
    if current_invocation:
        current_invocation.end_idx = len(messages)
        current_invocation.completed = True
        invocations.append(current_invocation)

    # Detect retries (same skill invoked within 5 messages)
    for i, inv in enumerate(invocations):
        for j in range(i + 1, min(i + 3, len(invocations))):
            if invocations[j].skill == inv.skill:
                invocations[j].retried = True
                break

    return invocations


def aggregate_metrics(
    invocations: List[SkillInvocation],
    group_by_version: bool = False,
) -> Dict[str, SkillMetrics]:
    """Aggregate invocations into per-skill metrics.

    Args:
        invocations: List of skill invocations
        group_by_version: If True, separate metrics by version

    Returns:
        Dict mapping skill key to SkillMetrics
    """
    metrics: Dict[str, SkillMetrics] = {}

    for inv in invocations:
        if group_by_version and inv.version:
            key = f"{inv.skill}:{inv.version}"
            version = inv.version
        else:
            key = inv.skill
            version = None

        if key not in metrics:
            metrics[key] = SkillMetrics(skill=inv.skill, version=version)

        m = metrics[key]
        m.invocations += 1
        m.total_tokens += inv.tokens_used
        m.corrections += inv.corrections
        m.invocation_details.append(inv)

        if inv.completed and not inv.superseded:
            m.completions += 1
        if inv.retried:
            m.retries += 1

    return metrics


def analyze_sessions(
    session_paths: Optional[List[str]] = None,
    skills_filter: Optional[List[str]] = None,
    group_by_version: bool = False,
    limit: int = 20,
) -> Dict[str, Any]:
    """Analyze skill usage across sessions.

    Args:
        session_paths: Specific sessions to analyze (defaults to recent)
        skills_filter: Only include these skills
        group_by_version: Separate metrics by version for A/B testing
        limit: Max sessions to analyze if not specified

    Returns:
        Analysis report with metrics and rankings
    """
    # Get sessions
    if session_paths:
        paths = [Path(p) for p in session_paths]
    else:
        sessions_dir = _get_claude_sessions_dir()
        if not sessions_dir.exists():
            return {"error": f"Sessions directory not found: {sessions_dir}"}

        paths = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    # Extract invocations from all sessions
    all_invocations: List[SkillInvocation] = []
    sessions_analyzed = 0

    for path in paths:
        try:
            messages = load_jsonl(str(path))
            invocations = extract_skill_invocations(messages, str(path))

            if skills_filter:
                invocations = [inv for inv in invocations if inv.skill in skills_filter]

            all_invocations.extend(invocations)
            sessions_analyzed += 1
        except Exception as e:
            continue  # Skip malformed sessions

    # Aggregate metrics
    metrics = aggregate_metrics(all_invocations, group_by_version=group_by_version)

    # Rank by failure score (weak skills)
    ranked = sorted(metrics.values(), key=lambda m: m.failure_score, reverse=True)

    # Build report
    report = {
        "sessions_analyzed": sessions_analyzed,
        "total_invocations": len(all_invocations),
        "unique_skills": len(metrics),
        "skill_metrics": [m.to_dict() for m in ranked],
        "weak_skills": [m.to_dict() for m in ranked[:5] if m.failure_score > 0.2],
    }

    # A/B comparison if versions present
    if group_by_version:
        version_pairs = defaultdict(list)
        for m in metrics.values():
            if m.version:
                version_pairs[m.skill].append(m)

        comparisons = []
        for skill, versions in version_pairs.items():
            if len(versions) >= 2:
                # Sort by version
                versions.sort(key=lambda m: m.version or "")
                comparisons.append(
                    {
                        "skill": skill,
                        "versions": [v.to_dict() for v in versions],
                        "recommendation": _compare_versions(versions),
                    }
                )
        report["version_comparisons"] = comparisons

    return report


def _compare_versions(versions: List[SkillMetrics]) -> str:
    """Generate recommendation comparing versions."""
    if len(versions) < 2:
        return "Insufficient versions for comparison"

    v1, v2 = versions[0], versions[-1]

    # Need minimum samples
    if v1.invocations < 5 or v2.invocations < 5:
        return f"Insufficient data (need 5+ invocations each, have {v1.invocations}/{v2.invocations})"

    # Compare metrics
    improvements = []
    regressions = []

    if v2.completion_rate > v1.completion_rate + 0.1:
        improvements.append(f"completion rate +{(v2.completion_rate - v1.completion_rate):.0%}")
    elif v2.completion_rate < v1.completion_rate - 0.1:
        regressions.append(f"completion rate {(v2.completion_rate - v1.completion_rate):.0%}")

    if v2.correction_rate < v1.correction_rate - 0.1:
        improvements.append(f"correction rate {(v2.correction_rate - v1.correction_rate):.0%}")
    elif v2.correction_rate > v1.correction_rate + 0.1:
        regressions.append(f"correction rate +{(v2.correction_rate - v1.correction_rate):.0%}")

    if v2.avg_tokens < v1.avg_tokens * 0.8:
        improvements.append(f"tokens -{(1 - v2.avg_tokens / v1.avg_tokens):.0%}")
    elif v2.avg_tokens > v1.avg_tokens * 1.2:
        regressions.append(f"tokens +{(v2.avg_tokens / v1.avg_tokens - 1):.0%}")

    if improvements and not regressions:
        return f"{v2.version} outperforms: {', '.join(improvements)}"
    elif regressions and not improvements:
        return f"{v2.version} regresses: {', '.join(regressions)}"
    elif improvements and regressions:
        return f"Mixed: improves {', '.join(improvements)}; regresses {', '.join(regressions)}"
    else:
        return "No significant difference"


def bucket_duration(seconds: float) -> str:
    """Bucket duration into privacy-safe ranges."""
    if seconds < 60:
        return "<1m"
    elif seconds < 300:
        return "1-5m"
    elif seconds < 900:
        return "5-15m"
    elif seconds < 1800:
        return "15-30m"
    else:
        return "30m+"


def bucket_tokens(tokens: int) -> str:
    """Bucket token count into privacy-safe ranges."""
    if tokens < 1000:
        return "<1k"
    elif tokens < 5000:
        return "1-5k"
    elif tokens < 20000:
        return "5-20k"
    elif tokens < 50000:
        return "20-50k"
    else:
        return "50k+"


def persist_outcome(
    outcome: SkillOutcome,
    db_path: str = None,
    experiment_variant_id: Optional[str] = None,
) -> None:
    """Persist a skill outcome to SQLite.

    Upserts based on (session_id, skill_name, start_time) to handle
    incremental updates as more information becomes available.

    Args:
        outcome: SkillOutcome to persist
        db_path: Path to database (defaults to standard location)
        experiment_variant_id: Optional variant ID if this outcome is part of an experiment
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)

    # Format start_time for SQLite
    start_time_str = outcome.start_time.isoformat() if outcome.start_time else None
    end_time_str = outcome.end_time.isoformat() if outcome.end_time else None

    conn.execute("""
        INSERT INTO skill_outcomes (
            skill_name, skill_version, session_id, project_encoded,
            start_time, end_time, duration_seconds, outcome,
            tokens_used, corrections, retries, experiment_variant_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, skill_name, start_time) DO UPDATE SET
            skill_version = excluded.skill_version,
            end_time = excluded.end_time,
            duration_seconds = excluded.duration_seconds,
            outcome = excluded.outcome,
            tokens_used = excluded.tokens_used,
            corrections = excluded.corrections,
            retries = excluded.retries,
            experiment_variant_id = excluded.experiment_variant_id
    """, (
        outcome.skill_name,
        outcome.skill_version,
        outcome.session_id,
        outcome.project_encoded,
        start_time_str,
        end_time_str,
        outcome.duration_seconds,
        outcome.outcome,
        outcome.tokens_used,
        outcome.corrections,
        outcome.retries,
        experiment_variant_id,
    ))
    conn.commit()


def finalize_session_outcomes(session_id: str, db_path: str = None) -> int:
    """Mark all open outcomes in a session as session_ended.

    Called when session file stops being modified (session ended).

    Args:
        session_id: Session identifier
        db_path: Path to database (defaults to standard location)

    Returns:
        Count of outcomes finalized
    """
    from spellbook_mcp.db import get_connection, get_db_path

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Update outcomes where outcome is empty (still open)
    cursor.execute("""
        UPDATE skill_outcomes
        SET outcome = ?
        WHERE session_id = ? AND outcome = ''
    """, (OUTCOME_SESSION_ENDED, session_id))

    count = cursor.rowcount
    conn.commit()
    return count


def get_analytics_summary(
    project_encoded: str = None,
    days: int = 30,
    skill: str = None,
    db_path: str = None,
) -> Dict[str, Any]:
    """Get skill analytics summary from persisted outcomes.

    Args:
        project_encoded: Filter to specific project (None for all)
        days: Time window in days (default 30)
        skill: Filter to specific skill (None for all)
        db_path: Path to database (defaults to standard location)

    Returns:
        {
            "total_outcomes": int,
            "by_skill": {skill_name: SkillMetrics dict},
            "weak_skills": [top 5 by failure_score],
            "version_comparisons": [...] if versions present
        }
    """
    from spellbook_mcp.db import get_connection, get_db_path
    from datetime import datetime, timedelta

    if db_path is None:
        db_path = str(get_db_path())

    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Build query with filters
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    params = [cutoff]
    where_clauses = ["created_at >= ?"]

    if project_encoded:
        where_clauses.append("project_encoded = ?")
        params.append(project_encoded)

    if skill:
        where_clauses.append("skill_name = ?")
        params.append(skill)

    where_sql = " AND ".join(where_clauses)

    cursor.execute(f"""
        SELECT skill_name, skill_version, outcome, tokens_used, corrections, retries
        FROM skill_outcomes
        WHERE {where_sql}
    """, params)

    rows = cursor.fetchall()

    # Aggregate metrics
    by_skill: Dict[str, Dict] = defaultdict(lambda: {
        "invocations": 0,
        "completions": 0,
        "abandonments": 0,
        "superseded": 0,
        "session_ended": 0,
        "corrections": 0,
        "retries": 0,
        "total_tokens": 0,
        "versions": set(),
    })

    for row in rows:
        skill_name, version, outcome, tokens, corrections, retries = row
        m = by_skill[skill_name]
        m["invocations"] += 1
        m["total_tokens"] += tokens or 0
        m["corrections"] += corrections or 0
        m["retries"] += retries or 0

        if version:
            m["versions"].add(version)

        if outcome == OUTCOME_COMPLETED:
            m["completions"] += 1
        elif outcome == OUTCOME_ABANDONED:
            m["abandonments"] += 1
        elif outcome == OUTCOME_SUPERSEDED:
            m["superseded"] += 1
        elif outcome == OUTCOME_SESSION_ENDED:
            m["session_ended"] += 1

    # Calculate rates and convert to serializable format
    result_by_skill = {}
    weak_skills = []

    for skill_name, m in by_skill.items():
        inv = m["invocations"]
        if inv == 0:
            continue

        completion_rate = m["completions"] / inv
        failure_score = (m["corrections"] + m["retries"] + inv - m["completions"]) / inv

        skill_result = {
            "skill": skill_name,
            "invocations": inv,
            "completions": m["completions"],
            "completion_rate": round(completion_rate, 2),
            "corrections": m["corrections"],
            "retries": m["retries"],
            "avg_tokens": round(m["total_tokens"] / inv),
            "failure_score": round(failure_score, 2),
            "versions": list(m["versions"]),
        }
        result_by_skill[skill_name] = skill_result

        if failure_score > 0.2:
            weak_skills.append(skill_result)

    # Sort weak skills by failure score
    weak_skills.sort(key=lambda x: x["failure_score"], reverse=True)

    return {
        "total_outcomes": len(rows),
        "by_skill": result_by_skill,
        "weak_skills": weak_skills[:5],
        "period_days": days,
    }


def anonymize_for_telemetry(
    outcomes: List[SkillOutcome],
    min_count: int = 5,
) -> List[TelemetryAggregate]:
    """Convert outcomes to anonymous aggregates for telemetry.

    Privacy guarantees:
    - No session_id, project_encoded, or exact timestamps
    - No corrections (require content inspection)
    - Duration bucketed: <1m, 1-5m, 5-15m, 15-30m, 30m+
    - Tokens bucketed: <1k, 1-5k, 5-20k, 20-50k, 50k+
    - Only aggregates with count >= min_count

    Args:
        outcomes: List of SkillOutcome records
        min_count: Minimum samples before aggregate is included (default 5)

    Returns:
        List of TelemetryAggregate, empty if insufficient data
    """
    # Group by (skill_name, skill_version, outcome, duration_bucket, token_bucket)
    groups: Dict[tuple, int] = defaultdict(int)

    for outcome in outcomes:
        if not outcome.outcome:
            continue  # Skip incomplete outcomes

        duration_bucket = bucket_duration(outcome.duration_seconds or 0)
        token_bucket = bucket_tokens(outcome.tokens_used)

        key = (
            outcome.skill_name,
            outcome.skill_version,
            outcome.outcome,
            duration_bucket,
            token_bucket,
        )
        groups[key] += 1

    # Filter by min_count and convert to TelemetryAggregate
    aggregates = []
    for key, count in groups.items():
        if count >= min_count:
            skill_name, skill_version, outcome, duration_bucket, token_bucket = key
            aggregates.append(TelemetryAggregate(
                skill_name=skill_name,
                skill_version=skill_version,
                outcome=outcome,
                duration_bucket=duration_bucket,
                token_bucket=token_bucket,
                count=count,
            ))

    return aggregates
