#!/usr/bin/env python3
"""Unified spellbook hook entrypoint.

Single Python script handling all hook events. Dispatches to handler
functions based on hook_event_name and tool_name from stdin JSON.

Replaces all individual shell hooks (bash-gate.sh, spawn-guard.sh,
state-sanitize.sh, notify-timer-start.sh, audit-log.sh, canary-check.sh,
memory-inject.sh, notify-on-complete.sh, memory-capture.sh,
pre-compact-save.sh, post-compact-recover.sh).
"""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

# DEBUG-level logger for best-effort silent-except paths. Python's default
# logging handler only emits WARNING and above, so DEBUG messages are a
# no-op unless an operator explicitly configures logging (e.g., via
# ``PYTHONLOGLEVEL=DEBUG``). This keeps the normal hook run quiet while
# leaving a trail for investigations.
logger = logging.getLogger("spellbook.hook")


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
    # ForgeCode session marker not yet exposed by upstream as of this writing;
    # sessions running under forge will fall through to "unknown". Tracked as
    # design follow-up #4 in 2026-04-30-forgecode-support-design.md. When
    # upstream surfaces a stable env-var marker (e.g. FORGE_SESSION_ID), add
    # an elif here returning "forgecode" (no dash form) to align with
    # installer/config.py SUPPORTED_PLATFORMS naming. Note: spellbook hook
    # IDs use dashes (claude-code, gemini-cli) while installer config uses
    # underscores; for forgecode the canonical hook return should be
    # "forgecode" to match the installer side.
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
        "timestamp": _utcnow().isoformat(),
        "event": f"{event}:{tool}",
        "traceback": tb,
    }
    result = _http_post("/api/hook-log", payload)
    if result is None:
        # Daemon unreachable -- write to stderr so it shows in Claude Code output
        print(f"[spellbook-hook] Error in {event}:{tool}:\n{tb}", file=sys.stderr)


_pending_emitter_threads: list[threading.Thread] = []


def _fire_and_forget(fn, *args):
    """Run a function in a daemon thread (dies with process).

    The thread is tracked in ``_pending_emitter_threads`` so ``main()`` can
    drain outstanding emitters with a short aggregate timeout before exit —
    otherwise the hook's ``sys.exit`` can race the POST and drop the record.
    """

    def _wrapper():
        try:
            fn(*args)
        except Exception as e:
            _log_hook_error("fire_and_forget", fn.__name__, e)

    t = threading.Thread(target=_wrapper, daemon=True)
    _pending_emitter_threads.append(t)
    t.start()


def _drain_pending_emitters(deadline_s: float = 1.0) -> None:
    """Best-effort wait for outstanding fire-and-forget threads.

    Joins each thread with a shrinking slice of ``deadline_s``. If the
    budget is exhausted before every thread finishes, the remaining ones
    stay daemonic and die with the process — same behavior as before the
    drain, no worse. The goal is to give fast, localhost emitters the
    ~10-50ms they need to flush WITHOUT materially slowing down the hook
    perceptibly when everything is healthy.

    Never raises: a thread that raised its own exception has already been
    logged via ``_log_hook_error`` inside ``_wrapper``.
    """
    deadline = time.monotonic() + deadline_s
    for t in _pending_emitter_threads:
        remaining = max(0.0, deadline - time.monotonic())
        if remaining <= 0:
            break
        t.join(timeout=remaining)
    _pending_emitter_threads.clear()


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


# Excluded tools for notifications (high-frequency, fast tools)
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

def _handle_check_result(result: dict) -> None:
    """Process a ``check_tool_input`` result, exiting if the gate denies or asks.

    On ``verdict == "ask"``: delegates to :func:`_emit_ask_and_exit` (which
    exits 0 with a ``permissionDecision`` JSON on stdout).
    On ``safe == False``: prints the error JSON to stderr and exits 2 (block).
    Otherwise returns silently (allow).
    """
    if result.get("verdict") == "ask":
        _emit_ask_and_exit(result["findings"])
    if not result["safe"]:
        reasons = "; ".join(
            f["message"]
            for f in result["findings"]
            if f.get("severity") != "LOW"
        )
        print(json.dumps({"error": f"Security check failed: {reasons}"}), file=sys.stderr)
        sys.exit(2)


