"""Security check module for Spellbook MCP.

Provides runtime security checks for tool inputs and outputs,
plus a CLI entry point for use as a Claude Code hook.

Functions:
    check_tool_input: Validates tool input against relevant pattern sets.
    check_tool_output: Scans tool output for sensitive data leaks.
    main: CLI entry point reading JSON from stdin.

Usage as CLI (Claude Code hook protocol):
    echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | python -m spellbook_mcp.security.check
    # Exit code 0 = safe, exit code 2 = blocked

Flags:
    --mode standard|paranoid|permissive   Security sensitivity level
    --check-output                        Switch to output checking mode
    --get-mode                            Print current security mode and exit
"""

import argparse
import json
import sys

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
        choices=["standard", "paranoid", "permissive"],
        default="standard",
        help="Security sensitivity level",
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
        print("standard")
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
