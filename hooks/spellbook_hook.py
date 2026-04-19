#!/usr/bin/env python3
"""Unified spellbook hook entrypoint.

Single Python script handling all hook events. Dispatches to handler
functions based on hook_event_name and tool_name from stdin JSON.

Replaces all individual shell hooks (bash-gate.sh, spawn-guard.sh,
state-sanitize.sh, tts-timer-start.sh, audit-log.sh, canary-check.sh,
memory-inject.sh, notify-on-complete.sh, tts-notify.sh, memory-capture.sh,
pre-compact-save.sh, post-compact-recover.sh).
"""

import hashlib
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# MCP Communication
# ---------------------------------------------------------------------------
MCP_HOST = os.environ.get("SPELLBOOK_MCP_HOST", "127.0.0.1")
MCP_PORT = os.environ.get("SPELLBOOK_MCP_PORT", "8765")
_host_part = f"[{MCP_HOST}]" if ":" in MCP_HOST else MCP_HOST  # IPv6 bracket
MCP_URL = f"http://{_host_part}:{MCP_PORT}/mcp"
TOKEN_FILE = Path.home() / ".local" / "spellbook" / ".mcp-token"
CONFIG_PATH = Path(os.environ.get(
    "SPELLBOOK_CONFIG_PATH",
    str(Path.home() / ".config" / "spellbook" / "spellbook.json"),
))

# ---------------------------------------------------------------------------
# Auto memory recall: budget, dedup, keyword extraction
# ---------------------------------------------------------------------------
DEDUP_LOG_PATH = Path.home() / ".local" / "spellbook" / "cache" / "recent-memory-injections.json"
DEDUP_TTL = timedelta(minutes=15)
MEMORY_BUDGET_MAX_COUNT = 5
MEMORY_BUDGET_MAX_TOKENS = 500
MEMORY_PROMPT_MIN_LENGTH = 10

_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "for", "with",
    "this", "that", "these", "those", "is", "was", "are",
    "were", "to", "of", "in", "on", "at",
})

# Identifiers: CamelCase, camelCase, snake_case (require an internal boundary).
_IDENT_RE = re.compile(r"\b(?:[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*|[a-z]+[A-Z][A-Za-z0-9]*|[A-Za-z]+_[A-Za-z0-9_]+)\b")
# File paths: contain a '/' and non-space characters (allow extensions).
_PATH_RE = re.compile(r"\b[\w.\-/]*/[\w.\-/]+")


def _utcnow() -> datetime:
    """Return current UTC time. Indirection lets tests freeze time."""
    return datetime.now(timezone.utc)


def _detect_platform() -> str:
    """Detect which AI coding assistant platform is running."""
    if os.environ.get("OPENCODE") == "1":
        return "opencode"
    if os.environ.get("CODEX_SANDBOX") or os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED"):
        return "codex"
    if os.environ.get("GEMINI_CLI") == "1":
        return "gemini-cli"
    if os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("CLAUDE_ENV_FILE"):
        return "claude-code"
    return "unknown"