def _emit_ask_and_exit(findings: list[dict]) -> None:
    """Emit Claude Code's ``permissionDecision: "ask"`` JSON and exit 0.

    Used when ``check_tool_input`` returns ``verdict == "ask"`` — every
    non-LOW finding is a TIER-ASK (e.g. ``git push``, ``gh pr merge``).
    The harness shows a yellow permission prompt the operator can
    approve from inside the session; T3 deny still hits the exit-2
    branch.
    """
    reason = "; ".join(
        f.get("message", "")
        for f in findings
        if f.get("rule_id", "").startswith("TIER-ASK")
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def _gate_bash(data: dict) -> None:
    """Security: validate bash commands. FAIL-CLOSED.

    Calls check_tool_input from the security module. The ``verdict`` field
    selects the action:

    - ``"allow"``: no findings above LOW; return silently.
    - ``"ask"``: only TIER-ASK findings (T2, e.g. ``git push``); emit
      ``permissionDecision: "ask"`` and exit 0 so the harness surfaces
      a permission prompt.
    - ``"deny"``: TIER-DENY (T3), CRITICAL bashlex/exfil findings, or
      any mix containing a non-ask finding; exit 2 with a structured
      error on stderr. Error messages never include blocked content
      (anti-reflection).

    If the security module cannot be imported, blocks (fail-closed).
    """
    try:
        from spellbook.gates.check import check_tool_input
    except ImportError as e:
        _log_hook_error("gate_bash", "Bash", e)
        print(json.dumps({"error": "Security check failed: security module not available"}), file=sys.stderr)
        sys.exit(2)

    tool_input = data.get("tool_input")
    if not tool_input:
        print(json.dumps({"error": "Security check failed: no tool input provided"}), file=sys.stderr)
        sys.exit(2)

    result = check_tool_input("Bash", tool_input, cwd=data.get("cwd", ""))
    _handle_check_result(result)


def _gate_spawn(data: dict) -> None:
    """Security: validate spawn prompts. FAIL-CLOSED.

    Normalizes tool_name from MCP prefix to bare name before checking.
    See :func:`_gate_bash` for the verdict / exit-code contract.
    """
    try:
        from spellbook.gates.check import check_tool_input
    except ImportError as e:
        _log_hook_error("gate_spawn", "spawn_claude_session", e)
        print(json.dumps({"error": "Security check failed: security module not available"}), file=sys.stderr)
        sys.exit(2)

    tool_input = data.get("tool_input")
    if not tool_input:
        print(json.dumps({"error": "Security check failed: no tool input provided"}), file=sys.stderr)
        sys.exit(2)

    result = check_tool_input("spawn_claude_session", tool_input, cwd=data.get("cwd", ""))
    _handle_check_result(result)


def _gate_state_sanitize(data: dict) -> None:
    """Security: validate workflow state. FAIL-CLOSED.

    Normalizes tool_name from MCP prefix to bare name before checking.
    See :func:`_gate_bash` for the verdict / exit-code contract.
    """
    try:
        from spellbook.gates.check import check_tool_input
    except ImportError as e:
        _log_hook_error("gate_state_sanitize", "workflow_state_save", e)
        print(json.dumps({"error": "Security check failed: security module not available"}), file=sys.stderr)
        sys.exit(2)

    tool_input = data.get("tool_input")
    if not tool_input:
        print(json.dumps({"error": "Security check failed: no tool input provided"}), file=sys.stderr)
        sys.exit(2)

    result = check_tool_input("workflow_state_save", tool_input, cwd=data.get("cwd", ""))
    _handle_check_result(result)


# ---------------------------------------------------------------------------
# Handlers: FAIL-OPEN (never block)
# ---------------------------------------------------------------------------

def _record_tool_start(tool_name: str, data: dict) -> None:
    """Record tool start time for notification thresholds.

    Writes current Unix timestamp to:
    - {tempdir}/claude-notify-start-{tool_use_id} (for OS notifications)
    """
    tool_use_id = data.get("tool_use_id", "")
    if not _validate_tool_use_id(tool_use_id):
        return
    now = str(int(time.time()))
    tmpdir = tempfile.gettempdir()
    try:
        Path(os.path.join(tmpdir, f"claude-notify-start-{tool_use_id}")).write_text(now)
    except OSError:
        pass


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

_SAFETY_APPLICABLE_TOOLS = frozenset({"Bash", "Write", "Edit"})


def _safety_warn_block(reasoning: str) -> str:
    """Render the ``<worker-llm-tool-safety verdict="WARN">`` output block.

    ``reasoning`` originates from the worker LLM and may contain arbitrary
    characters, including ``<``, ``>``, ``&``, and (under a prompt-injection
    attack) literal closing-tag strings. Escape before interpolation so a
    drifty or adversarial response cannot inject sibling tags into the
    orchestrator's output stream.
    """
    return (
        '<worker-llm-tool-safety verdict="WARN">\n'
        f"  {_xml_escape(reasoning)}\n"
        "</worker-llm-tool-safety>"
    )


def _emit_block_and_exit(reasoning: str) -> None:
    """Signal BLOCK to the platform via stderr + ``sys.exit(2)``.

    Claude Code convention: exit 2 with the message on stderr; the platform
    presents the reasoning to the user and vetoes the tool call. The 30-second
    bypass note lets a user retry the exact same invocation to override.

    ``reasoning`` is escaped for the same reason as ``_safety_warn_block``.
    """
    print(
        '<worker-llm-tool-safety verdict="BLOCK">\n'
        f"  {_xml_escape(reasoning)}\n"
        "  Retry the same tool call within 30 seconds to bypass this check.\n"
        "</worker-llm-tool-safety>",
        file=sys.stderr,
    )
    sys.exit(2)


def _recent_context_snippet(data: dict) -> str:
    """Best-effort grab of the last few transcript turns (<= 4KB)."""
    transcript_path = data.get("transcript_path", "") or ""
    if not transcript_path:
        return ""
    try:
        lines = Path(transcript_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-6:])[-4000:]


