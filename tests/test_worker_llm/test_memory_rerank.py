"""Tests for ``spellbook.worker_llm.tasks.memory_rerank``.

Covers: happy path, empty-input short-circuit, excerpt truncation at 600
chars, alignment to input order, missing-id defaults to 0.0, relevance
clamping, malformed responses, and event emission.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from spellbook.worker_llm.errors import (
    WorkerLLMBadResponse,
    WorkerLLMTimeout,
)


def _ok(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


# ---------------------------------------------------------------------------
# Short-circuit
# ---------------------------------------------------------------------------


def test_empty_candidates_short_circuits_without_http(
    worker_llm_transport, worker_llm_config
):
    # Install an empty script; the function MUST NOT dispatch any request.
    seen = worker_llm_transport([])
    from spellbook.worker_llm.tasks.memory_rerank import memory_rerank

    assert memory_rerank("q", []) == []
    assert seen == []


# ---------------------------------------------------------------------------
# Happy path + ordering/alignment
# ---------------------------------------------------------------------------


def test_happy_path_returns_scored_candidates_in_input_order(
    worker_llm_transport, worker_llm_config
):
    # Model returns b first, then a — result must preserve input order.
    payload = (
        '[{"id":"b.md","relevance_0_1":0.2},'
        '{"id":"a.md","relevance_0_1":0.8}]'
    )
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(payload))])

    from spellbook.worker_llm.tasks.memory_rerank import (
        ScoredCandidate,
        memory_rerank,
    )

    out = memory_rerank(
        "q",
        [
            {"id": "a.md", "excerpt": "xa"},
            {"id": "b.md", "excerpt": "xb"},
        ],
    )

    assert out == [
        ScoredCandidate(id="a.md", relevance=0.8),
        ScoredCandidate(id="b.md", relevance=0.2),
    ]


def test_missing_id_falls_back_to_ordinal_position(
    worker_llm_transport, worker_llm_config
):
    # Model scores only "a"; "b" is missing, so it falls back to its
    # ordinal position (index 1 of 2 candidates -> 1.0 - 1/2 = 0.5).
    worker_llm_transport(
        [
            SimpleNamespace(
                status=200,
                body=_ok('[{"id":"a.md","relevance_0_1":0.9}]'),
            )
        ]
    )

    from spellbook.worker_llm.tasks.memory_rerank import (
        ScoredCandidate,
        memory_rerank,
    )

    out = memory_rerank(
        "q",
        [{"id": "a.md", "excerpt": ""}, {"id": "b.md", "excerpt": ""}],
    )

    assert out == [
        ScoredCandidate(id="a.md", relevance=0.9),
        ScoredCandidate(id="b.md", relevance=0.5),
    ]


def test_missing_ids_preserve_qmd_ordinal_rank(
    worker_llm_transport, worker_llm_config
):
    # Three candidates in QMD-ranked order; worker scores only the middle
    # one. First and last must fall back to 1.0 - i/N so the upstream
    # ranking is preserved rather than pushing omissions to the bottom.
    worker_llm_transport(
        [
            SimpleNamespace(
                status=200,
                body=_ok('[{"id":"b.md","relevance_0_1":0.42}]'),
            )
        ]
    )

    from spellbook.worker_llm.tasks.memory_rerank import (
        ScoredCandidate,
        memory_rerank,
    )

    out = memory_rerank(
        "q",
        [
            {"id": "a.md", "excerpt": ""},
            {"id": "b.md", "excerpt": ""},
            {"id": "c.md", "excerpt": ""},
        ],
    )

    assert out[0] == ScoredCandidate(id="a.md", relevance=1.0)
    assert out[1] == ScoredCandidate(id="b.md", relevance=0.42)
    assert out[2].id == "c.md"
    assert out[2].relevance == pytest.approx(1.0 - 2 / 3)


def test_relevance_clamped_to_unit_interval(
    worker_llm_transport, worker_llm_config
):
    payload = (
        '[{"id":"hi.md","relevance_0_1":5.5},'
        '{"id":"lo.md","relevance_0_1":-2.0}]'
    )
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(payload))])

    from spellbook.worker_llm.tasks.memory_rerank import (
        ScoredCandidate,
        memory_rerank,
    )

    out = memory_rerank(
        "q",
        [{"id": "hi.md", "excerpt": ""}, {"id": "lo.md", "excerpt": ""}],
    )

    assert out == [
        ScoredCandidate(id="hi.md", relevance=1.0),
        ScoredCandidate(id="lo.md", relevance=0.0),
    ]


def test_relevance_non_numeric_defaults_to_zero(
    worker_llm_transport, worker_llm_config
):
    payload = '[{"id":"a.md","relevance_0_1":"nope"}]'
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(payload))])

    from spellbook.worker_llm.tasks.memory_rerank import (
        ScoredCandidate,
        memory_rerank,
    )

    out = memory_rerank("q", [{"id": "a.md", "excerpt": ""}])
    assert out == [ScoredCandidate(id="a.md", relevance=0.0)]


# ---------------------------------------------------------------------------
# Budget: excerpt truncation
# ---------------------------------------------------------------------------


def test_excerpt_truncated_to_600_chars(
    worker_llm_transport, worker_llm_config
):
    seen = worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok("[]"))]
    )

    long_excerpt = "a" * 1000
    from spellbook.worker_llm.tasks.memory_rerank import memory_rerank

    memory_rerank("q", [{"id": "a.md", "excerpt": long_excerpt}])

    assert len(seen) == 1
    body = json.loads(seen[0].content.decode())
    user_msg = body["messages"][1]["content"]
    payload = json.loads(user_msg)
    assert payload["query"] == "q"
    assert len(payload["candidates"]) == 1
    assert payload["candidates"][0]["id"] == "a.md"
    assert payload["candidates"][0]["excerpt"] == "a" * 600


# ---------------------------------------------------------------------------
# Malformed responses
# ---------------------------------------------------------------------------


def test_non_json_raises_bad_response(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok("prose not json"))]
    )

    from spellbook.worker_llm.tasks.memory_rerank import memory_rerank

    with pytest.raises(WorkerLLMBadResponse, match="memory_rerank: non-JSON"):
        memory_rerank("q", [{"id": "a.md", "excerpt": ""}])


def test_json_object_not_array_raises(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok('{"id":"a.md"}'))]
    )

    from spellbook.worker_llm.tasks.memory_rerank import memory_rerank

    with pytest.raises(WorkerLLMBadResponse, match="expected JSON array"):
        memory_rerank("q", [{"id": "a.md", "excerpt": ""}])


def test_code_fenced_response_parses(worker_llm_transport, worker_llm_config):
    fenced = '```json\n[{"id":"a.md","relevance_0_1":0.4}]\n```'
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(fenced))])

    from spellbook.worker_llm.tasks.memory_rerank import (
        ScoredCandidate,
        memory_rerank,
    )

    assert memory_rerank("q", [{"id": "a.md", "excerpt": ""}]) == [
        ScoredCandidate(id="a.md", relevance=0.4)
    ]


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


def test_timeout_propagates(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [SimpleNamespace(raise_on_send=httpx.TimeoutException("boom"))]
    )

    from spellbook.worker_llm.tasks.memory_rerank import memory_rerank

    with pytest.raises(WorkerLLMTimeout):
        memory_rerank("q", [{"id": "a.md", "excerpt": ""}])


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


def test_publishes_call_event_with_task_tag(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok("[]"))]
    )
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )

    from spellbook.worker_llm.tasks.memory_rerank import memory_rerank

    memory_rerank("q", [{"id": "a.md", "excerpt": "e"}])

    assert len(calls) == 1
    assert calls[0]["task"] == "memory_rerank"
    assert calls[0]["status"] == "ok"