def _mcp_call(tool_name: str, arguments: dict | None = None) -> dict | None:
    """Call an MCP tool via HTTP. Returns parsed result or None on failure."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    headers["X-Spellbook-Client"] = _detect_platform()
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


def _log_hook_error(event: str, tool: str, exc: BaseException) -> None:
    """Log hook error to daemon. Falls back to stderr if daemon unreachable."""
    import traceback as _tb

    tb = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": f"{event}:{tool}",
        "traceback": tb,
    }
    result = _http_post("/api/hook-log", payload)
    if result is None:
        # Daemon unreachable -- write to stderr so it shows in Claude Code output
        print(f"[spellbook-hook] Error in {event}:{tool}:\n{tb}", file=sys.stderr)


def _fire_and_forget(fn, *args):
    """Run a function in a daemon thread (dies with process)."""

    def _wrapper():
        try:
            fn(*args)
        except Exception as e:
            _log_hook_error("fire_and_forget", fn.__name__, e)

    t = threading.Thread(target=_wrapper, daemon=True)
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

def _http_post(path: str, payload: dict, timeout: float = 5) -> dict | None:
    """Direct HTTP POST (not JSON-RPC). Used by memory, TTS, capture.

    ``path`` is an absolute URL path (e.g. ``/api/hook-log``).  The daemon
    base URL is derived from MCP_HOST and MCP_PORT.
    """
    url = f"http://{_host_part}:{MCP_PORT}{path}"
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
            # Pass title and body as arguments to prevent AppleScript injection
            script = 'on run {title, body}\n  display notification body with title title\nend run'
            subprocess.run(
                ["osascript", "-e", script, title, body],
                capture_output=True, timeout=5,
            )
        else:
            subprocess.run(
                ["notify-send", title, body],
                capture_output=True, timeout=5,
            )
    except Exception:
        pass


# Excluded tools for notifications and TTS (high-frequency, fast tools)
_EXCLUDED_TOOLS = frozenset({
    "AskUserQuestion", "TodoRead", "TodoWrite",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
    "Read", "Grep", "Glob", "list_directory", "ls", "cat",
    "file_history_snapshot", "get_file_contents",
})

# Interactive/UI tools excluded from stint depth checks, memory capture,
# and other handlers where we still want file-related tools to fire
_INTERACTIVE_EXCLUDED_TOOLS = frozenset({
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
        from spellbook.gates.check import check_tool_input
    except ImportError as e:
        _log_hook_error("gate_bash", "Bash", e)
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
        from spellbook.gates.check import check_tool_input
    except ImportError as e:
        _log_hook_error("gate_spawn", "spawn_claude_session", e)
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
        from spellbook.gates.check import check_tool_input
    except ImportError as e:
        _log_hook_error("gate_state_sanitize", "workflow_state_save", e)
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


def _memory_inject(tool_name: str, data: dict) -> str | None:
    """Memory: inject file memories. FAIL-OPEN.

    For file-related tools (Read, Edit, Grep, Glob), extracts file_path
    from tool_input and recalls associated memories from the MCP server.
    Applies dedup + budget and returns formatted XML or None.
    """
    if not _auto_recall_enabled():
        return None

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

    namespace, resolved_cwd, branch = _derive_namespace(cwd)
    if not namespace:
        return None

    memories = _recall(
        namespace=namespace,
        branch=branch,
        resolved_cwd=resolved_cwd,
        file_path=file_path,
        limit=MEMORY_BUDGET_MAX_COUNT,
    )
    if not memories:
        return None

    log = _load_dedup_log()
    memories = _filter_memories_by_dedup(memories, log)
    memories = _apply_memory_budget(memories)
    if not memories:
        return None

    xml = _format_memory_xml(memories)
    if xml:
        _touch_dedup_log([m.get("path", "") for m in memories])
    return xml


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
        "/api/speak",
        {"text": message},
        timeout=10,
    )


def _memory_capture(tool_name: str, data: dict) -> None:
    """Memory: capture tool use events. FAIL-OPEN.

    Builds a summary of the tool call and POSTs to /api/memory/event.
    """
    if tool_name in _INTERACTIVE_EXCLUDED_TOOLS or not tool_name:
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

    # Canonical namespace encoding lives in
    # spellbook.memory.utils.derive_namespace_from_cwd; kept inline here
    # because the hook must avoid importing the spellbook package.
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
        "/api/memory/event",
        payload,
        timeout=5,
    )


def _is_auto_memory_path(file_path: str) -> bool:
    """Detect writes to Claude Code's auto-memory directory.

    Matches: ~/.claude/projects/<anything>/memory/<anything>.md
    """
    normalized = file_path.replace("\\", "/")
    return (
        "/.claude/projects/" in normalized
        and "/memory/" in normalized
        and normalized.endswith(".md")
    )


def _memory_bridge(tool_name: str, data: dict) -> None:
    """Bridge: capture auto-memory writes to spellbook. FAIL-OPEN."""
    if tool_name != "Write":
        return

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")

    if not _is_auto_memory_path(file_path):
        return

    content = tool_input.get("content", "")
    if not content:
        return

    # Skip re-capturing spellbook-generated content (design doc Section 8.3).
    # Bootstrap content will be re-captured when the model updates MEMORY.md,
    # which is accepted by design. This lightweight filter avoids the most
    # common echo: the regenerated header written by session init.
    if content.lstrip().startswith("# Spellbook Memory System"):
        return

    cwd = data.get("cwd", "")
    session_id = data.get("session_id", "")
    resolved_cwd, branch = _resolve_git_context(cwd)
    namespace = (
        resolved_cwd.replace("\\", "/").replace("/", "-").lstrip("-")
        if resolved_cwd else "unknown"
    )

    # Determine if this is MEMORY.md or a topic file
    normalized = file_path.replace("\\", "/")
    filename = normalized.rsplit("/", 1)[-1] if "/" in normalized else normalized
    is_primary = filename == "MEMORY.md"

    # 1. Audit trail (existing endpoint, lightweight)
    _http_post(
        "/api/memory/event",
        {
            "session_id": session_id,
            "project": namespace,
            "tool_name": "Write",
            "subject": file_path,
            "summary": f"auto-memory {'primary' if is_primary else 'topic'}: {filename}",
            "tags": "auto-memory,bridge," + filename.lower().replace(".md", ""),
            "event_type": "auto_memory_bridge",
            "branch": branch,
        },
        timeout=5,
    )

    # 2. Full content capture (new endpoint)
    _http_post(
        "/api/memory/bridge-content",
        {
            "session_id": session_id,
            "project": namespace,
            "file_path": file_path,
            "filename": filename,
            "content": content[:50000],  # Safety cap: 50KB
            "is_primary": is_primary,
            "branch": branch,
        },
        timeout=10,
    )


def _stint_depth_check(data: dict) -> str | None:
    """Check stint stack depth and emit behavioral mode + optional tree.

    Three independent outputs:
    1. Empty-stack nudge: emitted when stack is empty.
    2. Behavioral mode one-liner: ALWAYS returned if the top-of-stack
       stint has a non-empty behavioral_mode, regardless of depth.
    3. Full stack tree: only returned when depth >= threshold (default 5).
       Includes staleness warnings for entries >4h old.

    FAIL-OPEN: returns None on any error.
    """
    tool_name = data.get("tool_name", "")
    if tool_name in _INTERACTIVE_EXCLUDED_TOOLS:
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
        return '<stint-empty>No active focus declared. Use stint_push to declare what you\'re working on.</stint-empty>'

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

        # Staleness warnings for entries >4h old
        staleness_lines = []
        for entry in entries:
            entered_at = entry.get("entered_at", "")
            if not entered_at:
                continue
            try:
                entered_dt = datetime.fromisoformat(entered_at)
                now = datetime.now(timezone.utc)
                # Ensure both are tz-aware for comparison
                if entered_dt.tzinfo is None:
                    entered_dt = entered_dt.replace(tzinfo=timezone.utc)
                age_hours = (now - entered_dt).total_seconds() / 3600
                if age_hours > 4:
                    staleness_lines.append(
                        f'  Stale entry: "{entry["name"]}" entered {age_hours:.0f}h ago. Still active?'
                    )
            except (ValueError, TypeError, OverflowError):
                continue  # Malformed timestamp, skip silently

        if staleness_lines:
            lines.extend(staleness_lines)

        lines.append("</stint-check>")
        parts.append("\n".join(lines))

    return "\n".join(parts) if parts else None


def _messaging_check(session_id: str = "") -> str | None:
    """Check messaging inbox for pending messages and format for injection.

    Polls the daemon's /api/messaging/poll endpoint which handles file I/O
    (reading and deleting inbox files) on the daemon side.  The hook only
    performs presentation formatting.

    If no ``session_id`` is provided, no inboxes are drained to prevent one
    session from consuming another session's messages.

    Returns formatted message text or None if inbox is empty.
    """
    if not session_id:
        return None

    resp = _http_post("/api/messaging/poll", {"session_id": session_id})
    if resp is None or not resp.get("messages"):
        return None

    outputs = []
    for msg in resp["messages"]:
        msg_type = msg.get("message_type", "direct")
        sender = msg.get("sender", "unknown")
        correlation_id = msg.get("correlation_id")
        payload = msg.get("payload", {})
        payload_str = json.dumps(payload, indent=2) if isinstance(payload, dict) else str(payload)

        corr_part = f" (correlation_id: {correlation_id})" if correlation_id else ""
        if msg_type == "broadcast":
            formatted = f"[BROADCAST from {sender}]\n{payload_str}"
        elif msg_type == "reply":
            formatted = f"[REPLY from {sender}]{corr_part}\n{payload_str}"
        else:
            formatted = f"[MESSAGE from {sender}]{corr_part}\n{payload_str}"

        outputs.append(formatted)

    return "\n\n".join(outputs) if outputs else None


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
# Memory auto-recall helpers
# ---------------------------------------------------------------------------


def _extract_keywords(prompt: str) -> list[str]:
    """Extract significant keywords from a user prompt.

    Combines three sources in order, preserving order of first appearance:
    1. Path-like tokens (containing '/')
    2. Code identifiers (CamelCase, camelCase, snake_case)
    3. Plain words (len >= 4, not in stopword list)

    Duplicates are removed.
    """
    seen: set[str] = set()
    out: list[str] = []

    def _push(tok: str) -> None:
        if tok and tok not in seen:
            seen.add(tok)
            out.append(tok)

    # Pass 1: tokenize preserving order across identifiers, paths, words.
    # We walk the string, at each non-whitespace token classify it.
    for raw in prompt.split():
        # Strip common trailing punctuation but preserve '/' and '_' and '.'.
        tok = raw.strip(",;:!?()[]{}\"'`")
        if not tok:
            continue
        if "/" in tok:
            _push(tok)
            continue
        if _IDENT_RE.fullmatch(tok):
            _push(tok)
            continue
        # Plain word filter: accept alphanumerics with at least one letter
        # (so tokens like ``gap3``, ``py314``, ``ody0042`` survive).
        lower = tok.lower()
        if (
            len(tok) >= 4
            and lower not in _STOPWORDS
            and tok.isalnum()
            and any(c.isalpha() for c in tok)
        ):
            _push(tok)
    return out


def _extract_tool_paths(tool_name: str, tool_input: dict) -> list[str]:
    """Extract file paths from a tool invocation's input.

    For Bash: split command and keep tokens containing '/'.
    For Write/Edit: the 'file_path' field.
    """
    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        try:
            parts = shlex.split(cmd)
        except ValueError:
            parts = cmd.split()
        return [p for p in parts if "/" in p]
    if tool_name in ("Write", "Edit"):
        fp = tool_input.get("file_path", "") or ""
        return [fp] if fp else []
    return []


def _apply_memory_budget(
    memories: list[dict],
    max_count: int = MEMORY_BUDGET_MAX_COUNT,
    max_tokens: int = MEMORY_BUDGET_MAX_TOKENS,
) -> list[dict]:
    """Cap a memory list by count and cumulative token estimate.

    Token estimate: len(body) // 4 per memory. Stops before adding a memory
    that would push cumulative tokens above max_tokens.
    """
    out: list[dict] = []
    total = 0
    for m in memories:
        if len(out) >= max_count:
            break
        body = m.get("body", "") or ""
        cost = len(body) // 4
        if total + cost > max_tokens:
            break
        out.append(m)
        total += cost
    return out


def _load_dedup_log(now: datetime | None = None) -> dict[str, str]:
    """Load dedup log, dropping entries older than DEDUP_TTL.

    Returns the remaining (fresh) entries as a path->ISO8601 dict.
    """
    if now is None:
        now = _utcnow()
    if not DEDUP_LOG_PATH.exists():
        return {}
    try:
        raw = json.loads(DEDUP_LOG_PATH.read_text())
    except FileNotFoundError:
        # Raced with a delete between .exists() and .read_text() -> silent.
        return {}
    except (OSError, json.JSONDecodeError) as e:
        # Unexpected: permission denied, disk error, corrupt JSON, etc.
        # Route through the daemon's /api/hook-log endpoint so operators
        # can diagnose; fall back to stderr if daemon unreachable. Dedup
        # fails open regardless.
        _log_hook_error("memory_dedup_load", str(DEDUP_LOG_PATH), e)
        return {}
    fresh: dict[str, str] = {}
    cutoff = now - DEDUP_TTL
    for path, ts in raw.items():
        try:
            t = datetime.fromisoformat(ts)
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if t >= cutoff:
            fresh[path] = ts
    return fresh


def _filter_memories_by_dedup(memories: list[dict], log: dict[str, str]) -> list[dict]:
    """Drop memories whose path appears in the dedup log."""
    return [m for m in memories if m.get("path") not in log]


def _atomic_write_json(path: Path, data: dict) -> None:
    """Atomically write `data` as JSON to `path` via tempfile + os.replace.

    The tempfile is created with O_EXCL and a random suffix; on collision we
    retry with a fresh suffix. Once written, ``os.replace`` swaps it into
    place so readers never observe a partially-written file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data).encode("utf-8")
    for _ in range(5):
        tmp = path.with_suffix(
            f".tmp.{os.getpid()}.{secrets.token_hex(4)}"
        )
        try:
            fd = os.open(
                tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644,
            )
        except FileExistsError:
            continue
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
            os.replace(tmp, path)
            return
        except Exception:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
    raise OSError(
        f"unable to allocate unique tempfile for {path} after 5 retries"
    )


