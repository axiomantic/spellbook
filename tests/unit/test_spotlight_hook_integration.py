"""Test spotlighting integration in PostToolUse hook."""
import re
from pathlib import Path

HOOK_FILE = Path(__file__).resolve().parent.parent.parent / "hooks" / "spellbook_hook.py"


def test_hook_has_spotlight_import_or_call():
    """Hook must reference spotlight wrapping logic."""
    source = HOOK_FILE.read_text()
    assert "spotlight" in source.lower(), (
        "Hook file does not reference spotlighting"
    )


def test_hook_external_tools_includes_websearch():
    """External tool set in hook must include WebSearch."""
    source = HOOK_FILE.read_text()
    # Look for the external_tools set definition
    assert re.search(r'["\']WebSearch["\']', source), (
        "WebSearch not found in hook external tools handling"
    )


def test_hook_handles_mcp_prefix_tools():
    """Hook must treat mcp__* tools as external."""
    source = HOOK_FILE.read_text()
    assert 'startswith("mcp__")' in source or "startswith('mcp__')" in source, (
        "Hook does not check for mcp__ prefix in external tool detection"
    )
