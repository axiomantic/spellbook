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

    def _no_home():
        raise RuntimeError("no home directory")

    monkeypatch.setattr(Path, "home", staticmethod(_no_home))

    assert _dispatch(_task_payload(str(tmp_path), prompt="dehallucination")) == []


def test_recording_failure_does_not_propagate(dev_dir, tmp_path, monkeypatch):
    """Any unforeseen write failure degrades; the tool call still completes."""
    (dev_dir / "develop_gate_ledger.json").write_text("{}", encoding="utf-8")

    def _boom(*args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr(spellbook_hook, "_record_develop_dispatch", _boom)
    monkeypatch.setattr(spellbook_hook, "_log_hook_error", lambda *a: None)

    assert _dispatch(_task_payload(str(tmp_path), prompt="dehallucination")) == []