def _handle_pre_tool_use(tool_name: str, data: dict) -> list[str]:
    """PreToolUse handlers. Return list of output strings.

    Order of operations:
      1. Existing security gates (can exit non-zero) — untouched.
      2. Temporal tracking — untouched.
      3. Worker-LLM tool-safety sniff. Fails OPEN on any error, and is
         cache-first (consults safety_cache before calling the worker). A
         fresh BLOCK triggers a 30-second bypass window so the user can retry.
    """
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

    # Worker-LLM tool-safety sniff (fails OPEN)
    if tool_name in _SAFETY_APPLICABLE_TOOLS:
        _wl_tool_safety_sniff(tool_name, data, outputs)

    return outputs


def _wl_tool_safety_sniff(
    tool_name: str, data: dict, outputs: list[str]
) -> None:
    """Inline gate that consults the worker LLM for an OK/WARN/BLOCK verdict.

    Separated from the handler body to keep the handler's existing flow
    readable and so the paranoid outer try/except only wraps the new code.
    A ``sys.exit(2)`` raised here propagates through the handler as expected
    (``SystemExit`` is re-raised from the catch-all below).
    """
    _wl_start = time.monotonic()
    try:
        from spellbook.worker_llm import errors as _wl_errors
        from spellbook.worker_llm import events as _wl_events
        from spellbook.worker_llm import safety_cache as _wl_cache
        from spellbook.worker_llm.config import feature_enabled
        from spellbook.worker_llm.tasks import tool_safety as _wl_safety
    except Exception:
        # Import failure should never block a tool call.
        return

    try:
        if not feature_enabled("tool_safety"):
            return
    except Exception:
        # Config read failing should never block a tool call. DEBUG so an
        # operator auditing spurious fail-open traffic can correlate back
        # to a broken config file without polluting normal output.
        logger.debug(
            "tool_safety_hook: feature_enabled raised; treating as disabled",
            exc_info=True,
        )
        return

    params = data.get("tool_input") or {}
    cache_hit = False
    try:
        key = _wl_cache.make_key(tool_name, params)

        # 30-second bypass: a fresh BLOCK lets the user retry once without
        # re-consulting the worker. ``should_bypass`` consumes the bypass.
        if _wl_cache.should_bypass(key):
            _wl_events.publish_hook_integration(
                task="tool_safety",
                mode="",
                candidate_count=-1,
                duration_ms=int((time.monotonic() - _wl_start) * 1000),
                status="bypass",
                error=None,
            )
            return

        cached = _wl_cache.get_cached_verdict(key)
        if cached is not None:
            cache_hit = True
            verdict = cached
        else:
            verdict = _wl_safety.tool_safety(
                tool_name, params, _recent_context_snippet(data)
            )
            # tool_safety has fail-open semantics; it returns an OK "error;
            # fail-open" verdict on failure and does NOT cache those. Real
            # OK/WARN/BLOCK verdicts are already cached inside the task.

        if verdict.verdict == "WARN":
            outputs.append(_safety_warn_block(verdict.reasoning))
            _wl_events.publish_hook_integration(
                task="tool_safety",
                mode="",
                candidate_count=1 if cache_hit else 0,
                duration_ms=int((time.monotonic() - _wl_start) * 1000),
                status="warn",
                error=None,
            )
        elif verdict.verdict == "BLOCK":
            _wl_cache.record_block(key)
            # Emit the event BEFORE exiting so it still lands.
            _wl_events.publish_hook_integration(
                task="tool_safety",
                mode="",
                candidate_count=1 if cache_hit else 0,
                duration_ms=int((time.monotonic() - _wl_start) * 1000),
                status="block",
                error=None,
            )
            _emit_block_and_exit(verdict.reasoning)
        else:
            # OK verdict (including fail-open OK).
            _wl_events.publish_hook_integration(
                task="tool_safety",
                mode="",
                candidate_count=1 if cache_hit else 0,
                duration_ms=int((time.monotonic() - _wl_start) * 1000),
                status="ok",
                error=None,
            )

    except SystemExit:
        # BLOCK exits with code 2 -- let it through.
        raise
    except (_wl_errors.WorkerLLMTimeout,
            _wl_errors.WorkerLLMUnreachable,
            _wl_errors.WorkerLLMBadResponse) as e:
        # Known transient failures: FAIL OPEN. Stderr notice only.
        print(
            f"[worker-llm] tool_safety: {e} (failing open)",
            file=sys.stderr,
        )
    except Exception as e:
        # Paranoid catch: any unexpected exception must not block the user.
        _log_hook_error("worker_llm_tool_safety", tool_name, e)


