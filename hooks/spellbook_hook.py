#!/usr/bin/env python3
"""Unified spellbook hook entrypoint.

Single Python script handling all hook events. Dispatches to handler
functions based on hook_event_name and tool_name from stdin JSON.
"""

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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
    if (
        os.environ.get("CLAUDECODE") == "1"
        or os.environ.get("CLAUDE_CODE_ENTRYPOINT")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CLAUDE_ENV_FILE")
    ):
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
        "timestamp": _utcnow().isoformat(),
        "event": f"{event}:{tool}",
        "traceback": tb,
    }
    result = _http_post("/api/hook-log", payload)
    if result is None:
        print(f"[spellbook-hook] Error in {event}:{tool}:\n{tb}", file=sys.stderr)


_pending_emitter_threads: list[threading.Thread] = []


def _fire_and_forget(fn, *args):
    """Run a function in a daemon thread (dies with process)."""

    def _wrapper():
        try:
            fn(*args)
        except Exception as e:
            _log_hook_error("fire_and_forget", fn.__name__, e)

    t = threading.Thread(target=_wrapper, daemon=True)
    _pending_emitter_threads.append(t)
    t.start()


def _drain_pending_emitters(deadline_s: float = 1.0) -> None:
    """Best-effort wait for outstanding fire-and-forget threads."""
    deadline = time.monotonic() + deadline_s
    for t in _pending_emitter_threads:
        remaining = max(0.0, deadline - time.monotonic())
        if remaining <= 0:
            break
        t.join(timeout=remaining)
    _pending_emitter_threads.clear()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _http_post(path: str, payload: dict, timeout: float = 5) -> dict | None:
    """Direct HTTP POST (not JSON-RPC) to a daemon REST endpoint."""
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


# ---------------------------------------------------------------------------
# agent2agent: surface inbox metadata for sessions bound via `open <name>`
# ---------------------------------------------------------------------------

_A2A_DEFAULT_BUS_DIR = Path.home() / ".local" / "share" / "agent2agent"
_A2A_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_A2A_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_A2A_NOTIFY_TIMEOUT_S = 3.0


def _a2a_bus_dir() -> Path:
    env = os.environ.get("AGENT2AGENT_DIR")
    return Path(env) if env else _A2A_DEFAULT_BUS_DIR


def _a2a_helper_path() -> Path:
    """Resolve the agent2agent helper script."""
    env = os.environ.get("SPELLBOOK_DIR")
    if env:
        return Path(env) / "skills" / "agent2agent" / "scripts" / "agent2agent.py"
    return Path(__file__).resolve().parent.parent / "skills" / "agent2agent" / "scripts" / "agent2agent.py"


def _agent2agent_notify_for_prompt(data: dict) -> str | None:
    """UserPromptSubmit handler: surface inbox metadata for the bound name."""
    session_id = data.get("session_id", "") or ""
    if not session_id or not _A2A_SESSION_ID_RE.match(session_id):
        return None

    bus = _a2a_bus_dir()
    binding_path = bus / ".bindings" / session_id
    try:
        bound_name = binding_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError):
        return None
    if not bound_name or not _A2A_NAME_RE.match(bound_name):
        return None

    helper = _a2a_helper_path()
    if not helper.exists():
        return None

    helper_env = os.environ.copy()
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
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError) as e:
        logger.debug("agent2agent notify failed: %s", e)
        return None

    out = (proc.stdout or "").strip()
    return out if out else None


def _bg_agent_alive(agent_id, state) -> bool:
    """FAIL-SAFE-DEAD liveness probe of the bg watch-chain watcher."""
    if not agent_id:
        return False
    output_path = state.get("output_file") if isinstance(state, dict) else None
    if not output_path or not isinstance(output_path, str):
        return False
    op = Path(output_path)
    if not op.exists():
        return False
    try:
        age = time.time() - op.stat().st_mtime
    except OSError:
        return False
    return age < 90.0


def _a2a_count_pending(name_dir: Path) -> int:
    """Stat/enumerate-only count of pending messages for an orphan hint."""
    total = 0
    inbox = name_dir / "inbox"
    try:
        for entry in inbox.iterdir():
            if (
                entry.is_file()
                and entry.name.endswith(".json")
                and not entry.name.startswith(".")
            ):
                total += 1
    except OSError:
        pass
    pending_root = name_dir / "pending"
    try:
        batches = [d for d in pending_root.iterdir() if d.is_dir()]
    except OSError:
        batches = []
    for batch in batches:
        try:
            for f in batch.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    total += 1
        except OSError:
            continue
    return total