def _dedup_lock_path() -> Path:
    return DEDUP_LOG_PATH.with_suffix(DEDUP_LOG_PATH.suffix + ".lock")


def _acquire_dedup_lock(lock_fd: int, timeout_sec: float = 0.1) -> bool:
    """Try to take an exclusive advisory lock on ``lock_fd``.

    Non-blocking first, then a short spinning retry up to ``timeout_sec``.
    Returns True on success, False on timeout. Windows (no ``fcntl``)
    short-circuits to True (no lock taken; caller retains best-effort
    semantics).
    """
    try:
        import fcntl  # POSIX only
    except ImportError:
        return True

    deadline = time.monotonic() + timeout_sec
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.005)
        except OSError:
            # Lock call failed unexpectedly — give up cleanly.
            return False


def _release_dedup_lock(lock_fd: int) -> None:
    try:
        import fcntl  # POSIX only
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    except (ImportError, OSError):
        pass


def _touch_dedup_log(paths: list[str], now: datetime | None = None) -> None:
    """Stamp paths with ``now`` and write back the dedup log.

    Exclusive-lock best effort with a 100ms timeout; on timeout we fall back
    to the prior last-writer-wins semantics and log a diagnostic via
    ``_log_hook_error`` so operators can diagnose contention. The write
    itself is atomic (tempfile + os.replace) so partial writes are never
    observable.
    """
    if now is None:
        now = _utcnow()
    ts = now.isoformat()

    DEDUP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _dedup_lock_path()
    lock_fd: int | None = None
    locked = False
    try:
        try:
            lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
        except OSError:
            lock_fd = None

        if lock_fd is not None:
            locked = _acquire_dedup_lock(lock_fd)
            if not locked:
                _log_hook_error(
                    "memory_dedup_lock_timeout",
                    str(DEDUP_LOG_PATH),
                    TimeoutError("dedup log lock contended beyond 100ms"),
                )

        log = _load_dedup_log(now=now)
        for p in paths:
            if p:
                log[p] = ts
        try:
            _atomic_write_json(DEDUP_LOG_PATH, log)
        except OSError:
            pass
    finally:
        if lock_fd is not None:
            if locked:
                _release_dedup_lock(lock_fd)
            try:
                os.close(lock_fd)
            except OSError:
                pass


