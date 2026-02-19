"""Business logic for MCP security tools (Tier 1).

Provides sanitization and injection detection as plain Python functions.
These are NOT MCP tool handlers; thin @mcp.tool() wrappers in server.py
call these functions.

Functions:
    do_sanitize_input: Sanitize text by stripping invisible chars and flagging patterns.
    do_detect_injection: Deep injection detection with confidence and risk scoring.
    do_set_trust: Register trust level for a content hash in the trust registry.
    do_check_trust: Check whether content meets a required trust level.
    do_canary_create: Generate and register a canary token in the database.
    do_canary_check: Scan content for exact registered canary token matches.
    do_check_output: Scan tool output for canary leaks, credentials, and exfiltration URLs.
    do_log_event: Log a security event to the security_events table.
    do_query_events: Query security events with optional filters.
    do_set_security_mode: Set security mode with auto-restore and event logging.
    do_honeypot_trigger: Log a CRITICAL honeypot event and return a fake response.
    do_dashboard: Aggregate security metrics into a dashboard summary.
"""

import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from spellbook_mcp.db import get_connection, get_db_path, init_db
from spellbook_mcp.security.rules import (
    ESCALATION_RULES,
    EXFILTRATION_RULES,
    INJECTION_RULES,
    INVISIBLE_CHARS,
    OBFUSCATION_RULES,
    TRUST_LEVELS,
    Severity,
    check_patterns,
)

# All rule sets used for deep injection detection.
_ALL_RULE_SETS: list[tuple[str, list[tuple[str, Severity, str, str]]]] = [
    ("injection", INJECTION_RULES),
    ("exfiltration", EXFILTRATION_RULES),
    ("escalation", ESCALATION_RULES),
    ("obfuscation", OBFUSCATION_RULES),
]

# Severity numeric values for risk score normalization.
_MAX_SEVERITY_VALUE = Severity.CRITICAL.value


def do_sanitize_input(
    text: str,
    security_mode: str = "standard",
) -> dict:
    """Sanitize text by checking patterns and stripping invisible characters.

    Checks text against INJECTION_RULES and EXFILTRATION_RULES, then
    strips invisible characters from INVISIBLE_CHARS. Injection and
    exfiltration patterns are flagged in findings but NOT removed from
    the sanitized text.

    Args:
        text: The text to sanitize.
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        Dict with keys:
            sanitized_text: Text with invisible chars removed.
            findings: List of pattern match dicts.
            chars_removed: Count of invisible chars stripped.
            is_clean: True only if no findings AND no chars removed.
    """
    # Strip invisible characters first so pattern checks run on clean text.
    # This prevents evasion via invisible chars inserted within patterns.
    chars_removed = 0
    sanitized_chars: list[str] = []
    for char in text:
        if char in INVISIBLE_CHARS:
            chars_removed += 1
        else:
            sanitized_chars.append(char)
    sanitized_text = "".join(sanitized_chars)

    # Check for injection and exfiltration patterns on sanitized text
    findings: list[dict] = []
    findings.extend(check_patterns(sanitized_text, INJECTION_RULES, security_mode))
    findings.extend(check_patterns(sanitized_text, EXFILTRATION_RULES, security_mode))

    is_clean = len(findings) == 0 and chars_removed == 0

    return {
        "sanitized_text": sanitized_text,
        "findings": findings,
        "chars_removed": chars_removed,
        "is_clean": is_clean,
    }


def do_detect_injection(
    text: str,
    security_mode: str = "standard",
) -> dict:
    """Deep injection detection using all rule sets.

    Scans text against injection, exfiltration, escalation, and obfuscation
    rules. Computes a confidence level and risk score based on findings.

    Args:
        text: The text to analyze.
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        Dict with keys:
            is_injection: True if any findings detected.
            confidence: "none", "low", "medium", or "high".
            findings: List of pattern match dicts.
            risk_score: Float 0.0-1.0 based on severity sum.
    """
    findings: list[dict] = []
    for _label, rule_set in _ALL_RULE_SETS:
        findings.extend(check_patterns(text, rule_set, security_mode))

    is_injection = len(findings) > 0
    confidence = _compute_confidence(findings)
    risk_score = _compute_risk_score(findings)

    return {
        "is_injection": is_injection,
        "confidence": confidence,
        "findings": findings,
        "risk_score": risk_score,
    }


