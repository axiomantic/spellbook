"""Tests for the worker_llm exception hierarchy."""

from spellbook.worker_llm.errors import (
    WorkerLLMBadResponse,
    WorkerLLMError,
    WorkerLLMNotConfigured,
    WorkerLLMTimeout,
    WorkerLLMUnreachable,
)


def test_base_class_is_exception():
    assert issubclass(WorkerLLMError, Exception)


def test_all_subclasses_inherit_from_base():
    for cls in (
        WorkerLLMNotConfigured,
        WorkerLLMTimeout,
        WorkerLLMUnreachable,
        WorkerLLMBadResponse,
    ):
        assert issubclass(cls, WorkerLLMError)
        assert issubclass(cls, Exception)


def test_instantiable_with_message():
    e = WorkerLLMTimeout("took too long")
    assert str(e) == "took too long"


def test_not_configured_message_preserved():
    e = WorkerLLMNotConfigured("worker_llm_base_url is not set")
    assert str(e) == "worker_llm_base_url is not set"


def test_unreachable_message_preserved():
    e = WorkerLLMUnreachable("connect refused")
    assert str(e) == "connect refused"


def test_bad_response_message_preserved():
    e = WorkerLLMBadResponse("malformed JSON")
    assert str(e) == "malformed JSON"


def test_all_five_classes_are_distinct():
    classes = {
        WorkerLLMError,
        WorkerLLMNotConfigured,
        WorkerLLMTimeout,
        WorkerLLMUnreachable,
        WorkerLLMBadResponse,
    }
    assert len(classes) == 5
