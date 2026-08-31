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
def _mcp_env(canonical: str, legacy: str, default: str) -> str:
    """Read the canonical SPELLBOOK_* name, falling back to the SPELLBOOK_MCP_* one.

    Mirrors spellbook.core.config._ENV_ALIASES, which this module cannot use:
    hooks run as standalone scripts with no spellbook package on sys.path. Read
    in the same order, or an operator who sets only the canonical name gets a
    daemon bound to one port and hooks posting to another -- a mismatch whose
    only symptom is a hook that silently reaches nothing.
    """
    return os.environ.get(canonical) or os.environ.get(legacy) or default


MCP_HOST = _mcp_env("SPELLBOOK_HOST", "SPELLBOOK_MCP_HOST", "127.0.0.1")
MCP_PORT = _mcp_env("SPELLBOOK_PORT", "SPELLBOOK_MCP_PORT", "8765")
_host_part = f"[{MCP_HOST}]" if ":" in MCP_HOST else MCP_HOST  # IPv6 bracket
MCP_URL = f"http://{_host_part}:{MCP_PORT}/mcp"
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
    """PostToolUse handler. Returns list of output strings.

    Emits nothing into the LLM's context. The one thing it does -- recording
    ``Task`` dispatches into the develop gate ledger -- is deliberately
    invisible to the agent: its value comes from being written by the HARNESS,
    not by the party whose work it attests to.
    """
    if tool_name == "Task":
        try:
            _record_develop_dispatch(data)
        except Exception as exc:
            # A raising PostToolUse handler takes out the whole tool call. An
            # unrecorded dispatch is a gap in an audit trail; a dead Task call
            # is a broken session. Degrade, and leave a trace of why.
            _log_hook_error("record_develop_dispatch", "PostToolUse", exc)
    return []


def _handle_user_prompt_submit(data: dict) -> list[str]:
    """UserPromptSubmit handler: agent2agent hints, and the autonomous escape.

    The escape runs FIRST. The clear must land on the prompt that CONTAINS
    the phrase, so the ``Stop`` at the end of that same turn already reads no
    record; a clear deferred to the next prompt leaves one more turn trapped.
    """
    outputs: list[str] = []

    try:
        escaped = _autonomous_escape(data)
        if escaped:
            outputs.append(escaped)
    except Exception as e:
        # An escape that fails must not take out the prompt, and must not
        # skip the a2a hints below -- this is the same fail-open contract
        # the Stop handler runs under.
        _log_hook_error("autonomous_escape", "UserPromptSubmit", e)

    # Entry runs AFTER the escape and skips when a record already exists, so a
    # prompt carrying both phrases exits rather than re-enters: the escape
    # clears the record, and the entry's own existence check then sees none
    # only if the operator also asked to enter, which they did not.
    try:
        entered = _autonomous_entry(data)
        if entered:
            outputs.append(entered)
    except Exception as e:
        _log_hook_error("autonomous_entry", "UserPromptSubmit", e)

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
    "$SPELLBOOK_DIR/commands/develop-configure.md (phase non-fungibility, the "
    "Phase-0 ceremony lock, wave discipline, stop semantics, and the "
    "incidentals protocol) and re-read the ledger itself to recover the "
    "locked ceremony and the current phase."
)


def _import_develop_ledger():
    """Import ``scripts/develop_gate_ledger``, or None if it cannot be reached.

    The hook is installed as an absolute path into the spellbook checkout and
    runs under the daemon venv, where the ``scripts`` directory is not on
    ``sys.path``. Returning None rather than raising keeps every caller's
    failure mode the same: the feature goes quiet, the hook does not.
    """
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    try:
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import develop_gate_ledger

        return develop_gate_ledger
    except Exception:
        return None


