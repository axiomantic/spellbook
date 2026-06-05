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
    * watch: lockfile + RECOVER + WATCH_RECYCLE (subprocess-based)
    * watch: SIGKILL'd watcher releases flock via kernel fd cleanup
"""
from __future__ import annotations

import sys

import pytest

# The agent2agent helper uses fcntl.flock for watch-lockfile mutex. fcntl is
# POSIX-only, so the helper module fails to import on Windows. Skip the entire
# test module rather than collecting it. allow_module_level=True is required
# because pytest evaluates module skip marks AFTER imports run.
if sys.platform == "win32":
    pytest.skip(
        "agent2agent helper requires fcntl (POSIX-only)",
        allow_module_level=True,
    )

import fcntl
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import tripwire
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from dirty_equals import IsInstance
from pathlib import Path


HELPER_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "agent2agent" / "scripts" / "agent2agent.py"
)

SKILL_MD_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "agent2agent" / "SKILL.md"
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

    rc, stdout, _ = _run(a2a, "close", "bob")
    assert rc == 0
    assert stdout.strip() == "agent2agent: closed 'bob'"
    assert not (bus / "bob").exists()
    assert not (bus / ".bindings" / "session-close").exists()


def test_close_idempotent_reports_not_bound(a2a, monkeypatch):
    """Second close (or close of an unbound name) is exit 0 with a
    distinct ``not bound`` stdout, not the same ``closed`` line as the
    first call. Operators rely on the message to know whether the call
    actually released anything.
    """
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-close-idem")
    _run(a2a, "open", "bob")
    rc, stdout1, _ = _run(a2a, "close", "bob")
    assert rc == 0
    assert stdout1.strip() == "agent2agent: closed 'bob'"

    rc, stdout2, _ = _run(a2a, "close", "bob")
    assert rc == 0
    assert stdout2.strip() == "agent2agent: not bound to 'bob'"


def test_close_unknown_name_reports_not_bound(a2a, monkeypatch):
    """Closing a name that was never opened in this session is a no-op
    (exit 0, ``not bound`` stdout). No prior state required.
    """
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-close-unknown")
    rc, stdout, _ = _run(a2a, "close", "ghost")
    assert rc == 0
    assert stdout.strip() == "agent2agent: not bound to 'ghost'"


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


def test_drain_atomic_on_partial_failure(a2a):
    _run(a2a, "open", "alice")
    bus = a2a.bus_dir()
    _seed_pending(
        bus, "alice", "batch-x",
        [{"id": "m1", "from": "bob", "body": "one"},
         {"id": "m2", "from": "bob", "body": "two"},
         {"id": "m3", "from": "bob", "body": "three"}],
    )

    state = {"calls": 0}

    def flaky_replace(src, dst):
        state["calls"] += 1
        if state["calls"] == 2:
            raise OSError(13, "EACCES (simulated)")
        # Use os.rename (a distinct function from os.replace) to avoid
        # recursing back through the tripwire proxy. On POSIX these are
        # equivalent for our purposes; this test is POSIX-only via the
        # module-level skip on win32.
        os.rename(src, dst)

    # Patch os.replace via tripwire. The helper imports `os` and calls
    # os.replace; mocking on the os module intercepts that call. Each
    # .calls() pushes one entry onto the FIFO queue, so register twice:
    # once for m1 (success) and once for m2 (raises). m3 is never reached.
    m_replace = tripwire.mock("os:replace")
    m_replace.calls(flaky_replace).calls(flaky_replace)

    with tripwire:
        with pytest.raises(OSError):
            _run(a2a, "drain", "alice", "batch-x")
    # flaky_replace was invoked twice: m1 (succeeded via os.rename), m2
    # (raised). Each recorded interaction must be asserted.
    m_replace.assert_call(args=(IsInstance(Path), IsInstance(Path)), kwargs={})
    m_replace.assert_call(args=(IsInstance(Path), IsInstance(Path)), kwargs={})

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

    # tripwire restored os.replace automatically after the sandbox; re-run
    # drain — remaining messages must drain cleanly.
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


# ---------------------------------------------------------------------------
# watch: lockfile + RECOVER + WATCH_RECYCLE (T3a)
#
# These tests use subprocess.Popen on the helper script directly, NOT the
# in-process _run fixture. Reason: cmd_watch installs atexit handlers,
# signal handlers, and an fcntl.flock on a fd that is tied to process
# lifetime. Repeated in-process invocations leak state between tests.
# Each subprocess gets a fresh process boundary.
# ---------------------------------------------------------------------------


def _seed_pending_for_watch(bus: Path, name: str, batch_id: str, count: int = 1) -> None:
    """Seed N message files into pending/<batch_id>/ to force the RECOVER path."""
    pending_batch = bus / name / "pending" / batch_id
    pending_batch.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        msg_id = f"msg-{batch_id}-{i:03d}"
        (pending_batch / f"{msg_id}.json").write_text(
            json.dumps({"id": msg_id, "from": "bob", "body": f"hi-{i}"}),
            encoding="utf-8",
        )


def _watch_env(tmp_path: Path) -> dict:
    """Subprocess env with AGENT2AGENT_DIR pinned to tmp_path."""
    env = os.environ.copy()
    env["AGENT2AGENT_DIR"] = str(tmp_path)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    return env


def _open_inbox(tmp_path: Path, name: str) -> None:
    """Run `open <name>` via subprocess to create the inbox dir tree."""
    rc = subprocess.run(
        [sys.executable, str(HELPER_PATH), "open", name],
        env=_watch_env(tmp_path),
        capture_output=True,
        text=True,
    ).returncode
    assert rc == 0


def _spawn_watch(
    tmp_path: Path,
    name: str,
    max_elapsed: float = 10.0,
    *,
    infinite: bool = False,
    poll_interval: float | None = None,
    heartbeat_interval: float | None = None,
) -> subprocess.Popen:
    """Spawn `watch <name>` as a subprocess; returns Popen.

    - infinite=True omits --max-elapsed entirely (production infinite mode,
      design §12.1). When False, passes --max-elapsed <max_elapsed>.
    - poll_interval / heartbeat_interval, when given, append the corresponding
      flags (the latter is the slash-internal cadence test seam, §12.4).
    """
    argv = ["watch", name]
    if not infinite:
        argv += ["--max-elapsed", str(max_elapsed)]
    if poll_interval is not None:
        argv += ["--poll-interval", str(poll_interval)]
    if heartbeat_interval is not None:
        argv += ["--heartbeat-interval", str(heartbeat_interval)]
    return subprocess.Popen(
        [sys.executable, str(HELPER_PATH), *argv],
        env=_watch_env(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_watcher_locked(lockfile: Path, timeout: float = 2.0) -> None:
    """Block until the lockfile contains a pid (digits-only, non-empty).

    The watcher writes its pid into the lockfile AFTER ``fcntl.flock``
    succeeds. Polling for non-empty content (rather than ``exists()``)
    closes a TOCTOU window: ``os.open(O_CREAT)`` creates the file BEFORE
    flock returns, so existence alone does not prove the watcher actually
    holds the mutex.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if lockfile.exists():
            try:
                content = lockfile.read_text().strip()
            except OSError:
                content = ""
            if content.isdigit():
                return
        time.sleep(0.02)
    raise TimeoutError(f"watcher never wrote pid to {lockfile}")


