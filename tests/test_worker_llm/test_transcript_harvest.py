"""Tests for ``spellbook.worker_llm.tasks.transcript_harvest``.

Covers: happy path, empty-array short-circuit, code-fence tolerance,
malformed JSON, non-array top-level, skip-malformed-items, tag/citation
coercion, timeout propagation, and event emission.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from spellbook.worker_llm.errors import (
    WorkerLLMBadResponse,
    WorkerLLMTimeout,
)


def _ok(content: str) -> dict:
    """Wrap ``content`` in an OpenAI-compatible chat-completion envelope."""
    return {
        "choices": [{"message": {"content": content}}],
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_parses_candidates(worker_llm_transport, worker_llm_config):
    payload = (
        '[{"type":"feedback","content":"c1","tags":["x","y"],'
        '"citations":["p:1"]},'
        '{"type":"project","content":"c2"}]'
    )
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(payload))])

    from spellbook.worker_llm.tasks.transcript_harvest import (
        Candidate,
        transcript_harvest,
    )

    out = transcript_harvest("some transcript text")

    assert out == [
        Candidate(
            type="feedback",
            content="c1",
            tags=["x", "y"],
            citations=["p:1"],
        ),
        Candidate(type="project", content="c2", tags=[], citations=[]),
    ]


def test_empty_array_returns_empty_list(worker_llm_transport, worker_llm_config):
    worker_llm_transport([SimpleNamespace(status=200, body=_ok("[]"))])

    from spellbook.worker_llm.tasks.transcript_harvest import transcript_harvest

    assert transcript_harvest("nothing durable here") == []


# ---------------------------------------------------------------------------
# Robustness (small-model shapes)
# ---------------------------------------------------------------------------


def test_strips_code_fences(worker_llm_transport, worker_llm_config):
    fenced = '```json\n[{"type":"user","content":"hello"}]\n```'
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(fenced))])

    from spellbook.worker_llm.tasks.transcript_harvest import (
        Candidate,
        transcript_harvest,
    )

    assert transcript_harvest("t") == [
        Candidate(type="user", content="hello", tags=[], citations=[])
    ]


def test_tags_string_coerced_to_list(worker_llm_transport, worker_llm_config):
    payload = '[{"type":"user","content":"c","tags":"a, b , , c"}]'
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(payload))])

    from spellbook.worker_llm.tasks.transcript_harvest import transcript_harvest

    out = transcript_harvest("t")
    assert out[0].tags == ["a", "b", "c"]


def test_skips_item_without_type_or_content(
    worker_llm_transport, worker_llm_config
):
    payload = (
        '[{"type":"","content":"c"},'
        '{"type":"feedback","content":""},'
        '{"type":"user","content":"keep"}]'
    )
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(payload))])

    from spellbook.worker_llm.tasks.transcript_harvest import (
        Candidate,
        transcript_harvest,
    )

    assert transcript_harvest("t") == [
        Candidate(type="user", content="keep", tags=[], citations=[])
    ]


def test_skips_non_dict_items(worker_llm_transport, worker_llm_config):
    payload = '["not-a-dict", 42, {"type":"user","content":"ok"}]'
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(payload))])

    from spellbook.worker_llm.tasks.transcript_harvest import (
        Candidate,
        transcript_harvest,
    )

    assert transcript_harvest("t") == [
        Candidate(type="user", content="ok", tags=[], citations=[])
    ]


# ---------------------------------------------------------------------------
# Malformed responses
# ---------------------------------------------------------------------------


def test_non_json_raises_bad_response(worker_llm_transport, worker_llm_config):
    worker_llm_transport([SimpleNamespace(status=200, body=_ok("definitely not json"))])

    from spellbook.worker_llm.tasks.transcript_harvest import transcript_harvest

    with pytest.raises(WorkerLLMBadResponse, match="transcript_harvest: non-JSON"):
        transcript_harvest("t")


def test_json_object_not_array_raises(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok('{"type":"user","content":"x"}'))]
    )

    from spellbook.worker_llm.tasks.transcript_harvest import transcript_harvest

    with pytest.raises(WorkerLLMBadResponse, match="expected JSON array"):
        transcript_harvest("t")


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


def test_timeout_propagates(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [
            SimpleNamespace(
                raise_on_send=httpx.TimeoutException("boom"),
            )
        ]
    )

    from spellbook.worker_llm.tasks.transcript_harvest import transcript_harvest

    with pytest.raises(WorkerLLMTimeout):
        transcript_harvest("t")


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


# The worker_llm_transport fixture owns the tripwire sandbox for each
# test (registering mocks must happen before sandbox entry, which our
# fixture does up front). Registering ``tripwire.mock(...).calls(fn)``
# from test bodies after the sandbox is already active fails the
# sandbox exit gate. These tests therefore still use ``monkeypatch`` to
# replace the module-scoped ``publish_call`` binding — a carve-out
# limited to this observability assertion pattern.


def test_publishes_call_event_on_success(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    worker_llm_transport([SimpleNamespace(status=200, body=_ok("[]"))])
    calls: list = []
    # Intentional monkeypatch on a callable: see file comment above about
    # fixture-managed sandbox ordering.
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )

    from spellbook.worker_llm.tasks.transcript_harvest import transcript_harvest

    transcript_harvest("t")

    assert len(calls) == 1
    assert calls[0]["task"] == "transcript_harvest"
    assert calls[0]["status"] == "success"
    assert calls[0]["error"] is None


def test_publishes_failed_event_on_bad_response(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    # 200 OK but malformed OpenAI envelope: raises from client, not from task.
    worker_llm_transport([SimpleNamespace(status=200, body={"no_choices": True})])
    calls: list = []
    # Intentional monkeypatch on a callable: same rationale as the test above.
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )

    from spellbook.worker_llm.tasks.transcript_harvest import transcript_harvest

    with pytest.raises(WorkerLLMBadResponse):
        transcript_harvest("t")

    assert len(calls) == 1
    assert calls[0]["task"] == "transcript_harvest"
    assert calls[0]["status"] == "error"
    assert calls[0]["error"] is not None


# ---------------------------------------------------------------------------
# Async consumer callback (queue path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_callback_parses_and_writes_candidates(monkeypatch):
    """On success, the consumer callback parses the response and writes
    candidates via ``write_candidates_to_memory``."""
    from spellbook.worker_llm import queue as _queue
    from spellbook.worker_llm.tasks import transcript_harvest as th

    writes: list[dict] = []

    def fake_write(
        *, namespace, branch, candidates, session_id="", source="stop_hook"
    ):
        writes.append(
            {
                "namespace": namespace,
                "branch": branch,
                "candidates": list(candidates),
                "session_id": session_id,
                "source": source,
            }
        )
        return len(candidates)

    monkeypatch.setattr(th, "write_candidates_to_memory", fake_write)

    result = _queue.WorkerResult(
        task_name="transcript_harvest",
        text='[{"type":"user","content":"remember X"}]',
        context={
            "namespace": "Users-test-proj",
            "branch": "main",
            "session_id": "sess-1",
        },
    )

    await th.async_consumer_callback(result)

    assert len(writes) == 1
    w = writes[0]
    assert w["namespace"] == "Users-test-proj"
    assert w["branch"] == "main"
    assert w["session_id"] == "sess-1"
    assert w["source"] == "stop_hook_async"
    assert len(w["candidates"]) == 1
    assert w["candidates"][0].content == "remember X"


@pytest.mark.asyncio
async def test_async_callback_ignores_worker_errors(monkeypatch):
    """A ``WorkerResult`` with ``error`` set never writes candidates."""
    from spellbook.worker_llm import queue as _queue
    from spellbook.worker_llm.tasks import transcript_harvest as th

    calls: list = []
    monkeypatch.setattr(
        th, "write_candidates_to_memory", lambda **kw: calls.append(kw) or 0
    )

    result = _queue.WorkerResult(
        task_name="transcript_harvest",
        error=RuntimeError("boom"),
        context={"namespace": "ns"},
    )

    await th.async_consumer_callback(result)
    assert calls == []


@pytest.mark.asyncio
async def test_async_callback_skips_when_namespace_missing(monkeypatch):
    """Without a namespace we cannot route the write; skip rather than guess."""
    from spellbook.worker_llm import queue as _queue
    from spellbook.worker_llm.tasks import transcript_harvest as th

    calls: list = []
    monkeypatch.setattr(
        th, "write_candidates_to_memory", lambda **kw: calls.append(kw) or 0
    )

    result = _queue.WorkerResult(
        task_name="transcript_harvest",
        text='[{"type":"user","content":"c"}]',
        context={},  # no namespace
    )

    await th.async_consumer_callback(result)
    assert calls == []


@pytest.mark.asyncio
async def test_async_callback_swallows_bad_worker_response(monkeypatch):
    """A malformed response logs and returns without raising."""
    from spellbook.worker_llm import queue as _queue
    from spellbook.worker_llm.tasks import transcript_harvest as th

    calls: list = []
    monkeypatch.setattr(
        th, "write_candidates_to_memory", lambda **kw: calls.append(kw) or 0
    )

    result = _queue.WorkerResult(
        task_name="transcript_harvest",
        text="definitely not json",
        context={"namespace": "ns"},
    )

    await th.async_consumer_callback(result)
    assert calls == []


# ---------------------------------------------------------------------------
# parse_candidates is shared across sync + async paths
# ---------------------------------------------------------------------------


def test_parse_candidates_shared_parser():
    from spellbook.worker_llm.tasks.transcript_harvest import (
        Candidate,
        parse_candidates,
    )

    raw = '[{"type":"feedback","content":"c"}]'
    assert parse_candidates(raw) == [
        Candidate(type="feedback", content="c", tags=[], citations=[])
    ]