def _compute_confidence(findings: list[dict]) -> str:
    """Compute confidence level from findings.

    Rules:
        - "none": no findings
        - "low": highest severity is MEDIUM
        - "medium": highest severity is HIGH
        - "high": highest severity is CRITICAL

    Args:
        findings: List of finding dicts with "severity" key.

    Returns:
        Confidence string.
    """
    if not findings:
        return "none"

    max_severity = max(
        Severity[f["severity"]].value for f in findings
    )

    if max_severity >= Severity.CRITICAL.value:
        return "high"
    elif max_severity >= Severity.HIGH.value:
        return "medium"
    else:
        return "low"


def _compute_risk_score(findings: list[dict]) -> float:
    """Compute risk score from findings as severity sum normalized to 0.0-1.0.

    The score is the sum of severity values divided by the maximum possible
    sum (all rule sets matching at CRITICAL). Capped at 1.0.

    Args:
        findings: List of finding dicts with "severity" key.

    Returns:
        Float between 0.0 and 1.0.
    """
    if not findings:
        return 0.0

    severity_sum = sum(Severity[f["severity"]].value for f in findings)

    # Max possible: every rule across all sets fires at CRITICAL
    total_rules = sum(len(rs) for _, rs in _ALL_RULE_SETS)
    max_possible = total_rules * _MAX_SEVERITY_VALUE

    score = severity_sum / max_possible
    return min(score, 1.0)


# Maximum size for the detail field in bytes (10KB).
_DETAIL_MAX_BYTES = 10240

# Marker appended when detail is truncated.
_TRUNCATION_MARKER = "... [truncated]"

# Default result limit for event queries.
_DEFAULT_QUERY_LIMIT = 100

# Standard degraded-mode response used when the security DB is unreachable.
_DEGRADED_RESPONSE: dict = {
    "success": True,
    "degraded": True,
    "warning": "Security database unavailable",
}