def _record_develop_dispatch(data: dict) -> None:
    """Record a ``Task`` dispatch into the project's develop gate ledger.

    Gated on a ledger ALREADY EXISTING for the session's project, the same
    condition the post-compaction develop hint uses. Recording every Task call
    in every session would fill unrelated projects' state with noise, and a
    record that is always present says nothing about a develop run.

    What gets stored is the ``subagent_type``, a truncated ``description``, and
    the names of develop-dispatched skills RECOGNIZED in the prompt. The prompt
    body itself is never stored: it routinely carries file contents and
    operator text, and the ledger is an audit trail, not a transcript.

    Silence is the failure mode throughout -- an unresolvable ledger path, a
    missing module, an unreadable file. The caller adds one more layer for
    anything unforeseen.
    """
    cwd = (data.get("cwd") or "").strip()
    if not cwd:
        return
    ledger_file = _develop_ledger_path(cwd)
    if ledger_file is None:
        return
    try:
        if not ledger_file.is_file():
            return
    except OSError:
        return

    module = _import_develop_ledger()
    if module is None:
        return

    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    prompt = tool_input.get("prompt")
    module.record_dispatch(
        subagent_type=tool_input.get("subagent_type"),
        description=tool_input.get("description"),
        skills=module.extract_skills(prompt if isinstance(prompt, str) else None),
        source="hook:PostToolUse",
        path=ledger_file,
    )


