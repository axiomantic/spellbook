"""Session resume detection and boot prompt generation."""

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class ContinuationIntent(TypedDict):
    """Result of continuation intent detection.

    Attributes:
        intent: One of "continue", "fresh_start", or "neutral"
        confidence: One of "high", "medium", or "low"
        pattern: The regex pattern that matched, or None if no match
    """
    intent: str
    confidence: str
    pattern: Optional[str]


class ResumeFields(TypedDict, total=False):
    """Flattened resume fields for session_init response.

    All fields except resume_available are optional.
    """
    resume_available: bool
    resume_session_id: Optional[str]
    resume_age_hours: Optional[float]
    resume_bound_at: Optional[str]
    resume_active_skill: Optional[str]
    resume_skill_phase: Optional[str]
    resume_pending_todos: Optional[int]
    resume_todos_corrupted: Optional[bool]
    resume_workflow_pattern: Optional[str]
    resume_boot_prompt: Optional[str]


# Fresh start patterns (highest priority, override resume)
FRESH_START_PATTERNS = [
    r"^(start|begin)\s+(fresh|new|over)",
    r"^new\s+(session|task|project)",
    r"^forget\s+(previous|last|prior)",
    r"^clean\s+slate",
    r"^from\s+(scratch|beginning)",
]

# Explicit continue patterns (high confidence, match without recent session)
EXPLICIT_CONTINUE_PATTERNS = [
    r"^\s*continue\s*$",
    r"^\s*resume\s*$",
    r"^where\s+were\s+we",
    r"^pick\s+up\s+where",
    r"^let'?s\s+continue",
    r"^carry\s+on",
    r"^what\s+were\s+we\s+(doing|working)",
    r"^back\s+to\s+(it|work)",
]

# Implicit continue patterns (require recent session for medium confidence)
IMPLICIT_CONTINUE_PATTERNS = [
    r"^(ok|okay|alright|sure|ready|go)[\s,\.!]*$",
    r"^next\s*(step|task|item)?[\s,\.!]*$",
    r"^and\s+then",
    r"^also[,\s]",
]


def detect_continuation_intent(
    first_message: str,
    has_recent_session: bool
) -> ContinuationIntent:
    """Detect user's continuation intent from first message.

    Args:
        first_message: The user's first message in the session
        has_recent_session: Whether a recent (<24h) resumable session exists

    Returns:
        ContinuationIntent with intent, confidence, and matched pattern
    """
    msg = first_message.strip().lower()

    # Check fresh start patterns first (highest priority)
    for pattern in FRESH_START_PATTERNS:
        if re.match(pattern, msg, re.IGNORECASE):
            return ContinuationIntent(
                intent="fresh_start",
                confidence="high",
                pattern=pattern,
            )

    # Check explicit continue patterns (high confidence, no session required)
    for pattern in EXPLICIT_CONTINUE_PATTERNS:
        if re.match(pattern, msg, re.IGNORECASE):
            return ContinuationIntent(
                intent="continue",
                confidence="high",
                pattern=pattern,
            )

    # Check implicit patterns only if recent session exists
    if has_recent_session:
        for pattern in IMPLICIT_CONTINUE_PATTERNS:
            if re.match(pattern, msg, re.IGNORECASE):
                return ContinuationIntent(
                    intent="continue",
                    confidence="medium",
                    pattern=pattern,
                )

    return ContinuationIntent(
        intent="neutral",
        confidence="low",
        pattern=None,
    )


def count_pending_todos(todos_json: Optional[str]) -> tuple[int, bool]:
    """Count non-completed todos from JSON.

    Args:
        todos_json: JSON string of todos array, or None

    Returns:
        Tuple of (count, is_corrupted):
        - count: Number of pending todos (0 if corrupted or None)
        - is_corrupted: True if JSON was present but malformed
    """
    if todos_json is None:
        return (0, False)

    try:
        todos = json.loads(todos_json)
        if not isinstance(todos, list):
            return (0, True)  # Not an array
        pending = sum(
            1 for t in todos
            if isinstance(t, dict) and t.get("status") != "completed"
        )
        return (pending, False)
    except json.JSONDecodeError:
        return (0, True)


def _find_planning_docs(recent_files: list[str]) -> list[str]:
    """Extract planning documents from recent files.

    Looks for files matching patterns:
    - *-impl.md, *-design.md, *-plan.md
    - Files in plans/ directories

    Only includes files that still exist.

    Args:
        recent_files: List of recently accessed file paths

    Returns:
        List of existing planning doc paths (max 3)
    """
    plan_patterns = [
        r".*-impl\.md$",
        r".*-design\.md$",
        r".*-plan\.md$",
        r".*/plans/.*\.md$",
    ]

    docs = []
    missing = []

    for f in recent_files:
        for pattern in plan_patterns:
            if re.match(pattern, f):
                if os.path.exists(f):
                    docs.append(f)
                else:
                    missing.append(f)
                break

    if missing:
        logger.warning(f"Planning docs no longer exist: {missing}")

    return docs[:3]  # Limit to 3 docs