def _flock_acquirable(lockfile: Path) -> bool:
    """Return True iff a fresh opener can acquire LOCK_EX|LOCK_NB on lockfile.

    Used to assert release semantics without relying on ``lockfile.exists()``
    (the lockfile path is intentionally persistent; the mutex is enforced
    by flock + kernel fd cleanup, not by unlinking).
    """
    if not lockfile.exists():
        # Path absence is *also* fine — fresh opener would create+flock.
        return True
    fd = os.open(str(lockfile), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        return True
    finally:
        os.close(fd)


def _wait_proc(proc: subprocess.Popen, paranoia_timeout: float) -> tuple[int, str, str]:
    """Wait for proc with paranoia-bound timeout. Returns (rc, stdout, stderr)."""
    try:
        stdout, stderr = proc.communicate(timeout=paranoia_timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        raise AssertionError(
            f"watch subprocess did not exit within {paranoia_timeout}s "
            f"(stdout={stdout!r} stderr={stderr!r})"
        )
    return proc.returncode, stdout, stderr


def test_watch_recycles_when_no_message_arrives(tmp_path):
    """Empty inbox + empty pending: budget-only loop exits with WATCH_RECYCLE."""
    _open_inbox(tmp_path, "alice")
    proc = _spawn_watch(tmp_path, "alice", max_elapsed=2.0)
    rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=2.0 + 5)
    assert rc == 0, f"stderr={stderr!r}"
    assert re.match(r"^WATCH_RECYCLE elapsed=2s$", stdout.strip()), (
        f"stdout={stdout!r}"
    )
    # Lockfile path is intentionally persistent; the mutex is the flock,
    # not the path. Assert a fresh opener can acquire the lock.
    assert _flock_acquirable(tmp_path / "alice" / "inbox" / ".watcher.lock")


def test_watch_recovers_pending_on_entry(tmp_path):
    """Pre-existing pending/<batch>/ short-circuits idle wait; emits PENDING_BATCH."""
    _open_inbox(tmp_path, "alice")
    _seed_pending_for_watch(tmp_path, "alice", "batch-foo", count=1)

    t0 = time.monotonic()
    proc = _spawn_watch(tmp_path, "alice", max_elapsed=10.0)
    rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=5.0)
    elapsed = time.monotonic() - t0

    assert rc == 0, f"stderr={stderr!r}"
    assert stdout.strip() == "PENDING_BATCH batch-foo count=1"
    # RECOVER path must NOT wait for the budget; should exit promptly.
    assert elapsed < 3.0, (
        f"watch took {elapsed:.2f}s; RECOVER path must exit promptly without idling"
    )


def test_watch_recovers_oldest_batch_when_multiple_pending(tmp_path):
    """Multiple pending batches: emit oldest (lex-sorted) batch id."""
    _open_inbox(tmp_path, "alice")
    _seed_pending_for_watch(tmp_path, "alice", "batch-a", count=2)
    _seed_pending_for_watch(tmp_path, "alice", "batch-b", count=1)

    proc = _spawn_watch(tmp_path, "alice", max_elapsed=10.0)
    rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=5.0)
    assert rc == 0, f"stderr={stderr!r}"
    assert stdout.strip() == "PENDING_BATCH batch-a count=2"


def test_watch_inbox_gone_emits_marker(tmp_path):
    """Inbox dir not created (no `open`): exit 1 with WATCH_INBOX_GONE."""
    proc = _spawn_watch(tmp_path, "alice", max_elapsed=2.0)
    rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=5.0)
    assert rc == 1, f"stderr={stderr!r}"
    assert stdout.strip() == "WATCH_INBOX_GONE"


def test_watch_lockfile_released_on_exit(tmp_path):
    """After watch's RECOVER exit, the flock must be released so a fresh
    watcher can acquire it.

    The lockfile *path* is intentionally persistent (unlinking it would
    introduce a flock+unlink race). The mutex contract is "next opener
    can flock", not "path is gone".
    """
    _open_inbox(tmp_path, "alice")
    _seed_pending_for_watch(tmp_path, "alice", "batch-x", count=1)

    proc = _spawn_watch(tmp_path, "alice", max_elapsed=10.0)
    rc, stdout, _ = _wait_proc(proc, paranoia_timeout=5.0)
    assert rc == 0
    assert "PENDING_BATCH" in stdout

    lockfile = tmp_path / "alice" / "inbox" / ".watcher.lock"
    assert _flock_acquirable(lockfile), (
        "flock must be released on watch exit so a fresh opener can acquire"
    )


def test_watch_recycle_lockfile_released(tmp_path):
    """After WATCH_RECYCLE exit, flock is released and a new watch can run.

    The lockfile path persists; the mutex source is flock + kernel fd
    cleanup. We assert "fresh opener can flock" rather than "path is gone".
    """
    _open_inbox(tmp_path, "alice")

    proc1 = _spawn_watch(tmp_path, "alice", max_elapsed=1.0)
    rc1, stdout1, stderr1 = _wait_proc(proc1, paranoia_timeout=1.0 + 5)
    assert rc1 == 0, f"stderr={stderr1!r}"
    assert stdout1.strip() == "WATCH_RECYCLE elapsed=1s"
    assert _flock_acquirable(tmp_path / "alice" / "inbox" / ".watcher.lock")

    # Second watch must succeed (no WATCH_LOCKED).
    proc2 = _spawn_watch(tmp_path, "alice", max_elapsed=1.0)
    rc2, stdout2, stderr2 = _wait_proc(proc2, paranoia_timeout=1.0 + 5)
    assert rc2 == 0, f"stderr={stderr2!r}"
    assert stdout2.strip() == "WATCH_RECYCLE elapsed=1s"
    assert "WATCH_LOCKED" not in stderr2


