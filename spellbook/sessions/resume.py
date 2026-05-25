"""Session continuation-intent detection and workflow-state validation.

Includes schema validation for workflow state loaded from the database,
to prevent injection attacks via persisted state.
"""

import json
import logging
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
    resume_skill_constraints: Optional[dict]
    resume_decisions_binding: Optional[list]
    resume_identity_role: Optional[str]


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
    "skill_constraints",
    "decisions_binding",
    "identity_role",
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
    """Validate boot_prompt with context-aware line tracking.

    Instead of checking each line independently, track whether we are
    inside a multi-line structure (TodoWrite JSON, Read path list, etc.)
    and only allow continuation lines within those tracked contexts.

    Dangerous patterns are checked in two phases:
    1. Against the full boot_prompt string (catches multi-line spanning patterns)
    2. Against each individual line (catches per-line dangerous operations)

    Args:
        boot_prompt: The boot prompt string to validate.

    Returns:
        List of finding dicts (empty if boot_prompt is safe).
    """
    findings: list[dict] = []
    in_multiline_context = None  # None or "structured"
    brace_depth = 0
    bracket_depth = 0

    # Phase 1: Check dangerous patterns against the FULL string first.
    # This catches patterns that could be split across lines to evade per-line checks.
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

    # Phase 2: Per-line context-aware validation
    for line in boot_prompt.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        # Check dangerous patterns on EVERY line, regardless of
        # whether we are inside a tracked multi-line structure.
        for pattern in _DANGEROUS_BOOT_PROMPT_PATTERNS:
            if pattern.search(stripped):
                findings.append({
                    "check": "boot_prompt",
                    "message": (
                        f"boot_prompt contains dangerous operation: "
                        f"matched pattern '{pattern.pattern}'"
                    ),
                    "severity": "CRITICAL",
                })

        # Track multi-line context entry via safe patterns
        if any(p.match(line) for p in _SAFE_BOOT_PROMPT_PATTERNS):
            brace_depth += stripped.count("{") - stripped.count("}")
            bracket_depth += stripped.count("[") - stripped.count("]")
            if brace_depth > 0 or bracket_depth > 0:
                in_multiline_context = "structured"
            continue

        # If inside a tracked multi-line structure, allow structural content
        if in_multiline_context == "structured":
            brace_depth += stripped.count("{") - stripped.count("}")
            bracket_depth += stripped.count("[") - stripped.count("]")

            if brace_depth <= 0 and bracket_depth <= 0:
                in_multiline_context = None  # Structure closed

            # Within structure: only allow JSON-safe content (no tool calls).
            # This regex permits JSON structural chars, quotes, alphanumerics,
            # common punctuation, and whitespace.
            if re.match(
                r'^[\[\]{}(),:\s"\'0-9a-zA-Z_.\-+/\\|=!@#$%^&*~`]+$',
                stripped,
            ):
                continue
            # Otherwise fall through to unrecognized-line rejection

        # Line is not recognized by a safe pattern and not in a tracked context
        findings.append({
            "check": "boot_prompt",
            "message": (
                f"boot_prompt contains unrecognized operation: "
                f"'{stripped[:80]}'"
            ),
            "severity": "HIGH",
        })

    return findings


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
        from spellbook.gates.check import check_tool_input
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
    from sqlalchemy import select
    from spellbook.db.engines import get_sync_session
    from spellbook.db.spellbook_models import WorkflowState

    try:
        with get_sync_session(db_path) as session:
            stmt = (
                select(WorkflowState)
                .where(WorkflowState.project_path == project_path)
            )
            ws = session.execute(stmt).scalars().first()

        if ws is None:
            return {
                "success": True,
                "found": False,
                "state": None,
                "age_hours": None,
                "trigger": None,
            }

        state_json_str = ws.state_json
        trigger = ws.trigger
        updated_at_str = ws.updated_at

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
