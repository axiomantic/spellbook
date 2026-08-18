"""The post-compaction directive must re-load develop discipline mid-run.

A compacted context has lost the ceremony lock, the dispatch table, and the
gate semantics. A develop run that continues without them elides gates while
reporting success -- the silent-failure shape. The hook is the only mechanism
that fires at exactly that moment, so it must say WHERE to re-read from.

Two cases, both proven here rather than reasoned about:

* a ``develop_gate_ledger`` exists for the session's cwd -> the directive
  names the develop skill file.
* no ledger -> the generic post-compact directive only. A hook that fires
  unconditionally is indistinguishable from one that never checks.
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
    """Point the ledger lookup at an empty throwaway directory."""
    d = tmp_path / "dev"
    d.mkdir()
    monkeypatch.setenv("SPELLBOOK_DEV_DIR", str(d))
    return d


def _session_start(cwd: str) -> str:
    payload = spellbook_hook._handle_session_start(
        {"hook_event_name": "SessionStart", "source": "compact", "cwd": cwd}
    )
    assert payload is not None
    return payload["hookSpecificOutput"]["additionalContext"]


def test_directive_names_develop_when_a_ledger_exists(dev_dir, tmp_path):
    (dev_dir / "develop_gate_ledger.json").write_text(
        json.dumps({"current_phase": "4"}), encoding="utf-8"
    )
    context = _session_start(str(tmp_path))
    assert spellbook_hook.POST_COMPACT_FALLBACK_DIRECTIVE in context
    assert "skills/develop/SKILL.md" in context
    assert "develop_gate_ledger" in context


def test_directive_is_silent_about_develop_with_no_ledger(dev_dir, tmp_path):
    context = _session_start(str(tmp_path))
    assert spellbook_hook.POST_COMPACT_FALLBACK_DIRECTIVE in context
    assert "skills/develop" not in context


def test_no_home_directory_does_not_crash_the_hook(monkeypatch, tmp_path):
    """The ledger CLI REFUSES when no home resolves; the hook must not."""
    monkeypatch.delenv("SPELLBOOK_DEV_DIR", raising=False)

    def _no_home():
        raise RuntimeError("no home directory")

    monkeypatch.setattr(Path, "home", staticmethod(_no_home))
    context = _session_start(str(tmp_path))
    assert spellbook_hook.POST_COMPACT_FALLBACK_DIRECTIVE in context
