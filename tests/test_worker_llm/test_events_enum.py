"""Tests for the ``Subsystem.WORKER_LLM`` addition and daemon marker."""

from spellbook.admin.events import Subsystem, event_bus


def test_worker_llm_subsystem_value():
    assert Subsystem.WORKER_LLM.value == "worker_llm"


def test_worker_llm_subsystem_is_member():
    assert Subsystem("worker_llm") is Subsystem.WORKER_LLM


def test_event_bus_has_in_daemon_flag():
    assert hasattr(event_bus, "_in_daemon")


def test_event_bus_in_daemon_defaults_false_outside_daemon():
    # Tests run outside the daemon process, so the marker must be False.
    assert event_bus._in_daemon is False
