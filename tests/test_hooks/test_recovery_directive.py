"""Tests for `_build_recovery_directive` in spellbook_hook.py.

These exercise the pure directive-building function directly (not via the
hook subprocess) so we can assert exact-equality against the complete
produced directive string.

Covered:
- Remaining-gates rendering from `develop_gate_ledger` (the strengthened
  post-compaction ceremony re-assertion): checklist items, "DO NOT declare
  done" header, current phase, and plan pointer; plus the absent-ledger
  backward-compatibility case (no remaining-work section, no crash).
- The `decisions_binding` key fix: the live key renders a Binding Decisions
  section; the dead `binding_decisions` key renders nothing.
- The dead `next_action` block is gone: a state carrying `next_action`
  produces no "Next Action" section.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure hooks/ is on sys.path so we can import spellbook_hook directly.
HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402


@pytest.fixture(autouse=True)
def _no_skill_constraints(monkeypatch):
    """Stub `_mcp_call` so skill-constraint fetching is deterministic.

    `_build_recovery_directive` calls `_mcp_call("skill_instructions_get", ...)`
    when an active_skill is present. Without a daemon this would attempt a
    network call. Return a falsy result so no Skill Constraints section is
    appended, making the produced directive fully predictable.
    """
    monkeypatch.setattr(spellbook_hook, "_mcp_call", lambda *args, **kwargs: None)


def test_recovery_directive_renders_remaining_gates():
    """Populated develop_gate_ledger renders the remaining-work ceremony block."""
    state = {
        "active_skill": "develop",
        "skill_phase": "2",
        "develop_gate_ledger": {
            "current_phase": "2",
            "remaining_gates": "design review\ncode review",
            "plan_pointer": "/p.md",
        },
    }

    result = spellbook_hook._build_recovery_directive(state)

    expected = (
        "### Active Skill: develop\n"
        "Phase: 2\n"
        "Resume with: `Skill(skill='develop', --resume 2)`\n"
        "\n### Develop: Remaining Work (DO NOT declare done)\n"
        "Current phase: 2\n"
        "Remaining quality gates — these MUST still run:\n"
        "- [ ] design review\n"
        "- [ ] code review\n"
        "Plan: /p.md"
    )
    assert result == expected


def test_recovery_directive_remaining_gates_precedes_pending_todos():
    """The remaining-work block renders BEFORE the Pending Todos section."""
    state = {
        "develop_gate_ledger": {
            "current_phase": "3",
            "remaining_gates": "green-mirage\ntest suite",
            "plan_pointer": "/plan.md",
        },
        "todos": [
            {"content": "write the thing", "completed": False},
            {"content": "already done", "completed": True},
        ],
    }

    result = spellbook_hook._build_recovery_directive(state)

    expected = (
        "\n### Develop: Remaining Work (DO NOT declare done)\n"
        "Current phase: 3\n"
        "Remaining quality gates — these MUST still run:\n"
        "- [ ] green-mirage\n"
        "- [ ] test suite\n"
        "Plan: /plan.md\n"
        "\n### Pending Todos\n"
        "- [ ] write the thing"
    )
    assert result == expected


def test_recovery_directive_ledger_with_no_remaining_gates():
    """Empty remaining_gates renders the re-verify fallback, not a checklist."""
    state = {
        "develop_gate_ledger": {
            "current_phase": "4",
            "remaining_gates": "",
            "plan_pointer": "/p.md",
        },
    }

    result = spellbook_hook._build_recovery_directive(state)

    expected = (
        "\n### Develop: Remaining Work (DO NOT declare done)\n"
        "Current phase: 4\n"
        "No gates recorded as remaining; re-verify against the plan before finishing.\n"
        "Plan: /p.md"
    )
    assert result == expected


def test_recovery_directive_no_section_when_ledger_absent():
    """Absent develop_gate_ledger renders no remaining-work section and does not crash."""
    state = {
        "active_skill": "debugging",
        "skill_phase": "1",
    }

    result = spellbook_hook._build_recovery_directive(state)

    expected = (
        "### Active Skill: debugging\nPhase: 1\nResume with: `Skill(skill='debugging', --resume 1)`"
    )
    assert result == expected


def test_recovery_directive_empty_state_is_fallback():
    """An empty state produces the no-state fallback (no ledger crash on {})."""
    result = spellbook_hook._build_recovery_directive({})

    assert result == "No active workflow state found."


def test_recovery_directive_reads_decisions_binding():
    """The live `decisions_binding` key renders a Binding Decisions section."""
    state = {"decisions_binding": ["X"]}

    result = spellbook_hook._build_recovery_directive(state)

    expected = "\n### Binding Decisions\n- X"
    assert result == expected


def test_recovery_directive_old_binding_decisions_key_is_dead():
    """The old `binding_decisions` key renders nothing (proves old path dead)."""
    state = {"binding_decisions": ["X"]}

    result = spellbook_hook._build_recovery_directive(state)

    assert result == "No active workflow state found."


def test_recovery_directive_drops_dead_next_action():
    """A state carrying `next_action` produces no Next Action section."""
    state = {"next_action": "do the next thing"}

    result = spellbook_hook._build_recovery_directive(state)

    assert result == "No active workflow state found."
