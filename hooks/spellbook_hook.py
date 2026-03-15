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
import shlex
import subprocess
import sys
import tempfile
import threading
import time
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
            if isinstance(result, dict):
                if "structuredContent" in result and result["structuredContent"] is not None:
                    return result["structuredContent"]
                if "content" in result:
                    for item in result["content"]:
                        if item.get("type") == "text":
                            try:
                                return json.loads(item["text"])
                            except (json.JSONDecodeError, ValueError):
                                pass
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
# Shared helpers
# ---------------------------------------------------------------------------

def _http_post(url: str, payload: dict, timeout: float = 5) -> dict | None:
    """Direct HTTP POST (not JSON-RPC). Used by memory, TTS, capture."""
    headers = {"Content-Type": "application/json"}
    if TOKEN_FILE.exists():
        try:
            headers["Authorization"] = f"Bearer {TOKEN_FILE.read_text().strip()}"
        except OSError:
            pass
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _resolve_git_context(cwd: str) -> tuple[str, str]:
    """Resolve worktree root and current branch for a working directory."""
    resolved_cwd = cwd
    branch = ""
    if not cwd:
        return resolved_cwd, branch
    try:
        toplevel = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3,
        )
        if toplevel.returncode == 0 and toplevel.stdout.strip():
            resolved_cwd = toplevel.stdout.strip()
    except Exception:
        pass
    try:
        br = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        branch = br.stdout.strip() if br.returncode == 0 else ""
    except Exception:
        pass
    return resolved_cwd, branch


def _send_os_notification(title: str, body: str) -> None:
    """Send a platform-specific OS notification."""
    try:
        if sys.platform == "darwin":
            # Escape backslashes and double quotes to prevent AppleScript injection
            safe_body = body.replace("\\", "\\\\").replace('"', '\\"')
            safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{safe_body}" with title "{safe_title}"'],
                capture_output=True, timeout=5,
            )
        else:
            subprocess.run(
                ["notify-send", title, body],
                capture_output=True, timeout=5,
            )
    except Exception:
        pass


# Excluded tools for notifications, TTS, and memory capture
_EXCLUDED_TOOLS = frozenset({
    "AskUserQuestion", "TodoRead", "TodoWrite",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
})


def _validate_tool_use_id(tool_use_id: str) -> bool:
    """Validate tool_use_id against path traversal."""
    if not tool_use_id:
        return False
    if "/" in tool_use_id or ".." in tool_use_id:
        return False
    if any(c.isspace() for c in tool_use_id):
        return False
    return True


# ---------------------------------------------------------------------------
# Handlers: Security gates (FAIL-CLOSED)
# ---------------------------------------------------------------------------

def _gate_bash(data: dict) -> None:
    """Security: validate bash commands. FAIL-CLOSED.

    Calls check_tool_input from the security module. If the check finds
    dangerous patterns, exits with code 2 and a structured error on stdout.
    If the security module cannot be imported, blocks (fail-closed).
    Error messages never include blocked content (anti-reflection).
    """
    try:
        from spellbook_mcp.security.check import check_tool_input
    except ImportError:
        print(json.dumps({"error": "Security check failed: security module not available"}))
        sys.exit(2)

    tool_input = data.get("tool_input")
    if not tool_input:
        print(json.dumps({"error": "Security check failed: no tool input provided"}))
        sys.exit(2)

    result = check_tool_input("Bash", tool_input)
    if not result["safe"]:
        reasons = "; ".join(f["message"] for f in result["findings"])
        print(json.dumps({"error": f"Security check failed: {reasons}"}))
        sys.exit(2)


def _gate_spawn(data: dict) -> None:
    """Security: validate spawn prompts. FAIL-CLOSED.

    Normalizes tool_name from MCP prefix to bare name before checking.
    """
    try:
        from spellbook_mcp.security.check import check_tool_input
    except ImportError:
        print(json.dumps({"error": "Security check failed: security module not available"}))
        sys.exit(2)

    tool_input = data.get("tool_input")
    if not tool_input:
        print(json.dumps({"error": "Security check failed: no tool input provided"}))
        sys.exit(2)

    result = check_tool_input("spawn_claude_session", tool_input)
    if not result["safe"]:
        reasons = "; ".join(f["message"] for f in result["findings"])
        print(json.dumps({"error": f"Security check failed: {reasons}"}))
        sys.exit(2)