def _format_memory_xml(memories: list[dict]) -> str | None:
    """Format memories (filestore MemoryResult shape) as injected XML.

    Shape expected per memory:
      {path, score, match_context, frontmatter: {type, confidence, created,
       last_verified}, body}

    Returns None when the list is empty.
    """
    if not memories:
        return None
    lines = ["<spellbook-memory-context>"]
    for m in memories:
        fm = m.get("frontmatter") or {}
        path = m.get("path", "")
        mtype = fm.get("type", "") or ""
        confidence = fm.get("confidence", "") or ""
        created = fm.get("created", "") or ""
        last_verified = fm.get("last_verified") or ""
        score = m.get("score", 0.0) or 0.0
        body = m.get("body", "") or ""
        lines.append(
            f'  <memory path="{path}" type="{mtype}" confidence="{confidence}"'
            f' created="{created}" last_verified="{last_verified}"'
            f' score="{float(score):.2f}">'
        )
        lines.append(f"    {body}")
        lines.append("  </memory>")
    lines.append("</spellbook-memory-context>")
    return "\n".join(lines)


def _auto_recall_enabled() -> bool:
    """Return True when memory.auto_recall config is truthy (default True)."""
    val = _get_config_value("memory.auto_recall", default=True)
    return bool(val)


def _derive_namespace(cwd: str) -> tuple[str, str, str]:
    """Return (namespace, resolved_cwd, branch) for a given cwd.

    Falls back to an empty namespace when cwd is missing.

    Note: the namespace-encoding logic is canonicalized in
    ``spellbook.memory.utils.derive_namespace_from_cwd``. This hook keeps
    an inline copy to avoid importing the spellbook package at hook
    startup (cold-start cost). Keep the encoding in sync with the
    canonical implementation.
    """
    if not cwd:
        return "", "", ""
    resolved_cwd, branch = _resolve_git_context(cwd)
    namespace = (
        resolved_cwd.replace("\\", "/").replace("/", "-").lstrip("-")
        if resolved_cwd else ""
    )
    return namespace, resolved_cwd, branch