def generate_boot_prompt(soul: dict) -> str:
    """Generate Section 0 boot prompt from extracted soul.

    Args:
        soul: Dict with keys: todos, active_skill, skill_phase,
              recent_files, exact_position, workflow_pattern

    Returns:
        Markdown-formatted boot prompt for execution
    """
    sections = []

    # Header
    sections.append("## SECTION 0: MANDATORY FIRST ACTIONS\n")
    sections.append("**Execute IMMEDIATELY before reading any other content.**\n")

    # 0.1 Workflow Restoration
    sections.append("### 0.1 Workflow Restoration")
    if soul.get("active_skill"):
        skill_cmd = f'Skill("{soul["active_skill"]}"'
        if soul.get("skill_phase"):
            skill_cmd += f', "--resume {soul["skill_phase"]}"'
        skill_cmd += ")"
        sections.append(f"```\n{skill_cmd}\n```")
    else:
        sections.append("NO ACTIVE SKILL - proceed to 0.2")

    # 0.2 Document Reads
    sections.append("\n### 0.2 Required Document Reads")
    plan_docs = _find_planning_docs(soul.get("recent_files") or [])
    if plan_docs:
        read_cmds = [f'Read("{doc}")' for doc in plan_docs]
        sections.append("```\n" + "\n".join(read_cmds) + "\n```")
    else:
        sections.append("NO DOCUMENTS TO READ")

    # 0.3 Todo Restoration
    sections.append("\n### 0.3 Todo State Restoration")
    todos_json = soul.get("todos")
    if todos_json:
        try:
            todos = json.loads(todos_json)
            if isinstance(todos, list) and todos:
                # Limit to 10 items for boot prompt
                todo_items = [
                    {"content": t.get("content", ""), "status": t.get("status", "pending")}
                    for t in todos[:10]
                    if isinstance(t, dict)
                ]
                if todo_items:
                    sections.append("```\nTodoWrite(" + json.dumps(todo_items, indent=2) + ")\n```")
                else:
                    sections.append("NO TODOS TO RESTORE")
            else:
                sections.append("NO TODOS TO RESTORE")
        except json.JSONDecodeError:
            sections.append("NO TODOS TO RESTORE")
    else:
        sections.append("NO TODOS TO RESTORE")

    # 0.4 Checkpoint
    sections.append("\n### 0.4 Restoration Checkpoint")
    sections.append("Before proceeding: Skill invoked? Documents read? Todos restored?")

    # 0.5 Constraints
    sections.append("\n### 0.5 Behavioral Constraints")
    constraints = []
    if soul.get("workflow_pattern"):
        constraints.append(f"- Continue workflow pattern: {soul['workflow_pattern']}")
    constraints.append("- Honor decisions from prior session")
    constraints.append("- Run verification before marking tasks complete")
    sections.append("\n".join(constraints))

    return "\n".join(sections)


def _calculate_age_hours(bound_at: str) -> float:
    """Calculate hours since bound_at timestamp.

    Args:
        bound_at: ISO timestamp string

    Returns:
        Hours elapsed since bound_at
    """
    bound_dt = datetime.fromisoformat(bound_at.replace("Z", "+00:00"))
    # Handle timezone-naive datetime
    if bound_dt.tzinfo is None:
        now = datetime.now()
    else:
        from datetime import timezone
        now = datetime.now(timezone.utc)
    delta = now - bound_dt
    return delta.total_seconds() / 3600


def get_resume_fields(project_path: str, db_path: str) -> ResumeFields:
    """Query database for resumable session and build flattened fields.

    Args:
        project_path: Absolute path to project
        db_path: Path to SQLite database

    Returns:
        ResumeFields dict with resume_available and optional resume context
    """
    from spellbook_mcp.db import get_connection

    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        # Calculate threshold time (24 hours ago)
        from datetime import timedelta
        threshold = (datetime.now() - timedelta(hours=24)).isoformat()

        # Query for recent soul (within 24 hours)
        cursor.execute("""
            SELECT
                id,
                session_id,
                bound_at,
                persona,
                active_skill,
                skill_phase,
                todos,
                recent_files,
                exact_position,
                workflow_pattern
            FROM souls
            WHERE project_path = ?
              AND bound_at > ?
            ORDER BY bound_at DESC
            LIMIT 1
        """, (project_path, threshold))

        row = cursor.fetchone()

        if not row:
            return ResumeFields(resume_available=False)

        # Parse row
        soul_id = row[0]
        session_id = row[1]
        bound_at = row[2]
        persona = row[3]
        active_skill = row[4]
        skill_phase = row[5]
        todos_json = row[6]
        recent_files_json = row[7]
        exact_position = row[8]
        workflow_pattern = row[9]

        # Validate required fields
        if not soul_id or not bound_at:
            logger.error("Corrupted soul record: missing required fields")
            return ResumeFields(resume_available=False)

        # Parse recent_files
        recent_files = []
        if recent_files_json:
            try:
                recent_files = json.loads(recent_files_json)
            except json.JSONDecodeError:
                logger.warning("Could not parse recent_files JSON")

        # Count pending todos and check for corruption
        pending_count, todos_corrupted = count_pending_todos(todos_json)

        # Build soul dict for boot prompt generation
        soul = {
            "id": soul_id,
            "session_id": session_id,
            "project_path": project_path,
            "bound_at": bound_at,
            "persona": persona,
            "active_skill": active_skill,
            "skill_phase": skill_phase,
            "todos": todos_json,
            "recent_files": recent_files,
            "exact_position": exact_position,
            "workflow_pattern": workflow_pattern,
        }

        # Generate boot prompt
        boot_prompt = generate_boot_prompt(soul)

        return ResumeFields(
            resume_available=True,
            resume_session_id=soul_id,
            resume_age_hours=round(_calculate_age_hours(bound_at), 1),
            resume_bound_at=bound_at,
            resume_active_skill=active_skill,
            resume_skill_phase=skill_phase,
            resume_pending_todos=pending_count,
            resume_todos_corrupted=todos_corrupted if todos_corrupted else None,
            resume_workflow_pattern=workflow_pattern,
            resume_boot_prompt=boot_prompt,
        )

    except Exception as e:
        logger.error(f"Failed to get resume context: {e}")
        return ResumeFields(resume_available=False)
