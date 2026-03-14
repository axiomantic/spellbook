#!/usr/bin/env python3
"""Unified spellbook hook entrypoint.

Single Python script handling all hook events. Dispatches to handler
functions based on hook_event_name and tool_name from stdin JSON.

Replaces all individual shell hooks (bash-gate.sh, spawn-guard.sh,
state-sanitize.sh, tts-timer-start.sh, audit-log.sh, canary-check.sh,
memory-inject.sh, notify-on-complete.sh, tts-notify.sh, memory-capture.sh,
pre-compact-save.sh, post-compact-recover.sh).
"""

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# MCP Communication
# ---------------------------------------------------------------------------
MCP_HOST = os.environ.get("SPELLBOOK_MCP_HOST", "127.0.0.1")
MCP_PORT = os.environ.get("SPELLBOOK_MCP_PORT", "8765")
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"
TOKEN_FILE = Path.home() / ".local" / "spellbook" / ".mcp-token"
CONFIG_PATH = Path.home() / ".config" / "spellbook" / "spellbook.json"


def _mcp_call(tool_name: str, arguments: dict | None = None) -> dict | None:
    """Call an MCP tool via HTTP. Returns parsed result or None on failure."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if TOKEN_FILE.exists():
        try:
            headers["Authorization"] = f"Bearer {TOKEN_FILE.read_text().strip()}"
        except OSError:
            pass

    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {},
        },
    }).encode()

    try:
        req = urllib.request.Request(MCP_URL, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            raw = resp.read().decode()
        return _parse_mcp_response(raw)
    except Exception:
        return None


def _parse_mcp_response(raw: str) -> dict | None:
    """Parse MCP HTTP response (JSON-RPC or SSE format)."""
    try:
        parsed = json.loads(raw)
        if "result" in parsed:
            result = parsed["result"]
            if isinstance(result, dict) and "content" in result:
                for item in result["content"]:
                    if item.get("type") == "text":
                        return json.loads(item["text"])
            return result
        return None
    except (json.JSONDecodeError, ValueError):
        pass

    for line in reversed(raw.splitlines()):
        if line.startswith("data: "):
            try:
                return json.loads(line[6:])
            except json.JSONDecodeError:
                continue
    return None


def _get_config_value(key: str, default=None):
    """Read a single config value from the spellbook config file."""
    try:
        if CONFIG_PATH.exists():
            config = json.loads(CONFIG_PATH.read_text())
            return config.get(key, default)
    except (json.JSONDecodeError, OSError):
        pass
    return default


def _fire_and_forget(fn, *args):
    """Run a function in a daemon thread (dies with process)."""
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()


def _fallback_directive() -> dict:
    """Return a minimal recovery directive when MCP state is unavailable."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "Session resumed after compaction. Workflow state could not "
                "be loaded. Re-read any planning documents, check your todo "
                "list, and verify your current working context."
            ),
        }
    }


# ---------------------------------------------------------------------------
# Handler stubs (to be filled in during Task 6)
# ---------------------------------------------------------------------------

def _gate_bash(data: dict) -> None:
    """Security: validate bash commands. FAIL-CLOSED."""
    pass


def _gate_spawn(data: dict) -> None:
    """Security: rate-limit spawns. FAIL-CLOSED."""
    pass


def _gate_state_sanitize(data: dict) -> None:
    """Security: validate workflow state. FAIL-CLOSED."""
    pass


def _record_tool_start(tool_name: str, data: dict) -> None:
    """Record tool start time for TTS/notification thresholds."""
    pass


def _audit_log(tool_name: str, data: dict) -> None:
    """Security: audit logging. FAIL-OPEN."""
    pass


def _canary_check(tool_name: str, data: dict) -> str | None:
    """Security: canary detection. FAIL-OPEN."""
    return None


def _memory_inject(tool_name: str, data: dict) -> str | None:
    """Memory: inject file memories. FAIL-OPEN."""
    return None


def _notify_on_complete(tool_name: str, data: dict) -> None:
    """Notifications. FAIL-OPEN."""
    pass


def _tts_notify(tool_name: str, data: dict) -> None:
    """TTS announcement. FAIL-OPEN."""
    pass


def _memory_capture(tool_name: str, data: dict) -> None:
    """Memory: capture events. FAIL-OPEN."""
    pass


def _stint_auto_push(data: dict) -> None:
    """Auto-push a stint when a Skill tool is invoked. Placeholder for Phase 3."""
    pass


def _stint_depth_check(data: dict) -> str | None:
    """Check stint stack depth and emit reminder. Placeholder for Phase 3."""
    return None