def _recall(namespace: str, branch: str, resolved_cwd: str,
            query: str = "", file_path: str | None = None,
            limit: int = MEMORY_BUDGET_MAX_COUNT) -> list[dict]:
    """POST to /api/memory/recall and return the memories list."""
    payload: dict = {
        "namespace": namespace,
        "branch": branch,
        "repo_path": resolved_cwd,
        "limit": limit,
    }
    if query:
        payload["query"] = query
    if file_path:
        payload["file_path"] = file_path
    resp = _http_post("/api/memory/recall", payload)
    if not resp:
        return []
    return resp.get("memories", []) or []


def _memory_recall_for_prompt(prompt: str, cwd: str) -> str | None:
    """UserPromptSubmit handler: recall memories for a user prompt.

    Skips trivial prompts (< 10 chars) and slash commands. Extracts keywords,
    queries /api/memory/recall, applies dedup + budget, injects XML, and
    records injected paths in the dedup log.
    """
    if not _auto_recall_enabled():
        return None
    if not prompt or len(prompt) < MEMORY_PROMPT_MIN_LENGTH:
        return None
    if prompt.startswith("/"):
        return None

    namespace, resolved_cwd, branch = _derive_namespace(cwd)
    if not namespace:
        return None

    keywords = _extract_keywords(prompt)
    if not keywords:
        return None

    query = " ".join(keywords)
    memories = _recall(
        namespace=namespace,
        branch=branch,
        resolved_cwd=resolved_cwd,
        query=query,
        limit=MEMORY_BUDGET_MAX_COUNT * 4,
    )
    if not memories:
        return None

    log = _load_dedup_log()
    memories = _filter_memories_by_dedup(memories, log)
    memories = _apply_memory_budget(memories)
    if not memories:
        return None

    xml = _format_memory_xml(memories)
    if xml:
        _touch_dedup_log([m.get("path", "") for m in memories])
    return xml


# ---------------------------------------------------------------------------
# Memory auto-store (Gap 4)
# ---------------------------------------------------------------------------

# Rule-dictation patterns take priority — match these FIRST and skip capture.
_RULE_DICTATION_PATTERNS = [
    re.compile(r"\bgive yourself the rule\b", re.IGNORECASE),
    re.compile(r"\bthe rule is:", re.IGNORECASE),
    re.compile(r"\bwrite this down as\b", re.IGNORECASE),
    re.compile(r"\boutput the text only\b", re.IGNORECASE),
    re.compile(r"\bwhat rule to give you\b", re.IGNORECASE),
    re.compile(r"\bhere'?s a rule\b", re.IGNORECASE),
]

# Correction / feedback patterns.
_CORRECTION_PREFIX_RE = re.compile(
    r"^(no|don'?t|stop|actually)\b",
    re.IGNORECASE,
)
_CORRECTION_BODY_PATTERNS = [
    re.compile(r"\buse\s+\S+\s+instead\b", re.IGNORECASE),
    re.compile(r"\balways\s+\S+", re.IGNORECASE),
    re.compile(r"\bnever\s+\S+", re.IGNORECASE),
]

# Confirmation patterns.
_CONFIRMATION_PATTERNS = [
    re.compile(r"\byes exactly\b", re.IGNORECASE),
    re.compile(r"\bperfect keep doing that\b", re.IGNORECASE),
    re.compile(r"\bthat was right\b", re.IGNORECASE),
    re.compile(r"\bnice that worked\b", re.IGNORECASE),
]

# Explicit remember / save patterns.
_REMEMBER_PATTERNS = [
    re.compile(r"\bremember that\b", re.IGNORECASE),
    re.compile(r"\bremember this\b", re.IGNORECASE),
    re.compile(r"\bsave this\b", re.IGNORECASE),
    re.compile(r"\bnote for next time\b", re.IGNORECASE),
    re.compile(r"\bfor future reference\b", re.IGNORECASE),
]

# XML parser for <memory-candidate> blocks. Non-greedy, multiline-aware.
_CANDIDATE_BLOCK_RE = re.compile(
    r"<memory-candidate>(.*?)</memory-candidate>",
    re.DOTALL | re.IGNORECASE,
)
_FIELD_RE_CACHE: dict[str, re.Pattern[str]] = {}

# Max content size for client-side auto-store. Single-fact feedback should
# never exceed this; oversized content is almost always a mis-classified
# pasted blob and must be skipped with a diagnostic log entry.
_AUTO_STORE_MAX_CONTENT_BYTES = 2000


def _log_autostore_oversized(content: str) -> None:
    """Record an auto_store_skipped_oversized_prompt entry via the daemon.

    Does NOT raise. Synthesizes a RuntimeError describing the skipped content
    (first 200 chars preview + total length) and routes it through
    ``_log_hook_error`` so the daemon's rotation-aware sink captures it.
    """
    preview = content[:200].replace("\n", " ")
    detail = f"total_length={len(content)} preview={preview!r}"
    _log_hook_error(
        "auto_store_skipped_oversized_prompt",
        "UserPromptSubmit",
        RuntimeError(detail),
    )


def _auto_store_enabled() -> bool:
    """Return True when memory.auto_store config is truthy (default True)."""
    val = _get_config_value("memory.auto_store", default=True)
    return bool(val)


