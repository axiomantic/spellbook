"""Tests for spellbook.planlint.registry — Rule, RuleContext, run_rules().

RULES starts empty in this task and is populated one row per rule module in
Tasks 5-11 (each of those tasks Modifies this file to append its own Rule()
entry). This task tests the dispatch mechanism — the per-rule error barrier
and phase filtering — against synthetic dummy rules, not real ones.
"""

import dataclasses
import enum

import pytest
import tripwire

from spellbook.planlint import registry
from spellbook.planlint.document import PlanDocument
from spellbook.planlint.finding import LintResult


class Phase(enum.Enum):
    """A test-only stand-in for the real `api.Phase`, which is Task 12 —
    later in build order than this task. `RuleContext.phase` is typed `object`
    and `run_rules()` only ever does `ctx.phase not in rule.phases`, a
    membership test that works identically against either enum, so this
    stand-in proves the dispatch mechanism is decoupled from `api.Phase`'s
    concrete identity. It STAYS after Task 12 lands; it is not scaffolding."""

    AUTHORING = "authoring"
    REVIEW = "review"
    EXECUTION = "execution"


def _ctx():
    doc = PlanDocument.from_text("**Schema:** planlint-v1\n\n### Task 1: X\n\n**Files:**\n- Create: `x.py`\n")
    return registry.RuleContext(doc=doc, phase=Phase.REVIEW, repo_root=None)


def test_run_rules_returns_empty_when_rules_is_empty():
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns(())
    with tripwire:
        results, crashes = registry.run_rules(_ctx())
    rules_mock.assert_call(args=(), kwargs={})
    assert results == ()
    assert crashes == ()


def test_run_rules_calls_every_rule_in_phase():
    calls = []

    def ok_rule(ctx):
        calls.append(ctx)
        return LintResult(name="ok", findings=[], examined=1)

    dummy = registry.Rule(
        name="dummy", run=ok_rule, emits=frozenset({"dummy-id"}), phases=frozenset(Phase)
    )
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns((dummy,))
    ctx = _ctx()
    with tripwire:
        results, crashes = registry.run_rules(ctx)
    rules_mock.assert_call(args=(), kwargs={})
    assert calls == [ctx]
    assert results == (LintResult(name="ok", findings=[], examined=1),)
    assert crashes == ()


def test_run_rules_skips_a_rule_outside_its_declared_phases():
    def never_called(ctx):
        raise AssertionError("should not be called")

    dummy = registry.Rule(
        name="dummy", run=never_called, emits=frozenset(), phases=frozenset({Phase.EXECUTION})
    )
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns((dummy,))
    ctx = dataclasses.replace(_ctx(), phase=Phase.AUTHORING)
    with tripwire:
        results, crashes = registry.run_rules(ctx)
    rules_mock.assert_call(args=(), kwargs={})
    assert results == ()
    assert crashes == ()


def test_run_rules_barrier_catches_one_rule_crash_without_stopping_others():
    def crashing_rule(ctx):
        raise KeyError("boom")

    def ok_rule(ctx):
        return LintResult(name="ok", findings=[], examined=1)

    crasher = registry.Rule(
        name="crasher", run=crashing_rule, emits=frozenset(), phases=frozenset(Phase)
    )
    survivor = registry.Rule(
        name="survivor", run=ok_rule, emits=frozenset(), phases=frozenset(Phase)
    )
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns((crasher, survivor))
    with tripwire:
        results, crashes = registry.run_rules(_ctx())
    rules_mock.assert_call(args=(), kwargs={})
    assert results == (LintResult(name="ok", findings=[], examined=1),)
    assert len(crashes) == 1
    assert crashes[0].rule == "crasher"
    assert crashes[0].exc_type == "KeyError"
    # KeyError's str() quotes single-arg messages: repr(the arg), not the
    # bare text — str(KeyError("boom")) == "'boom'", not "boom".
    assert crashes[0].message == "'boom'"
    assert crashes[0].traceback_text


def test_run_rules_barrier_does_not_catch_keyboardinterrupt():
    def interrupting_rule(ctx):
        raise KeyboardInterrupt()

    dummy = registry.Rule(
        name="dummy", run=interrupting_rule, emits=frozenset(), phases=frozenset(Phase)
    )
    rules_mock = tripwire.mock("spellbook.planlint.registry:_rules")
    rules_mock.returns((dummy,))
    with tripwire, pytest.raises(KeyboardInterrupt):
        registry.run_rules(_ctx())
    rules_mock.assert_call(args=(), kwargs={})
