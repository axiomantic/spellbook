"""Unit tests for skills/agent2agent/scripts/agent2agent.py.

Imports the helper as a module (without executing main) and exercises
each subcommand against an isolated bus directory. These tests run in
the default test suite — no integration marker.

Coverage:
    * send + read + peek roundtrip
    * open / close lifecycle
    * bind / unbind / bound-name
    * names listing
    * notify metadata-only output (count + senders, no bodies)
    * notify dedup of duplicate senders
    * invalid name rejection (path-traversal guard)
    * invalid session-id rejection
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest


HELPER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "agent2agent" / "scripts" / "agent2agent.py"
)


@pytest.fixture
def a2a(tmp_path, monkeypatch):
    """Load the helper module fresh per test, with bus pinned to tmp_path."""
    monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    spec = importlib.util.spec_from_file_location("_a2a_helper_test", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(module, *argv: str) -> tuple[int, str, str]:
    """Invoke the helper's main() and capture (rc, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = module.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Lifecycle: open / close / bind / unbind / bound-name
# ---------------------------------------------------------------------------


def test_open_creates_inbox_and_bindings(a2a, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-open")
    rc, _, _ = _run(a2a, "open", "alice")
    assert rc == 0
    bus = a2a.bus_dir()
    assert (bus / "alice" / "inbox").is_dir()
    assert (bus / "alice" / "processed").is_dir()
    assert (bus / "alice" / "sent").is_dir()
    assert (bus / ".bindings" / "session-open").read_text() == "alice"


def test_open_without_session_id_still_creates_inbox(a2a):
    rc, stdout, _ = _run(a2a, "open", "alice")
    assert rc == 0
    assert "no CLAUDE_CODE_SESSION_ID" in stdout
    assert (a2a.bus_dir() / "alice" / "inbox").is_dir()


def test_close_removes_inbox_and_clears_binding(a2a, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-close")
    _run(a2a, "open", "bob")
    bus = a2a.bus_dir()
    assert (bus / "bob").is_dir()

    rc, _, _ = _run(a2a, "close", "bob")
    assert rc == 0
    assert not (bus / "bob").exists()
    assert not (bus / ".bindings" / "session-close").exists()


def test_bind_then_unbind_then_bound_name(a2a, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-bind")
    _run(a2a, "open", "carol")  # creates inbox
    # Re-bind to a different name that already has an inbox.
    _run(a2a, "open", "dave")
    rc, _, _ = _run(a2a, "bind", "carol")
    assert rc == 0

    rc, stdout, _ = _run(a2a, "bound-name")
    assert rc == 0
    assert stdout.strip() == "carol"

    rc, _, _ = _run(a2a, "unbind")
    assert rc == 0
    rc, stdout, _ = _run(a2a, "bound-name")
    assert rc == 1
    assert stdout.strip() == ""


def test_bound_name_with_explicit_session_id(a2a, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-A")
    _run(a2a, "open", "alice")

    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    rc, stdout, _ = _run(a2a, "bound-name", "--session-id", "session-A")
    assert rc == 0
    assert stdout.strip() == "alice"


# ---------------------------------------------------------------------------
# Roundtrip: send / read / peek / check
# ---------------------------------------------------------------------------


def test_send_to_unregistered_recipient_fails(a2a):
    rc, _, stderr = _run(a2a, "send", "--from", "bob", "--to", "ghost", "hi")
    assert rc == 1
    assert "no inbox" in stderr


def test_send_then_peek_then_read_roundtrip(a2a):
    _run(a2a, "open", "alice")
    rc, stdout, _ = _run(a2a, "send", "--from", "bob", "--to", "alice", "hello-world")
    assert rc == 0
    msg_id = stdout.strip().split()[-3]  # "agent2agent: sent <id> to alice"

    # peek does not move the message.
    rc, peek_out, _ = _run(a2a, "peek", "alice")
    assert rc == 0
    payload = json.loads(peek_out)
    assert payload["from"] == "bob"
    assert payload["to"] == "alice"
    assert payload["body"] == "hello-world"
    assert payload["id"] == msg_id

    inbox = a2a.bus_dir() / "alice" / "inbox"
    assert any(p.suffix == ".json" for p in inbox.iterdir()), "peek must not consume"

    # read prints AND moves to processed/.
    rc, read_out, _ = _run(a2a, "read", "alice")
    assert rc == 0
    assert json.loads(read_out)["body"] == "hello-world"
    assert not any(p.suffix == ".json" for p in inbox.iterdir())
    processed = a2a.bus_dir() / "alice" / "processed"
    assert any(p.suffix == ".json" for p in processed.iterdir())

    # Sent log is written to sender's sent/ even though sender never listened.
    sent = a2a.bus_dir() / "bob" / "sent"
    assert sent.is_dir()
    assert any(p.suffix == ".json" for p in sent.iterdir())


def test_send_with_reply_to_records_correlation(a2a):
    _run(a2a, "open", "alice")
    _run(a2a, "send", "--from", "bob", "--to", "alice", "first")
    rc, peek_out, _ = _run(a2a, "peek", "alice")
    first_id = json.loads(peek_out)["id"]

    rc, _, _ = _run(
        a2a, "send", "--from", "bob", "--to", "alice",
        "--reply-to", first_id, "follow-up",
    )
    assert rc == 0
    msgs = sorted((a2a.bus_dir() / "alice" / "inbox").iterdir())
    assert len(msgs) == 2
    payloads = [json.loads(m.read_text()) for m in msgs]
    assert {p.get("in_reply_to") for p in payloads} == {None, first_id}


def test_check_lists_pending_messages(a2a):
    _run(a2a, "open", "alice")
    _run(a2a, "send", "--from", "bob", "--to", "alice", "one")
    _run(a2a, "send", "--from", "carol", "--to", "alice", "two")

    rc, stdout, _ = _run(a2a, "check", "alice")
    assert rc == 0
    assert "2 pending" in stdout
    assert "from=bob" in stdout
    assert "from=carol" in stdout


# ---------------------------------------------------------------------------
# notify: metadata-only, dedup, stale binding
# ---------------------------------------------------------------------------


def test_notify_silent_when_inbox_empty(a2a):
    _run(a2a, "open", "alice")
    rc, stdout, _ = _run(a2a, "notify", "alice")
    assert rc == 0
    assert stdout == ""


def test_notify_reports_count_and_senders_without_bodies(a2a):
    _run(a2a, "open", "alice")
    _run(a2a, "send", "--from", "bob", "--to", "alice", "secret-body-A")
    _run(a2a, "send", "--from", "carol", "--to", "alice", "secret-body-B")

    rc, stdout, _ = _run(a2a, "notify", "alice")
    assert rc == 0
    assert "alice has 2 pending" in stdout
    assert "bob" in stdout and "carol" in stdout
    # CRITICAL: bodies must NEVER appear in notify output.
    assert "secret-body-A" not in stdout
    assert "secret-body-B" not in stdout


def test_notify_dedupes_repeated_senders(a2a):
    _run(a2a, "open", "alice")
    _run(a2a, "send", "--from", "bob", "--to", "alice", "msg1")
    _run(a2a, "send", "--from", "bob", "--to", "alice", "msg2")
    _run(a2a, "send", "--from", "bob", "--to", "alice", "msg3")

    rc, stdout, _ = _run(a2a, "notify", "alice")
    assert rc == 0
    assert "alice has 3 pending" in stdout
    # 'bob' must appear in the sender list exactly once.
    sender_line = next(
        line for line in stdout.splitlines() if "from:" in line
    )
    assert sender_line.count("bob") == 1


def test_notify_stale_binding_is_silently_cleaned_up(a2a, monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-stale")
    _run(a2a, "open", "ghost")
    binding = a2a.bus_dir() / ".bindings" / "session-stale"
    assert binding.exists()

    # Simulate another session having closed 'ghost'.
    import shutil
    shutil.rmtree(a2a.bus_dir() / "ghost")

    rc, stdout, _ = _run(a2a, "notify", "ghost")
    assert rc == 0
    assert stdout == ""
    assert not binding.exists(), "notify must clean up stale binding"


# ---------------------------------------------------------------------------
# names listing
# ---------------------------------------------------------------------------


def test_names_lists_only_valid_dirs(a2a):
    _run(a2a, "open", "alice")
    _run(a2a, "open", "bob")
    # Hidden + invalid-name dirs must be skipped.
    (a2a.bus_dir() / ".bindings").mkdir(exist_ok=True)
    (a2a.bus_dir() / ".hidden").mkdir(exist_ok=True)
    (a2a.bus_dir() / "with space").mkdir(exist_ok=True)

    rc, stdout, _ = _run(a2a, "names")
    assert rc == 0
    listed = stdout.strip().splitlines()
    assert listed == ["alice", "bob"]


def test_names_returns_zero_when_bus_missing(a2a, tmp_path, monkeypatch):
    """Bus dir does not exist -> exit 0, empty output."""
    monkeypatch.setenv("AGENT2AGENT_DIR", str(tmp_path / "does-not-exist"))
    rc, stdout, _ = _run(a2a, "names")
    assert rc == 0
    assert stdout == ""


# ---------------------------------------------------------------------------
# Validation: invalid names + invalid session ids
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_name", [
    "../escape",
    "/abs/path",
    ".hidden",
    "-leading-dash",
    "with space",
    "x" * 65,  # 65 chars exceeds the 64-char cap
    "",
])
def test_invalid_name_is_rejected_with_exit_2(a2a, bad_name):
    """Any subcommand that takes <name> must reject path-traversal-shaped input."""
    with pytest.raises(SystemExit) as ei:
        _run(a2a, "open", bad_name)
    assert ei.value.code == 2


def test_invalid_session_id_is_rejected(a2a, monkeypatch):
    """Bind/open reject malformed session ids via SystemExit(2)."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "with space")
    with pytest.raises(SystemExit) as ei:
        _run(a2a, "open", "alice")
    assert ei.value.code == 2


def test_send_rejects_invalid_from_name(a2a):
    _run(a2a, "open", "alice")
    with pytest.raises(SystemExit) as ei:
        _run(a2a, "send", "--from", "../escape", "--to", "alice", "hi")
    assert ei.value.code == 2