# ---------------------------------------------------------------------------
# agent2agent: surface inbox metadata for sessions bound via `open <name>`
# ---------------------------------------------------------------------------

# Mirror of the helper's bus-dir resolution. Kept in sync with
# skills/agent2agent/scripts/agent2agent.py.
_A2A_DEFAULT_BUS_DIR = Path.home() / ".local" / "share" / "agent2agent"
_A2A_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_A2A_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_A2A_NOTIFY_TIMEOUT_S = 3.0


def _a2a_bus_dir() -> Path:
    env = os.environ.get("AGENT2AGENT_DIR")
    return Path(env) if env else _A2A_DEFAULT_BUS_DIR


def _a2a_helper_path() -> Path:
    """Resolve the agent2agent helper script.

    Honors $SPELLBOOK_DIR (set in tests and most installs); otherwise falls
    back to the source location relative to this hook file.
    """
    env = os.environ.get("SPELLBOOK_DIR")
    if env:
        return Path(env) / "skills" / "agent2agent" / "scripts" / "agent2agent.py"
    # spellbook_hook.py lives at <repo>/hooks/spellbook_hook.py
    return Path(__file__).resolve().parent.parent / "skills" / "agent2agent" / "scripts" / "agent2agent.py"


def _agent2agent_notify_for_prompt(data: dict) -> str | None:
    """UserPromptSubmit handler: surface inbox metadata for the bound name.

    SECURITY: this MUST only invoke the helper's ``notify`` subcommand,
    which produces metadata-only output (count + sender names). Wiring
    ``read``/``peek``/``check`` here would inject untrusted message bodies
    into the session context — a prompt-injection vector.

    Returns the helper's stdout (a one- or two-line ``[agent2agent] ...``
    notice) when the bound name has pending mail, else None.
    """
    session_id = data.get("session_id", "") or ""
    if not session_id or not _A2A_SESSION_ID_RE.match(session_id):
        return None

    bus = _a2a_bus_dir()
    binding_path = bus / ".bindings" / session_id
    try:
        bound_name = binding_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError:
        return None
    if not bound_name or not _A2A_NAME_RE.match(bound_name):
        return None

    helper = _a2a_helper_path()
    if not helper.exists():
        return None

    helper_env = os.environ.copy()
    # Pass the active session id so the helper can perform stale-binding
    # cleanup (it falls back to $CLAUDE_CODE_SESSION_ID, which may not be
    # propagated into the hook subprocess by every harness).
    helper_env["CLAUDE_CODE_SESSION_ID"] = session_id
    helper_env["AGENT2AGENT_DIR"] = str(bus)
    try:
        proc = subprocess.run(
            [sys.executable, str(helper), "notify", bound_name],
            capture_output=True,
            text=True,
            timeout=_A2A_NOTIFY_TIMEOUT_S,
            env=helper_env,
        )
    except subprocess.TimeoutExpired:
        logger.debug("agent2agent notify timed out")
        return None
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("agent2agent notify failed: %s", e)
        return None

    out = (proc.stdout or "").strip()
    return out if out else None


