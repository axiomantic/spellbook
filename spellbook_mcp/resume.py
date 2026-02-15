"""Session resume detection and boot prompt generation.

Includes schema validation for workflow state loaded from the database,
to prevent injection attacks via persisted state.
"""

import hashlib
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


# =============================================================================
# Workflow State Schema Validation
# =============================================================================

# Expected keys in a workflow state dict. Any key not in this set is rejected.
_ALLOWED_STATE_KEYS = frozenset({
    "active_skill",
    "skill_phase",
    "todos",
    "recent_files",
    "workflow_pattern",
    "boot_prompt",
    "pending_todos",
})

# Maximum total state size when serialized to JSON (1 MB).
_MAX_STATE_TOTAL_BYTES = 1024 * 1024

# Maximum size for any single field value when serialized to JSON (100 KB).
_MAX_FIELD_BYTES = 100 * 1024

# Safe operations allowed in boot_prompt content.
# Each line in the boot_prompt must match one of these patterns,
# or be non-functional text (section headers, comments, blank lines).
_SAFE_BOOT_PROMPT_PATTERNS = [
    # Skill invocations: Skill("name") or Skill("name", "--resume PHASE")
    re.compile(r'^\s*Skill\('),
    # Read operations: Read("path")
    re.compile(r'^\s*Read\('),
    # TodoWrite operations: TodoWrite([...])
    re.compile(r'^\s*TodoWrite\('),
    # Markdown headers (used in boot prompt formatting)
    re.compile(r'^\s*#{1,6}\s'),
    # Bold text markers
    re.compile(r'^\s*\*\*'),
    # List items starting with dash
    re.compile(r'^\s*-\s'),
    # Code fence markers
    re.compile(r'^\s*```'),
    # Plain text labels (NO ACTIVE SKILL, NO DOCUMENTS, etc.)
    re.compile(r'^\s*NO\s+(ACTIVE|DOCUMENTS|TODOS)'),
    # Checkpoint questions
    re.compile(r'^\s*Before\s+proceeding'),
    # Empty or whitespace-only lines
    re.compile(r'^\s*$'),
]

# Dangerous operations that are never allowed in boot_prompt.
_DANGEROUS_BOOT_PROMPT_PATTERNS = [
    re.compile(r'Bash\s*\(', re.IGNORECASE),
    re.compile(r'(?<![A-Za-z])Write\s*\(', re.IGNORECASE),
    re.compile(r'(?<![A-Za-z])Edit\s*\(', re.IGNORECASE),
    re.compile(r'WebFetch\s*\(', re.IGNORECASE),
    re.compile(r'WebSearch\s*\(', re.IGNORECASE),
    re.compile(r'NotebookEdit\s*\(', re.IGNORECASE),
    re.compile(r'curl\s+', re.IGNORECASE),
    re.compile(r'wget\s+', re.IGNORECASE),
    re.compile(r'rm\s+-', re.IGNORECASE),
]


def validate_workflow_state(
    state: dict,
    db_path: Optional[str] = None,
) -> dict:
    """Validate a workflow state dict against the expected schema.

    Checks performed:
    1. No unexpected keys (only _ALLOWED_STATE_KEYS permitted)
    2. Total serialized size under 1MB
    3. Individual field serialized size under 100KB
    4. boot_prompt restricted to safe operations (Skill, Read, TodoWrite)
    5. All string fields checked for injection patterns via check_tool_input

    On validation failure:
    - If db_path is provided, marks the state as hostile in the trust registry
      and logs a security event.

    Args:
        state: The workflow state dict to validate.
        db_path: Optional path to the database for trust marking and event logging.

    Returns:
        Dict with keys:
            valid: True if the state passed all checks.
            state: The original state dict (only if valid is True).
            findings: List of finding dicts describing each issue.
    """
    findings: list[dict] = []

    # 1. Check for unexpected keys
    unexpected_keys = set(state.keys()) - _ALLOWED_STATE_KEYS
    if unexpected_keys:
        findings.append({
            "check": "schema",
            "message": f"Unexpected keys in workflow state: {sorted(unexpected_keys)}",
            "severity": "HIGH",
        })

    # 2. Check total serialized size
    try:
        state_json = json.dumps(state, default=str)
        total_size = len(state_json.encode("utf-8"))
        if total_size > _MAX_STATE_TOTAL_BYTES:
            findings.append({
                "check": "size",
                "message": (
                    f"Total size exceeds limit: {total_size} bytes "
                    f"> {_MAX_STATE_TOTAL_BYTES} bytes"
                ),
                "severity": "HIGH",
            })
    except (TypeError, ValueError) as e:
        findings.append({
            "check": "size",
            "message": f"Cannot serialize state to JSON: {e}",
            "severity": "HIGH",
        })
        state_json = ""

    # 3. Check individual field sizes
    for key, value in state.items():
        if key not in _ALLOWED_STATE_KEYS:
            continue  # Already flagged in step 1
        try:
            field_json = json.dumps(value, default=str)
            field_size = len(field_json.encode("utf-8"))
            if field_size > _MAX_FIELD_BYTES:
                findings.append({
                    "check": "field_size",
                    "message": (
                        f"Field '{key}' size exceeds limit: {field_size} bytes "
                        f"> {_MAX_FIELD_BYTES} bytes"
                    ),
                    "severity": "HIGH",
                })
        except (TypeError, ValueError):
            pass

    # 4. Check boot_prompt content restrictions
    boot_prompt = state.get("boot_prompt")
    if boot_prompt and isinstance(boot_prompt, str) and boot_prompt.strip():
        boot_findings = _validate_boot_prompt(boot_prompt)
        findings.extend(boot_findings)

    # 5. Check all string values for injection patterns
    injection_findings = _check_state_injection(state)
    findings.extend(injection_findings)

    is_valid = len(findings) == 0

    if not is_valid and db_path is not None:
        _mark_hostile_and_log(state, findings, db_path)

    if is_valid:
        return {
            "valid": True,
            "state": state,
            "findings": [],
        }
    else:
        return {
            "valid": False,
            "state": None,
            "findings": findings,
        }