def _gate_state_sanitize(data: dict) -> None:
    """Security: validate workflow state. FAIL-CLOSED.

    Normalizes tool_name from MCP prefix to bare name before checking.
    """
    try:
        from spellbook_mcp.security.check import check_tool_input
    except ImportError:
        print(json.dumps({"error": "Security check failed: security module not available"}))
        sys.exit(2)

    tool_input = data.get("tool_input")
    if not tool_input:
        print(json.dumps({"error": "Security check failed: no tool input provided"}))
        sys.exit(2)

    result = check_tool_input("workflow_state_save", tool_input)
    if not result["safe"]:
        reasons = "; ".join(f["message"] for f in result["findings"])
        print(json.dumps({"error": f"Security check failed: {reasons}"}))
        sys.exit(2)


# ---------------------------------------------------------------------------
# Handlers: FAIL-OPEN (never block)
# ---------------------------------------------------------------------------

def _record_tool_start(tool_name: str, data: dict) -> None:
    """Record tool start time for TTS/notification thresholds.

    Writes current Unix timestamp to two files:
    - {tempdir}/claude-tool-start-{tool_use_id} (for TTS)
    - {tempdir}/claude-notify-start-{tool_use_id} (for OS notifications)
    """
    tool_use_id = data.get("tool_use_id", "")
    if not _validate_tool_use_id(tool_use_id):
        return
    now = str(int(time.time()))
    tmpdir = tempfile.gettempdir()
    for prefix in ("claude-tool-start-", "claude-notify-start-"):
        try:
            Path(os.path.join(tmpdir, f"{prefix}{tool_use_id}")).write_text(now)
        except OSError:
            pass


def _audit_log(tool_name: str, data: dict) -> None:
    """Security: audit logging. FAIL-OPEN.

    Logs tool call to security_events table via the security check module.
    """
    try:
        from spellbook_mcp.security.check import log_audit_event
        tool_input = data.get("tool_input", {})
        log_audit_event(tool_name, tool_input)
    except Exception:
        pass  # Fail-open: audit failures never block


def _canary_check(tool_name: str, data: dict) -> str | None:
    """Security: canary detection. FAIL-OPEN.

    Scans tool output for registered canary tokens. Returns warning
    string for context injection if found, None otherwise.
    """
    try:
        output_content = data.get("tool_output", "") or data.get("tool_result", "")
        if not output_content:
            return None

        from spellbook_mcp.security.tools import do_canary_check
        db_path = os.environ.get("SPELLBOOK_DB_PATH")
        result = do_canary_check(output_content, db_path=db_path)
        if not result.get("clean", True):
            return "[canary-check] WARNING: canary token detected in tool output"
    except Exception:
        pass
    return None


def _memory_inject(tool_name: str, data: dict) -> str | None:
    """Memory: inject file memories. FAIL-OPEN.

    For file-related tools (Read, Edit, Grep, Glob), extracts file_path
    from tool_input and recalls associated memories from the MCP server.
    Returns formatted XML or None.
    """
    tool_input = data.get("tool_input") or {}
    cwd = data.get("cwd", "")

    # Extract file path based on tool
    if tool_name in ("Read", "Edit"):
        file_path = tool_input.get("file_path", "")
    elif tool_name in ("Grep", "Glob"):
        file_path = tool_input.get("path", "")
    else:
        return None
    if not file_path:
        return None

    # Resolve worktree and branch (best-effort)
    resolved_cwd, branch = _resolve_git_context(cwd)
    namespace = resolved_cwd.replace("\\", "/").replace("/", "-").lstrip("-") if resolved_cwd else ""
    if not namespace:
        return None

    # Call recall API
    payload = {
        "file_path": file_path,
        "namespace": namespace,
        "branch": branch,
        "repo_path": resolved_cwd,
        "limit": 5,
    }
    response = _http_post(
        f"http://{MCP_HOST}:{MCP_PORT}/api/memory/recall",
        payload,
    )
    if not response:
        return None

    memories = response.get("memories", [])
    if not memories:
        return None

    # Format as XML
    lines = ["<spellbook-memory>"]
    for mem in memories[:5]:
        content = mem.get("content", "")
        mtype = mem.get("memory_type", "fact")
        importance = mem.get("importance", 1.0)
        status = mem.get("status", "active")
        confidence = "verified" if status == "active" else "unverified"
        lines.append(
            f'  <memory type="{mtype}" confidence="{confidence}" '
            f'importance="{importance:.1f}">'
        )
        lines.append(f"    {content}")
        lines.append("  </memory>")
    lines.append("</spellbook-memory>")
    return "\n".join(lines)