def _classify_prompt_for_autostore(prompt: str) -> tuple[str, str, str] | None:
    """Classify a user prompt for auto-store.

    Returns (type, tag_suffix, content_override) or None when the prompt
    should not be auto-captured. ``content_override`` is an empty string
    when the raw prompt should be stored verbatim; otherwise it is the
    transformed content (e.g. for confirmations we prefix ``CONFIRMATION:``).

    Rule-dictation patterns are checked FIRST. If any match, return None
    so the dictation is echoed/stored by the user's own intent, not
    auto-captured by this hook.
    """
    for pat in _RULE_DICTATION_PATTERNS:
        if pat.search(prompt):
            return None

    if _CORRECTION_PREFIX_RE.match(prompt.lstrip()):
        return ("feedback", "correction", "")
    for pat in _CORRECTION_BODY_PATTERNS:
        if pat.search(prompt):
            return ("feedback", "correction", "")

    for pat in _CONFIRMATION_PATTERNS:
        if pat.search(prompt):
            return ("feedback", "confirmation", f"CONFIRMATION: {prompt}")

    for pat in _REMEMBER_PATTERNS:
        if pat.search(prompt):
            return ("user", "remember", "")

    return None


def _post_unconsolidated(
    *,
    project: str,
    branch: str,
    mtype: str,
    content: str,
    tags: str,
    citations: str,
    source: str,
) -> bool:
    """POST a self-nominated memory candidate to the unconsolidated endpoint.

    Returns True when ``_http_post`` returned a non-None response body
    (success), False on transport failure. Relies on ``_http_post`` being
    fail-open — do not add a try/except wrapper here. That would mask real
    bugs in payload construction and was a green-mirage double-catch.

    Callers that need retry semantics (e.g. the Stop hook's per-transcript
    idempotency record) MUST inspect the return value. Fire-and-forget
    callers (e.g. UserPromptSubmit) can safely discard it.
    """
    resp = _http_post(
        "/api/memory/unconsolidated",
        {
            "project": project,
            "branch": branch,
            "type": mtype,
            "content": content,
            "tags": tags,
            "citations": citations,
            "source": source,
        },
        timeout=5,
    )
    return resp is not None


def _memory_autostore_for_prompt(prompt: str, cwd: str) -> None:
    """UserPromptSubmit auto-store. FAIL-OPEN.

    Detects correction/confirmation/remember patterns and POSTs a raw
    unconsolidated event. Rule-dictation prompts are skipped entirely.
    """
    if not _auto_store_enabled():
        return
    if not prompt or len(prompt) < MEMORY_PROMPT_MIN_LENGTH:
        return
    if prompt.startswith("/"):
        return

    classification = _classify_prompt_for_autostore(prompt)
    if classification is None:
        return
    mtype, tag_suffix, content_override = classification
    content = content_override if content_override else prompt

    # Single-fact feedback should be short. If the prompt produces an
    # oversized content payload, skip the auto-store and log a diagnostic
    # rather than POSTing a giant prompt as a "memory".
    if len(content) > _AUTO_STORE_MAX_CONTENT_BYTES:
        _log_autostore_oversized(content)
        return

    namespace, _resolved_cwd, branch = _derive_namespace(cwd)
    if not namespace:
        return

    _post_unconsolidated(
        project=namespace,
        branch=branch,
        mtype=mtype,
        content=content,
        tags=f"auto-store,user-prompt,{tag_suffix}",
        citations="",
        source="user_prompt_submit",
    )


def _extract_last_assistant_text(transcript_path: str) -> str:
    """Return concatenated text of the final assistant message in a JSONL transcript.

    Returns empty string when the file is missing, unreadable, or has no
    assistant messages. Fail-open for the Stop hook.
    """
    p = Path(transcript_path)
    if not p.exists():
        return ""
    try:
        raw_lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    last_text = ""
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Transcript entries wrap an inner message dict.
        inner = msg.get("message", msg)
        role = inner.get("role") or msg.get("type")
        if role != "assistant":
            continue
        content = inner.get("content", "")
        if isinstance(content, str):
            last_text = content
            continue
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            last_text = "\n".join(parts)
    return last_text


def _extract_candidate_field(block: str, field: str) -> str:
    """Extract a named field from a <memory-candidate> block body.

    Returns empty string when the field is absent. Case-insensitive tag match.
    """
    pat = _FIELD_RE_CACHE.get(field)
    if pat is None:
        pat = re.compile(
            rf"<{field}>\s*(.*?)\s*</{field}>",
            re.DOTALL | re.IGNORECASE,
        )
        _FIELD_RE_CACHE[field] = pat
    m = pat.search(block)
    if not m:
        return ""
    return m.group(1).strip()


def _parse_memory_candidates(text_body: str) -> list[dict]:
    """Parse all well-formed <memory-candidate> blocks from assistant text.

    A candidate is well-formed when it has a non-empty ``<type>`` AND
    ``<content>``. Malformed blocks are silently dropped.
    """
    out: list[dict] = []
    for m in _CANDIDATE_BLOCK_RE.finditer(text_body):
        block = m.group(1)
        mtype = _extract_candidate_field(block, "type")
        content = _extract_candidate_field(block, "content")
        if not mtype or not content:
            continue
        out.append({
            "type": mtype,
            "content": content,
            "tags": _extract_candidate_field(block, "tags"),
            "citations": _extract_candidate_field(block, "citations"),
        })
    return out


STOP_HARVEST_CACHE_PATH = (
    Path.home() / ".local" / "spellbook" / "cache" / "last-stop-harvest.json"
)