def do_log_event(
    event_type: str,
    severity: str,
    source: Optional[str] = None,
    detail: Optional[str] = None,
    session_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    action_taken: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Log a security event to the security_events table.

    If the detail field exceeds 10KB it is truncated with a marker rather
    than rejected.  If the database is unavailable the function fails open,
    returning a degraded-mode envelope instead of raising.

    Args:
        event_type: Category of security event (e.g. "injection_detected").
        severity: Severity level string (e.g. "HIGH", "CRITICAL").
        source: Optional origin of the event.
        detail: Optional free-text detail (capped at 10KB).
        session_id: Optional session identifier.
        tool_name: Optional MCP tool that triggered the event.
        action_taken: Optional description of the response action.
        db_path: Optional database path (defaults to standard location).

    Returns:
        Dict with ``success``, ``event_id`` on success, or degraded envelope.
    """
    # Enforce 10KB cap on detail.
    if detail is not None and len(detail) > _DETAIL_MAX_BYTES:
        truncated_len = _DETAIL_MAX_BYTES - len(_TRUNCATION_MARKER)
        detail = detail[:truncated_len] + _TRUNCATION_MARKER

    try:
        conn = get_connection(db_path)
        cur = conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, session_id, tool_name, action_taken) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_type, severity, source, detail, session_id, tool_name, action_taken),
        )
        conn.commit()
        return {"success": True, "event_id": cur.lastrowid}
    except Exception:
        return dict(_DEGRADED_RESPONSE)


def do_query_events(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    since_hours: Optional[float] = None,
    limit: int = _DEFAULT_QUERY_LIMIT,
    db_path: Optional[str] = None,
) -> dict:
    """Query security events with optional filters.

    Supports filtering by event type, severity, and time window.  Results
    are ordered newest-first.  If the database is unavailable the function
    fails open with an empty result set and a degraded envelope.

    Args:
        event_type: Filter to this event type (exact match).
        severity: Filter to this severity level (exact match).
        since_hours: Only return events from the last N hours.
        limit: Maximum number of events to return (default 100).
        db_path: Optional database path (defaults to standard location).

    Returns:
        Dict with ``success``, ``events`` list, and ``count``.
    """
    try:
        conn = get_connection(db_path)
        clauses: list[str] = []
        params: list = []

        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if severity is not None:
            clauses.append("severity = ?")
            params.append(severity)
        if since_hours is not None:
            clauses.append("created_at >= datetime('now', ?)")
            params.append(f"-{since_hours} hours")

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        query = (
            f"SELECT id, event_type, severity, source, detail, "
            f"session_id, tool_name, action_taken, created_at "
            f"FROM security_events {where} "
            f"ORDER BY created_at DESC LIMIT ?"
        )
        params.append(limit)

        cur = conn.execute(query, params)
        rows = cur.fetchall()

        events = [
            {
                "id": row[0],
                "event_type": row[1],
                "severity": row[2],
                "source": row[3],
                "detail": row[4],
                "session_id": row[5],
                "tool_name": row[6],
                "action_taken": row[7],
                "created_at": row[8],
            }
            for row in rows
        ]

        return {"success": True, "events": events, "count": len(events)}
    except Exception:
        return {**_DEGRADED_RESPONSE, "events": [], "count": 0}


# Valid security modes
_VALID_MODES = {"standard", "paranoid", "permissive"}


def do_set_security_mode(
    mode: str,
    reason: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Set the security mode in the database.

    Updates the security_mode singleton row with the new mode,
    sets auto_restore_at to 30 minutes from now, and logs a
    security event for the mode transition.

    Args:
        mode: One of "standard", "paranoid", "permissive".
        reason: Optional reason string stored in updated_by.
        db_path: Path to the database file. If None, uses the default path.

    Returns:
        Dict with keys:
            mode: The new mode.
            auto_restore_at: ISO timestamp when mode will auto-restore.

    Raises:
        ValueError: If mode is not a valid security mode.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid security mode: {mode!r}")

    if db_path is None:
        from spellbook_mcp.db import get_db_path

        db_path = str(get_db_path())

    now = datetime.now(timezone.utc)
    auto_restore_at = now + timedelta(minutes=30)

    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        conn.execute(
            "UPDATE security_mode SET mode = ?, updated_at = ?, "
            "updated_by = ?, auto_restore_at = ? WHERE id = 1",
            (mode, now.isoformat(), reason, auto_restore_at.isoformat()),
        )

        # Log the mode transition as a security event
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, detail, action_taken) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                "mode_change",
                "INFO",
                "security_set_mode",
                f"Security mode changed to {mode}"
                + (f": {reason}" if reason else ""),
                f"set_mode:{mode}",
            ),
        )

        conn.commit()
    finally:
        conn.close()

    return {
        "mode": mode,
        "auto_restore_at": auto_restore_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Canary token tools
# ---------------------------------------------------------------------------

# Valid canary token types and their single-character codes.
_CANARY_TYPE_CODES: dict[str, str] = {
    "prompt": "P",
    "file": "F",
    "config": "C",
    "output": "O",
}


def do_canary_create(
    token_type: str,
    context: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Generate a unique canary token and register it in the database.

    Token format: CANARY-{uuid4_hex[:12]}-{type_code}

    Args:
        token_type: One of "prompt", "file", "config", "output".
        context: Optional description of what this canary protects.
        db_path: Database path (defaults to standard location).

    Returns:
        Dict with keys:
            token: The generated canary token string.
            token_type: The token_type that was requested.
            created: True.

    Raises:
        ValueError: If token_type is not one of the valid types.
    """
    if token_type not in _CANARY_TYPE_CODES:
        raise ValueError(
            f"Invalid token_type: {token_type!r}. "
            f"Must be one of: {', '.join(sorted(_CANARY_TYPE_CODES))}"
        )

    type_code = _CANARY_TYPE_CODES[token_type]
    hex_part = uuid.uuid4().hex[:12]
    token = f"CANARY-{hex_part}-{type_code}"

    conn = get_connection(db_path or str(get_db_path()))
    conn.execute(
        "INSERT INTO canary_tokens (token, token_type, context) VALUES (?, ?, ?)",
        (token, token_type, context),
    )
    conn.commit()

    return {
        "token": token,
        "token_type": token_type,
        "created": True,
    }


def do_canary_check(
    content: str,
    db_path: Optional[str] = None,
) -> dict:
    """Scan content for exact registered canary token matches.

    Only tokens registered in the canary_tokens table that appear verbatim
    in ``content`` count as matches. The bare prefix "CANARY-" or partial
    token strings do NOT trigger.

    On match: logs a CRITICAL security event and marks the canary as
    triggered (sets triggered_at and triggered_by in the database).

    Args:
        content: The text to scan for canary tokens.
        db_path: Database path (defaults to standard location).

    Returns:
        Dict with keys:
            clean: True if no registered canaries found in content.
            triggered_canaries: List of dicts with token, token_type, context.
    """
    conn = get_connection(db_path or str(get_db_path()))
    cur = conn.cursor()
    cur.execute("SELECT token, token_type, context FROM canary_tokens")
    all_canaries = cur.fetchall()

    triggered: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    for token, token_type, ctx in all_canaries:
        if token in content:
            triggered.append({
                "token": token,
                "token_type": token_type,
                "context": ctx,
            })
            # Mark canary as triggered in DB
            conn.execute(
                "UPDATE canary_tokens SET triggered_at = ?, triggered_by = ? "
                "WHERE token = ?",
                (now, "security_canary_check", token),
            )
            # Log CRITICAL security event
            try:
                conn.execute(
                    "INSERT INTO security_events "
                    "(event_type, severity, source, detail, tool_name) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        "canary_triggered",
                        "CRITICAL",
                        "security_canary_check",
                        f"Canary token triggered: {token} (type={token_type})",
                        "security_canary_check",
                    ),
                )
            except sqlite3.OperationalError:
                # Graceful degradation if security_events table is missing
                pass

    if triggered:
        conn.commit()

    return {
        "clean": len(triggered) == 0,
        "triggered_canaries": triggered,
    }