def _develop_ledger_path(cwd: str) -> Path | None:
    """Where this project's develop ledger would live, or None if unknowable.

    Mirrors ``scripts/develop_gate_ledger.py``: ``$SPELLBOOK_DEV_DIR`` names an
    exact directory; otherwise the per-project file under the state dir. That
    module REFUSES when no home directory resolves. A refusal is right for a
    CLI writing state and wrong here -- a hook that raises on a Windows runner
    with no ``USERPROFILE`` would take out the compaction notice as well, so
    an unknowable path degrades to "no develop hint".

    ``encode_cwd`` is not a string operation: it resolves the git repo root,
    and for layouts it cannot read off the filesystem it still spawns ``git
    worktree list --porcelain`` (and ``git rev-parse --show-toplevel`` on
    fallback). This function runs on every ``Task`` PostToolUse, so an empty
    state directory settles the question before any of that: a ledger for THIS
    project cannot exist when no ledger exists for ANY project, and one
    directory listing is the cheapest way to learn it. Both callers treat
    ``None`` and "file absent" identically, so the short circuit is not
    observable to them.

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
        if not any(state_dir.glob("develop_gate_ledger-*.json")):
            return None
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


# ---------------------------------------------------------------------------
# Autonomous mode: the Stop hook
# ---------------------------------------------------------------------------

# The literal escape phrases, defined ONCE here. The block message below
# restates them every time -- a trap whose exit is not printed at the moment
# it closes is undiscoverable. The UserPromptSubmit recognizer below reads
# this same tuple rather than duplicating the literals; two copies of an
# escape hatch drift, and the copy that drifts is the one nobody tests.
AUTONOMOUS_ESCAPE_PHRASES = ("stop autonomous", "exit autonomous mode")

# The ENTRY is a mirror of the escape, and it exists because the entry gate it
# replaces was a step the agent had to REMEMBER. An unwired autonomous mode
# looks exactly like a wired one from the transcript: the agent behaves
# autonomously either way, and only the record decides whether `Stop` refuses
# a turn-end. Observed: an operator asked for autonomous mode twice in one
# session, the agent never wrote the record, and the hook allowed every
# turn-end it exists to refuse.
#
# So the recognizer runs before the agent sees the prompt, and writes the
# record itself. The phrases are ordered longest-first only for readability;
# the match is a plain case-insensitive substring, decidable by reading the
# string, with no inference about intent and no synonyms -- the same
# discipline the escape carries, for the same reason.
AUTONOMOUS_ENTRY_PHRASES = (
    "work autonomously",
    "working autonomously",
    "continue autonomously",
    "proceed autonomously",
    "run autonomously",
    "keep working autonomously",
    "autonomous mode on",
    "enter autonomous mode",
    "go autonomous",
    "be autonomous",
    "stay autonomous",
    "autonomously",
)


def _prompt_requests_autonomous_entry(prompt: object) -> bool:
    """Whether ``prompt`` contains a literal entry phrase."""
    if not isinstance(prompt, str):
        return False
    lowered = prompt.lower()
    return any(phrase in lowered for phrase in AUTONOMOUS_ENTRY_PHRASES)


def _prompt_requests_autonomous_escape(prompt: object) -> bool:
    """Whether ``prompt`` contains a literal escape phrase.

    Case-insensitive substring match over ``AUTONOMOUS_ESCAPE_PHRASES`` --
    the same tuple the block message prints, read rather than copied, so the
    recognizer and the advertised exit cannot drift apart. No inference about
    operator intent, no synonyms, no fuzziness: a last-resort exit is only
    trustworthy if what opens it is decidable by reading the string.
    """
    if not isinstance(prompt, str):
        return False
    lowered = prompt.lower()
    return any(phrase in lowered for phrase in AUTONOMOUS_ESCAPE_PHRASES)


def _autonomous_escape(data: dict) -> str | None:
    """Clear the autonomous record when the prompt asks for the exit.

    Returns a confirmation to inject, or ``None`` when there was nothing to
    clear -- including when no record existed, so a prompt that merely
    mentions the phrase outside autonomous mode says nothing.

    When the record survives the attempt, this returns a FAILURE notice
    rather than the confirmation. This is the operator's only exit from a
    hook that refuses every turn-end; printing the success line over a
    no-op tells them the trap is open while it is still shut, and they have
    no other signal to contradict it. The verdict is the artifact -- the
    record is gone -- not the fact that the call was made.
    """
    if not _prompt_requests_autonomous_escape(data.get("prompt")):
        return None

    session_id = data.get("session_id", "") or ""
    if not isinstance(session_id, str) or not _A2A_SESSION_ID_RE.match(session_id):
        return None

    autonomous = _autonomous_module()
    if autonomous is None:
        return None
    if autonomous.read_autonomous_record(session_id) is None:
        return None

    if not autonomous.clear_autonomous_record(session_id):
        return (
            "Autonomous mode COULD NOT BE CLEARED: the record for this session "
            "could not be removed, so the Stop hook will KEEP refusing to end "
            "a turn. This is a filesystem fault, not a refusal of the escape "
            "phrase. To clear it, delete the record file at "
            f"{_autonomous_record_path_for_message(autonomous, session_id)} "
            "(check its directory's permissions and free space), or end this "
            "session -- the record is per-session and grants nothing to a new "
            "one."
        )
    return (
        "Autonomous mode CLEARED for this session by operator escape phrase. "
        "The Stop hook no longer blocks the end of a turn."
    )


def _autonomous_entry(data: dict) -> str | None:
    """Write the autonomous record when the prompt asks for the mode.

    Returns a confirmation to inject, a FAILURE notice, or ``None`` when the
    prompt does not ask or a record already exists (re-asking is a no-op, not
    a reset -- a second "keep working autonomously" must not zero the block
    counters the valve reads).

    The record is written HERE rather than by the agent, and that inversion is
    the whole point. The skill's gate asked the operator two questions and
    then wrote the record; every step in front of the write was a step the
    agent could skip, and skipping it was invisible, because an agent
    behaving autonomously without a record is indistinguishable from one with
    it until a turn ends and nothing refuses. Defaults are used so that no
    answer is a precondition for the mode existing; the agent may refine them
    afterwards through the helper, against a record that is already live.

    When the write does not land, this returns a FAILURE notice rather than
    the confirmation, for the escape's reason inverted: telling the operator
    the mode is ON while the record is absent hands them a guarantee nothing
    is holding.
    """
    if not _prompt_requests_autonomous_entry(data.get("prompt")):
        return None

    # A prompt carrying BOTH phrases exits. The escape ran first and cleared
    # the record, so the existence check below would see none and re-enter --
    # trapping the operator in the mode they just asked to leave. The exit is
    # a last resort and wins outright.
    if _prompt_requests_autonomous_escape(data.get("prompt")):
        return None

    session_id = data.get("session_id", "") or ""
    if not isinstance(session_id, str) or not _A2A_SESSION_ID_RE.match(session_id):
        return None

    autonomous = _autonomous_module()
    if autonomous is None:
        return None
    if autonomous.read_autonomous_record(session_id) is not None:
        return None

    prompt = data.get("prompt", "")
    goal = prompt.strip() if isinstance(prompt, str) else ""
    if not goal:
        return None

    try:
        written = autonomous.write_autonomous_record(
            session_id,
            mode="fully",
            philosophy="build-right",
            goal=goal,
            set_at=_utc_now_iso(),
        )
    except Exception as e:
        _log_hook_error("autonomous_entry_write", "UserPromptSubmit", e)
        written = False

    # The verdict is the artifact, not the call's return value: read it back.
    if not written or autonomous.read_autonomous_record(session_id) is None:
        return (
            "Autonomous mode COULD NOT BE ENABLED: the record for this session "
            "was not written, so the Stop hook will NOT refuse a turn-end and "
            "the mode is off however this session behaves. This is a "
            "filesystem or validation fault, not a refusal of the phrase. The "
            "record belongs at "
            f"{_autonomous_record_path_for_message(autonomous, session_id)} "
            "(check its directory's permissions and free space). Do not report "
            "the mode as on."
        )

    escape = " / ".join(f'"{p}"' for p in AUTONOMOUS_ESCAPE_PHRASES)
    return (
        "Autonomous mode is ON for this session, enabled mechanically by this "
        "prompt -- mode=fully, philosophy=build-right. The Stop hook will now "
        "REFUSE to end a turn that is not done, was not asked to pause, and "
        "has no genuine blocker; continuing is how you answer it. The recorded "
        f"goal is the operator's own words: {goal!r}. Refine that goal through "
        "the autonomous_mode helper's record if it is too vague to be held to "
        f"-- do not re-ask for the mode. The operator's exit is {escape}."
    )


def _utc_now_iso() -> str:
    """An ISO-8601 UTC timestamp for the record's ``set_at`` field."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _autonomous_record_path_for_message(autonomous, session_id: str) -> str:
    """The record's path for the escape-failure notice, or a fallback phrase.

    Naming the file is the whole value of that notice -- an operator told
    only that the clear failed has nothing to act on. Resolving it must not
    itself raise inside the handler that reports a failure.
    """
    try:
        path = autonomous._record_path(session_id)
    except Exception:
        return "the autonomous record for this session"
    if path is None:
        return "the autonomous record for this session"
    return str(path)