def _agent2agent_check_orphaned_chain(data: dict) -> str | None:
    """SessionStart / UserPromptSubmit backstop: detect a dropped watch chain."""
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

    name_dir = bus / name
    age_s = None
    output_path = state.get("output_file")
    if output_path:
        try:
            age_s = max(0, int(time.time() - Path(output_path).stat().st_mtime))
        except (OSError, TypeError, ValueError):
            age_s = None
    count = _a2a_count_pending(name_dir)
    age_clause = f"heartbeat ~{age_s}s stale" if age_s is not None else "heartbeat stale"
    count_clause = f"; {count} message(s) waiting" if count > 0 else ""
    return (
        f"[agent2agent] watch chain looks dropped for '{name}' ({age_clause}"
        f"{count_clause}). Likely session compaction, process death, or a laptop "
        f"wake. Run `/a2a open {name}` to re-arm; if the watcher is in fact still "
        f"alive you'll see \"watcher actually alive, no action needed\" and "
        f"nothing else changes."
    )


# ---------------------------------------------------------------------------
# Event Handlers
# ---------------------------------------------------------------------------

def _handle_pre_tool_use(tool_name: str, data: dict) -> list[str]:
    """PreToolUse handler. Returns list of output strings."""
    return []


def _handle_post_tool_use(tool_name: str, data: dict) -> list[str]:
    """PostToolUse handler. Returns list of output strings."""
    return []


def _handle_user_prompt_submit(data: dict) -> list[str]:
    """UserPromptSubmit handler: surface agent2agent inbox/watch-chain hints."""
    outputs: list[str] = []

    try:
        out = _agent2agent_notify_for_prompt(data)
        if out:
            outputs.append(out)
    except Exception as e:
        _log_hook_error("agent2agent_notify_for_prompt", "UserPromptSubmit", e)

    try:
        orphan_hint = _agent2agent_check_orphaned_chain(data)
        if orphan_hint:
            outputs.append(orphan_hint)
    except Exception as e:
        _log_hook_error("agent2agent_check_orphaned_chain", "UserPromptSubmit", e)

    return outputs


# ---------------------------------------------------------------------------
# Main Dispatch
# ---------------------------------------------------------------------------

# Fallback directive emitted on SessionStart after compaction when the
# daemon is unreachable (or has no workflow state). The text is part of
# the public contract with the test suite and any downstream consumer;
# changing it changes the directive the LLM sees on first turn after a
# compaction, so coordinate with the test fixture before editing.
POST_COMPACT_FALLBACK_DIRECTIVE = (
    "Session resumed after compaction. Workflow state could not "
    "be loaded. Re-read any planning documents, check your todo "
    "list, and verify your current working context."
)

# Appended to the post-compaction directive when a develop_gate_ledger exists
# for the session's project. A compacted context has dropped the ceremony
# lock, the dispatch table, and the gate semantics; a develop run that
# continues without them elides gates while still reporting success. Naming
# the file to re-read is the whole mechanism -- a directive that only says
# "you were compacted" leaves the LLM to reconstruct the discipline from
# memory, which is the failure this exists to prevent.
POST_COMPACT_DEVELOP_DIRECTIVE = (
    "A develop_gate_ledger exists for this project, so a develop run may be "
    "in progress. Before your next dispatch, re-read "
    "$SPELLBOOK_DIR/skills/develop/SKILL.md (phase non-fungibility, the "
    "Phase-0 ceremony lock, wave discipline, stop semantics, and the "
    "incidentals protocol) and re-read the ledger itself to recover the "
    "locked ceremony and the current phase."
)


def _develop_ledger_path(cwd: str) -> Path | None:
    """Where this project's develop ledger would live, or None if unknowable.

    Mirrors ``scripts/develop_gate_ledger.py``: ``$SPELLBOOK_DEV_DIR`` names an
    exact directory; otherwise the per-project file under the state dir. That
    module REFUSES when no home directory resolves. A refusal is right for a
    CLI writing state and wrong here -- a hook that raises on a Windows runner
    with no ``USERPROFILE`` would take out the compaction notice as well, so
    an unknowable path degrades to "no develop hint".
    """
    override = os.environ.get("SPELLBOOK_DEV_DIR")
    if override:
        return Path(override) / "develop_gate_ledger.json"
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    try:
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import develop_gate_ledger

        state_dir = develop_gate_ledger.default_state_dir()
        encoded = develop_gate_ledger.encode_cwd(cwd)
    except Exception:
        return None
    return state_dir / f"develop_gate_ledger-{encoded}.json"