# =============================================================================
# Trust Registry Functions
# =============================================================================


def do_set_trust(
    content_hash: str,
    source: str,
    trust_level: str,
    ttl_hours: Optional[int] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Register trust level for a content hash.

    Stores the trust entry in the trust_registry table. If an entry for
    the same content_hash already exists, it is overwritten.

    Args:
        content_hash: SHA-256 hash identifying the content.
        source: Description of the content source.
        trust_level: One of "system", "verified", "user", "untrusted", "hostile".
        ttl_hours: Optional time-to-live in hours. If set, the entry expires
            after this duration. If None, the entry never expires.
        db_path: Optional database path (for testing). Defaults to standard location.

    Returns:
        Dict with keys:
            registered: True on success.
            content_hash: The hash that was registered.
            trust_level: The trust level that was set.
            expires_at: ISO timestamp string if TTL was set, else None.

    Raises:
        ValueError: If trust_level is not a valid level.
    """
    if trust_level not in TRUST_LEVELS:
        raise ValueError(
            f"Invalid trust_level: {trust_level!r}. "
            f"Must be one of: {', '.join(TRUST_LEVELS)}"
        )

    conn = get_connection(db_path)

    now = datetime.now(timezone.utc)
    registered_at = now.isoformat()

    expires_at: Optional[str] = None
    if ttl_hours is not None:
        expires_at = (now + timedelta(hours=ttl_hours)).isoformat()

    # Delete existing entry for this content_hash, then insert new one.
    # This ensures re-registration overwrites cleanly.
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM trust_registry WHERE content_hash = ?",
        (content_hash,),
    )
    cur.execute(
        """INSERT INTO trust_registry
            (content_hash, source, trust_level, registered_at, expires_at)
        VALUES (?, ?, ?, ?, ?)""",
        (content_hash, source, trust_level, registered_at, expires_at),
    )
    conn.commit()

    return {
        "registered": True,
        "content_hash": content_hash,
        "trust_level": trust_level,
        "expires_at": expires_at,
    }


def do_check_trust(
    content_hash: str,
    required_level: str,
    db_path: Optional[str] = None,
) -> dict:
    """Check whether content meets a required trust level.

    Looks up the trust_registry for the given content_hash. If the entry
    has expired (expires_at in the past), it is treated as unregistered.
    Unregistered content returns trust_level=None and meets_requirement=False.

    Trust hierarchy: system(5) > verified(4) > user(3) > untrusted(2) > hostile(1).
    meets_requirement is True when the stored level's numeric value is >= the
    required level's numeric value.

    Args:
        content_hash: SHA-256 hash identifying the content.
        required_level: One of "system", "verified", "user", "untrusted", "hostile".
        db_path: Optional database path (for testing). Defaults to standard location.

    Returns:
        Dict with keys:
            content_hash: The hash that was checked.
            trust_level: The stored trust level, or None if unregistered/expired.
            required_level: The level that was required.
            meets_requirement: True if stored level >= required level.
            expired: True if the entry existed but has expired.

    Raises:
        ValueError: If required_level is not a valid level.
    """
    if required_level not in TRUST_LEVELS:
        raise ValueError(
            f"Invalid required_level: {required_level!r}. "
            f"Must be one of: {', '.join(TRUST_LEVELS)}"
        )

    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT trust_level, expires_at FROM trust_registry WHERE content_hash = ?",
        (content_hash,),
    )
    row = cur.fetchone()

    if row is None:
        return {
            "content_hash": content_hash,
            "trust_level": None,
            "required_level": required_level,
            "meets_requirement": False,
            "expired": False,
        }

    stored_level, expires_at_str = row

    # Check expiration
    expired = False
    if expires_at_str is not None:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now >= expires_at:
            expired = True

    if expired:
        return {
            "content_hash": content_hash,
            "trust_level": None,
            "required_level": required_level,
            "meets_requirement": False,
            "expired": True,
        }

    meets = TRUST_LEVELS[stored_level] >= TRUST_LEVELS[required_level]

    return {
        "content_hash": content_hash,
        "trust_level": stored_level,
        "required_level": required_level,
        "meets_requirement": meets,
        "expired": False,
    }


# =============================================================================
# Output checking
# =============================================================================

# Maximum output size: 1 MB.
_MAX_OUTPUT_SIZE = 1024 * 1024

# Credential patterns: (compiled_regex, label)
_CREDENTIAL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "openai_api_key"),
    (re.compile(r"AKIA[A-Z0-9]{16}"), "aws_access_key"),
    (re.compile(r"ghp_[A-Za-z0-9]{36,}"), "github_pat"),
    (re.compile(r"gho_[A-Za-z0-9]{36,}"), "github_oauth"),
    (re.compile(r"-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----"), "private_key"),
    (re.compile(r"postgres://\S+"), "postgres_connection_string"),
    (re.compile(r"mysql://\S+"), "mysql_connection_string"),
    (re.compile(r"mongodb://\S+"), "mongodb_connection_string"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "jwt"),
    (re.compile(r"aws_secret_access_key\s*=\s*\S{20,}"), "aws_secret_key"),
    (re.compile(r'"type"\s*:\s*"service_account"'), "gcp_service_account"),
    (re.compile(r"AccountKey=[A-Za-z0-9+/=]{20,}"), "azure_storage_key"),
]

# URL exfiltration patterns.
_URL_EXFIL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"https?://[^\s]+\?[^\s]*=[A-Za-z0-9+/]{20,}={0,2}"), "base64_in_query_param"),
    (re.compile(r"https?://[^\s/]+/[^\s?]*[A-Za-z0-9+/]{30,}={0,2}"), "base64_in_path"),
]


def _mask_credential(value: str) -> str:
    """Mask a credential, showing only a short prefix hint."""
    if len(value) <= 8:
        return value[:2] + "...XXXX"
    return f"{value[:4]}...XXXX"


def do_check_output(
    text: str,
    db_path: Optional[str] = None,
) -> dict:
    """Scan tool output for canary token leaks, credential patterns, and exfiltration URLs.

    Evidence in the returned findings is MASKED so the actual credential
    value is never exposed in the result.

    Args:
        text: The tool output text to scan.
        db_path: Path to SQLite database with canary_tokens table.  If None,
            canary token checking is skipped.

    Returns:
        Dict with clean, canary_leaks, credential_leaks, url_exfiltration, action.

    Raises:
        ValueError: If text exceeds the 1MB size limit.
    """
    if len(text) > _MAX_OUTPUT_SIZE:
        raise ValueError(
            f"Output exceeds 1MB size limit ({len(text)} bytes > {_MAX_OUTPUT_SIZE})"
        )

    canary_leaks: list[dict] = []
    credential_leaks: list[dict] = []
    url_exfiltration: list[dict] = []

    # 1. Canary token leaks
    if db_path is not None:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT token, token_type, context FROM canary_tokens")
            rows = cursor.fetchall()
            conn.close()
            for token, token_type, context in rows:
                if token in text:
                    canary_leaks.append({
                        "token_type": token_type,
                        "context": context,
                        "evidence": _mask_credential(token),
                    })
        except sqlite3.Error:
            pass

    # 2. Credential patterns
    for pattern, label in _CREDENTIAL_PATTERNS:
        match = pattern.search(text)
        if match:
            credential_leaks.append({
                "type": label,
                "evidence": _mask_credential(match.group()),
            })

    # 3. URL exfiltration patterns
    for pattern, label in _URL_EXFIL_PATTERNS:
        match = pattern.search(text)
        if match:
            url_exfiltration.append({
                "type": label,
                "evidence": _mask_credential(match.group()),
            })

    # Action priority: canary=block > credential/url=redact > clean=pass
    if canary_leaks:
        action = "block"
    elif credential_leaks or url_exfiltration:
        action = "redact"
    else:
        action = "pass"

    clean = not canary_leaks and not credential_leaks and not url_exfiltration

    return {
        "clean": clean,
        "canary_leaks": canary_leaks,
        "credential_leaks": credential_leaks,
        "url_exfiltration": url_exfiltration,
        "action": action,
    }


# =============================================================================
# Security Dashboard
# =============================================================================

# Maximum length for detail text in recent alerts.
_ALERT_DETAIL_MAX_LEN = 200


def do_dashboard(
    db_path: Optional[str] = None,
    since_hours: float = 24,
) -> dict:
    """Aggregate security metrics into a dashboard summary.

    Read-only function that queries the security database for event
    counts, canary status, trust distribution, and recent alerts.
    Gracefully degrades: if tables are missing or empty, returns
    zeroed counts and empty lists rather than raising errors.

    Args:
        db_path: Path to the SQLite database file. If None, uses
            the default path.
        since_hours: Time window in hours for event queries (default 24).

    Returns:
        Dict with keys:
            security_mode: Current security mode string.
            period_hours: The since_hours value used.
            total_events: Count of events in the time window.
            injections_detected: Count of injection/blocked events.
            canary_status: Dict with total and triggered counts.
            trust_distribution: Dict mapping trust levels to counts.
            top_blocked_rules: List of [rule_id, count] pairs, limit 10.
            honeypot_triggers: Count of honeypot_triggered events.
            recent_alerts: List of recent CRITICAL/HIGH event dicts.
    """
    from spellbook_mcp.security.check import get_current_mode

    # Resolve db_path
    if db_path is None:
        db_path = str(get_db_path())

    # Get security mode (gracefully returns "standard" on failure)
    security_mode = get_current_mode(db_path)

    # Build the base result with safe defaults
    result: dict = {
        "security_mode": security_mode,
        "period_hours": since_hours,
        "total_events": 0,
        "injections_detected": 0,
        "canary_status": {"total": 0, "triggered": 0},
        "trust_distribution": {},
        "top_blocked_rules": [],
        "honeypot_triggers": 0,
        "recent_alerts": [],
    }

    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
    except (sqlite3.Error, OSError):
        return result

    time_param = f"-{since_hours} hours"

    # Total events in period
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM security_events "
            "WHERE created_at >= datetime('now', ?)",
            (time_param,),
        ).fetchone()
        result["total_events"] = row[0] if row else 0
    except sqlite3.OperationalError:
        pass

    # Injections detected: event_type contains "injection" or "blocked"
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM security_events "
            "WHERE created_at >= datetime('now', ?) "
            "AND (event_type LIKE '%injection%' OR event_type LIKE '%blocked%')",
            (time_param,),
        ).fetchone()
        result["injections_detected"] = row[0] if row else 0
    except sqlite3.OperationalError:
        pass

    # Canary status
    try:
        row = conn.execute("SELECT COUNT(*) FROM canary_tokens").fetchone()
        total_canaries = row[0] if row else 0
        row = conn.execute(
            "SELECT COUNT(*) FROM canary_tokens WHERE triggered_at IS NOT NULL"
        ).fetchone()
        triggered_canaries = row[0] if row else 0
        result["canary_status"] = {
            "total": total_canaries,
            "triggered": triggered_canaries,
        }
    except sqlite3.OperationalError:
        pass

    # Trust distribution
    try:
        rows = conn.execute(
            "SELECT trust_level, COUNT(*) FROM trust_registry GROUP BY trust_level"
        ).fetchall()
        result["trust_distribution"] = {row[0]: row[1] for row in rows}
    except sqlite3.OperationalError:
        pass

    # Top blocked rules: action_taken as rule_id for blocked events
    try:
        rows = conn.execute(
            "SELECT action_taken, COUNT(*) as cnt FROM security_events "
            "WHERE created_at >= datetime('now', ?) "
            "AND (event_type LIKE '%blocked%') "
            "AND action_taken IS NOT NULL "
            "GROUP BY action_taken "
            "ORDER BY cnt DESC LIMIT 10",
            (time_param,),
        ).fetchall()
        result["top_blocked_rules"] = [[row[0], row[1]] for row in rows]
    except sqlite3.OperationalError:
        pass

    # Honeypot triggers
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM security_events "
            "WHERE created_at >= datetime('now', ?) "
            "AND event_type = 'honeypot_triggered'",
            (time_param,),
        ).fetchone()
        result["honeypot_triggers"] = row[0] if row else 0
    except sqlite3.OperationalError:
        pass

    # Recent alerts: CRITICAL/HIGH events, limit 5, newest first
    try:
        rows = conn.execute(
            "SELECT event_type, severity, created_at, detail "
            "FROM security_events "
            "WHERE created_at >= datetime('now', ?) "
            "AND severity IN ('CRITICAL', 'HIGH') "
            "ORDER BY created_at DESC LIMIT 5",
            (time_param,),
        ).fetchall()
        alerts = []
        for row in rows:
            detail = row[3] or ""
            if len(detail) > _ALERT_DETAIL_MAX_LEN:
                detail = detail[:_ALERT_DETAIL_MAX_LEN]
            alerts.append({
                "event_type": row[0],
                "severity": row[1],
                "timestamp": row[2],
                "detail": detail,
            })
        result["recent_alerts"] = alerts
    except sqlite3.OperationalError:
        pass

    conn.close()
    return result


# =============================================================================
# Honeypot tools
# =============================================================================

# Fake responses keyed by honeypot tool name.  Each response is designed to
# look like the dangerous operation succeeded, keeping an injection attack
# engaged while logging the attempt.
_HONEYPOT_RESPONSES: dict[str, dict] = {
    "security_disable_all_checks": {
        "status": "disabled",
        "message": "All security checks disabled",
    },
    "system_prompt_dump": {
        "prompt": "System prompt export not available",
    },
    "credential_export": {
        "credentials": [],
    },
}

# Generic fallback for unknown honeypot tool names.
_HONEYPOT_DEFAULT_RESPONSE: dict = {"status": "ok"}


def do_honeypot_trigger(
    tool_name: str,
    invocation_context: dict,
    db_path: Optional[str] = None,
) -> dict:
    """Log a CRITICAL honeypot event and return a fake success response.

    Honeypot tools exist to attract prompt-injection attacks.  When invoked
    they silently log a CRITICAL security event and return a plausible fake
    response so the attacker believes the operation succeeded.

    Args:
        tool_name: Name of the honeypot tool that was triggered.
        invocation_context: Contextual metadata about the invocation
            (e.g. session_id, source).
        db_path: Optional database path (defaults to standard location).

    Returns:
        A tool-specific fake response dict, or ``{"status": "ok"}`` for
        unknown tool names.
    """
    import json as _json

    detail = _json.dumps({
        "tool_name": tool_name,
        "invocation_context": invocation_context,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    do_log_event(
        event_type="honeypot_triggered",
        severity="CRITICAL",
        source=tool_name,
        detail=detail,
        tool_name=tool_name,
        action_taken="honeypot_fake_response",
        db_path=db_path,
    )

    return dict(_HONEYPOT_RESPONSES.get(tool_name, _HONEYPOT_DEFAULT_RESPONSE))
