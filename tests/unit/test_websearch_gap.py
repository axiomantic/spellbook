"""Verify WebSearch is included in security_tools set."""
import ast
import re
from pathlib import Path

HOOK_FILE = Path(__file__).resolve().parent.parent.parent / "hooks" / "spellbook_hook.py"


def test_websearch_in_security_tools():
    """WebSearch must be in the security_tools set for PostToolUse scanning."""
    source = HOOK_FILE.read_text()
    # Find the security_tools assignment in _handle_post_tool_use
    match = re.search(r'security_tools\s*=\s*(\{[^}]+\})', source)
    assert match is not None, "Could not find security_tools set in hook file"
    set_literal = match.group(1)
    # Parse the set literal to get actual members
    node = ast.parse(set_literal, mode="eval")
    members = {elt.value for elt in node.body.elts if isinstance(elt, ast.Constant)}
    assert "WebSearch" in members, (
        f"WebSearch missing from security_tools. Found: {members}"
    )


def test_websearch_security_tools_complete():
    """All external content tools must be in security_tools."""
    source = HOOK_FILE.read_text()
    match = re.search(r'security_tools\s*=\s*(\{[^}]+\})', source)
    assert match is not None
    set_literal = match.group(1)
    node = ast.parse(set_literal, mode="eval")
    members = {elt.value for elt in node.body.elts if isinstance(elt, ast.Constant)}
    required = {"Bash", "Read", "WebFetch", "WebSearch", "Grep"}
    missing = required - members
    assert not missing, f"Missing from security_tools: {missing}"