def _bg_agent_alive(agent_id, state) -> bool:
    """FAIL-SAFE-DEAD liveness probe of the bg watch-chain Task agent.

    Shares the mtime+600s-window probe with
    ``skills/agent2agent/scripts/agent2agent.py::cmd_open_state``
    op=``alive`` (T4); differs in return contract — this hook helper
    returns a ``bool``, while the helper's CLI op returns exit codes
    (0 alive, 1 dead, 2 state missing/malformed). Both are
    fail-safe-DEAD: there is no fail-safe-alive branch on either side,
    so any divergence in the shared probe is a bug. The agent is
    considered ALIVE only when ALL of:

      - ``agent_id`` is non-empty
      - ``state`` is a dict containing ``output_file`` (the absolute path
        the slash command captured at Task dispatch time)
      - that path exists on disk
      - its mtime is fresh (< 600.0 seconds ago)

    Any failure of those preconditions returns ``False`` (DEAD). There is
    no fail-safe-alive branch: a missing output_file, a stat error, or an
    older-than-600s mtime are all treated as DEAD. This matches T4's exit
    1 / 2 ``not alive`` semantics from ``cmd_open_state alive``.

    The 600s threshold must EXCEED the 540s WATCH_RECYCLE budget. While
    blocked on ``watch``, the bg agent emits no stdout, so its transcript
    mtime does not advance during idle windows (validated by the A9
    zero-idle-tokens manual e2e). A threshold smaller than 540s would
    false-positive ``DEAD`` mid-idle. 600s gives a 60s grace margin for
    the inter-cycle re-dispatch (Task agent exit → main loop reads marker
    → spawns next bg agent → first transcript write).
    """
    if not agent_id:
        return False
    output_path = state.get("output_file") if isinstance(state, dict) else None
    if not output_path:
        return False
    op = Path(output_path)
    if not op.exists():
        return False
    try:
        age = time.time() - op.stat().st_mtime
    except OSError:
        return False
    return age < 600.0


