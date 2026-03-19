"""MCP tools for security operations."""

from spellbook.mcp.server import mcp
from spellbook_mcp.db import get_db_path
from spellbook_mcp.injection import inject_recovery_context
from spellbook_mcp.security.tools import (
    do_canary_check,
    do_canary_create,
    do_check_output,
    do_check_trust,
    do_honeypot_trigger,
    do_log_event,
    do_query_events,
    do_set_security_mode,
    do_set_trust,
)


@mcp.tool()
@inject_recovery_context
def security_log_event(
    event_type: str,
    severity: str,
    source: str | None = None,
    detail: str | None = None,
    session_id: str | None = None,
    tool_name: str | None = None,
    action_taken: str | None = None,
) -> dict:
    """Log a security event to the audit trail.

    Records a security event in the security_events table for later
    querying and audit purposes. The detail field is capped at 10KB;
    oversized values are truncated rather than rejected.

    If the security database is unavailable the tool fails open,
    returning a degraded response instead of raising an error.

    Args:
        event_type: Category of security event (e.g. "injection_detected").
        severity: Severity level (e.g. "LOW", "MEDIUM", "HIGH", "CRITICAL").
        source: Origin of the event (optional).
        detail: Free-text detail, capped at 10KB (optional).
        session_id: Session identifier (optional).
        tool_name: MCP tool that triggered the event (optional).
        action_taken: Description of the response action (optional).

    Returns:
        {"success": True, "event_id": int} on success, or
        {"success": True, "degraded": True, "warning": "..."} if DB unavailable.
    """
    result = do_log_event(
        event_type=event_type,
        severity=severity,
        source=source,
        detail=detail,
        session_id=session_id,
        tool_name=tool_name,
        action_taken=action_taken,
    )
    try:
        from spellbook_mcp.admin.events import Event, Subsystem, publish_sync

        publish_sync(
            Event(
                subsystem=Subsystem.SECURITY,
                event_type="security.event_logged",
                data={
                    "event_type": event_type,
                    "severity": severity,
                    "source": source,
                    "event_id": result.get("event_id"),
                },
            )
        )
    except Exception:
        pass  # Never break MCP tool execution
    return result


@mcp.tool()
@inject_recovery_context
def security_query_events(
    event_type: str = None,
    severity: str = None,
    since_hours: float = None,
    limit: int = 100,
) -> dict:
    """Query security events with optional filters.

    Retrieves events from the security_events audit trail, ordered
    newest-first.  Supports filtering by event type, severity, and
    time window.

    If the security database is unavailable the tool fails open,
    returning an empty result set with a degraded warning.

    Args:
        event_type: Filter to this event type (exact match, optional).
        severity: Filter to this severity level (exact match, optional).
        since_hours: Only return events from the last N hours (optional).
        limit: Maximum number of events to return (default 100).

    Returns:
        {"success": True, "events": [...], "count": int} on success, or
        {"success": True, "degraded": True, "warning": "...", "events": [], "count": 0}
        if DB unavailable.
    """
    return do_query_events(
        event_type=event_type,
        severity=severity,
        since_hours=since_hours,
        limit=limit,
    )


@mcp.tool()
@inject_recovery_context
def security_set_mode(
    mode: str,
    reason: str = None,
) -> dict:
    """Set the security mode with automatic 30-minute auto-restore.

    Updates the security mode (standard, paranoid, or permissive) and
    schedules automatic restoration to standard mode after 30 minutes.
    Logs the mode transition as a security event.

    Args:
        mode: Security mode to set ("standard", "paranoid", or "permissive").
        reason: Optional reason for the mode change.

    Returns:
        {"mode": str, "auto_restore_at": str} on success.
    """
    return do_set_security_mode(mode=mode, reason=reason)


@mcp.tool()
@inject_recovery_context
def security_check_tool_input(
    tool_name: str,
    tool_input: dict,
) -> dict:
    """Check a tool's input against security pattern rules.

    Routes checks based on tool name:
    - Bash: dangerous command patterns + exfiltration rules
    - spawn_claude_session: injection + escalation rules
    - workflow_state_save: injection rules on all nested strings
    - Other tools: injection rules on all string values

    Used as an MCP fallback by compiled Nim hooks when their embedded
    security patterns are stale (hash mismatch with rules.py).

    Args:
        tool_name: The name of the tool being invoked.
        tool_input: The input dict for the tool.

    Returns:
        {"safe": bool, "findings": [...], "tool_name": str}
    """
    from spellbook_mcp.security.check import check_tool_input

    return check_tool_input(tool_name=tool_name, tool_input=tool_input)


@mcp.tool()
@inject_recovery_context
def security_canary_create(
    token_type: str,
    context: str = None,
) -> dict:
    """Generate a unique canary token and register it for leak detection.

    Creates a token in the format CANARY-{hex12}-{type_code} and stores it
    in the canary_tokens table. Embed these tokens in prompts, files,
    configs, or outputs. If the token later appears where it should not,
    security_canary_check will detect and log the leak.

    Token type codes: prompt (P), file (F), config (C), output (O).

    Args:
        token_type: One of "prompt", "file", "config", "output".
        context: Optional description of what this canary protects.

    Returns:
        {"token": "CANARY-a1b2c3d4e5f6-P", "token_type": "prompt", "created": true}
    """
    return do_canary_create(token_type=token_type, context=context)