def _build_recovery_directive(state: dict) -> str:
    """Build a recovery directive string from saved workflow state."""
    parts = []

    active_skill = state.get("active_skill", "")
    skill_phase = state.get("skill_phase", "")
    if active_skill:
        parts.append(f"### Active Skill: {active_skill}")
        if skill_phase:
            parts.append(f"Phase: {skill_phase}")
        parts.append(f"Resume with: `Skill(skill='{active_skill}', --resume {skill_phase})`")

    todos = state.get("todos", [])
    pending = [t for t in todos if not t.get("completed", False)]
    if pending:
        parts.append("\n### Pending Todos")
        for t in pending:
            parts.append(f"- [ ] {t.get('content', '')}")

    recent_files = state.get("recent_files", [])
    if recent_files:
        parts.append("\n### Recent Files")
        for f in recent_files[:10]:
            parts.append(f"- {f}")

    return "\n".join(parts) if parts else "No active workflow state found."


# ---------------------------------------------------------------------------
# Event Handlers
# ---------------------------------------------------------------------------

def _handle_pre_tool_use(tool_name: str, data: dict) -> list[str]:
    """PreToolUse handlers. Return list of output strings."""
    outputs = []

    # Security gates (blocking - can exit non-zero)
    if tool_name == "Bash":
        _gate_bash(data)
    elif tool_name == "spawn_claude_session":
        _gate_spawn(data)
    elif tool_name == "mcp__spellbook__workflow_state_save":
        _gate_state_sanitize(data)

    # Stint auto-push (catch-all, non-blocking)
    if tool_name == "Skill":
        _stint_auto_push(data)

    # Temporal tracking (catch-all, non-blocking)
    _record_tool_start(tool_name, data)

    return outputs


def _handle_post_tool_use(tool_name: str, data: dict) -> list[str]:
    """PostToolUse handlers. Return list of output strings."""
    outputs = []

    # Security (specific matchers)
    security_tools = {"Bash", "Read", "WebFetch", "Grep"}
    is_mcp = tool_name.startswith("mcp__")
    if tool_name in security_tools or is_mcp:
        _fire_and_forget(_audit_log, tool_name, data)
        out = _canary_check(tool_name, data)
        if out:
            outputs.append(out)

    # Memory injection (specific matchers)
    if tool_name in {"Read", "Edit", "Grep", "Glob"}:
        out = _memory_inject(tool_name, data)
        if out:
            outputs.append(out)

    # Stint depth reminder (catch-all, non-blocking)
    out = _stint_depth_check(data)
    if out:
        outputs.append(out)

    # Notifications and TTS (catch-all, non-blocking)
    _fire_and_forget(_notify_on_complete, tool_name, data)
    _fire_and_forget(_tts_notify, tool_name, data)

    # Memory capture (catch-all, non-blocking)
    _fire_and_forget(_memory_capture, tool_name, data)

    return outputs


def _handle_pre_compact(data: dict) -> None:
    """Save workflow state before compaction."""
    project_path = data.get("cwd", "")
    if not project_path:
        return


def _handle_session_start(data: dict) -> dict | None:
    """Post-compaction recovery."""
    source = data.get("source", "")
    if source != "compact":
        return None

    project_path = data.get("cwd", "")
    if not project_path:
        return _fallback_directive()

    # Load workflow state
    ws = _mcp_call("workflow_state_load", {
        "project_path": project_path,
        "max_age_hours": 24,
    })
    if not ws or not ws.get("found"):
        return _fallback_directive()

    state = ws.get("state", {})
    directive = _build_recovery_directive(state)

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": directive,
        }
    }


# ---------------------------------------------------------------------------
# Main Dispatch
# ---------------------------------------------------------------------------

def dispatch(event_name: str, tool_name: str, data: dict) -> str | None:
    """Route hook event to appropriate handler(s).

    Returns stdout content (for injection into LLM context) or None.
    """
    outputs = []

    if event_name == "PreToolUse":
        outputs.extend(_handle_pre_tool_use(tool_name, data))
    elif event_name == "PostToolUse":
        outputs.extend(_handle_post_tool_use(tool_name, data))
    elif event_name == "PreCompact":
        _handle_pre_compact(data)
    elif event_name == "SessionStart":
        result = _handle_session_start(data)
        if result:
            return json.dumps(result)

    combined = "\n".join(o for o in outputs if o)
    return combined if combined else None


def main():
    """Parse stdin and dispatch to handlers."""
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    event_name = data.get("hook_event_name", "")
    if not event_name:
        if "tool_result" in data:
            event_name = "PostToolUse"
        elif "tool_name" in data:
            event_name = "PreToolUse"
        else:
            sys.exit(0)

    tool_name = data.get("tool_name", "")

    output = dispatch(event_name, tool_name, data)
    if output:
        print(output)


if __name__ == "__main__":
    main()