def _load_stop_harvest_cache() -> dict[str, str]:
    """Return the {transcript_path: last_text_sha256} map, or {} on failure."""
    if not STOP_HARVEST_CACHE_PATH.exists():
        return {}
    try:
        raw = json.loads(STOP_HARVEST_CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _record_stop_harvest(transcript_path: str, text_sha: str) -> None:
    """Persist the last-seen sha256 for a transcript. Best-effort."""
    cache = _load_stop_harvest_cache()
    cache[transcript_path] = text_sha
    try:
        _atomic_write_json(STOP_HARVEST_CACHE_PATH, cache)
    except OSError:
        pass


def _merge_candidates(
    regex_cands: list[dict], worker_cands: list[dict]
) -> list[dict]:
    """Content-hash dedup for merge-mode transcript harvest.

    Worker wins on collision: the worker response carries strongly-typed
    tags/citations (lists converted to comma strings), while the regex
    path produces whatever the assistant wrote verbatim.
    """
    seen: dict[str, dict] = {}
    for c in worker_cands:
        key = hashlib.sha256(c["content"].strip().encode()).hexdigest()
        seen[key] = c
    for c in regex_cands:
        key = hashlib.sha256(c["content"].strip().encode()).hexdigest()
        seen.setdefault(key, c)
    return list(seen.values())


def _worker_error_block(task: str, err: BaseException) -> str:
    """Render a ``<worker-llm-error>`` block for injection into the orchestrator.

    Consumed by Claude Code / OpenCode / Codex / Gemini CLI as a structured
    signal that a worker-LLM step failed. The <hint> points operators at
    the doctor CLI and admin event monitor.
    """
    return (
        "<worker-llm-error>\n"
        f"  <task>{task}</task>\n"
        f"  <type>{type(err).__name__}</type>\n"
        f"  <message>{str(err)[:500]}</message>\n"
        "  <hint>Check `spellbook worker-llm doctor` and the admin EventMonitorPage.</hint>\n"
        "</worker-llm-error>"
    )


def _handle_stop(data: dict) -> None:
    """Stop hook: harvest <memory-candidate> blocks and POST each. FAIL-OPEN.

    Idempotent: we hash the extracted final-assistant text per transcript
    and skip harvest when the hash matches the most-recent processed value.

    Three modes driven by ``worker_llm_feature_transcript_harvest`` +
    ``worker_llm_transcript_harvest_mode``:

    - Feature off (default): regex path unchanged. Byte-identical to the
      pre-worker-LLM baseline.
    - ``replace``: worker supersedes regex. Loud-fail on worker error —
      inject ``<worker-llm-error>``, POST nothing, DO NOT record sha so the
      next Stop retries.
    - ``merge``: run both, content-hash dedup. Soft-fail on worker error
      so existing regex behavior never regresses; record sha when regex
      posts succeeded (the error block carries the loss-of-fidelity signal).
    """
    if not _auto_store_enabled():
        return
    transcript_path = data.get("transcript_path", "") or ""
    if not transcript_path:
        return
    try:
        text_body = _extract_last_assistant_text(transcript_path)
    except Exception as e:
        _log_hook_error("stop_extract_transcript", "Stop", e)
        return
    if not text_body:
        return

    text_sha = hashlib.sha256(text_body.encode("utf-8")).hexdigest()
    cache = _load_stop_harvest_cache()
    if cache.get(transcript_path) == text_sha:
        return  # Already processed this exact transcript + final message.

    # ---------- Worker-LLM gate ----------
    # Imports are deferred to function scope so the hook module remains
    # importable by the installer / standalone checks that do not carry
    # the ``spellbook`` package on ``sys.path``.
    try:
        from spellbook.worker_llm import errors as _wl_errors
        from spellbook.worker_llm import events as _wl_events
        from spellbook.worker_llm.config import feature_enabled, get_worker_config
        from spellbook.worker_llm.tasks import transcript_harvest as _wl_harvest
        _wl_import_ok = True
    except Exception:
        _wl_import_ok = False
        _wl_events = None  # type: ignore[assignment]

    _wl_start = time.monotonic()

    use_worker = _wl_import_ok and feature_enabled("transcript_harvest")
    mode = (
        get_worker_config().transcript_harvest_mode.lower()
        if use_worker
        else "skip"
    )
    worker_cands: list[dict] = []
    worker_error: BaseException | None = None

    if use_worker:
        try:
            result = _wl_harvest.transcript_harvest(text_body)
            worker_cands = [
                {
                    "type": c.type,
                    "content": c.content,
                    "tags": ",".join(c.tags),
                    "citations": ",".join(c.citations),
                }
                for c in result
            ]
        except _wl_errors.WorkerLLMError as e:
            worker_error = e
            print(f"[worker-llm] transcript_harvest: {e}", file=sys.stderr)

    if use_worker and mode == "replace":
        if worker_error is not None:
            # Loud: do not fall back, do not record sha.
            print(
                _worker_error_block("transcript_harvest", worker_error),
                file=sys.stdout,
            )
            if _wl_events is not None:
                _wl_events.publish_hook_integration(
                    task="transcript_harvest",
                    mode=mode,
                    candidate_count=0,
                    duration_ms=int((time.monotonic() - _wl_start) * 1000),
                    status="worker_error",
                    error=type(worker_error).__name__,
                )
            return
        candidates = worker_cands
    elif use_worker and mode == "merge":
        regex_cands = _parse_memory_candidates(text_body)
        if worker_error is not None:
            candidates = regex_cands
            print(
                _worker_error_block("transcript_harvest", worker_error),
                file=sys.stdout,
            )
        else:
            candidates = _merge_candidates(regex_cands, worker_cands)
    else:
        # Feature off (or mode == "skip"): existing regex path unchanged.
        candidates = _parse_memory_candidates(text_body)

    if not candidates:
        _record_stop_harvest(transcript_path, text_sha)
        return

    namespace, _resolved_cwd, branch = _derive_namespace(data.get("cwd", ""))
    if not namespace:
        _record_stop_harvest(transcript_path, text_sha)
        return

    failed = 0
    for cand in candidates:
        ok = _post_unconsolidated(
            project=namespace,
            branch=branch,
            mtype=cand["type"],
            content=cand["content"],
            tags=cand.get("tags", ""),
            citations=cand.get("citations", ""),
            source="stop_hook",
        )
        if not ok:
            failed += 1

    # Sha recording policy:
    #   REPLACE mode: recorded only when the worker succeeded (early return
    #     above covers worker_error) AND every POST succeeded.
    #   MERGE mode: record sha even when worker_error is set, because the
    #     regex candidates were already POSTed successfully; NOT recording
    #     would cause the same transcript to be re-harvested on every Stop
    #     (duplicate regex posts) even though the only thing that failed is
    #     the optional worker augmentation. The <worker-llm-error> block has
    #     already been injected into the orchestrator, so the loss-of-fidelity
    #     signal is preserved.
    merge_mode_with_worker_only_error = (
        use_worker
        and mode == "merge"
        and worker_error is not None
        and failed == 0
    )
    if failed == 0 and (worker_error is None or merge_mode_with_worker_only_error):
        _record_stop_harvest(transcript_path, text_sha)
        _status = "ok" if worker_error is None else "worker_error"
    else:
        # Do NOT record the sha: the next Stop invocation must retry the
        # whole harvest. Server-side consolidation dedups on content, so
        # double-posting on retry is acceptable.
        _log_hook_error(
            "stop_harvest_partial_failure",
            "Stop",
            RuntimeError(
                f"stop_harvest_partial_failure failed={failed} "
                f"total={len(candidates)} "
                f"worker_error={type(worker_error).__name__ if worker_error else 'none'}"
            ),
        )
        _status = "partial"

    if use_worker and _wl_events is not None:
        _wl_events.publish_hook_integration(
            task="transcript_harvest",
            mode=mode,
            candidate_count=len(candidates),
            duration_ms=int((time.monotonic() - _wl_start) * 1000),
            status=_status,
            error=(type(worker_error).__name__ if worker_error else None),
        )


def _memory_recall_for_tool(tool_name: str, tool_input: dict, cwd: str) -> str | None:
    """PreToolUse handler: recall memories for Bash/Write/Edit file targets."""
    if not _auto_recall_enabled():
        return None
    if tool_name not in ("Bash", "Write", "Edit"):
        return None

    paths = _extract_tool_paths(tool_name, tool_input or {})
    if not paths:
        return None

    namespace, resolved_cwd, branch = _derive_namespace(cwd)
    if not namespace:
        return None

    collected: list[dict] = []
    seen_paths: set[str] = set()
    for fp in paths:
        mems = _recall(
            namespace=namespace,
            branch=branch,
            resolved_cwd=resolved_cwd,
            file_path=fp,
            limit=MEMORY_BUDGET_MAX_COUNT,
        )
        for m in mems:
            p = m.get("path", "")
            if p and p not in seen_paths:
                seen_paths.add(p)
                collected.append(m)

    if not collected:
        return None

    log = _load_dedup_log()
    collected = _filter_memories_by_dedup(collected, log)
    collected = _apply_memory_budget(collected)
    if not collected:
        return None

    xml = _format_memory_xml(collected)
    if xml:
        _touch_dedup_log([m.get("path", "") for m in collected])
    return xml


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

    # Temporal tracking (catch-all, non-blocking)
    _record_tool_start(tool_name, data)

    # Memory auto-recall for file-modifying tools (non-blocking)
    if tool_name in ("Bash", "Write", "Edit"):
        try:
            out = _memory_recall_for_tool(
                tool_name, data.get("tool_input") or {}, data.get("cwd", ""),
            )
            if out:
                outputs.append(out)
        except Exception as e:
            _log_hook_error("memory_recall_for_tool", tool_name, e)

    return outputs


def _handle_user_prompt_submit(data: dict) -> list[str]:
    """UserPromptSubmit handler: auto-inject memory context for prompts."""
    outputs: list[str] = []
    prompt = data.get("prompt", "") or data.get("user_prompt", "") or ""
    try:
        out = _memory_recall_for_prompt(prompt, data.get("cwd", ""))
        if out:
            outputs.append(out)
    except Exception as e:
        _log_hook_error("memory_recall_for_prompt", "UserPromptSubmit", e)

    # Pattern-based self-capture (Gap 4). Non-blocking, fail-open.
    try:
        _memory_autostore_for_prompt(prompt, data.get("cwd", ""))
    except Exception as e:
        _log_hook_error("memory_autostore_for_prompt", "UserPromptSubmit", e)
    return outputs


def _handle_post_tool_use(tool_name: str, data: dict) -> list[str]:
    """PostToolUse handlers. Return list of output strings."""
    outputs = []

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

    # Auto-memory bridge (specific matcher: Write to auto-memory paths)
    if tool_name == "Write":
        _fire_and_forget(_memory_bridge, tool_name, data)

    # Messaging inbox check (catch-all, synchronous - injects into context)
    out = _messaging_check(session_id=data.get("session_id", ""))
    if out:
        outputs.append(out)

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
    elif event_name == "UserPromptSubmit":
        outputs.extend(_handle_user_prompt_submit(data))
    elif event_name == "Stop":
        try:
            _handle_stop(data)
        except Exception as e:
            _log_hook_error("stop", "Stop", e)
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

    try:
        output = dispatch(event_name, tool_name, data)
        if output:
            print(output)
    except Exception as e:
        _log_hook_error(event_name, tool_name, e)


if __name__ == "__main__":
    main()