def _autonomous_module():
    """Import ``spellbook.core.autonomous``, or ``None`` if unavailable.

    Hooks run as standalone scripts with no spellbook package on ``sys.path``
    (see ``_mcp_env``), so the repo root is prepended here the same way
    ``_develop_ledger_path`` prepends ``scripts/``. An import that fails for
    any reason -- a partial checkout, a Python that cannot load the package --
    degrades to "not autonomous" rather than raising, because this function's
    only caller gates the end of the operator's turn.
    """
    root = Path(__file__).resolve().parent.parent
    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from spellbook.core import autonomous

        return autonomous
    except Exception:
        return None


def _autonomous_block_reason(record: dict) -> str:
    """The block message: a question handed back to the model, not a verdict.

    The hook cannot tell whether a turn is genuinely finished -- nothing it
    can read from outside the model distinguishes "the project is done" from
    "the model lost momentum". So it does not try. It refuses the stop once
    and asks, and the model answers by acting: it continues if it was not
    done, and it stops again if it was. ``BLOCK_WINDOW_LIMIT`` refusals
    inside ``BLOCK_WINDOW_SECONDS`` is that second answer arriving that many
    times, and the valve then lets the session end.

    The escape phrase and the active philosophy are restated on every refusal
    because this text is the only place the operator's exit is visible from
    inside a session that has been running for hours.
    """
    phrases = " / ".join(f'"{p}"' for p in AUTONOMOUS_ESCAPE_PHRASES)
    goal = record.get("goal") or "(no goal recorded)"
    return (
        "Autonomous mode is ACTIVE for this session "
        f"(mode: {record.get('mode')}, philosophy: {record.get('philosophy')}).\n"
        "This turn-end is refused. Before ending a turn, answer this: are you "
        "DONE with the whole project goal, were you asked to PAUSE by the "
        "operator, or do you have a GENUINE BLOCKER?\n"
        "If you have a genuine blocker, you MUST use the AskUserQuestion tool "
        "to ask the operator how to continue -- do not end the turn on it.\n"
        "If none of the three holds, you are not finished. A long session, a "
        "finished list item, a returned subagent result, and a phase boundary "
        "are none of them. Keep working.\n"
        f"Goal: {goal}\n"
        f"To leave autonomous mode, the OPERATOR types one of: {phrases}. "
        "Nothing you do ends it."
    )