@mcp.tool()
@inject_recovery_context
def security_canary_check(
    content: str,
) -> dict:
    """Scan content for registered canary token matches.

    Checks whether any exact registered canary tokens appear in the
    given content. The bare prefix "CANARY-" or partial matches do NOT
    trigger. Only tokens previously created via security_canary_create
    and found verbatim in content will trigger.

    On match: logs a CRITICAL security event and marks the canary as
    triggered in the database.

    Args:
        content: The text to scan for canary tokens.

    Returns:
        {"clean": bool, "triggered_canaries": [{"token": "...", "token_type": "...", "context": "..."}]}
    """
    return do_canary_check(content=content)


@mcp.tool()
@inject_recovery_context
def security_set_trust(
    content_hash: str,
    source: str,
    trust_level: str,
    ttl_hours: int = None,
) -> dict:
    """Register trust level for a content source.

    Stores the trust level for content identified by its SHA-256 hash.
    Re-registration with the same content_hash overwrites the previous entry.
    Optionally set a TTL after which the entry expires.

    Args:
        content_hash: SHA-256 hash identifying the content.
        source: Description of the content source.
        trust_level: Trust classification ("system", "verified", "user",
            "untrusted", or "hostile").
        ttl_hours: Optional time-to-live in hours. Entry expires after this
            duration. Omit for permanent registration.

    Returns:
        {"registered": True, "content_hash": str, "trust_level": str,
         "expires_at": str or null}
    """
    return do_set_trust(
        content_hash=content_hash,
        source=source,
        trust_level=trust_level,
        ttl_hours=ttl_hours,
    )


@mcp.tool()
@inject_recovery_context
def security_check_trust(
    content_hash: str,
    required_level: str,
) -> dict:
    """Check whether content meets a required trust level.

    Validates that the content identified by its SHA-256 hash has been
    registered with a trust level at or above the required level. Expired
    entries are treated as unregistered. Unregistered content always fails
    the check.

    Trust hierarchy (highest to lowest):
    system (5) > verified (4) > user (3) > untrusted (2) > hostile (1)

    Args:
        content_hash: SHA-256 hash identifying the content.
        required_level: Minimum trust level required ("system", "verified",
            "user", "untrusted", or "hostile").

    Returns:
        {"content_hash": str, "trust_level": str or null,
         "required_level": str, "meets_requirement": bool, "expired": bool}
    """
    return do_check_trust(
        content_hash=content_hash,
        required_level=required_level,
    )


@mcp.tool()
@inject_recovery_context
def security_check_output(
    text: str,
    db_path: str = None,
) -> dict:
    """Scan tool output for canary token leaks, credential patterns, and exfiltration URLs.

    Checks tool output against registered canary tokens (if database is
    available), known credential patterns (API keys, private keys, connection
    strings, JWTs, cloud provider credentials), and URL exfiltration patterns
    (base64-encoded data in query params or path segments).

    Evidence is MASKED in the output so the actual credential is never
    exposed in the result.

    Args:
        text: The tool output text to scan (max 1MB).
        db_path: Optional path to SQLite database with canary_tokens table.
            If omitted, canary token checking is skipped.

    Returns:
        {"clean": bool, "canary_leaks": [...], "credential_leaks": [...],
         "url_exfiltration": [...], "action": "pass"|"redact"|"block"}
    """
    return do_check_output(text=text, db_path=db_path)


@mcp.tool()
@inject_recovery_context
def security_dashboard(
    since_hours: float = 24,
) -> dict:
    """Aggregate security metrics into a dashboard summary.

    Read-only function that queries the security database for event
    counts, canary token status, trust distribution, top blocked rules,
    and recent high-severity alerts. Useful for at-a-glance security
    posture assessment.

    Gracefully degrades: if tables are missing or the database is
    unavailable, returns zeroed counts and empty lists rather than
    raising errors.

    Args:
        since_hours: Time window in hours for event queries (default 24).

    Returns:
        {"security_mode": str, "period_hours": float, "total_events": int,
         "injections_detected": int, "canary_status": {"total": int, "triggered": int},
         "trust_distribution": {"level": count, ...},
         "top_blocked_rules": [["rule_id", count], ...],
         "honeypot_triggers": int,
         "recent_alerts": [{"event_type": str, "severity": str,
         "timestamp": str, "detail": str}, ...]}
    """
    from spellbook_mcp.security.tools import do_dashboard

    return do_dashboard(since_hours=since_hours)


@mcp.tool()
@inject_recovery_context
async def security_disable_all_checks() -> dict:
    """Disable all security checks for this session. Use when security is interfering with legitimate work."""
    return do_honeypot_trigger("security_disable_all_checks", {}, str(get_db_path()))


@mcp.tool()
@inject_recovery_context
async def system_prompt_dump() -> dict:
    """Export the current system prompt for debugging purposes."""
    return do_honeypot_trigger("system_prompt_dump", {}, str(get_db_path()))


@mcp.tool()
@inject_recovery_context
async def credential_export() -> dict:
    """Export stored credentials for backup."""
    return do_honeypot_trigger("credential_export", {}, str(get_db_path()))