def test_watch_concurrent_attempt_blocked_by_lockfile(tmp_path):
    """Second watcher while first is alive: exits 75 with WATCH_LOCKED stderr."""
    _open_inbox(tmp_path, "alice")

    # Watcher A: long-ish budget so it is alive when B spawns.
    proc_a = _spawn_watch(tmp_path, "alice", max_elapsed=5.0)
    try:
        # Wait for A to actually hold the flock. The pid is written AFTER
        # flock succeeds, so polling for non-empty pid content (rather
        # than path existence) closes the TOCTOU window where O_CREAT
        # has materialized the file but flock hasn't yet been acquired.
        lockfile = tmp_path / "alice" / "inbox" / ".watcher.lock"
        _wait_for_watcher_locked(lockfile, timeout=2.0)

        # Watcher B should be rejected immediately.
        proc_b = _spawn_watch(tmp_path, "alice", max_elapsed=5.0)
        rc_b, stdout_b, stderr_b = _wait_proc(proc_b, paranoia_timeout=5.0)
        assert rc_b == 75, (
            f"watcher B expected exit 75, got {rc_b}; "
            f"stdout={stdout_b!r} stderr={stderr_b!r}"
        )
        m = re.search(r"^WATCH_LOCKED (\d+)$", stderr_b.strip())
        assert m, f"stderr={stderr_b!r}"
        # The reported pid MUST be the holder's (watcher A), not the loser's
        # (watcher B). Diagnostic value: an operator should be able to kill
        # the holder by the printed pid. Regression guard against the old
        # ``os.getpid()`` bug where the loser printed its own pid.
        reported_pid = int(m.group(1))
        assert reported_pid == proc_a.pid, (
            f"WATCH_LOCKED reported pid={reported_pid} (loser={proc_b.pid}); "
            f"expected holder pid={proc_a.pid}"
        )
        # B must not have produced PENDING_BATCH or WATCH_RECYCLE.
        assert stdout_b.strip() == ""
    finally:
        # Let A run to completion.
        rc_a, stdout_a, stderr_a = _wait_proc(proc_a, paranoia_timeout=5.0 + 5)

    assert rc_a == 0, f"stderr={stderr_a!r}"
    assert stdout_a.strip() == "WATCH_RECYCLE elapsed=5s"


def test_watch_recover_with_only_empty_batch_dir_falls_through_to_recycle(tmp_path):
    """An empty pending/<batch>/ directory must NOT trigger RECOVER."""
    _open_inbox(tmp_path, "alice")
    # Empty batch dir (no files) -- watch must skip it and fall to WAIT/recycle.
    (tmp_path / "alice" / "pending" / "batch-empty").mkdir(parents=True)

    proc = _spawn_watch(tmp_path, "alice", max_elapsed=1.0)
    rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=1.0 + 5)
    assert rc == 0, f"stderr={stderr!r}"
    assert stdout.strip() == "WATCH_RECYCLE elapsed=1s"


def test_watch_kill_releases_lockfile_via_kernel(tmp_path):
    """SIGKILL'd watcher must release flock via kernel fd cleanup.

    SIGKILL bypasses atexit and signal handlers entirely, so the only
    thing standing between watcher A's death and watcher B's spawn is
    the kernel auto-releasing the flock when A's fd is reaped. If the
    spec ever drifts away from kernel-fd-cleanup as the source of mutex
    release, this test catches it: B would observe WATCH_LOCKED 75 and
    fail.
    """
    _open_inbox(tmp_path, "alice")
    lockfile = tmp_path / "alice" / "inbox" / ".watcher.lock"

    # Watcher A: long budget so it's alive (and holding flock) when killed.
    proc_a = _spawn_watch(tmp_path, "alice", max_elapsed=30.0)
    try:
        # Wait until A has actually acquired the flock (pid written).
        _wait_for_watcher_locked(lockfile, timeout=2.0)
        proc_a.kill()  # SIGKILL — bypasses atexit + signal handlers.
        rc_a = proc_a.wait(timeout=1.0)
        # SIGKILL = 9; conventional rc = -9 from Popen.wait when killed.
        assert rc_a == -9 or rc_a == 137 or rc_a < 0, (
            f"watcher A expected to die from SIGKILL, got rc={rc_a}"
        )
    finally:
        # Drain stdio so the OS can reap A's fds.
        try:
            proc_a.stdout.close()
        except Exception:
            pass
        try:
            proc_a.stderr.close()
        except Exception:
            pass

    # Watcher B: same name, same env. With kernel fd-cleanup intact, B must
    # acquire the flock immediately and run normally (empty inbox -> recycle).
    proc_b = _spawn_watch(tmp_path, "alice", max_elapsed=0.5)
    rc_b, stdout_b, stderr_b = _wait_proc(proc_b, paranoia_timeout=5.0)
    assert rc_b == 0, (
        f"watcher B expected exit 0 (kernel auto-released A's flock), "
        f"got rc={rc_b}; stdout={stdout_b!r} stderr={stderr_b!r}"
    )
    assert "WATCH_LOCKED" not in stderr_b, (
        f"watcher B saw WATCH_LOCKED — kernel did not release A's flock; "
        f"stderr={stderr_b!r}"
    )
    assert re.match(r"^WATCH_RECYCLE elapsed=0s$", stdout_b.strip()), (
        f"stdout={stdout_b!r}"
    )


def test_watch_infinite_mode_delivers_without_recycle(a2a, tmp_path):
    """Production path: NO --max-elapsed (infinite). The loop survives >=2 poll
    intervals (proves both line-718 and line-764 guards), a sent message yields
    PENDING_BATCH, and WATCH_RECYCLE never appears (design §12.1)."""
    _open_inbox(tmp_path, "alice")
    proc = _spawn_watch(tmp_path, "alice", infinite=True, poll_interval=0.2)
    try:
        # Loop-survival: alive after >=2 full poll intervals + slack.
        time.sleep(0.2 * 2 + 0.6)
        assert proc.poll() is None, (
            "watcher crashed within 2 poll intervals — likely the line-764 "
            "None - float TypeError (infinite mode unguarded)"
        )
        # Deliver a message.
        _run(a2a, "send", "--from", "bob", "--to", "alice", "hello")
        # Expect PENDING_BATCH within ~3s.
        stdout, stderr = proc.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        raise AssertionError(f"watcher did not deliver in time; stderr={stderr!r}")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}; stderr={stderr!r}"
    assert re.search(r"^PENDING_BATCH \S+ count=1$", stdout, re.M), stdout
    assert "WATCH_RECYCLE" not in stdout, "infinite mode must never recycle"
    # Diagnostic: a regression must name the cause.
    assert "Traceback" not in stderr and "TypeError" not in stderr, stderr


