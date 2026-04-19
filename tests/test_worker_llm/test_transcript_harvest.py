"""Tests for ``spellbook.worker_llm.tasks.transcript_harvest``.

Covers: happy path, empty-array short-circuit, code-fence tolerance,
malformed JSON, non-array top-level, skip-malformed-items, tag/citation
coercion, timeout propagation, and event emission.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

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


def test_publishes_call_event_on_success(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    worker_llm_transport([SimpleNamespace(status=200, body=_ok("[]"))])
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )

    from spellbook.worker_llm.tasks.transcript_harvest import transcript_harvest

    transcript_harvest("t")

    assert len(calls) == 1
    assert calls[0]["task"] == "transcript_harvest"
    assert calls[0]["status"] == "ok"
    assert calls[0]["error"] is None


def test_publishes_failed_event_on_bad_response(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    # 200 OK but malformed OpenAI envelope: raises from client, not from task.
    worker_llm_transport([SimpleNamespace(status=200, body={"no_choices": True})])
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )

    from spellbook.worker_llm.tasks.transcript_harvest import transcript_harvest

    with pytest.raises(WorkerLLMBadResponse):
        transcript_harvest("t")

    assert len(calls) == 1
    assert calls[0]["task"] == "transcript_harvest"
    assert calls[0]["status"] == "WorkerLLMBadResponse"
    assert calls[0]["error"] is not None