def _develop_post_compact_hint(cwd: str) -> str | None:
    """The develop re-load directive, when a ledger exists for ``cwd``."""
    if not cwd:
        return None
    path = _develop_ledger_path(cwd)
    if path is None:
        return None
    try:
        exists = path.is_file()
    except OSError:
        return None
    return POST_COMPACT_DEVELOP_DIRECTIVE if exists else None



def _handle_session_start(data: dict) -> dict | None:
    """SessionStart handler.

    Returns a ``{"hookSpecificOutput": ...}`` dict when there is
    something to emit, or None when SessionStart is a non-event for
    this session. Two independent contributions may be combined:

    - **Post-compact recovery directive** when ``source == "compact"``.
      This is what the LLM sees on the first turn after a compaction,
      so it MUST be emitted unconditionally -- otherwise the LLM
      silently starts with no indication that its context was just
      truncated.

      This used to first attempt a richer directive built from a
      ``workflow_state_load`` MCP call, falling back to the constant
      only on failure. That tool has no implementation: it is not among
      the server's registered tools, and ``load_workflow_state`` /
      ``resume_boot_prompt`` do not exist anywhere in ``spellbook/`` --
      the state subsystem was removed. So the call could only ever
      raise, and the fallback was in truth the only path. The dead
      branch is gone; emitting a directive that instructs the LLM to
      call a nonexistent tool is the same defect this change set
      removed from the fact-checking skill.
    - **Orphan-chain hint** when an a2a watch chain looks dropped.
      Applies on every SessionStart, regardless of source, because a
      dropped chain is independent of why the session opened.

    These are appended in that order (recovery first, orphan second)
    separated by a blank line, matching the original shell-hook's
    output ordering.
    """
    fragments: list[str] = []

    source = (data.get("source") or "").strip()

    if source == "compact":
        # Emitted regardless of cwd. The directive carries no per-project
        # content, and a compaction with a missing or blank cwd is exactly
        # when the LLM most needs telling that its context was truncated --
        # gating on cwd would drop the notice precisely then.
        fragments.append(POST_COMPACT_FALLBACK_DIRECTIVE)

        # Project-specific second fragment: only when this project has a
        # develop ledger. Unlike the notice itself, this one IS gated on cwd
        # -- without a project there is no ledger to point at.
        try:
            develop_hint = _develop_post_compact_hint(
                (data.get("cwd") or "").strip()
            )
            if develop_hint:
                fragments.append(develop_hint)
        except Exception as exc:
            _log_hook_error("develop_post_compact_hint", "SessionStart", exc)

    # Orphan-chain hint is independent of compaction. It fires on every
    # SessionStart that detects a dropped a2a watch chain, because the
    # reason the session opened (resume, startup, compact) does not
    # change whether the chain is dropped.
    try:
        orphan_hint = _agent2agent_check_orphaned_chain(data)
        if orphan_hint:
            fragments.append(orphan_hint)
    except Exception as exc:
        _log_hook_error("agent2agent_check_orphaned_chain", "SessionStart", exc)

    if not fragments:
        return None

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n".join(fragments),
        }
    }


def dispatch(event_name: str, tool_name: str, data: dict) -> str | None:
    """Route hook event to appropriate handler(s).

    Returns stdout content (for injection into LLM context) or None.
    """
    if event_name == "PreToolUse":
        outputs = _handle_pre_tool_use(tool_name, data)
    elif event_name == "PostToolUse":
        outputs = _handle_post_tool_use(tool_name, data)
    elif event_name == "UserPromptSubmit":
        outputs = _handle_user_prompt_submit(data)
    elif event_name == "SessionStart":
        # SessionStart returns a dict or None directly (not a list).
        # Serialize to JSON here so the subprocess can print it.
        session_payload = _handle_session_start(data)
        if session_payload is None:
            return None
        return json.dumps(session_payload)
    else:
        outputs = []

    if isinstance(outputs, list):
        combined = "\n".join(o for o in outputs if o)
        return combined if combined else None
    return outputs


def _record_hook_event_fire_and_forget(
    event_name: str,
    tool_name: str,
    duration_ms: int,
    exit_code: int,
    error: str | None,
) -> None:
    """POST a hook event record to the daemon. <0.5s timeout; swallow errors."""
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
        pass


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