def _notify_on_complete(tool_name: str, data: dict) -> None:
    """OS notifications for long-running tools. FAIL-OPEN.

    Reads timer file created by _record_tool_start, checks elapsed time
    against threshold, and sends a platform-specific notification.
    """
    if os.environ.get("SPELLBOOK_NOTIFY_ENABLED", "true") != "true":
        return
    if tool_name in _EXCLUDED_TOOLS:
        return
    tool_use_id = data.get("tool_use_id", "")
    if not _validate_tool_use_id(tool_use_id):
        return
    start_file = Path(os.path.join(tempfile.gettempdir(), f"claude-notify-start-{tool_use_id}"))
    if not start_file.exists():
        return
    try:
        start_time = int(start_file.read_text().strip())
        start_file.unlink(missing_ok=True)
    except (ValueError, OSError):
        return
    elapsed = int(time.time()) - start_time
    threshold = int(os.environ.get("SPELLBOOK_NOTIFY_THRESHOLD", "30"))
    if elapsed < threshold:
        return
    title = os.environ.get("SPELLBOOK_NOTIFY_TITLE", "Spellbook")
    body = f"{tool_name} finished ({elapsed}s)"
    _send_os_notification(title, body)


def _tts_notify(tool_name: str, data: dict) -> None:
    """TTS announcement for long-running tools. FAIL-OPEN.

    Reads timer file created by _record_tool_start, checks elapsed time
    against threshold, and POSTs to MCP server /api/speak endpoint.
    """
    if tool_name in _EXCLUDED_TOOLS:
        return
    tool_use_id = data.get("tool_use_id", "")
    if not _validate_tool_use_id(tool_use_id):
        return
    start_file = Path(os.path.join(tempfile.gettempdir(), f"claude-tool-start-{tool_use_id}"))
    if not start_file.exists():
        return
    try:
        start_ts = int(start_file.read_text().strip())
        start_file.unlink(missing_ok=True)
    except (ValueError, OSError):
        return
    elapsed = int(time.time()) - start_ts
    threshold = int(os.environ.get("SPELLBOOK_TTS_THRESHOLD", "30"))
    if elapsed < threshold:
        return
    # Build message
    cwd = data.get("cwd", "")
    project = os.path.basename(cwd) if cwd else "unknown"
    inp = data.get("tool_input") or {}
    detail = ""
    if tool_name == "Bash":
        cmd = inp.get("command", "")
        if cmd:
            try:
                parts = shlex.split(cmd)
            except ValueError:
                parts = cmd.split()
            detail = parts[0].split("/")[-1] if parts else ""
    elif tool_name == "Task":
        detail = inp.get("description", "")[:40]
    msg_parts = [project, tool_name]
    if detail:
        msg_parts.append(detail)
    msg_parts.append("finished")
    message = " ".join(msg_parts)
    _http_post(
        f"http://{MCP_HOST}:{MCP_PORT}/api/speak",
        {"text": message},
        timeout=10,
    )