def test_watch_touches_heartbeat_on_entry_and_interval(tmp_path):
    """Heartbeat exists within <1s of start (first-touch-immediate) and its
    mtime advances across an interval (design §3.1, §12.4). Uses the
    --heartbeat-interval test seam (cadence only)."""
    _open_inbox(tmp_path, "alice")
    proc = _spawn_watch(
        tmp_path, "alice", max_elapsed=6.0, heartbeat_interval=1.0
    )
    try:
        inbox = tmp_path / "alice" / "inbox"  # two-level: <root>/<name>/inbox
        hb = inbox / ".watcher.heartbeat"
        # First-touch-immediate: heartbeat exists within ~1s.
        deadline = time.time() + 1.5
        while time.time() < deadline and not hb.exists():
            time.sleep(0.05)
        assert hb.exists(), "heartbeat not created on loop entry"
        mtime1 = hb.stat().st_mtime
        # Interval touch: mtime advances after >1 interval.
        time.sleep(2.5)
        mtime2 = hb.stat().st_mtime
        assert mtime2 > mtime1, "heartbeat mtime did not advance across interval"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# watch: fswatch + 500ms polling backstop + spurious-wake re-entry (T3b)
#
# These tests extend T3a coverage to the full WAIT/DRAIN state machine:
#   - fswatch wake (when fswatch is on PATH) returns PENDING_BATCH
#   - polling backstop wakes even with fswatch unavailable (PATH stripped)
#   - spurious fswatch events (dotfiles) do NOT exit early
#   - atomic concurrent claim: one watcher + one read, never duplicates
# All tests use subprocess.Popen for the same isolation reasons as T3a.
# ---------------------------------------------------------------------------


def _watch_env_no_fswatch(tmp_path: Path) -> dict:
    """Subprocess env with AGENT2AGENT_DIR set AND PATH stripped of fswatch.

    Forces ``shutil.which("fswatch")`` inside the subprocess to return None
    so we exercise the polling-only branch on every host (incl. CI without
    fswatch installed). PATH is set to a directory that we know does not
    contain fswatch so the python interpreter and other essentials remain
    unchanged for the test runner's spawn.
    """
    env = _watch_env(tmp_path)
    # Use an empty/nonexistent PATH so shutil.which("fswatch") -> None.
    # We invoke python by absolute path (sys.executable) so PATH stripping
    # does not break the subprocess spawn itself.
    env["PATH"] = "/nonexistent-dir-for-watch-test"
    return env


def _spawn_watch_no_fswatch(
    tmp_path: Path, name: str, max_elapsed: float
) -> subprocess.Popen:
    """Like _spawn_watch but with PATH stripped of fswatch."""
    return subprocess.Popen(
        [
            sys.executable, str(HELPER_PATH),
            "watch", name, "--max-elapsed", str(max_elapsed),
        ],
        env=_watch_env_no_fswatch(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _drop_inbox_message(
    tmp_path: Path, name: str, msg_id: str, sender: str = "bob", body: str = "hi"
) -> Path:
    """Atomically drop a message file into <name>/inbox/. Mirrors cmd_send's
    tempfile + os.replace idiom so the watcher only ever sees a fully-written
    file (no half-baked content during fswatch wake).
    """
    inbox = tmp_path / name / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"id": msg_id, "from": sender, "body": body})
    target = inbox / f"{msg_id}.json"
    # tempfile in same dir -> os.replace = atomic rename on POSIX.
    fd, tmp = tempfile.mkstemp(dir=str(inbox), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return target


def _fswatch_available() -> bool:
    return shutil.which("fswatch") is not None


@pytest.mark.skipif(not _fswatch_available(), reason="fswatch not on PATH")
def test_watch_blocks_then_returns_on_send(tmp_path):
    """fswatch path: empty inbox; drop a message after 0.6s; watcher exits
    with PENDING_BATCH count=1 within ~2s and the file is in pending/."""
    _open_inbox(tmp_path, "alice")
    proc = _spawn_watch(tmp_path, "alice", max_elapsed=10.0)
    try:
        time.sleep(0.6)
        msg_id = "msg-fswatch-0001"
        _drop_inbox_message(tmp_path, "alice", msg_id, sender="bob", body="hi-fs")
        rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=5.0)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2.0)

    assert rc == 0, f"stderr={stderr!r} stdout={stdout!r}"
    m = re.match(r"^PENDING_BATCH (\S+) count=1$", stdout.strip())
    assert m, f"stdout={stdout!r}"
    batch_id = m.group(1)

    # File moved out of inbox/ and into pending/<batch_id>/.
    inbox_files = list((tmp_path / "alice" / "inbox").glob("*.json"))
    assert inbox_files == [], f"inbox should be empty, got {inbox_files!r}"
    batch_dir = tmp_path / "alice" / "pending" / batch_id
    assert batch_dir.is_dir(), f"missing batch dir {batch_dir}"
    pending_files = sorted(p.name for p in batch_dir.iterdir())
    assert pending_files == [f"{msg_id}.json"], (
        f"pending files: {pending_files!r}"
    )


def test_watch_polling_path_when_no_fswatch(tmp_path):
    """Polling-only branch: PATH stripped so shutil.which('fswatch') is None.

    Watcher logs the fallback marker to stderr ONCE, then a message dropped
    after 0.3s is detected via the 0.5s poll within ~1s and emits
    PENDING_BATCH count=1.
    """
    _open_inbox(tmp_path, "alice")
    proc = _spawn_watch_no_fswatch(tmp_path, "alice", max_elapsed=10.0)
    try:
        time.sleep(0.3)
        msg_id = "msg-poll-0001"
        _drop_inbox_message(tmp_path, "alice", msg_id, sender="bob", body="hi-poll")
        rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=5.0)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2.0)

    assert rc == 0, f"stderr={stderr!r} stdout={stdout!r}"
    m = re.match(r"^PENDING_BATCH (\S+) count=1$", stdout.strip())
    assert m, f"stdout={stdout!r}"
    batch_id = m.group(1)
    assert "fswatch unavailable, polling-only" in stderr, (
        f"polling-only marker missing in stderr={stderr!r}"
    )

    # File moved out of inbox/ and into pending/<batch_id>/.
    inbox_files = list((tmp_path / "alice" / "inbox").glob("*.json"))
    assert inbox_files == [], f"inbox should be empty, got {inbox_files!r}"
    batch_dir = tmp_path / "alice" / "pending" / batch_id
    pending_files = sorted(p.name for p in batch_dir.iterdir())
    assert pending_files == [f"{msg_id}.json"], (
        f"pending files: {pending_files!r}"
    )


