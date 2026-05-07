"""Tests for the agent2agent UserPromptSubmit notify path in spellbook_hook.

The hook MUST surface inbox metadata only (count + sender names) for the
name bound to the current Claude session id. It MUST NOT read or expose
message bodies — wiring the helper's read/peek/check subcommands here
would create a prompt-injection vector.

Cases:
    1. Session bound, no pending messages       -> no [agent2agent] line
    2. Session bound, two pending messages      -> count=2 + senders, body absent
    3. Session not bound                        -> silent
    4. Session bound but inbox dir is missing   -> silent + binding cleaned up
    5. Helper script missing                    -> silent, no exception
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

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
        [sys.executable, HELPER, "listen", name],
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
        # Simulate another session having unlisten'd 'ghost' meanwhile.
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