def _agent2agent_check_orphaned_chain(data: dict) -> str | None:
    """SessionStart / UserPromptSubmit backstop: detect a dropped watch chain.

    Returns a static-template re-arm hint string when the current session
    has an open watch-chain record (``<bus>/.open/<sid>``) whose bg agent
    is no longer alive (per ``_bg_agent_alive`` / T4). Returns ``None`` in
    every other case (silent path: no state, alive agent, malformed JSON,
    invalid bound name, etc.).

    SECURITY: this function ONLY:
      - reads JSON from ``.open/<sid>`` (a file written by THIS user's
        slash command);
      - stats the bg-agent transcript path captured in that JSON;
      - emits a static template that includes the bound name (already
        public to the operator).
    NEVER calls ``read``, ``peek``, ``check``, or anything that could
    surface message bodies. The transcript file is stat'd, NOT read.
    """
    session_id = data.get("session_id", "") or ""
    if not session_id or not _A2A_SESSION_ID_RE.match(session_id):
        return None
    bus = _a2a_bus_dir()
    state_path = bus / ".open" / session_id
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(state, dict):
        return None
    name = state.get("name")
    agent_id = state.get("agent_id")
    if not name or not _A2A_NAME_RE.match(name):
        return None
    if _bg_agent_alive(agent_id, state):
        return None
    return (
        f"[agent2agent] watch chain dropped (likely session compaction or "
        f"process death). Run `/a2a open {name}` to re-arm the inbox watcher."
    )


def _handle_user_prompt_submit(data: dict) -> list[str]:
    """UserPromptSubmit handler: surface agent2agent inbox/watch-chain hints."""
    outputs: list[str] = []

    # agent2agent inbox metadata (only for sessions bound via `open <name>`).
    # Metadata-only by design: NEVER call read/peek/check from here.
    try:
        out = _agent2agent_notify_for_prompt(data)
        if out:
            outputs.append(out)
    except Exception as e:
        _log_hook_error("agent2agent_notify_for_prompt", "UserPromptSubmit", e)

    # agent2agent orphaned-chain backstop: surface a re-arm hint when the
    # bg watch agent for an open chain has died (compaction, process death).
    # Metadata-only: reads `.open/<sid>` JSON + stats the transcript path.
    try:
        orphan_hint = _agent2agent_check_orphaned_chain(data)
        if orphan_hint:
            outputs.append(orphan_hint)
    except Exception as e:
        _log_hook_error("agent2agent_check_orphaned_chain", "UserPromptSubmit", e)

    return outputs


