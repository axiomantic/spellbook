"""MCP tools for security operations.

Only one tool remains: a thin wrapper around the pattern-matching
gate used for Bash commands, spawn prompts, and workflow state
payloads. Everything else (event logging, canary tokens, trust
registry, crypto signing, dashboards, spotlighting, PromptSleuth,
security modes, accumulator) was removed in the nuclear security
cleanup.
"""

__all__ = [
    "security_check_tool_input",
]

from spellbook.mcp.server import mcp
from spellbook.sessions.injection import inject_recovery_context


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

    Used as an MCP fallback by compiled hooks when their embedded
    security patterns are stale (hash mismatch with rules.py).

    Args:
        tool_name: The name of the tool being invoked.
        tool_input: The input dict for the tool.

    Returns:
        {"safe": bool, "findings": [...], "tool_name": str}
    """
    from spellbook.gates.check import check_tool_input

    return check_tool_input(tool_name=tool_name, tool_input=tool_input)
