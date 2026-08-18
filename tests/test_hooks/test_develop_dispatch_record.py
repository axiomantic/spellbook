"""The Task PostToolUse hook must record dispatches the agent did not author.

The develop skill's phase-verification lists carry items like "Design review
subagent was dispatched". Those were marked ``[SELF]`` because the gate ledger
recorded no dispatches at all -- and a record the AGENT writes is worth little,
since an agent that skips a dispatch will also skip the record, or write it
falsely. The record only becomes evidence when the harness writes it.

Three cases, all proven here rather than reasoned about:

* a ledger exists for the session's cwd -> a ``Task`` PostToolUse payload
  produces a ``dispatches`` entry naming the skills found in the prompt.
* no ledger -> nothing is written, and nothing raises. A hook that records
  unconditionally is noise in every non-develop session.
* no resolvable home directory -> the hook degrades. The ledger CLI REFUSES
  here by design; a hook that raised would take out the whole tool call.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import tripwire

HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402


@pytest.fixture
def dev_dir(tmp_path, monkeypatch):
    d = tmp_path / "dev"
    d.mkdir()
    monkeypatch.setenv("SPELLBOOK_DEV_DIR", str(d))
    return d


_NO_HOME = RuntimeError("no home directory")
_DISK_GONE = OSError("disk gone")


def _task_payload(cwd: str, *, prompt: str = "", description: str = "") -> dict:
    """A PostToolUse payload for a Task call, in the shape the harness sends."""
    return {
        "hook_event_name": "PostToolUse",
        "session_id": "s-1",
        "cwd": cwd,
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "general-purpose",
            "description": description,
            "prompt": prompt,
        },
        "tool_response": {"content": [{"type": "text", "text": "done"}]},
    }


def _dispatch(payload: dict) -> list[str]:
    return spellbook_hook.dispatch(
        payload["hook_event_name"], payload.get("tool_name", ""), payload
    ) or []


def test_task_dispatch_is_recorded_when_a_ledger_exists(dev_dir, tmp_path):
    ledger = dev_dir / "develop_gate_ledger.json"
    ledger.write_text(json.dumps({"current_phase": "2"}), encoding="utf-8")

    _dispatch(
        _task_payload(
            str(tmp_path),
            description="Review the design doc",
            prompt="Invoke the reviewing-design-docs skill on the design document.",
        )
    )

    data = json.loads(ledger.read_text(encoding="utf-8"))
    assert data["current_phase"] == "2", "the merge must not clobber siblings"
    entries = list(data["dispatches"].values())
    assert len(entries) == 1
    entry = entries[0]
    assert entry["skills"] == ["reviewing-design-docs"]
    assert entry["subagent_type"] == "general-purpose"
    assert entry["description"] == "Review the design doc"
    assert entry["source"] == "hook:PostToolUse"
    assert entry["recorded_at"]


def test_prompt_body_is_never_stored(dev_dir, tmp_path):
    """Only recognized skill names are extracted; the prompt is not an artifact."""
    ledger = dev_dir / "develop_gate_ledger.json"
    ledger.write_text("{}", encoding="utf-8")

    _dispatch(
        _task_payload(
            str(tmp_path),
            prompt="test-driven-development. The API token is hunter2-do-not-store.",
        )
    )

    raw = ledger.read_text(encoding="utf-8")
    assert "test-driven-development" in raw
    assert "hunter2" not in raw


def test_two_dispatches_in_the_same_second_both_survive(dev_dir, tmp_path):
    """Parallel waves make same-second dispatches ordinary, not rare."""
    ledger = dev_dir / "develop_gate_ledger.json"
    ledger.write_text("{}", encoding="utf-8")

    for skill in ("dehallucination", "devils-advocate"):
        _dispatch(_task_payload(str(tmp_path), prompt=f"invoke {skill}"))

    entries = list(json.loads(ledger.read_text(encoding="utf-8"))["dispatches"].values())
    assert sorted(s for e in entries for s in e["skills"]) == [
        "dehallucination",
        "devils-advocate",
    ]


def test_non_task_tools_are_not_recorded(dev_dir, tmp_path):
    ledger = dev_dir / "develop_gate_ledger.json"
    ledger.write_text("{}", encoding="utf-8")

    payload = _task_payload(str(tmp_path), prompt="dehallucination")
    payload["tool_name"] = "Read"
    _dispatch(payload)

    assert json.loads(ledger.read_text(encoding="utf-8")) == {}


def test_no_ledger_means_no_record_and_no_crash(dev_dir, tmp_path):
    """Recording every Task call in every session is noise, not evidence."""
    assert not (dev_dir / "develop_gate_ledger.json").exists()

    _dispatch(_task_payload(str(tmp_path), prompt="invoke test-driven-development"))

    assert not (dev_dir / "develop_gate_ledger.json").exists()
    assert list(dev_dir.iterdir()) == []


def test_no_home_directory_does_not_crash_the_hook(monkeypatch, tmp_path):
    """The ledger CLI REFUSES with no home; a raising hook kills the tool call."""
    monkeypatch.delenv("SPELLBOOK_DEV_DIR", raising=False)

    home = tripwire.mock("pathlib:Path.home")
    home.raises(_NO_HOME)

    with tripwire:
        assert _dispatch(_task_payload(str(tmp_path), prompt="dehallucination")) == []

    home.assert_call(args=(), kwargs={}, raised=_NO_HOME)


def test_recording_failure_does_not_propagate(dev_dir, tmp_path):
    """Any unforeseen write failure degrades; the tool call still completes."""
    (dev_dir / "develop_gate_ledger.json").write_text("{}", encoding="utf-8")
    payload = _task_payload(str(tmp_path), prompt="dehallucination")

    record = tripwire.mock("spellbook_hook:_record_develop_dispatch")
    record.raises(_DISK_GONE)
    logged = tripwire.mock("spellbook_hook:_log_hook_error")
    logged.returns(None)

    with tripwire:
        assert _dispatch(payload) == []

    record.assert_call(args=(payload,), kwargs={}, raised=_DISK_GONE)
    logged.assert_call(
        args=("record_develop_dispatch", "PostToolUse", _DISK_GONE),
        kwargs={},
        returned=None,
    )


def test_no_ledger_anywhere_needs_no_repo_root_resolution(monkeypatch, tmp_path):
    """The path is unknowable without git; an empty state dir answers first.

    ``encode_cwd`` spawns ``git worktree list --porcelain`` to resolve the repo
    root, and this runs on every ``Task`` dispatch. When the state directory
    holds no ledger for any project, no resolution can change the answer -- so
    none is performed, and the result is ``None`` rather than the path a git
    probe would have built.

    Deliberately outside a tripwire sandbox: real git must be free to run, so
    that a regression which drops the short circuit produces a Path here
    instead of silently passing on a sandbox error the caller swallows.
    """
    monkeypatch.delenv("SPELLBOOK_DEV_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    assert spellbook_hook._develop_ledger_path(str(tmp_path)) is None


def _seed_state_dir(tmp_path, monkeypatch):
    """A state dir holding a ledger for an unrelated project.

    Enough to get past the "no ledger for ANY project" short circuit, so
    what the tests below observe is the repo-root resolution itself.
    """
    monkeypatch.delenv("SPELLBOOK_DEV_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    state_dir = tmp_path / ".local" / "spellbook"
    state_dir.mkdir(parents=True)
    (state_dir / "develop_gate_ledger-some-other-project.json").write_text(
        "{}", encoding="utf-8"
    )
    return state_dir


def test_a_ledger_for_another_project_still_resolves_the_repo_root(monkeypatch, tmp_path):
    """The short circuit must not block resolution once any ledger exists.

    A linked worktree is the probe because its answer cannot be reached by
    any string rule: the main worktree is NOT an ancestor of the worktree's
    cwd, so a path that keys to it proves resolution actually ran. The
    resolution is a filesystem walk, hence no ``git`` process and no mock;
    ``tests/test_path_utils.py`` is where that walk is held against real git.
    """
    state_dir = _seed_state_dir(tmp_path, monkeypatch)

    repo = tmp_path / "repo"
    (repo / ".git" / "objects").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    git_dir = repo / ".git" / "worktrees" / "wt"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/side\n")
    (git_dir / "commondir").write_text("../..\n")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {git_dir}\n")

    from spellbook.core.path_utils import encode_cwd

    with tripwire:
        path = spellbook_hook._develop_ledger_path(str(worktree))

    expected_key = encode_cwd(str(repo), resolve_git_root=False)
    assert path == state_dir / f"develop_gate_ledger-{expected_key}.json"


def test_resolution_falls_back_to_git_for_a_layout_it_cannot_read(monkeypatch, tmp_path):
    """A bare repository still reaches ``git``, and its answer is still used.

    The filesystem walk answers only the layouts it can prove; a bare repo
    is not one of them (git reports the bare directory itself, and there is
    no ``.git`` entry to walk to). Keeping this path covered matters because
    it is the one that still spawns a process -- an optimization that
    silently swallowed the exotic cases instead of deferring them would look
    identical everywhere else.
    """
    state_dir = _seed_state_dir(tmp_path, monkeypatch)

    bare = tmp_path / "bare.git"
    (bare / "objects").mkdir(parents=True)
    (bare / "HEAD").write_text("ref: refs/heads/main\n")

    tripwire.subprocess.mock_run(
        command=["git", "worktree", "list", "--porcelain"],
        stdout="worktree /repos/thing\n",
    )

    with tripwire:
        path = spellbook_hook._develop_ledger_path(str(bare))

    assert path == state_dir / "develop_gate_ledger-repos-thing.json"
    tripwire.subprocess.assert_run(
        command=["git", "worktree", "list", "--porcelain"],
        returncode=0,
        stdout="worktree /repos/thing\n",
        stderr="",
    )