def _handle_post_tool_use(tool_name: str, data: dict) -> list[str]:
    """PostToolUse handlers. Return list of output strings."""
    outputs = []

    # Stint depth reminder (catch-all, non-blocking)
    out = _stint_depth_check(data)
    if out:
        outputs.append(out)

    # Notifications (catch-all, non-blocking)
    _fire_and_forget(_notify_on_complete, tool_name, data)

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
    """Post-compaction recovery + orphaned-watch-chain backstop.

    The orphan check runs FIRST, BEFORE the ``source != "compact"`` early
    return, so the re-arm hint surfaces on every SessionStart (cold start,
    resume, compaction). The check depends only on ``session_id`` and the
    presence of a ``<bus>/.open/<sid>`` record, NOT on the source kind.

    Wiring (per design §6.1):
      - Non-compact source + orphan: return a SessionStart payload whose
        ``additionalContext`` is the orphan hint.
      - Non-compact source + no orphan: return None (existing behavior
        preserved).
      - Compact source: build the existing recovery directive AS-IS,
        then APPEND the orphan hint (separated by a blank line) when
        present.
    """
    source = data.get("source", "")

    # Backstop runs unconditionally — orphan detection is independent of
    # source. Fail-open: any unexpected exception is logged and the rest
    # of SessionStart proceeds as if no orphan was detected.
    try:
        orphan_hint = _agent2agent_check_orphaned_chain(data)
    except Exception as e:
        _log_hook_error("agent2agent_check_orphaned_chain", "SessionStart", e)
        orphan_hint = None

    if source != "compact":
        if orphan_hint:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": orphan_hint,
                }
            }
        return None

    project_path = data.get("cwd", "")
    ws = None
    if project_path:
        ws = _mcp_call("workflow_state_load", {
            "project_path": project_path,
            "max_age_hours": 24,
        })

    if not ws or not ws.get("found"):
        result = _fallback_directive()
        if orphan_hint:
            result["hookSpecificOutput"]["additionalContext"] += (
                "\n\n" + orphan_hint
            )
        return result

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

    # Append orphan hint last so it remains visible alongside the recovery
    # directive without being buried.
    if orphan_hint:
        directive += "\n\n" + orphan_hint

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
    elif event_name == "PreCompact":
        _handle_pre_compact(data)
    elif event_name == "SessionStart":
        result = _handle_session_start(data)
        if result:
            return json.dumps(result)

    combined = "\n".join(o for o in outputs if o)
    return combined if combined else None


def _record_hook_event_fire_and_forget(
    event_name: str,
    tool_name: str,
    duration_ms: int,
    exit_code: int,
    error: str | None,
) -> None:
    """POST a hook event record to the daemon. <0.5s timeout; swallow errors.

    In-daemon writers use ``spellbook.hooks.observability.record_hook_event``
    directly; subprocess hook callers (this module) re-enter via the daemon
    endpoint because they have no running event loop.
    """
    payload = {
        "hook_name": "spellbook_hook",
        "event_name": event_name or "unknown",
        "duration_ms": int(max(0, duration_ms)),
        "exit_code": int(exit_code),
    }
    if tool_name:
        payload["tool_name"] = tool_name[:128]
    if error:
        payload["error"] = error[:1000]
    try:
        _http_post("/api/hooks/record", payload, timeout=0.5)
    except Exception:
        pass  # Best-effort; hooks must never fail on observability.


def main():
    """Parse stdin and dispatch to handlers."""
    start = time.monotonic()
    event_name = ""
    tool_name = ""
    exit_code = 0
    error_str: str | None = None

    def _emit_record() -> None:
        duration_ms = int((time.monotonic() - start) * 1000)
        _fire_and_forget(
            _record_hook_event_fire_and_forget,
            event_name, tool_name, duration_ms, exit_code, error_str,
        )

    # Wrap the entire body in try/finally so outstanding emitter threads are
    # drained before the process exits, including when an inner ``sys.exit``
    # fires. Without this, the hook process can exit before the daemon POST
    # completes and the record is silently dropped.
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            _emit_record()
            sys.exit(0)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            error_str = "JSONDecodeError"
            _emit_record()
            sys.exit(0)

        event_name = data.get("hook_event_name", "")
        if not event_name:
            if "tool_result" in data:
                event_name = "PostToolUse"
            elif "tool_name" in data:
                event_name = "PreToolUse"
            else:
                _emit_record()
                sys.exit(0)

        tool_name = data.get("tool_name", "")

        try:
            output = dispatch(event_name, tool_name, data)
            if output:
                print(output)
        except SystemExit as e:
            # _emit_block_and_exit calls sys.exit(2); capture exit code.
            exit_code = int(e.code) if isinstance(e.code, int) else 1
            _emit_record()
            raise
        except Exception as e:
            error_str = f"{type(e).__name__}: {e}"[:1000]
            exit_code = 1
            _log_hook_error(event_name, tool_name, e)

        _emit_record()
    finally:
        _drain_pending_emitters(1.0)


if __name__ == "__main__":
    main()
