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

    # Sent log is written to sender's sent/ even though sender never opened.
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


# ---------------------------------------------------------------------------
# pending/ staging dir + drain
# ---------------------------------------------------------------------------


def test_open_creates_pending_dir(a2a):
    """`open <name>` must create the pending/ subdir alongside inbox/processed/sent."""
    rc, _, _ = _run(a2a, "open", "alice")
    assert rc == 0
    bus = a2a.bus_dir()
    assert (bus / "alice" / "pending").is_dir()


def _seed_pending(bus: Path, name: str, batch_id: str, payloads: list[dict]) -> list[str]:
    """Write each payload as ``pending/<batch_id>/<id>.json``. Returns the ids."""
    pending_batch = bus / name / "pending" / batch_id
    pending_batch.mkdir(parents=True, exist_ok=True)
    ids = []
    for i, payload in enumerate(payloads):
        msg_id = payload.get("id", f"msg-{batch_id}-{i:03d}")
        ids.append(msg_id)
        (pending_batch / f"{msg_id}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
    return ids


def test_drain_returns_messages_and_moves_to_processed(a2a):
    _run(a2a, "open", "alice")
    bus = a2a.bus_dir()
    ids = _seed_pending(
        bus, "alice", "batch-x",
        [{"id": "m1", "from": "bob", "body": "hello"},
         {"id": "m2", "from": "carol", "body": "world"}],
    )

    rc, stdout, _ = _run(a2a, "drain", "alice", "batch-x")
    assert rc == 0
    payload = json.loads(stdout)
    # Order: lex-sorted by file name, so m1 then m2
    assert payload == {
        "messages": [
            {"id": "m1", "from": "bob", "body": "hello"},
            {"id": "m2", "from": "carol", "body": "world"},
        ],
        "count": 2,
    }
    # Files moved to processed/.
    processed = bus / "alice" / "processed"
    assert {p.name for p in processed.iterdir() if p.suffix == ".json"} == {
        f"{ids[0]}.json", f"{ids[1]}.json"
    }
    # pending/batch-x/ removed (empty rmdir).
    assert not (bus / "alice" / "pending" / "batch-x").exists()


def test_drain_idempotent(a2a):
    _run(a2a, "open", "alice")
    bus = a2a.bus_dir()
    _seed_pending(
        bus, "alice", "batch-x",
        [{"id": "m1", "from": "bob", "body": "hello"},
         {"id": "m2", "from": "carol", "body": "world"}],
    )

    rc1, stdout1, _ = _run(a2a, "drain", "alice", "batch-x")
    assert rc1 == 0
    assert json.loads(stdout1)["count"] == 2

    rc2, stdout2, _ = _run(a2a, "drain", "alice", "batch-x")
    assert rc2 == 0
    assert json.loads(stdout2) == {"messages": [], "count": 0}


def test_drain_atomic_move(a2a):
    _run(a2a, "open", "alice")
    bus = a2a.bus_dir()
    _seed_pending(bus, "alice", "batch-x",
                  [{"id": "m1", "from": "bob", "body": "hello"}])
    pending_file = bus / "alice" / "pending" / "batch-x" / "m1.json"
    processed_file = bus / "alice" / "processed" / "m1.json"
    assert pending_file.exists()
    assert not processed_file.exists()

    rc, _, _ = _run(a2a, "drain", "alice", "batch-x")
    assert rc == 0
    assert not pending_file.exists()
    assert processed_file.exists()
    assert json.loads(processed_file.read_text()) == {
        "id": "m1", "from": "bob", "body": "hello"
    }


def test_drain_batch_id_selection(a2a):
    _run(a2a, "open", "alice")
    bus = a2a.bus_dir()
    _seed_pending(bus, "alice", "batch-a",
                  [{"id": "ma1", "from": "bob", "body": "from-a"}])
    _seed_pending(bus, "alice", "batch-b",
                  [{"id": "mb1", "from": "carol", "body": "from-b"}])

    rc, stdout, _ = _run(a2a, "drain", "alice", "batch-a")
    assert rc == 0
    assert json.loads(stdout) == {
        "messages": [{"id": "ma1", "from": "bob", "body": "from-a"}],
        "count": 1,
    }
    # batch-b untouched.
    assert (bus / "alice" / "pending" / "batch-b" / "mb1.json").exists()
    assert not (bus / "alice" / "pending" / "batch-a").exists()


def test_drain_all_processes_oldest_first(a2a):
    _run(a2a, "open", "alice")
    bus = a2a.bus_dir()
    # batch ids sort lexicographically: batch-a < batch-b
    _seed_pending(bus, "alice", "batch-a",
                  [{"id": "ma1", "from": "bob", "body": "from-a"}])
    _seed_pending(bus, "alice", "batch-b",
                  [{"id": "mb1", "from": "carol", "body": "from-b"}])

    rc, stdout, _ = _run(a2a, "drain", "alice", "--all")
    assert rc == 0
    assert json.loads(stdout) == {
        "messages": [
            {"id": "ma1", "from": "bob", "body": "from-a"},
            {"id": "mb1", "from": "carol", "body": "from-b"},
        ],
        "count": 2,
    }
    assert not (bus / "alice" / "pending" / "batch-a").exists()
    assert not (bus / "alice" / "pending" / "batch-b").exists()


def test_drain_no_args_picks_oldest_batch(a2a):
    _run(a2a, "open", "alice")
    bus = a2a.bus_dir()
    _seed_pending(bus, "alice", "batch-a",
                  [{"id": "ma1", "from": "bob", "body": "from-a"}])
    _seed_pending(bus, "alice", "batch-b",
                  [{"id": "mb1", "from": "carol", "body": "from-b"}])

    rc, stdout, _ = _run(a2a, "drain", "alice")
    assert rc == 0
    assert json.loads(stdout) == {
        "messages": [{"id": "ma1", "from": "bob", "body": "from-a"}],
        "count": 1,
    }
    # Only batch-a drained; batch-b remains.
    assert (bus / "alice" / "pending" / "batch-b" / "mb1.json").exists()
    assert not (bus / "alice" / "pending" / "batch-a").exists()


def test_drain_handles_malformed(a2a):
    _run(a2a, "open", "alice")
    bus = a2a.bus_dir()
    pending_batch = bus / "alice" / "pending" / "batch-m"
    pending_batch.mkdir(parents=True, exist_ok=True)
    bad = pending_batch / "bad.json"
    bad.write_text("not-json", encoding="utf-8")

    rc, stdout, _ = _run(a2a, "drain", "alice", "batch-m")
    assert rc == 0
    payload = json.loads(stdout)
    assert payload["count"] == 1
    assert len(payload["messages"]) == 1
    entry = payload["messages"][0]
    assert entry["id"] == "bad.json"
    assert "error" in entry
    assert entry["error"].startswith("JSONDecodeError:")
    expected_processed = bus / "alice" / "processed" / "bad.json"
    assert entry["raw_path"] == str(expected_processed)
    # File moved to processed/, gone from pending/.
    assert not bad.exists()
    assert expected_processed.exists()
    assert expected_processed.read_text() == "not-json"
    assert "body" not in entry


def test_drain_missing_batch_returns_count_zero(a2a):
    _run(a2a, "open", "alice")
    rc, stdout, _ = _run(a2a, "drain", "alice", "missing-batch-id")
    assert rc == 0
    assert json.loads(stdout) == {"messages": [], "count": 0}


def test_drain_atomic_on_partial_failure(a2a, monkeypatch):
    _run(a2a, "open", "alice")
    bus = a2a.bus_dir()
    _seed_pending(
        bus, "alice", "batch-x",
        [{"id": "m1", "from": "bob", "body": "one"},
         {"id": "m2", "from": "bob", "body": "two"},
         {"id": "m3", "from": "bob", "body": "three"}],
    )

    real_replace = a2a.os.replace
    state = {"calls": 0}

    def flaky_replace(src, dst):
        state["calls"] += 1
        if state["calls"] == 2:
            raise OSError(13, "EACCES (simulated)")
        return real_replace(src, dst)

    monkeypatch.setattr(a2a.os, "replace", flaky_replace)

    with pytest.raises(OSError):
        _run(a2a, "drain", "alice", "batch-x")

    pending_dir_x = bus / "alice" / "pending" / "batch-x"
    processed = bus / "alice" / "processed"

    pending_files = {p.name for p in pending_dir_x.iterdir() if p.suffix == ".json"}
    processed_files = {p.name for p in processed.iterdir() if p.suffix == ".json"}

    # Exactly one file should have moved (the first call), then the second
    # call raised and aborted. m1.json moved; m2.json + m3.json remain.
    assert processed_files == {"m1.json"}
    assert pending_files == {"m2.json", "m3.json"}
    # Invariant: every message is in EXACTLY ONE place.
    assert pending_files.isdisjoint(processed_files)

    # Restore real os.replace and re-run; remaining messages must drain cleanly.
    monkeypatch.setattr(a2a.os, "replace", real_replace)
    rc, stdout, _ = _run(a2a, "drain", "alice", "batch-x")
    assert rc == 0
    payload = json.loads(stdout)
    assert payload == {
        "messages": [
            {"id": "m2", "from": "bob", "body": "two"},
            {"id": "m3", "from": "bob", "body": "three"},
        ],
        "count": 2,
    }
    final_processed = {p.name for p in processed.iterdir() if p.suffix == ".json"}
    assert final_processed == {"m1.json", "m2.json", "m3.json"}
    assert not pending_dir_x.exists()
