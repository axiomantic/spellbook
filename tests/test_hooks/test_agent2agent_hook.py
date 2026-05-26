"""Tests for the agent2agent UserPromptSubmit notify path in spellbook_hook.

The hook MUST surface inbox metadata only (count + sender names) for the
name bound to the current Claude session id. It MUST NOT read or expose
message bodies — wiring the helper's read/peek/check subcommands here
would create a prompt-injection vector.

This file has two test classes:

* ``TestAgent2AgentHookFast`` — fast unit tests that import the hook
  function directly and stub the helper subprocess. Run by default.
* ``TestAgent2AgentHook`` — integration tests that spawn the real hook
  + real helper as subprocesses. Marked ``integration``.

Integration cases:
    1. Session bound, no pending messages       -> no [agent2agent] line
    2. Session bound, two pending messages      -> count=2 + senders, body absent
    3. Session not bound                        -> silent
    4. Session bound but inbox dir is missing   -> silent + binding cleaned up
    5. Helper script missing                    -> silent, no exception
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import tripwire
from dirty_equals import IsInstance

# Ensure hooks/ is on sys.path so we can import spellbook_hook directly.
HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
UNIFIED_HOOK = os.path.join(PROJECT_ROOT, "hooks", "spellbook_hook.py")
HELPER = os.path.join(
    PROJECT_ROOT, "skills", "agent2agent", "scripts", "agent2agent.py",
)
DEAD_PORT = "19999"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hook_env(bus_dir: Path, *, spellbook_dir: str | None = PROJECT_ROOT) -> dict:
    env = os.environ.copy()
    if spellbook_dir is not None:
        env["SPELLBOOK_DIR"] = spellbook_dir
    elif "SPELLBOOK_DIR" in env:
        del env["SPELLBOOK_DIR"]
    env["PYTHONPATH"] = PROJECT_ROOT
    env["SPELLBOOK_MCP_PORT"] = DEAD_PORT
    env["SPELLBOOK_MCP_HOST"] = "127.0.0.1"
    env["AGENT2AGENT_DIR"] = str(bus_dir)
    return env


def _run_user_prompt_submit(
    bus_dir: Path,
    session_id: str,
    *,
    prompt: str = "hi",
    spellbook_dir: str | None = PROJECT_ROOT,
) -> subprocess.CompletedProcess:
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": session_id,
        "cwd": str(bus_dir),  # arbitrary; we don't exercise memory paths here
        "prompt": prompt,
    }
    return subprocess.run(
        [sys.executable, UNIFIED_HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_hook_env(bus_dir, spellbook_dir=spellbook_dir),
        timeout=15,
    )


def _bind(bus_dir: Path, session_id: str, name: str) -> None:
    """Set up an inbox for ``name`` and bind ``session_id`` to it."""
    env = os.environ.copy()
    env["AGENT2AGENT_DIR"] = str(bus_dir)
    env["CLAUDE_CODE_SESSION_ID"] = session_id
    proc = subprocess.run(
        [sys.executable, HELPER, "open", name],
        capture_output=True, text=True, env=env, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr


def _send(bus_dir: Path, sender: str, recipient: str, body: str) -> None:
    env = os.environ.copy()
    env["AGENT2AGENT_DIR"] = str(bus_dir)
    proc = subprocess.run(
        [sys.executable, HELPER, "send", "--from", sender, "--to", recipient, body],
        capture_output=True, text=True, env=env, timeout=10,
    )
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="agent2agent helper requires fcntl (POSIX-only); subprocess spawn fails on Windows",
)
class TestAgent2AgentHook:
    def test_bound_no_messages_silent(self, tmp_path):
        """Session bound to alice, no pending messages -> no [agent2agent] line."""
        bus = tmp_path / "bus"
        sid = "session-alpha"
        _bind(bus, sid, "alice")
        proc = _run_user_prompt_submit(bus, sid)
        assert proc.returncode == 0
        assert "[agent2agent]" not in proc.stdout

    def test_bound_with_messages_surfaces_metadata_not_bodies(self, tmp_path):
        """Two pending messages -> count=2 + senders; bodies must NOT appear."""
        bus = tmp_path / "bus"
        sid = "session-beta"
        _bind(bus, sid, "alice")
        # Bob needs an inbox to be a "registered" sender, but we send TO alice.
        # Sending does not require sender registration; only recipient.
        _send(bus, "bob", "alice", "secret-body-one")
        _send(bus, "bob", "alice", "secret-body-two")

        proc = _run_user_prompt_submit(bus, sid)
        assert proc.returncode == 0
        assert "[agent2agent]" in proc.stdout
        assert "alice has 2 pending" in proc.stdout
        assert "from: bob" in proc.stdout
        # CRITICAL: no body content may appear in hook output.
        assert "secret-body-one" not in proc.stdout
        assert "secret-body-two" not in proc.stdout

    def test_unbound_session_silent(self, tmp_path):
        """No binding for this session id -> hook stdout has no [agent2agent]."""
        bus = tmp_path / "bus"
        # Don't bind. Bus dir need not even exist.
        proc = _run_user_prompt_submit(bus, "session-unbound")
        assert proc.returncode == 0
        assert "[agent2agent]" not in proc.stdout

    def test_stale_binding_cleaned_up(self, tmp_path):
        """Binding points to a name with no inbox dir -> silent + binding removed."""
        bus = tmp_path / "bus"
        sid = "session-stale"
        _bind(bus, sid, "ghost")
        # Simulate another session having close'd 'ghost' meanwhile.
        shutil.rmtree(bus / "ghost")
        binding_path = bus / ".bindings" / sid
        assert binding_path.exists(), "precondition: binding file must still exist"

        proc = _run_user_prompt_submit(bus, sid)
        assert proc.returncode == 0
        assert "[agent2agent]" not in proc.stdout
        # Binding must have been silently removed.
        assert not binding_path.exists()

    def test_helper_missing_silent(self, tmp_path):
        """If the helper script can't be found, hook stays silent and exits 0."""
        bus = tmp_path / "bus"
        sid = "session-helper-missing"
        _bind(bus, sid, "alice")
        # Point SPELLBOOK_DIR at an empty dir so the helper path doesn't exist.
        empty = tmp_path / "empty-spellbook"
        empty.mkdir()

        # Also need to make sure the fallback (Path(__file__).parent.parent)
        # doesn't accidentally find the real helper. The fallback IS the real
        # repo, so we have to override SPELLBOOK_DIR to a path that does NOT
        # contain the helper. The hook uses SPELLBOOK_DIR when set, so this
        # reliably forces a "missing helper" branch.
        proc = _run_user_prompt_submit(bus, sid, spellbook_dir=str(empty))
        assert proc.returncode == 0
        assert "[agent2agent]" not in proc.stdout