def _validate_boot_prompt(boot_prompt: str) -> list[dict]:
    """Validate that a boot_prompt only contains safe operations.

    Safe operations are: Skill invocations, Read operations, TodoWrite calls,
    markdown formatting (headers, bold, lists, code fences), and plain text labels.

    Dangerous operations (Bash, Write, Edit, curl, etc.) are always rejected.

    Args:
        boot_prompt: The boot prompt string to validate.

    Returns:
        List of finding dicts (empty if boot_prompt is safe).
    """
    findings: list[dict] = []

    # Check for dangerous patterns first (these are always rejected)
    for pattern in _DANGEROUS_BOOT_PROMPT_PATTERNS:
        if pattern.search(boot_prompt):
            findings.append({
                "check": "boot_prompt",
                "message": (
                    f"boot_prompt contains dangerous operation: "
                    f"matched pattern '{pattern.pattern}'"
                ),
                "severity": "CRITICAL",
            })

    # Check each line for allowed patterns
    for line in boot_prompt.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            continue  # Empty lines are fine

        line_is_safe = any(
            p.match(line) for p in _SAFE_BOOT_PROMPT_PATTERNS
        )
        if not line_is_safe:
            # Check if it looks like a continuation of a multi-line structure
            # (e.g., JSON inside TodoWrite, or continuation of Read path)
            if _is_likely_continuation(line_stripped):
                continue

            findings.append({
                "check": "boot_prompt",
                "message": (
                    f"boot_prompt contains unrecognized operation on line: "
                    f"'{line_stripped[:80]}'"
                ),
                "severity": "HIGH",
            })

    return findings


def _is_likely_continuation(line: str) -> bool:
    """Check if a line is a likely continuation of a multi-line safe structure.

    Recognizes JSON fragments (inside TodoWrite calls), closing parens/brackets,
    and quoted strings that are part of function call arguments.

    Args:
        line: A stripped line of text.

    Returns:
        True if the line looks like a continuation of safe content.
    """
    continuation_patterns = [
        re.compile(r'^[\[\]{},\s]*$'),           # JSON structural chars
        re.compile(r'^\)$'),                       # Closing paren
        re.compile(r'^"[^"]*"\s*[:,\]})]?\s*$'),   # Quoted string in JSON
        re.compile(r'^\d+\s*[,\]}]?\s*$'),         # Number in JSON
        re.compile(r'^(true|false|null)\s*[,\]}]?\s*$'),  # JSON literals
        re.compile(r'^\s*"content"'),              # JSON key in todo
        re.compile(r'^\s*"status"'),               # JSON key in todo
    ]
    return any(p.match(line) for p in continuation_patterns)


def _check_state_injection(state: dict) -> list[dict]:
    """Check all string values in the state for injection patterns.

    Uses check_tool_input from security.check to detect prompt injection
    attempts in any field of the workflow state.

    Args:
        state: The workflow state dict.

    Returns:
        List of finding dicts for detected injection patterns.
    """
    findings: list[dict] = []

    try:
        from spellbook_mcp.security.check import check_tool_input
    except ImportError:
        logger.warning("Security check module not available, skipping injection check")
        return findings

    # Build a synthetic tool input from state string values for checking
    result = check_tool_input(
        tool_name="workflow_state_save",
        tool_input=state,
        security_mode="paranoid",  # Use paranoid mode for state validation
    )

    if not result["safe"]:
        for finding in result["findings"]:
            findings.append({
                "check": "injection",
                "message": finding.get("message", "Injection pattern detected in workflow state"),
                "severity": finding.get("severity", "HIGH"),
                "rule_id": finding.get("rule_id", "unknown"),
            })

    return findings