def _autonomous_thrash_valve_open(autonomous, record: dict) -> bool:
    """Whether recorded blocks show thrashing, so this stop must be allowed.

    Every failure resolves to ``True`` -- ALLOW. This predicate is the ONLY
    thing bounding the block loop now that the harness cap is disabled, so a
    fault in it must release the session, not hold it. A valve that jams shut
    when its own bookkeeping breaks is worse than no valve.
    """
    try:
        return bool(autonomous.thrash_valve_open(record, now=time.time()))
    except Exception:
        return True


def _handle_stop(data: dict) -> dict | None:
    """Stop handler. Returns a decision dict, or None to allow silently.

    Decision table, evaluated in order, and complete:

    1. No autonomous record for this session -> ALLOW.
    2. The rolling-window valve is open -> ALLOW.
    3. The blocked stop cannot be recorded -> ALLOW.
    4. Otherwise -> block.

    The hook decides NOTHING about the work. It reads one small record to
    learn whether the session is autonomous, and if it is, it kicks the
    session and hands the question back to the model. Everything the handler
    once inspected to answer that question itself -- the session transcript,
    the develop gate ledger, a declared evidence artifact -- is gone, and with
    it the reasons this hook used to be slow and the reasons it used to be
    wrong. What replaced them is row 2: ``BLOCK_WINDOW_LIMIT`` blocks inside
    ``BLOCK_WINDOW_SECONDS`` means the model has insisted that many times,
    that fast, that it is done, paused, or blocked, and one more refusal
    cannot teach it anything those did not.

    ``stop_hook_active`` is deliberately NOT consulted. The harness sets it on
    the stop FOLLOWING a block, so treating it as an allow makes the hook
    block at most once per session and then permit every subsequent turn-end
    -- inert in the only case the feature exists for. The valve at row 2 is
    what prevents an infinite block loop; it and the disabled
    ``CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`` are one change.

    Every unknown resolves to ALLOW. A hook that raises takes out the
    operator's turn; a hook that blocks on an unknown traps the session with
    no way out. That includes the valve's own bookkeeping: malformed
    ``block_times`` makes the record read as absent, which lands on row 1.

    Row 3 is that rule applied to the act of blocking itself, and it is not
    optional. The valve at row 2 opens on blocks that were RECORDED, so a
    block issued when the record could not be written accumulates nothing
    that could ever open it. With the harness's own block cap disabled,
    nothing else bounds the loop: an unwritable state directory would refuse
    every turn-end for the rest of the session, and the escape phrase would
    be the operator's only way out of a session they never chose to trap. A
    block that cannot be accounted for is therefore not issued.
    """
    session_id = data.get("session_id", "") or ""
    if not isinstance(session_id, str) or not _A2A_SESSION_ID_RE.match(session_id):
        return None

    autonomous = _autonomous_module()
    if autonomous is None:
        return None

    record = autonomous.read_autonomous_record(session_id)
    if record is None:
        return None

    if _autonomous_thrash_valve_open(autonomous, record):
        return None

    if not _autonomous_block_is_accounted(autonomous, session_id):
        return None

    return {"decision": "block", "reason": _autonomous_block_reason(record)}


def _autonomous_block_is_accounted(autonomous, session_id: str) -> bool:
    """Whether this block was recorded, and so may be issued.

    Every failure resolves to ``False`` -- ALLOW -- for the reason row 3 of
    ``_handle_stop`` states: an unrecorded block can never open the valve
    that is the only bound on the block loop.
    """
    try:
        return autonomous.record_blocked_stop(session_id) is not None
    except Exception:
        return False


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
    elif event_name == "Stop":
        # Like SessionStart, this returns a JSON decision rather than a list
        # of strings. Wrapped so that no exception can escape to the caller:
        # an unexpected failure here must ALLOW the stop, not raise.
        try:
            stop_payload = _handle_stop(data)
        except Exception as exc:
            _log_hook_error("handle_stop", "Stop", exc)
            return None
        if stop_payload is None:
            return None
        return json.dumps(stop_payload)
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
