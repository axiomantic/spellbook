"""Tests for the PreToolUse security-gate enable/disable resolution.

``hooks.spellbook_hook._gates_disabled`` decides whether the blocking gates
(bash / spawn / workflow-state-sanitize) and the worker-LLM tool-safety sniff
run. The gates are **disabled by default** (opt-in). Resolution order:

1. ``SPELLBOOK_GATES_DISABLED`` env var (set + non-empty): authoritative in
   either direction — ``0``/``false``/``no``/``off`` force gates ON, anything
   else forces them OFF.
2. ``gates-disabled`` flag file in the config dir: forces gates OFF.
3. ``security_gates_enabled`` in spellbook.json: enabled → gates run.
4. Default: disabled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402

# These tests drive the switch directly, so opt out of the conftest
# ``_force_gates_enabled`` fixture that pins the gates on everywhere else.
pytestmark = pytest.mark.gate_killswitch


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Hermetic env for the resolver.

    Points the config dir (flag file) and ``CONFIG_PATH`` (spellbook.json)
    at tmp_path and clears the env var, so ``_gates_disabled`` never reads
    real host state.
    """
    monkeypatch.setenv("SPELLBOOK_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("SPELLBOOK_GATES_DISABLED", raising=False)
    monkeypatch.setattr(spellbook_hook, "CONFIG_PATH", tmp_path / "spellbook.json")
    return tmp_path


def _write_config(tmp_path, enabled):
    (tmp_path / "spellbook.json").write_text(
        json.dumps({"security_gates_enabled": enabled})
    )


# --- default / config -------------------------------------------------------


def test_disabled_by_default(isolated):
    assert spellbook_hook._gates_disabled() is True


def test_config_enabled_runs_gates(isolated):
    _write_config(isolated, True)
    assert spellbook_hook._gates_disabled() is False


def test_config_disabled_keeps_gates_off(isolated):
    _write_config(isolated, False)
    assert spellbook_hook._gates_disabled() is True


# --- env var (authoritative) ------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", "anything"])
def test_env_truthy_disables(monkeypatch, value):
    monkeypatch.setenv("SPELLBOOK_GATES_DISABLED", value)
    assert spellbook_hook._gates_disabled() is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off"])
def test_env_falsy_forces_gates_on(monkeypatch, value):
    monkeypatch.setenv("SPELLBOOK_GATES_DISABLED", value)
    assert spellbook_hook._gates_disabled() is False


def test_env_off_overrides_enabled_config(isolated, monkeypatch):
    _write_config(isolated, True)
    monkeypatch.setenv("SPELLBOOK_GATES_DISABLED", "1")
    assert spellbook_hook._gates_disabled() is True


# --- flag file --------------------------------------------------------------


def test_flag_file_disables_over_enabled_config(isolated):
    _write_config(isolated, True)
    (isolated / "gates-disabled").touch()
    assert spellbook_hook._gates_disabled() is True


def test_env_off_overrides_flag_file(isolated, monkeypatch):
    (isolated / "gates-disabled").touch()
    monkeypatch.setenv("SPELLBOOK_GATES_DISABLED", "0")
    assert spellbook_hook._gates_disabled() is False


# --- dispatch integration ---------------------------------------------------


def test_handle_pre_tool_use_skips_bash_gate_by_default(isolated, monkeypatch):
    """Gates are disabled by default, so the blocking bash gate must not run."""
    called = {"bash": False}
    monkeypatch.setattr(
        spellbook_hook, "_gate_bash", lambda data: called.__setitem__("bash", True)
    )
    monkeypatch.setattr(spellbook_hook, "_record_tool_start", lambda *a, **k: None)
    monkeypatch.setattr(spellbook_hook, "_wl_tool_safety_sniff", lambda *a, **k: None)

    outputs = spellbook_hook._handle_pre_tool_use("Bash", {"tool_input": {}})

    assert called["bash"] is False
    assert outputs == []


def test_handle_pre_tool_use_runs_bash_gate_when_enabled(isolated, monkeypatch):
    """With gates enabled in config, the blocking bash gate runs."""
    _write_config(isolated, True)
    called = {"bash": False}
    monkeypatch.setattr(
        spellbook_hook, "_gate_bash", lambda data: called.__setitem__("bash", True)
    )
    monkeypatch.setattr(spellbook_hook, "_record_tool_start", lambda *a, **k: None)
    monkeypatch.setattr(spellbook_hook, "_wl_tool_safety_sniff", lambda *a, **k: None)

    spellbook_hook._handle_pre_tool_use("Bash", {"tool_input": {}})

    assert called["bash"] is True