@pytest.mark.skipif(not _fswatch_available(), reason="fswatch not on PATH")
def test_watch_recovers_from_spurious_fswatch_event(tmp_path):
    """fswatch fires for a dotfile: _list_inbox filters it; watcher must NOT
    emit PENDING_BATCH count=0 and must NOT exit early. It runs out the
    --max-elapsed budget and exits with WATCH_RECYCLE.
    """
    _open_inbox(tmp_path, "alice")
    proc = _spawn_watch(tmp_path, "alice", max_elapsed=4.0)
    try:
        time.sleep(0.4)
        # Dotfile in inbox triggers fswatch but is filtered by _list_inbox.
        # We use a dotfile name distinct from .watcher.lock to avoid stomping
        # the active watcher's mutex fd.
        spurious = tmp_path / "alice" / "inbox" / ".tmp-spurious-event"
        spurious.write_text("ignore-me", encoding="utf-8")
        rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=4.0 + 5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2.0)

    assert rc == 0, f"stderr={stderr!r}"
    assert stdout.strip() == "WATCH_RECYCLE elapsed=4s", (
        f"watcher must NOT exit early on spurious wake; stdout={stdout!r}"
    )
    # Specifically: must not have emitted a zero-count PENDING_BATCH.
    assert "count=0" not in stdout, f"unexpected zero-count batch: stdout={stdout!r}"


@pytest.mark.skipif(not _fswatch_available(), reason="fswatch not on PATH")
def test_watch_atomic_consume_under_concurrent_reader(tmp_path):
    """Pre-seed 3 messages; race watcher vs cmd_read on one of them.

    Invariants:
      - watcher's PENDING_BATCH count is 2 or 3 (never duplicated).
      - every original message ends up in EXACTLY ONE of:
        processed/<id>.json  (read claimed it) OR
        pending/<batch>/<id>.json  (watcher claimed it).
      - total file count across both dirs == 3 (no duplicates, no losses
        beyond the inherent race).
    """
    _open_inbox(tmp_path, "alice")
    msg_ids = ["msg-race-001", "msg-race-002", "msg-race-003"]
    for mid in msg_ids:
        _drop_inbox_message(tmp_path, "alice", mid, sender="bob", body=f"b-{mid}")

    # Spawn watcher; concurrently fire `read` on one specific message.
    proc = _spawn_watch(tmp_path, "alice", max_elapsed=5.0)
    try:
        # Run read targeting the middle message. We do not assert read's
        # rc here: if the watcher beat it to the rename, read returns 1
        # ("no message"). The invariants below are the contract.
        read_proc = subprocess.run(
            [sys.executable, str(HELPER_PATH), "read", "alice", "msg-race-002"],
            env=_watch_env(tmp_path),
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=5.0 + 5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2.0)

    assert rc == 0, f"stderr={stderr!r} stdout={stdout!r}"
    m = re.match(r"^PENDING_BATCH (\S+) count=(\d+)$", stdout.strip())
    assert m, f"stdout={stdout!r}"
    batch_id = m.group(1)
    count = int(m.group(2))
    assert count in (2, 3), (
        f"PENDING_BATCH count must be 2 or 3 (no duplicates); got {count}"
    )

    # Inbox must be empty (everything was claimed by exactly one path).
    inbox_files = sorted(
        p.name for p in (tmp_path / "alice" / "inbox").iterdir()
        if p.is_file() and p.name.endswith(".json")
        and not p.name.startswith(".")
    )
    assert inbox_files == [], f"inbox should be drained, got {inbox_files!r}"

    pending_dir = tmp_path / "alice" / "pending" / batch_id
    pending_files = (
        sorted(p.name for p in pending_dir.iterdir())
        if pending_dir.is_dir() else []
    )
    processed_dir = tmp_path / "alice" / "processed"
    processed_files = (
        sorted(p.name for p in processed_dir.iterdir())
        if processed_dir.is_dir() else []
    )

    # Disjoint: no message is in both places.
    assert set(pending_files).isdisjoint(set(processed_files)), (
        f"duplicate claim: pending={pending_files!r} processed={processed_files!r}"
    )

    # Union covers ALL original messages exactly once.
    expected = sorted(f"{mid}.json" for mid in msg_ids)
    actual = sorted(pending_files + processed_files)
    assert actual == expected, (
        f"messages lost or duplicated; expected={expected!r} actual={actual!r} "
        f"(pending={pending_files!r} processed={processed_files!r}) "
        f"read_rc={read_proc.returncode} read_stderr={read_proc.stderr!r}"
    )

    # PENDING_BATCH count must equal len(pending_files).
    assert count == len(pending_files), (
        f"PENDING_BATCH count={count} mismatches actual pending file count "
        f"{len(pending_files)}"
    )


_FSWATCH_OR_PS_MISSING = (
    shutil.which("fswatch") is None or shutil.which("ps") is None
)


def _count_stray_fswatch(inbox) -> int:
    """Count live `fswatch ... <inbox>` processes (matches the helper's
    str(inbox)-exact substring predicate)."""
    out = subprocess.run(
        ["ps", "-axo", "command="], capture_output=True, text=True
    ).stdout
    return sum(
        1 for ln in out.splitlines()
        if "fswatch" in ln and str(inbox) in ln
    )