def _memory_capture(tool_name: str, data: dict) -> None:
    """Memory: capture tool use events. FAIL-OPEN.

    Builds a summary of the tool call and POSTs to /api/memory/event.
    """
    if tool_name in _EXCLUDED_TOOLS or not tool_name:
        return
    tool_input = data.get("tool_input") or {}
    cwd = data.get("cwd", "")
    session_id = data.get("session_id", "")

    # Extract subject
    if tool_name in ("Read", "Write", "Edit"):
        subject = tool_input.get("file_path", "")
    elif tool_name == "Bash":
        subject = (tool_input.get("command", "") or "")[:200]
    elif tool_name in ("Grep", "Glob"):
        subject = tool_input.get("pattern", "")
    elif tool_name == "WebFetch":
        subject = tool_input.get("url", "")
    else:
        subject = tool_name

    summary = tool_name
    if subject:
        summary += f": {subject[:100]}"
    desc = tool_input.get("description", "")
    if desc:
        summary += f" ({desc[:80]})"

    resolved_cwd, branch = _resolve_git_context(cwd)
    namespace = resolved_cwd.replace("\\", "/").replace("/", "-").lstrip("-") if resolved_cwd else "unknown"

    tags_list = [tool_name.lower()]
    if subject:
        normalized = subject.replace("\\", "/")
        parts = normalized.rsplit("/", 1)
        if len(parts) > 1:
            tags_list.append(parts[-1].lower())

    payload = {
        "session_id": session_id,
        "project": namespace,
        "tool_name": tool_name,
        "subject": subject,
        "summary": summary[:500],
        "tags": ",".join(tags_list),
        "event_type": "tool_use",
        "branch": branch,
    }
    _http_post(
        f"http://{MCP_HOST}:{MCP_PORT}/api/memory/event",
        payload,
        timeout=5,
    )


def _stint_auto_push(data: dict) -> None:
    """Auto-push a stint when a Skill tool is invoked.

    Fetches behavioral mode from the skill's SKILL.md <BEHAVIORAL_MODE>
    tag via skill_instructions_get. If the fetch fails, pushes with an
    empty behavioral_mode (fail-open).

    Best-effort (fail-open). If MCP is unreachable, silently skips.
    """
    tool_input = data.get("tool_input", {})
    skill_name = tool_input.get("skill", "")
    if not skill_name:
        return

    project_path = data.get("cwd", "")
    if not project_path:
        return

    # Fetch behavioral mode from SKILL.md (fail-open)
    behavioral_mode = ""
    skill_info = _mcp_call("skill_instructions_get", {
        "skill_name": skill_name,
        "sections": ["BEHAVIORAL_MODE"],
    })
    if skill_info and skill_info.get("success"):
        sections = skill_info.get("sections", {})
        behavioral_mode = (sections.get("BEHAVIORAL_MODE", "") or "").strip()
        # Fallback: if sections key missing (MCP serialization edge case),
        # try extracting from raw content via _mcp_call response
        if not behavioral_mode:
            content = skill_info.get("content") or ""
            if "<BEHAVIORAL_MODE>" in content and "</BEHAVIORAL_MODE>" in content:
                start = content.index("<BEHAVIORAL_MODE>") + len("<BEHAVIORAL_MODE>")
                end = content.index("</BEHAVIORAL_MODE>")
                behavioral_mode = content[start:end].strip()

    _mcp_call("stint_push", {
        "project_path": project_path,
        "name": skill_name,
        "type": "skill",
        "purpose": f"Skill invocation: {skill_name}",
        "behavioral_mode": behavioral_mode,
        "success_criteria": "Skill workflow complete",
    })


