"""Security check module for the surviving bash/spawn/state gates.

Provides a single runtime gate function used by:

- ``hooks/spellbook_hook.py`` (PreToolUse gates for Bash and
  ``spawn_claude_session``)
- ``spellbook/sessions/resume.py`` (workflow state validation)
- ``spellbook/mcp/tools/security.py`` (MCP fallback when hooks
  cannot reach the embedded patterns)

Everything else that used to live here (audit logging, security
modes, canary output scanning) was removed in the nuclear
security cleanup.
"""

import json
import sys

from spellbook.gates.rules import (
    DANGEROUS_BASH_PATTERNS,
    ESCALATION_RULES,
    EXFILTRATION_RULES,
    INJECTION_RULES,
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
        security_mode: One of "standard" or "paranoid".

    Returns:
        Dict with keys:
            safe: bool - True if no findings above LOW severity
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
        "safe": all(f.get("severity") == "LOW" for f in findings),
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
    """CLI entry point for security gate checks.

    Reads JSON from stdin in the Claude Code hook protocol format:
        {"tool_name": str, "tool_input": dict}

    Exits 0 if safe, 2 if blocked. On block, prints a JSON error
    object to stdout:
        {"error": "Security check failed: <reason>"}

    This keeps the opencode plugin and gemini policy toml entry
    points working without pulling in the larger CLI surface that
    used to live in ``spellbook.security.check``.
    """
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        print(
            json.dumps({"error": "Security check failed: invalid JSON input"}),
            flush=True,
        )
        sys.exit(1)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    result = check_tool_input(tool_name, tool_input)
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