def _plant_fswatch_stray(inbox: Path) -> subprocess.Popen:
    """Plant a long-lived `fswatch -0 -l 0.1 <inbox>` process whose command
    line matches the helper's sweep predicate exactly.

    NOTE (empirical, 2026-06-05): a real watcher's own fswatch child does NOT
    survive parent SIGKILL on this platform — its stdout pipe to the dead
    parent breaks and SIGPIPE reaps it, independent of process group. So the
    SIGKILL-orphans-fswatch premise is not reproducible here. To exercise the
    sweep contract deterministically we plant a stray ourselves with stdout to
    DEVNULL (no pipe to break) and its own session, then assert the next
    watcher's pre-spawn sweep SIGTERMs it. This tests the load-bearing
    behavior (_sweep_stray_fswatch) without relying on unreproducible
    orphaning.
    """
    return subprocess.Popen(
        ["fswatch", "-0", "-l", "0.1", str(inbox)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


@pytest.mark.skipif(_FSWATCH_OR_PS_MISSING, reason="needs fswatch and ps")
def test_fswatch_stray_swept_on_rearm(tmp_path):
    """A pre-existing fswatch stray on an inbox is SIGTERM-reaped by the next
    watcher on that inbox, before that watcher spawns its own (design §6.2,
    §12.8). The sweep runs after flock + before spawn."""
    _open_inbox(tmp_path, "alice")
    inbox = tmp_path / "alice" / "inbox"  # two-level: <root>/<name>/inbox
    stray = _plant_fswatch_stray(inbox)
    try:
        # Let the stray register in the process table.
        deadline = time.time() + 2.0
        while time.time() < deadline and _count_stray_fswatch(inbox) < 1:
            time.sleep(0.05)
        assert _count_stray_fswatch(inbox) == 1, "planted stray not visible in ps"

        # Run a short finite watch on the same inbox: its pre-spawn sweep must
        # SIGTERM the planted stray. Run to completion so the watcher's own
        # fswatch child is gone too, leaving zero strays.
        proc = _spawn_watch(tmp_path, "alice", max_elapsed=1.0)
        rc, _, stderr = _wait_proc(proc, paranoia_timeout=10.0)
        assert rc == 0, f"stderr={stderr!r}"

        # The planted stray received SIGTERM and exited.
        stray.wait(timeout=5)
        assert stray.poll() is not None, "sweep did not reap the planted stray"
        # No fswatch remains on this inbox (stray reaped, watcher's own gone).
        assert _count_stray_fswatch(inbox) == 0, "stray survived the sweep"
    finally:
        if stray.poll() is None:
            stray.terminate()
            stray.wait(timeout=5)


@pytest.mark.skipif(_FSWATCH_OR_PS_MISSING, reason="needs fswatch and ps")
def test_sweep_spares_fswatch_for_different_inbox(tmp_path):
    """The sweep's str(inbox)-exact predicate reaps the same-inbox stray but
    must NOT kill an fswatch watching a DIFFERENT inbox (design §6.2, §12.8).

    Plant a stray on BOTH alice and bob, then run a watcher on alice: alice's
    stray must be reaped (proves the sweep ran) AND bob's stray must survive
    (proves the predicate is inbox-exact, not 'any fswatch')."""
    _open_inbox(tmp_path, "alice")
    _open_inbox(tmp_path, "bob")
    alice_inbox = tmp_path / "alice" / "inbox"
    bob_inbox = tmp_path / "bob" / "inbox"  # two-level
    alice_stray = _plant_fswatch_stray(alice_inbox)
    bob_stray = _plant_fswatch_stray(bob_inbox)
    try:
        deadline = time.time() + 2.0
        while time.time() < deadline and (
            _count_stray_fswatch(alice_inbox) < 1
            or _count_stray_fswatch(bob_inbox) < 1
        ):
            time.sleep(0.05)
        assert _count_stray_fswatch(alice_inbox) == 1, "alice stray not visible"
        assert _count_stray_fswatch(bob_inbox) == 1, "bob stray not visible"

        # A watcher on ALICE's inbox sweeps. Inbox-exact predicate: reap
        # alice's stray, spare bob's.
        proc = _spawn_watch(tmp_path, "alice", max_elapsed=1.0)
        rc, _, stderr = _wait_proc(proc, paranoia_timeout=10.0)
        assert rc == 0, f"stderr={stderr!r}"

        # alice's planted stray reaped (proves the sweep actually ran).
        alice_stray.wait(timeout=5)
        assert alice_stray.poll() is not None, "alice's stray was not swept"
        assert _count_stray_fswatch(alice_inbox) == 0, "alice stray survived"
        # bob's fswatch must still be alive — the sweep is inbox-exact.
        assert bob_stray.poll() is None, "bob's fswatch was wrongly reaped"
        assert _count_stray_fswatch(bob_inbox) == 1, "bob's stray must survive"
    finally:
        for s in (alice_stray, bob_stray):
            if s.poll() is None:
                s.terminate()
                s.wait(timeout=5)


def test_watch_caps_batch_at_max_batch(tmp_path):
    """--max-batch caps the batch size; overflow stays in inbox for next cycle.

    Pre-seed 7 messages with --max-batch=3. Watcher claims exactly 3 into
    pending/<batch>/, leaves 4 in inbox.
    """
    _open_inbox(tmp_path, "alice")
    msg_ids = [f"msg-cap-{i:03d}" for i in range(7)]
    for mid in msg_ids:
        _drop_inbox_message(tmp_path, "alice", mid, sender="bob", body=mid)

    # We need to pass --max-batch; existing _spawn_watch does not, so build inline.
    proc = subprocess.Popen(
        [
            sys.executable, str(HELPER_PATH),
            "watch", "alice",
            "--max-elapsed", "5.0",
            "--max-batch", "3",
        ],
        env=_watch_env(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        rc, stdout, stderr = _wait_proc(proc, paranoia_timeout=5.0 + 5)
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2.0)

    assert rc == 0, f"stderr={stderr!r}"
    m = re.match(r"^PENDING_BATCH (\S+) count=3$", stdout.strip())
    assert m, f"stdout={stdout!r}"
    batch_id = m.group(1)

    pending_files = sorted(
        p.name for p in (tmp_path / "alice" / "pending" / batch_id).iterdir()
    )
    assert len(pending_files) == 3, f"pending: {pending_files!r}"

    # 4 messages remain in inbox (lex-sortable: the LAST 4 of 7, since
    # _list_inbox returns them sorted and we claim the FIRST max_batch).
    inbox_remaining = sorted(
        p.name for p in (tmp_path / "alice" / "inbox").iterdir()
        if p.is_file() and p.name.endswith(".json") and not p.name.startswith(".")
    )
    assert len(inbox_remaining) == 4, f"inbox remaining: {inbox_remaining!r}"

    # Disjoint: no overlap between claimed and remaining.
    assert set(pending_files).isdisjoint(set(inbox_remaining)), (
        f"overlap: pending={pending_files!r} inbox={inbox_remaining!r}"
    )

    # Union covers all 7.
    all_seen = sorted(pending_files + inbox_remaining)
    expected = sorted(f"{mid}.json" for mid in msg_ids)
    assert all_seen == expected, (
        f"messages lost; expected={expected!r} actual={all_seen!r}"
    )


# ---------------------------------------------------------------------------
# _open_state: slash-command-internal write/clear/read/alive (T4)
#
# Per impl plan §"Task 4" and design §3.5:
#   - State file lives at <bus>/.open/<session-id> (one record per session,
#     not per name; a session opens at most one chain at a time).
#   - JSON payload: {name, agent_id, started_at (UTC ISO8601), output_file}.
#   - `write` requires absolute --output-file. `clear` is idempotent.
#   - `read` prints raw JSON or empty string when absent (exit 0).
#   - `alive`:
#         exit 2 → state file missing or malformed (FAIL-SAFE-DEAD)
#         exit 0 → transcript exists AND mtime < 600s old
#         exit 1 → transcript missing OR mtime ≥ 600s old
#     Stdout is empty on every alive exit (machine-checkable via $? only).
# ---------------------------------------------------------------------------


def _open_state_path(bus: Path, session_id: str) -> Path:
    return bus / ".open" / session_id


def test_open_state_write_atomic(a2a, tmp_path):
    """write creates .open/<sid> with the expected JSON payload."""
    transcript = tmp_path / "fake-transcript.output"
    transcript.write_text("ignored body", encoding="utf-8")

    rc, _, _ = _run(
        a2a,
        "_open_state", "write", "sess-foo", "alice", "agent-xyz",
        "--output-file", str(transcript),
    )
    assert rc == 0

    bus = a2a.bus_dir()
    state_file = _open_state_path(bus, "sess-foo")
    assert state_file.is_file()

    payload = json.loads(state_file.read_text(encoding="utf-8"))
    # started_at is dynamic (clock); construct expected from observed value
    # after parsing it as UTC ISO8601 to round-trip the contract.
    started_at = payload.get("started_at", "")
    parsed = datetime.fromisoformat(started_at)
    assert parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), (
        f"started_at must be UTC ISO8601, got {started_at!r}"
    )

    expected = {
        "name": "alice",
        "agent_id": "agent-xyz",
        "started_at": started_at,
        "output_file": str(transcript),
    }
    assert payload == expected


def test_open_state_write_requires_output_file(a2a):
    """Missing --output-file fails with exit 2 + stderr mentioning the flag."""
    rc, _, stderr = _run(
        a2a, "_open_state", "write", "sess-foo", "alice", "agent-xyz",
    )
    assert rc == 2
    assert "--output-file" in stderr


def test_open_state_write_rejects_relative_output_file(a2a):
    """Relative --output-file path fails with exit 2 + 'must be absolute'."""
    rc, _, stderr = _run(
        a2a,
        "_open_state", "write", "sess-foo", "alice", "agent-xyz",
        "--output-file", "rel/path.output",
    )
    assert rc == 2
    assert "must be absolute" in stderr


def test_open_state_clear_idempotent(a2a, tmp_path):
    """clear is exit-0 when state absent; removes file when present; idempotent."""
    bus = a2a.bus_dir()
    state_file = _open_state_path(bus, "sess-foo")

    # Phase 1: clear with no state file present → exit 0, no error.
    rc, _, stderr = _run(a2a, "_open_state", "clear", "sess-foo")
    assert rc == 0
    assert stderr == ""
    assert not state_file.exists()

    # Phase 2: write then clear → file removed.
    transcript = tmp_path / "t.output"
    transcript.write_text("x", encoding="utf-8")
    rc, _, _ = _run(
        a2a,
        "_open_state", "write", "sess-foo", "alice", "agent-xyz",
        "--output-file", str(transcript),
    )
    assert rc == 0
    assert state_file.is_file()

    rc, _, stderr = _run(a2a, "_open_state", "clear", "sess-foo")
    assert rc == 0
    assert stderr == ""
    assert not state_file.exists()

    # Phase 3: clear again → still exit 0 (idempotent).
    rc, _, stderr = _run(a2a, "_open_state", "clear", "sess-foo")
    assert rc == 0
    assert stderr == ""
    assert not state_file.exists()


def test_open_state_read_missing(a2a, tmp_path):
    """read with no state file: exit 0, stdout empty. With state: exact JSON."""
    # Missing state.
    rc, stdout, stderr = _run(a2a, "_open_state", "read", "sess-foo")
    assert rc == 0
    assert stdout == ""
    assert stderr == ""

    # Write state, then read returns the exact JSON contents.
    transcript = tmp_path / "t.output"
    transcript.write_text("x", encoding="utf-8")
    rc, _, _ = _run(
        a2a,
        "_open_state", "write", "sess-foo", "alice", "agent-xyz",
        "--output-file", str(transcript),
    )
    assert rc == 0

    bus = a2a.bus_dir()
    on_disk = _open_state_path(bus, "sess-foo").read_text(encoding="utf-8")

    rc, stdout, stderr = _run(a2a, "_open_state", "read", "sess-foo")
    assert rc == 0
    assert stdout == on_disk
    assert stderr == ""


def test_open_state_alive_missing_returns_2(a2a):
    """alive with no state file: FAIL-SAFE-DEAD via exit 2, empty stdout."""
    rc, stdout, _ = _run(a2a, "_open_state", "alive", "sess-foo")
    assert rc == 2
    assert stdout == ""


def test_open_state_alive_recent_transcript_returns_0(a2a, tmp_path):
    """alive: state present + transcript mtime < 600s ago → exit 0."""
    transcript = tmp_path / "fresh.output"
    transcript.write_text("x", encoding="utf-8")

    rc, _, _ = _run(
        a2a,
        "_open_state", "write", "sess-foo", "alice", "agent-xyz",
        "--output-file", str(transcript),
    )
    assert rc == 0

    # Fresh mtime (now). os.utime to be explicit; default write was already fresh.
    now = time.time()
    os.utime(str(transcript), (now, now))

    rc, stdout, _ = _run(a2a, "_open_state", "alive", "sess-foo")
    assert rc == 0
    assert stdout == ""


def test_open_state_alive_uses_heartbeat_90s(a2a, tmp_path):
    """alive: output_file = heartbeat path. Fresh -> exit 0; 91s -> exit 1;
    removed -> exit 1; missing state -> exit 2 (design §3.5, §12.4)."""
    hb = tmp_path / ".watcher.heartbeat"
    hb.write_text("", encoding="utf-8")

    rc, _, _ = _run(
        a2a, "_open_state", "write", "sess-hb", "alice", "agent-xyz",
        "--output-file", str(hb),
    )
    assert rc == 0

    now = time.time()
    os.utime(str(hb), (now, now))
    rc, _, _ = _run(a2a, "_open_state", "alive", "sess-hb")
    assert rc == 0, "fresh heartbeat must read ALIVE"

    stale = now - 91.0
    os.utime(str(hb), (stale, stale))
    rc, _, _ = _run(a2a, "_open_state", "alive", "sess-hb")
    assert rc == 1, "91s-stale heartbeat must read DEAD at the 90s window"

    hb.unlink()
    rc, _, _ = _run(a2a, "_open_state", "alive", "sess-hb")
    assert rc == 1, "removed heartbeat must read DEAD"

    rc, _, _ = _run(a2a, "_open_state", "alive", "sess-missing")
    assert rc == 2, "missing state must read 2 (malformed/absent)"


def test_open_state_alive_stale_transcript_returns_1(a2a, tmp_path):
    """alive: 91s-stale heartbeat → exit 1 (DEAD); 60s-stale → exit 0 (ALIVE).
    The pair fences the window to (60, 91) i.e. 90s; the 60s-ALIVE assertion
    FAILS iff the threshold is left at 600 (design §12.9)."""
    hb = tmp_path / "stale.heartbeat"
    hb.write_text("x", encoding="utf-8")

    rc, _, _ = _run(
        a2a,
        "_open_state", "write", "sess-foo", "alice", "agent-xyz",
        "--output-file", str(hb),
    )
    assert rc == 0

    now = time.time()
    # 91s stale -> DEAD at the 90s window.
    stale = now - 91.0
    os.utime(str(hb), (stale, stale))
    rc, stdout, _ = _run(a2a, "_open_state", "alive", "sess-foo")
    assert rc == 1
    assert stdout == ""

    # 60s stale -> ALIVE. This FAILS if the threshold is still 600.
    fresh_ish = now - 60.0
    os.utime(str(hb), (fresh_ish, fresh_ish))
    rc, stdout, _ = _run(a2a, "_open_state", "alive", "sess-foo")
    assert rc == 0
    assert stdout == ""


def test_open_state_alive_missing_transcript_returns_1(a2a, tmp_path):
    """alive: state present but output_file path doesn't exist → exit 1."""
    transcript = tmp_path / "exists-briefly.output"
    transcript.write_text("x", encoding="utf-8")

    rc, _, _ = _run(
        a2a,
        "_open_state", "write", "sess-foo", "alice", "agent-xyz",
        "--output-file", str(transcript),
    )
    assert rc == 0

    # Remove transcript AFTER writing state, so state references a missing path.
    transcript.unlink()

    rc, stdout, _ = _run(a2a, "_open_state", "alive", "sess-foo")
    assert rc == 1
    assert stdout == ""


# ---------------------------------------------------------------------------
# _watcher_kill: probe-gated SIGTERM close helper (T6)
# ---------------------------------------------------------------------------


def test_watcher_kill_lock_free_reports_gone(a2a, tmp_path):
    """No live watcher (lock free or absent) -> WATCHER_GONE, exit 0
    (design §8.1 rows 2-3, §12.7)."""
    _open_inbox(tmp_path, "alice")  # inbox exists, no watcher holding the lock
    rc, stdout, _ = _run(a2a, "_watcher_kill", "alice")
    assert rc == 0
    assert stdout.strip() == "WATCHER_GONE"


@pytest.mark.skipif(shutil.which("python3") is None, reason="needs python3")
def test_watcher_kill_lock_held_sends_sigterm(a2a, tmp_path):
    """A live watch holds the flock -> WATCHER_KILLED <pid>, exit 0, and the
    watcher terminates (design §8.1 row 4, §12.7)."""
    _open_inbox(tmp_path, "alice")
    watcher = _spawn_watch(tmp_path, "alice", max_elapsed=60.0)
    try:
        # Wait until the watcher actually holds the flock (pid written).
        lockfile = tmp_path / "alice" / "inbox" / ".watcher.lock"
        _wait_for_watcher_locked(lockfile, timeout=2.0)
        rc, stdout, _ = _run(a2a, "_watcher_kill", "alice")
        assert rc == 0
        assert re.match(r"^WATCHER_KILLED \d+$", stdout.strip()), stdout
        # The killed pid must be the live watcher's own pid.
        killed_pid = int(stdout.strip().split()[1])
        assert killed_pid == watcher.pid, (
            f"WATCHER_KILLED reported pid={killed_pid}; expected watcher "
            f"pid={watcher.pid}"
        )
        # The watcher's SIGTERM handler exits cleanly.
        watcher.wait(timeout=5)
        assert watcher.poll() is not None
    finally:
        if watcher.poll() is None:
            watcher.kill()
            watcher.wait(timeout=5)


# ---------------------------------------------------------------------------
# Infinite-mode sentinel: _max_elapsed parser (T2)
# ---------------------------------------------------------------------------


def test_max_elapsed_none_skips_recycle_branch(a2a):
    """_max_elapsed parser: 'none' (any case) -> None; numeric -> float;
    <=0 -> ArgumentTypeError; float('inf') is never produced (design §4.1)."""
    assert a2a._max_elapsed("none") is None
    assert a2a._max_elapsed("NONE") is None
    assert a2a._max_elapsed("540") == 540.0
    assert a2a._max_elapsed("0.2") == 0.2

    import argparse as _ap
    for bad in ("0", "-1", "-0.5"):
        with pytest.raises(_ap.ArgumentTypeError):
            a2a._max_elapsed(bad)

    # Sentinel is None, never a numeric magic value.
    assert a2a._max_elapsed("none") is not float("inf")


# ---------------------------------------------------------------------------
# Documentation-vs-implementation pin test
# ---------------------------------------------------------------------------
#
# Guards against drift between SKILL.md prose and the actual fswatch argv in
# cmd_watch. A prior T8 review caught SKILL.md saying ``fswatch -1 inbox/``
# (one-shot mode) when the helper actually invokes ``fswatch -0 -l 0.1`` (a
# long-running NUL-delimited stream with 100ms event coalescing). The two
# operating modes are not interchangeable, and the smoke tests only assert
# the substring "fswatch", which is why the drift slipped through.
#
# This test pins both the source and the docs to the same flag triple so any
# future change to either side without updating the other fails the suite.
# ---------------------------------------------------------------------------


def test_helper_invokes_fswatch_with_documented_flags():
    """SKILL.md prose and cmd_watch source must agree on the fswatch argv.

    The canonical invocation is ``fswatch -0 -l 0.1 <inbox>``:
        -0     NUL-delimited output (so paths with newlines parse cleanly)
        -l 0.1 100ms event-coalescing latency
    Anything else (notably the one-shot ``-1`` mode) is a bug.
    """
    helper_src = HELPER_PATH.read_text(encoding="utf-8")
    skill_md = SKILL_MD_PATH.read_text(encoding="utf-8")

    # (a) Source must contain the exact argv literal in cmd_watch's Popen.
    #     Matches the line: [fswatch_path, "-0", "-l", "0.1", str(inbox)]
    expected_argv_literal = '[fswatch_path, "-0", "-l", "0.1", str(inbox)]'
    assert expected_argv_literal in helper_src, (
        f"cmd_watch fswatch invocation drifted from documented argv. "
        f"Expected literal {expected_argv_literal!r} in helper source."
    )

    # (b) SKILL.md must document the same flags. We assert each flag token is
    #     present in the prose so a reader debugging the watcher sees the
    #     real invocation, not a one-shot ``-1`` placeholder.
    for token in ("-0", "-l", "0.1"):
        assert token in skill_md, (
            f"SKILL.md is missing fswatch flag {token!r}; prose has drifted "
            f"from cmd_watch source. Update SKILL.md to match "
            f"{expected_argv_literal!r}."
        )

    # (c) SKILL.md must NOT describe the watcher with the one-shot ``-1`` flag,
    #     which would imply exit-after-first-event semantics — the opposite
    #     of the actual long-running stream.
    assert "fswatch -1 " not in skill_md, (
        "SKILL.md still describes fswatch with the one-shot ``-1`` flag. "
        "The actual invocation is a long-running stream: ``fswatch -0 -l 0.1``."
    )