def _stint_depth_check(data: dict) -> str | None:
    """Check stint stack depth and emit behavioral mode + optional tree.

    Two independent outputs:
    1. Behavioral mode one-liner: ALWAYS returned if the top-of-stack
       stint has a non-empty behavioral_mode, regardless of depth.
    2. Full stack tree: only returned when depth >= threshold (default 5).

    FAIL-OPEN: returns None on any error.
    """
    tool_name = data.get("tool_name", "")
    if tool_name in _EXCLUDED_TOOLS:
        return None

    project_path = data.get("cwd", "")
    if not project_path:
        return None

    stack = _mcp_call("stint_check", {"project_path": project_path})
    if not stack or not stack.get("success"):
        return None

    entries = stack.get("stack", [])
    depth = len(entries)
    if depth == 0:
        return None

    parts = []

    # behavioral-mode appears BEFORE stint-check tree intentionally:
    # it's the higher-priority signal and must survive even when depth < threshold

    # Always show behavioral_mode for top-of-stack (not depth-gated)
    top = entries[-1]
    bm = top.get("behavioral_mode", "")
    if bm:
        parts.append(f"<behavioral-mode>{bm}</behavioral-mode>")

    # Full stack tree is depth-gated
    threshold = _get_config_value("stint_depth_threshold", default=5)
    if depth >= threshold:
        lines = [f'<stint-check depth="{depth}">']
        for i, entry in enumerate(entries):
            indent = "  " * (i + 1)
            marker = "        <-- you are here" if i == len(entries) - 1 else ""
            lines.append(f"  {i+1}. {indent}{entry['name']}{marker}")
            lines.append(f"     {indent}purpose: {entry.get('purpose', '') or 'unspecified'}")
        lines.append("")
        lines.append("  Verify this matches your current work.")
        lines.append("  Close completed stints with stint_pop.")
        lines.append("</stint-check>")
        parts.append("\n".join(lines))

    return "\n".join(parts) if parts else None


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
        else:
            parts.append(f"Resume with: `Skill(skill='{active_skill}')`")

        # Fetch skill constraints (FORBIDDEN/REQUIRED sections only -- NOT full SKILL.md)
        skill_info = _mcp_call("skill_instructions_get", {"skill_name": active_skill, "sections": ["FORBIDDEN", "REQUIRED"]})
        if skill_info and skill_info.get("success"):
            constraints = skill_info.get("content", "")
            if constraints:
                parts.append(f"\n### Skill Constraints\n{constraints}")

    # Binding decisions
    binding_decisions = state.get("binding_decisions", [])
    if binding_decisions:
        parts.append("\n### Binding Decisions")
        for decision in binding_decisions:
            parts.append(f"- {decision}")

    # Next action
    next_action = state.get("next_action", "")
    if next_action:
        parts.append(f"\n### Next Action\n{next_action}")

    # Workflow pattern
    workflow_pattern = state.get("workflow_pattern", "")
    if workflow_pattern:
        parts.append(f"\n### Workflow Pattern: {workflow_pattern}")

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
        try:
            _stint_auto_push(data)
        except Exception:
            pass  # fail-open: auto-push errors never block tool execution

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
    """Save workflow state and stint stack before compaction."""
    project_path = data.get("cwd", "")
    if not project_path:
        return

    # Load current stint stack
    stack = _mcp_call("stint_check", {"project_path": project_path})

    # Load existing workflow state and merge stint_stack into it
    ws = _mcp_call("workflow_state_load", {
        "project_path": project_path,
        "max_age_hours": 24,
    })
    existing_state = {}
    if ws and ws.get("found"):
        existing_state = ws.get("state", {})

    if stack and stack.get("success"):
        existing_state["stint_stack"] = stack.get("stack", [])

    existing_state["compaction_flag"] = True

    _mcp_call("workflow_state_save", {
        "project_path": project_path,
        "state": existing_state,
        "trigger": "auto",
    })


def _handle_session_start(data: dict) -> dict | None:
    """Post-compaction recovery including stint stack restoration."""
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

    # Restore stint stack if present
    saved_stack = state.get("stint_stack", [])
    if saved_stack:
        _mcp_call("stint_replace", {
            "project_path": project_path,
            "stack": saved_stack,
            "reason": "post-compaction restoration",
        })

    directive = _build_recovery_directive(state)

    # Append stint stack info to directive
    if saved_stack:
        directive += "\n\n### Focus Stack (restored)\n"
        for i, entry in enumerate(saved_stack):
            bm = entry.get('behavioral_mode', '')
            bm_suffix = f" [MODE: {bm[:80]}]" if bm else ""
            directive += f"  {i+1}. {entry['name']} - {entry.get('purpose', '')}{bm_suffix}\n"

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