def _mark_hostile_and_log(
    state: dict,
    findings: list[dict],
    db_path: str,
) -> None:
    """Mark rejected state as hostile in trust registry and log security event.

    Args:
        state: The rejected workflow state dict.
        findings: List of finding dicts describing the issues.
        db_path: Path to the database.
    """
    try:
        from spellbook_mcp.security.tools import do_log_event, do_set_trust
    except ImportError:
        logger.warning("Security tools not available, skipping hostile marking")
        return

    # Compute a content hash for the state
    state_json = json.dumps(state, sort_keys=True, default=str)
    content_hash = hashlib.sha256(state_json.encode("utf-8")).hexdigest()

    # Mark as hostile in trust registry
    try:
        do_set_trust(
            content_hash=content_hash,
            source="workflow_state_validation",
            trust_level="hostile",
            db_path=db_path,
        )
    except Exception as e:
        logger.error(f"Failed to mark state as hostile: {e}")

    # Log security event
    max_severity = "HIGH"
    for f in findings:
        if f.get("severity") == "CRITICAL":
            max_severity = "CRITICAL"
            break

    findings_summary = "; ".join(
        f.get("message", "unknown issue")[:100] for f in findings[:5]
    )

    try:
        do_log_event(
            event_type="workflow_state_rejected",
            severity=max_severity,
            source="workflow_state_validation",
            detail=f"Workflow state rejected: {findings_summary}",
            tool_name="workflow_state_load",
            action_taken="state_rejected",
            db_path=db_path,
        )
    except Exception as e:
        logger.error(f"Failed to log security event: {e}")


def load_workflow_state(
    project_path: str,
    max_age_hours: float = 24.0,
    db_path: Optional[str] = None,
) -> dict:
    """Load and validate persisted workflow state for a project.

    Queries the workflow_state table for the given project, checks age,
    and validates the state schema before returning it.

    Args:
        project_path: Absolute path to the project directory.
        max_age_hours: Maximum age of state to consider valid (default 24h).
        db_path: Optional database path (defaults to standard location).

    Returns:
        Dict with keys:
            success: True if operation succeeded (no DB errors).
            found: True if a valid, fresh state was found.
            state: The validated state dict, or None.
            age_hours: Hours since state was last updated, or None.
            trigger: The trigger that saved the state, or None.
            rejected: True if state existed but failed validation.
    """
    from spellbook_mcp.db import get_connection

    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT state_json, trigger, updated_at
            FROM workflow_state
            WHERE project_path = ?
            """,
            (project_path,),
        )
        row = cursor.fetchone()

        if row is None:
            return {
                "success": True,
                "found": False,
                "state": None,
                "age_hours": None,
                "trigger": None,
            }

        state_json_str, trigger, updated_at_str = row

        # Parse updated_at timestamp
        from datetime import timezone
        if updated_at_str.endswith("Z"):
            updated_at_str = updated_at_str[:-1] + "+00:00"
        if "+" not in updated_at_str and updated_at_str.count(":") < 3:
            updated_at = datetime.fromisoformat(updated_at_str).replace(
                tzinfo=timezone.utc
            )
        else:
            updated_at = datetime.fromisoformat(updated_at_str)

        now = datetime.now(timezone.utc)
        age_hours = (now - updated_at).total_seconds() / 3600.0

        if age_hours > max_age_hours:
            return {
                "success": True,
                "found": False,
                "state": None,
                "age_hours": age_hours,
                "trigger": trigger,
            }

        state = json.loads(state_json_str)

        # Validate the loaded state
        validation = validate_workflow_state(state, db_path=db_path)

        if not validation["valid"]:
            logger.warning(
                f"Workflow state for {project_path} failed validation: "
                f"{[f['message'] for f in validation['findings']]}"
            )
            return {
                "success": True,
                "found": False,
                "state": None,
                "age_hours": age_hours,
                "trigger": trigger,
                "rejected": True,
            }

        return {
            "success": True,
            "found": True,
            "state": state,
            "age_hours": age_hours,
            "trigger": trigger,
        }
    except Exception as e:
        logger.error(f"Failed to load workflow state: {e}")
        return {
            "success": False,
            "found": False,
            "state": None,
            "age_hours": None,
            "trigger": None,
            "error": str(e),
        }