# ---------------------------------------------------------------------------
# Fast unit tests for _agent2agent_notify_for_prompt
# ---------------------------------------------------------------------------
#
# These tests import the hook function directly and stub the helper
# subprocess via unittest.mock. They run in the default test suite
# (no integration marker) so the hook's UserPromptSubmit path has
# fast-feedback coverage.


def _stub_helper_tree(tmp_path: Path) -> Path:
    """Create a fake helper script under tmp_path so the hook reaches subprocess."""
    helper = tmp_path / "skills" / "agent2agent" / "scripts" / "agent2agent.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("# stub\n", encoding="utf-8")
    return helper


def _expected_helper_argv(helper: Path, bound_name: str) -> list[str]:
    """Mirror of the argv the hook constructs for the helper subprocess."""
    return [sys.executable, str(helper), "notify", bound_name]


class TestAgent2AgentHookFast:
    def test_invalid_session_id_returns_none(self, tmp_path, monkeypatch):
        """Empty / malformed session_id short-circuits before any IO."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        for sid in ("", "with space", "x" * 200):
            assert spellbook_hook._agent2agent_notify_for_prompt({"session_id": sid}) is None

    def test_no_binding_returns_none(self, tmp_path, monkeypatch):
        """Valid session id but no binding file -> silent."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        result = spellbook_hook._agent2agent_notify_for_prompt(
            {"session_id": "session-no-binding"}
        )
        assert result is None

    def test_invalid_bound_name_returns_none(self, tmp_path, monkeypatch):
        """Binding file present but content fails name regex -> silent."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        bindings = tmp_path / ".bindings"
        bindings.mkdir()
        (bindings / "session-bad-bound").write_text("../escape", encoding="utf-8")
        result = spellbook_hook._agent2agent_notify_for_prompt(
            {"session_id": "session-bad-bound"}
        )
        assert result is None

    def test_helper_missing_returns_none(self, tmp_path, monkeypatch):
        """SPELLBOOK_DIR points at an empty tree -> helper not found, silent."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        empty_repo = tmp_path / "empty-spellbook"
        empty_repo.mkdir()
        monkeypatch.setenv("SPELLBOOK_DIR", str(empty_repo))
        bindings = tmp_path / ".bindings"
        bindings.mkdir()
        (bindings / "session-helper-missing").write_text("alice", encoding="utf-8")

        result = spellbook_hook._agent2agent_notify_for_prompt(
            {"session_id": "session-helper-missing"}
        )
        assert result is None

    def test_subprocess_timeout_returns_none(self, tmp_path, monkeypatch):
        """Helper hang -> timeout caught, hook returns None silently."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        helper = _stub_helper_tree(tmp_path)
        monkeypatch.setenv("SPELLBOOK_DIR", str(tmp_path))
        bindings = tmp_path / ".bindings"
        bindings.mkdir()
        (bindings / "session-timeout").write_text("alice", encoding="utf-8")

        argv = _expected_helper_argv(helper, "alice")
        tripwire.subprocess.mock_run(
            command=argv,
            raises=subprocess.TimeoutExpired(cmd=argv, timeout=3.0),
        )

        with tripwire:
            result = spellbook_hook._agent2agent_notify_for_prompt(
                {"session_id": "session-timeout"}
            )
        assert result is None
        tripwire.subprocess.assert_run(
            command=argv, returncode=0, stdout="", stderr="",
        )

    def test_helper_stdout_is_returned_verbatim(self, tmp_path, monkeypatch):
        """Helper succeeds with stdout -> stripped stdout is returned."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        helper = _stub_helper_tree(tmp_path)
        monkeypatch.setenv("SPELLBOOK_DIR", str(tmp_path))
        bindings = tmp_path / ".bindings"
        bindings.mkdir()
        (bindings / "session-ok").write_text("alice", encoding="utf-8")

        argv = _expected_helper_argv(helper, "alice")
        fake_stdout = "[agent2agent] alice has 1 pending\n"
        tripwire.subprocess.mock_run(
            command=argv,
            returncode=0,
            stdout=fake_stdout,
        )

        with tripwire:
            result = spellbook_hook._agent2agent_notify_for_prompt(
                {"session_id": "session-ok"}
            )

        assert result == "[agent2agent] alice has 1 pending"
        # Drift guard: argv MUST invoke `notify` (never read/peek/check).
        assert argv[2] == "notify"
        assert argv[3] == "alice"
        tripwire.subprocess.assert_run(
            command=argv, returncode=0, stdout=fake_stdout, stderr="",
        )

    def test_helper_empty_stdout_returns_none(self, tmp_path, monkeypatch):
        """Helper exits 0 but prints nothing -> hook returns None (silent)."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        helper = _stub_helper_tree(tmp_path)
        monkeypatch.setenv("SPELLBOOK_DIR", str(tmp_path))
        bindings = tmp_path / ".bindings"
        bindings.mkdir()
        (bindings / "session-silent").write_text("alice", encoding="utf-8")

        argv = _expected_helper_argv(helper, "alice")
        tripwire.subprocess.mock_run(
            command=argv,
            returncode=0,
            stdout="   \n",
        )

        with tripwire:
            result = spellbook_hook._agent2agent_notify_for_prompt(
                {"session_id": "session-silent"}
            )
        assert result is None
        tripwire.subprocess.assert_run(
            command=argv, returncode=0, stdout="   \n", stderr="",
        )


# ---------------------------------------------------------------------------
# Drift guard: hook constants must mirror helper constants
# ---------------------------------------------------------------------------


def _load_helper_module():
    """Import the helper script as a module without executing main()."""
    import importlib.util
    helper_path = (
        Path(__file__).resolve().parent.parent.parent
        / "skills" / "agent2agent" / "scripts" / "agent2agent.py"
    )
    spec = importlib.util.spec_from_file_location("_a2a_helper", helper_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="loads the agent2agent helper module which requires fcntl (POSIX-only)",
)
def test_hook_helper_constants_in_sync():
    """The hook's name regex / session-id regex / default bus dir must
    exactly mirror the helper's. If one side drifts, the hook silently
    rejects names the helper accepts (or vice versa).
    """
    helper = _load_helper_module()
    assert spellbook_hook._A2A_NAME_RE.pattern == helper._NAME_RE.pattern
    assert spellbook_hook._A2A_SESSION_ID_RE.pattern == helper._SESSION_ID_RE.pattern
    assert spellbook_hook._A2A_DEFAULT_BUS_DIR == helper.DEFAULT_BUS_DIR


# ---------------------------------------------------------------------------
# T5: Orphaned watch-chain detection
# ---------------------------------------------------------------------------
#
# These tests exercise the hook-side backstop that surfaces a re-arm hint
# when the bg watch agent for an `open <name>` session has died. The
# liveness probe is FAIL-SAFE-DEAD and shares the mtime+600s-window probe
# with the helper's `cmd__open_state alive` (see T4); the two sides
# differ only in return contract (bool here, exit codes 0/1/2 there).


def _seed_open_state(
    bus_dir: Path,
    session_id: str,
    *,
    name: str = "alice",
    agent_id: str = "agent-fake-001",
    output_file: Path | None = None,
) -> Path:
    """Plant a `<bus>/.open/<sid>` state file. Returns the state path."""
    open_dir = bus_dir / ".open"
    open_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": name,
        "agent_id": agent_id,
        "started_at": "2026-05-07T00:00:00+00:00",
    }
    if output_file is not None:
        payload["output_file"] = str(output_file)
    state_path = open_dir / session_id
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    return state_path


REARM_HINT_PREFIX = "[agent2agent] watch chain dropped"


class TestBgAgentAlive:
    """Direct unit tests of `_bg_agent_alive(agent_id, state)`.

    Semantics MUST match `cmd__open_state alive` (FAIL-SAFE-DEAD):
      - missing/empty agent_id        -> False
      - state missing output_file     -> False
      - output_file path not on disk  -> False
      - mtime stale (>= 600s)         -> False
      - mtime fresh (< 600s)          -> True
    """

    def test_returns_true_when_transcript_recent(self, tmp_path):
        transcript = tmp_path / "agent-transcript.output"
        transcript.write_text("", encoding="utf-8")
        now = time.time()
        os.utime(transcript, (now, now))
        state = {"agent_id": "agent-x", "output_file": str(transcript)}
        assert spellbook_hook._bg_agent_alive("agent-x", state) is True

    def test_returns_false_when_transcript_stale(self, tmp_path):
        transcript = tmp_path / "agent-transcript.output"
        transcript.write_text("", encoding="utf-8")
        # Push mtime past the 600s liveness threshold (use 700s to leave
        # plenty of margin against clock skew on slow CI runners).
        old = time.time() - 700.0
        os.utime(transcript, (old, old))
        state = {"agent_id": "agent-x", "output_file": str(transcript)}
        assert spellbook_hook._bg_agent_alive("agent-x", state) is False

    def test_returns_false_when_transcript_missing(self, tmp_path):
        # output_file path that does not exist on disk.
        # FAIL-SAFE-DEAD: there is no fail-safe-alive branch.
        missing = tmp_path / "never-created.output"
        state = {"agent_id": "agent-x", "output_file": str(missing)}
        assert spellbook_hook._bg_agent_alive("agent-x", state) is False

    def test_returns_false_when_agent_id_empty(self, tmp_path):
        transcript = tmp_path / "agent-transcript.output"
        transcript.write_text("", encoding="utf-8")
        state = {"agent_id": "", "output_file": str(transcript)}
        assert spellbook_hook._bg_agent_alive("", state) is False

    def test_returns_false_when_state_missing_output_file(self, tmp_path):
        state = {"agent_id": "agent-x"}  # no output_file key
        assert spellbook_hook._bg_agent_alive("agent-x", state) is False

    def test_docstring_does_not_overclaim_byte_for_byte_parity(self):
        """T8 docstring reconciliation: hook returns bool, helper returns exit codes.

        Pre-T8 the docstring claimed `_bg_agent_alive` mirrored
        ``cmd_open_state`` op=alive **byte-for-byte**, but the two
        differ in their return contract (the hook returns ``bool``;
        the helper returns exit codes 0/1/2). The docstring must
        honestly describe what is shared (the mtime+600s-window probe)
        and what differs (return type, fail-safe orientation),
        without the misleading "byte-for-byte" claim.
        """
        doc = spellbook_hook._bg_agent_alive.__doc__ or ""
        assert "byte-for-byte" not in doc, (
            "T8 reconciliation: `_bg_agent_alive` and `cmd_open_state alive` "
            "share the mtime+600s-window probe but differ in return contract "
            "(bool vs exit code). The docstring must not claim "
            "byte-for-byte parity. Drop the phrase or qualify it."
        )
        # The docstring still has to call out the FAIL-SAFE-DEAD orientation
        # so a future reader knows neither side fails-safe-alive.
        assert "FAIL-SAFE-DEAD" in doc or "fail-safe-DEAD" in doc, (
            "Docstring must continue to call out FAIL-SAFE-DEAD orientation "
            "(no fail-safe-alive branch)."
        )


class TestOrphanedChainCheck:
    """Direct unit tests of `_agent2agent_check_orphaned_chain`."""

    def test_no_state_file_silent(self, tmp_path, monkeypatch):
        """No `.open/<sid>` exists -> returns None."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        result = spellbook_hook._agent2agent_check_orphaned_chain(
            {"session_id": "sess-no-state"}
        )
        assert result is None

    def test_alive_silent(self, tmp_path, monkeypatch):
        """State present + agent alive -> returns None."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        transcript = tmp_path / "live.output"
        transcript.write_text("", encoding="utf-8")
        _seed_open_state(
            tmp_path, "sess-alive", name="alice",
            agent_id="agent-x", output_file=transcript,
        )
        # Sanity: liveness probe must say alive for fresh transcript.
        result = spellbook_hook._agent2agent_check_orphaned_chain(
            {"session_id": "sess-alive"}
        )
        assert result is None

    def test_dead_emits_rearm_hint(self, tmp_path, monkeypatch):
        """State present + agent dead -> returns the static-template hint."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        # output_file path that does NOT exist -> FAIL-SAFE-DEAD -> orphan.
        missing_transcript = tmp_path / "missing.output"
        _seed_open_state(
            tmp_path, "sess-dead", name="alice",
            agent_id="agent-x", output_file=missing_transcript,
        )
        result = spellbook_hook._agent2agent_check_orphaned_chain(
            {"session_id": "sess-dead"}
        )
        expected = (
            "[agent2agent] watch chain dropped (likely session compaction or "
            "process death). Run `/a2a open alice` to re-arm the inbox watcher."
        )
        assert result == expected

    def test_invalid_session_id_silent(self, tmp_path, monkeypatch):
        """Empty / bad session_id short-circuits before any IO."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        for sid in ("", "with space", "x" * 200):
            result = spellbook_hook._agent2agent_check_orphaned_chain(
                {"session_id": sid}
            )
            assert result is None

    def test_invalid_bound_name_in_state_silent(self, tmp_path, monkeypatch):
        """State file with malformed `name` -> silent (defense-in-depth)."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        open_dir = tmp_path / ".open"
        open_dir.mkdir()
        (open_dir / "sess-badname").write_text(
            json.dumps({
                "name": "../escape",
                "agent_id": "agent-x",
                "started_at": "2026-05-07T00:00:00+00:00",
                "output_file": "/nonexistent",
            }),
            encoding="utf-8",
        )
        result = spellbook_hook._agent2agent_check_orphaned_chain(
            {"session_id": "sess-badname"}
        )
        assert result is None

    def test_malformed_json_silent(self, tmp_path, monkeypatch):
        """State file with invalid JSON -> silent."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        open_dir = tmp_path / ".open"
        open_dir.mkdir()
        (open_dir / "sess-malformed").write_text(
            "{not valid json", encoding="utf-8"
        )
        result = spellbook_hook._agent2agent_check_orphaned_chain(
            {"session_id": "sess-malformed"}
        )
        assert result is None

    def test_never_reads_message_bodies(self, tmp_path, monkeypatch):
        """Plant a body containing distinctive bytes; orphan check must
        never surface them (security boundary: metadata only).
        """
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        # Plant a message body in the inbox tree with a distinctive marker.
        secret = "SECRET_BODY_PAYLOAD_DO_NOT_LEAK"
        inbox = tmp_path / "alice" / "inbox"
        inbox.mkdir(parents=True)
        (inbox / "msg-001.json").write_text(
            json.dumps({"from": "bob", "body": secret}),
            encoding="utf-8",
        )
        # Set up an orphaned open-state record for alice.
        missing_transcript = tmp_path / "dead.output"
        _seed_open_state(
            tmp_path, "sess-leakcheck", name="alice",
            agent_id="agent-x", output_file=missing_transcript,
        )
        result = spellbook_hook._agent2agent_check_orphaned_chain(
            {"session_id": "sess-leakcheck"}
        )
        # The hint must be returned (orphan was detected).
        assert result is not None
        assert result.startswith(REARM_HINT_PREFIX)
        # Critically: the secret body must NOT appear in the hint.
        assert secret not in result


class TestSessionStartOrphanWiring:
    """`_handle_session_start` must run the orphan check BEFORE the
    `source != "compact"` early return so non-compact starts also get
    the re-arm hint when an orphan is detected.
    """

    def test_orphan_on_non_compact_source_returns_hint(self, tmp_path, monkeypatch):
        """source=startup + orphan present -> SessionStart additionalContext
        returns the orphan hint string (not None).
        """
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        missing_transcript = tmp_path / "dead.output"
        _seed_open_state(
            tmp_path, "sess-orphan-startup", name="alice",
            agent_id="agent-x", output_file=missing_transcript,
        )
        result = spellbook_hook._handle_session_start({
            "session_id": "sess-orphan-startup",
            "source": "startup",
        })
        expected_hint = (
            "[agent2agent] watch chain dropped (likely session compaction or "
            "process death). Run `/a2a open alice` to re-arm the inbox watcher."
        )
        assert result == {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": expected_hint,
            }
        }

    def test_no_orphan_on_non_compact_source_returns_none(self, tmp_path, monkeypatch):
        """source=startup + no orphan state -> existing behavior preserved
        (returns None).
        """
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        result = spellbook_hook._handle_session_start({
            "session_id": "sess-no-orphan-startup",
            "source": "startup",
        })
        assert result is None

    def test_compact_path_with_orphan_appends_hint_to_directive(
        self, tmp_path, monkeypatch
    ):
        """source=compact + orphan present + workflow_state unavailable
        (MCP unreachable) -> falls through to fallback directive AND
        appends the orphan hint to additionalContext (separated by blank line).
        """
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        # Force MCP failure so we hit the _fallback_directive branch.
        # _mcp_call returns None when MCP is unreachable.
        m_mcp = tripwire.mock("spellbook_hook:_mcp_call")
        m_mcp.returns(None)

        missing_transcript = tmp_path / "dead.output"
        _seed_open_state(
            tmp_path, "sess-orphan-compact", name="alice",
            agent_id="agent-x", output_file=missing_transcript,
        )
        with tripwire:
            result = spellbook_hook._handle_session_start({
                "session_id": "sess-orphan-compact",
                "source": "compact",
                "cwd": str(tmp_path),
            })
        m_mcp.assert_call(args=("workflow_state_load", IsInstance(dict)), kwargs={})
        expected_hint = (
            "[agent2agent] watch chain dropped (likely session compaction or "
            "process death). Run `/a2a open alice` to re-arm the inbox watcher."
        )
        fallback_text = (
            "Session resumed after compaction. Workflow state could not "
            "be loaded. Re-read any planning documents, check your todo "
            "list, and verify your current working context."
        )
        assert result == {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": fallback_text + "\n\n" + expected_hint,
            }
        }

    def test_compact_path_without_orphan_unchanged(self, tmp_path, monkeypatch):
        """source=compact + no orphan state -> existing fallback directive
        verbatim, no orphan hint appended.
        """
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        m_mcp = tripwire.mock("spellbook_hook:_mcp_call")
        m_mcp.returns(None)

        with tripwire:
            result = spellbook_hook._handle_session_start({
                "session_id": "sess-noorphan-compact",
                "source": "compact",
                "cwd": str(tmp_path),
            })
        m_mcp.assert_call(args=("workflow_state_load", IsInstance(dict)), kwargs={})
        fallback_text = (
            "Session resumed after compaction. Workflow state could not "
            "be loaded. Re-read any planning documents, check your todo "
            "list, and verify your current working context."
        )
        assert result == {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": fallback_text,
            }
        }


class TestUserPromptSubmitOrphanWiring:
    """`_handle_user_prompt_submit` MUST call the orphan check after the
    existing `_agent2agent_notify_for_prompt` call, with both contributing
    to the outputs list.
    """

    def test_orphan_hint_appended_to_outputs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        missing_transcript = tmp_path / "dead.output"
        _seed_open_state(
            tmp_path, "sess-ups-orphan", name="alice",
            agent_id="agent-x", output_file=missing_transcript,
        )
        # Stub out the agent2agent notify call so it does not contribute
        # extra lines to outputs; only the orphan hint should remain.
        m_notify = tripwire.mock("spellbook_hook:_agent2agent_notify_for_prompt")
        m_notify.returns(None)

        with tripwire:
            outputs = spellbook_hook._handle_user_prompt_submit({
                "session_id": "sess-ups-orphan",
                "prompt": "hello",
                "cwd": str(tmp_path),
            })
        m_notify.assert_call(args=(IsInstance(dict),), kwargs={})
        expected_hint = (
            "[agent2agent] watch chain dropped (likely session compaction or "
            "process death). Run `/a2a open alice` to re-arm the inbox watcher."
        )
        assert outputs == [expected_hint]

    def test_no_orphan_no_hint_in_outputs(self, tmp_path, monkeypatch):
        """No `.open/<sid>` -> no orphan line in outputs."""
        monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
        m_notify = tripwire.mock("spellbook_hook:_agent2agent_notify_for_prompt")
        m_notify.returns(None)

        with tripwire:
            outputs = spellbook_hook._handle_user_prompt_submit({
                "session_id": "sess-ups-clean",
                "prompt": "hello",
                "cwd": str(tmp_path),
            })
        m_notify.assert_call(args=(IsInstance(dict),), kwargs={})
        assert outputs == []
