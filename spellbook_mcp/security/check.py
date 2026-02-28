"""Security check module for Spellbook MCP.

Provides runtime security checks for tool inputs and outputs,
plus a CLI entry point for use as a Claude Code hook.

Functions:
    check_tool_input: Validates tool input against relevant pattern sets.
    check_tool_output: Scans tool output for sensitive data leaks.
    should_auto_elevate: Determine if security mode should be auto-elevated.
    get_current_mode: Read current security mode from DB with lazy restore.
    main: CLI entry point reading JSON from stdin.

Usage as CLI (Claude Code hook protocol):
    echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | python -m spellbook_mcp.security.check
    # Exit code 0 = safe, exit code 2 = blocked

Flags:
    --mode standard|paranoid|permissive|audit|canary   Security sensitivity level
    --check-output                                      Switch to output checking mode
    --get-mode                                          Print current security mode and exit
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Optional

from spellbook_mcp.security.rules import (
    DANGEROUS_BASH_PATTERNS,
    ESCALATION_RULES,
    EXFILTRATION_PATTERNS,
    EXFILTRATION_RULES,
    INJECTION_RULES,
    INJECTION_TRIGGERS,
    INVISIBLE_CHARS,
    check_patterns,
)


def check_tool_input(
    tool_name: str,
    tool_input: dict,
    security_mode: str = "standard",
) -> dict:
    """Check tool input against relevant security pattern sets.

    Routes checks based on tool name:
    - Bash: DANGEROUS_BASH_PATTERNS + EXFILTRATION_RULES
    - spawn_claude_session: INJECTION_RULES + ESCALATION_RULES
    - workflow_state_save: INJECTION_RULES (on all string values in state)
    - Other tools: INJECTION_RULES (on all string values)

    Args:
        tool_name: The name of the tool being invoked.
        tool_input: The input dict for the tool.
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        Dict with keys:
            safe: bool - True if no findings
            findings: list[dict] - matched patterns
            tool_name: str - the tool name checked
    """
    findings: list[dict] = []

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        findings.extend(
            check_patterns(command, DANGEROUS_BASH_PATTERNS, security_mode)
        )
        findings.extend(
            check_patterns(command, EXFILTRATION_RULES, security_mode)
        )
    elif tool_name == "spawn_claude_session":
        prompt = tool_input.get("prompt", "")
        findings.extend(
            check_patterns(prompt, INJECTION_RULES, security_mode)
        )
        findings.extend(
            check_patterns(prompt, ESCALATION_RULES, security_mode)
        )
    elif tool_name == "workflow_state_save":
        for text in _extract_strings(tool_input):
            findings.extend(
                check_patterns(text, INJECTION_RULES, security_mode)
            )
    else:
        for text in _extract_strings(tool_input):
            findings.extend(
                check_patterns(text, INJECTION_RULES, security_mode)
            )

    return {
        "safe": len(findings) == 0,
        "findings": findings,
        "tool_name": tool_name,
    }


def check_tool_output(
    tool_name: str,
    output_text: str,
    security_mode: str = "standard",
) -> dict:
    """Check tool output for sensitive data leaks and injection triggers.

    Scans output text for:
    - EXFILTRATION_PATTERNS (data leak indicators)
    - INJECTION_TRIGGERS (prompt injection in output)
    - INVISIBLE_CHARS (Unicode steganography)

    Args:
        tool_name: The name of the tool that produced the output.
        output_text: The raw output text to scan.
        security_mode: One of "standard", "paranoid", "permissive".

    Returns:
        Dict with keys:
            safe: bool - True if no findings
            findings: list[dict] - matched patterns and invisible char detections
            tool_name: str - the tool name checked
    """
    findings: list[dict] = []

    # Check for invisible characters
    for char in output_text:
        if char in INVISIBLE_CHARS:
            findings.append({
                "rule_id": "INVIS-001",
                "severity": "HIGH",
                "message": "Invisible character detected in output",
                "matched_text": repr(char),
            })
            break  # One finding per invisible char type is enough

    # Check for exfiltration patterns
    findings.extend(
        check_patterns(output_text, EXFILTRATION_PATTERNS, security_mode)
    )

    # Check for injection triggers
    findings.extend(
        check_patterns(output_text, INJECTION_TRIGGERS, security_mode)
    )

    return {
        "safe": len(findings) == 0,
        "findings": findings,
        "tool_name": tool_name,
    }


def should_auto_elevate(context: dict) -> Optional[str]:
    """Determine if security mode should be auto-elevated based on context.

    Checks for known high-risk contexts that warrant paranoid security mode:
    - External PR review (context has "pr_review": True)
    - Untrusted repository (context has "untrusted_repo": True)
    - Web content fetching (context has "tool_name": "WebFetch")
    - Third-party skill (context has "third_party_skill": True)

    Args:
        context: Dict describing the current operation context.

    Returns:
        "paranoid" if elevation is warranted, None otherwise.
    """
    if context.get("pr_review") is True:
        return "paranoid"
    if context.get("untrusted_repo") is True:
        return "paranoid"
    if context.get("tool_name") == "WebFetch":
        return "paranoid"
    if context.get("third_party_skill") is True:
        return "paranoid"
    return None


def get_current_mode(db_path: Optional[str] = None) -> str:
    """Read the current security mode from the database.

    Performs lazy restore: if the current mode is not "standard" and
    auto_restore_at has passed, resets to "standard" and updates the DB.

    Args:
        db_path: Path to the database file. If None, uses the default path.

    Returns:
        Current security mode string ("standard", "paranoid", or "permissive").
        Falls back to "standard" if the DB is unavailable.
    """
    if db_path is None:
        from spellbook_mcp.db import get_db_path

        db_path = str(get_db_path())

    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT mode, auto_restore_at FROM security_mode WHERE id = 1"
            ).fetchone()

            if row is None:
                return "standard"

            mode = row["mode"]
            auto_restore_at = row["auto_restore_at"]

            # Lazy restore: if mode != standard and auto_restore_at has expired
            if mode != "standard" and auto_restore_at is not None:
                try:
                    restore_time = datetime.fromisoformat(auto_restore_at)
                    # Ensure timezone-aware comparison
                    if restore_time.tzinfo is None:
                        restore_time = restore_time.replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    if now > restore_time:
                        conn.execute(
                            "UPDATE security_mode SET mode = 'standard', "
                            "updated_at = ?, auto_restore_at = NULL WHERE id = 1",
                            (now.isoformat(),),
                        )
                        conn.commit()
                        return "standard"
                except (ValueError, TypeError):
                    pass

            return mode
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return "standard"


_AUDIT_DETAIL_MAX_LEN = 500


def log_audit_event(
    tool_name: str,
    tool_input: dict,
    db_path: Optional[str] = None,
) -> None:
    """Log a tool call to the security_events table.

    Truncates tool_input detail to prevent DB bloat. Uses the
    SPELLBOOK_DB_PATH environment variable if db_path is not provided.

    Args:
        tool_name: Name of the tool that was called.
        tool_input: The input dict for the tool.
        db_path: Path to the database file. If None, uses env or default.
    """
    if db_path is None:
        db_path = os.environ.get("SPELLBOOK_DB_PATH")
    if db_path is None:
        from spellbook_mcp.db import get_db_path

        db_path = str(get_db_path())

    from spellbook_mcp.db import init_db

    init_db(db_path)

    detail = json.dumps(tool_input, default=str)
    if len(detail) > _AUDIT_DETAIL_MAX_LEN:
        detail = detail[:_AUDIT_DETAIL_MAX_LEN] + "..."

    conn = sqlite3.connect(db_path, timeout=5.0)
    try:
        conn.execute(
            "INSERT INTO security_events "
            "(event_type, severity, source, tool_name, detail) "
            "VALUES (?, ?, ?, ?, ?)",
            ("tool_call", "INFO", "audit-log.sh", tool_name, detail),
        )
        conn.commit()
    finally:
        conn.close()


def _extract_strings(obj: object) -> list[str]:
    """Recursively extract all string values from a nested dict/list structure.

    Args:
        obj: The object to extract strings from.

    Returns:
        List of string values found.
    """
    strings: list[str] = []
    if isinstance(obj, str):
        strings.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            strings.extend(_extract_strings(value))
    elif isinstance(obj, list):
        for item in obj:
            strings.extend(_extract_strings(item))
    return strings


def main() -> None:
    """CLI entry point for security checks.

    Reads JSON from stdin matching Claude Code hook protocol:
        {"tool_name": str, "tool_input": dict}

    Exits with code 0 if safe, code 2 if blocked.
    On block, prints JSON: {"error": "Security check failed: [reason]"}
    """
    parser = argparse.ArgumentParser(
        description="Spellbook security check CLI"
    )
    parser.add_argument(
        "--mode",
        choices=["standard", "paranoid", "permissive", "audit", "canary"],
        default="standard",
        help="Security sensitivity level (audit = log only, canary = scan output for canary tokens, both fail-open)",
    )
    parser.add_argument(
        "--check-output",
        action="store_true",
        help="Switch to output checking mode",
    )
    parser.add_argument(
        "--get-mode",
        action="store_true",
        help="Print current security mode and exit",
    )
    args = parser.parse_args()

    if args.get_mode:
        print(get_current_mode())
        sys.exit(0)

    # Audit mode: log tool call and exit 0 (fail-open, never block)
    if args.mode == "audit":
        try:
            raw = sys.stdin.read()
            data = json.loads(raw)
            tool_name = data.get("tool_name", "")
            tool_input = data.get("tool_input", {})
            log_audit_event(tool_name, tool_input)
        except Exception:
            # Fail-open: audit failures never block work
            pass
        sys.exit(0)

    # Canary mode: scan tool output for registered canary tokens (fail-open)
    if args.mode == "canary":
        try:
            raw = sys.stdin.read()
            data = json.loads(raw)
            output_content = data.get("tool_output", "")

            if output_content:
                from spellbook_mcp.security.tools import do_canary_check

                db_path = os.environ.get("SPELLBOOK_DB_PATH")
                result = do_canary_check(output_content, db_path=db_path)
                if not result.get("clean", True):
                    # Canary triggered: log warning to stderr (never block)
                    print(
                        "[canary-check] WARNING: canary token detected in tool output",
                        file=sys.stderr,
                    )
        except Exception:
            # Fail-open: canary check failures never block work
            print(
                "[canary-check] WARNING: canary check failed",
                file=sys.stderr,
            )
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print(
            json.dumps({"error": "Security check failed: invalid JSON input"}),
            flush=True,
        )
        sys.exit(1)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    if args.check_output:
        output_text = data.get("tool_output", "")
        result = check_tool_output(tool_name, output_text, security_mode=args.mode)
    else:
        result = check_tool_input(tool_name, tool_input, security_mode=args.mode)

    if not result["safe"]:
        reasons = "; ".join(f["message"] for f in result["findings"])
        print(
            json.dumps({"error": f"Security check failed: {reasons}"}),
            flush=True,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
