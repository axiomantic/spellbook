"""Integration test: full PostToolUse pipeline with spotlight + accumulator."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


# Add hooks dir to path for import
HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


def _import_hook():
    """Import the hook module from hooks directory."""
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        import importlib
        if "spellbook_hook" in sys.modules:
            importlib.reload(sys.modules["spellbook_hook"])
            return sys.modules["spellbook_hook"]
        import spellbook_hook
        return spellbook_hook
    finally:
        if str(HOOKS_DIR) in sys.path:
            sys.path.remove(str(HOOKS_DIR))


def test_post_tool_use_webfetch_produces_spotlight_output():
    """WebFetch tool result should produce spotlight-wrapped output."""
    hook = _import_hook()

    data = {
        "tool_name": "WebFetch",
        "tool_result": "Hello from the internet",
        "session_id": "test-session",
        "cwd": "/tmp/test",
    }

    # Mock _mcp_call to avoid network calls, _fire_and_forget to avoid threads
    with patch.object(hook, "_mcp_call", return_value=None), \
         patch.object(hook, "_fire_and_forget"):
        outputs = hook._handle_post_tool_use("WebFetch", data)

    # Should have at least one output with spotlight delimiters
    spotlight_outputs = [o for o in outputs if "[EXTERNAL_DATA_BEGIN" in o]
    assert len(spotlight_outputs) >= 1, (
        f"Expected spotlight output for WebFetch, got: {outputs}"
    )
    assert "source=WebFetch" in spotlight_outputs[0]


def test_post_tool_use_websearch_produces_spotlight_output():
    """WebSearch tool result should produce spotlight-wrapped output."""
    hook = _import_hook()

    data = {
        "tool_name": "WebSearch",
        "tool_result": "Search result content",
        "session_id": "test-session",
        "cwd": "/tmp/test",
    }

    with patch.object(hook, "_mcp_call", return_value=None), \
         patch.object(hook, "_fire_and_forget"):
        outputs = hook._handle_post_tool_use("WebSearch", data)

    spotlight_outputs = [o for o in outputs if "[EXTERNAL_DATA_BEGIN" in o]
    assert len(spotlight_outputs) >= 1


def test_post_tool_use_mcp_tool_produces_spotlight_output():
    """mcp__* tool result should produce spotlight-wrapped output."""
    hook = _import_hook()

    data = {
        "tool_name": "mcp__external__fetch_data",
        "tool_result": "External MCP tool data",
        "session_id": "test-session",
        "cwd": "/tmp/test",
    }

    with patch.object(hook, "_mcp_call", return_value=None), \
         patch.object(hook, "_fire_and_forget"):
        outputs = hook._handle_post_tool_use("mcp__external__fetch_data", data)

    spotlight_outputs = [o for o in outputs if "[EXTERNAL_DATA_BEGIN" in o]
    assert len(spotlight_outputs) >= 1


def test_post_tool_use_read_tool_no_spotlight():
    """Non-external tools like Read should not get spotlight wrapping."""
    hook = _import_hook()

    data = {
        "tool_name": "Read",
        "tool_result": "file content",
        "session_id": "test-session",
        "cwd": "/tmp/test",
    }

    with patch.object(hook, "_mcp_call", return_value=None), \
         patch.object(hook, "_fire_and_forget"):
        outputs = hook._handle_post_tool_use("Read", data)

    spotlight_outputs = [o for o in outputs if "EXTERNAL_DATA_BEGIN" in o]
    assert len(spotlight_outputs) == 0, (
        "Read tool should not produce spotlight output"
    )


def test_post_tool_use_fires_accumulator_for_external():
    """External tool should fire accumulator write."""
    hook = _import_hook()

    data = {
        "tool_name": "WebFetch",
        "tool_result": "content",
        "session_id": "test-session",
        "cwd": "/tmp/test",
    }

    fire_calls = []
    original_fire = hook._fire_and_forget

    def capture_fire(fn, *args):
        fire_calls.append((fn.__name__, args))

    with patch.object(hook, "_mcp_call", return_value=None), \
         patch.object(hook, "_fire_and_forget", side_effect=capture_fire):
        hook._handle_post_tool_use("WebFetch", data)

    accumulator_calls = [c for c in fire_calls if c[0] == "_accumulator_write"]
    assert len(accumulator_calls) >= 1, (
        f"Expected _accumulator_write fire-and-forget call, got: {[c[0] for c in fire_calls]}"
    )


def test_spotlight_disabled_via_config():
    """When spotlighting is disabled, no spotlight output should appear."""
    hook = _import_hook()

    data = {
        "tool_name": "WebFetch",
        "tool_result": "content",
        "session_id": "test-session",
        "cwd": "/tmp/test",
    }

    def config_with_disabled(key, default=None):
        if key == "security.spotlighting.enabled":
            return False
        return default

    with patch.object(hook, "_mcp_call", return_value=None), \
         patch.object(hook, "_fire_and_forget"), \
         patch.object(hook, "_get_config_value", side_effect=config_with_disabled):
        outputs = hook._handle_post_tool_use("WebFetch", data)

    spotlight_outputs = [o for o in outputs if "EXTERNAL_DATA_BEGIN" in o]
    assert len(spotlight_outputs) == 0, (
        "Spotlight should not produce output when disabled"
    )
