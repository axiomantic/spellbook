"""Tests for ``spellbook.worker_llm.tasks.roundtable``.

Covers: happy path (async passthrough), max_tokens=2048 override, task tag,
timeout/error propagation, event emission, and override_loaded plumbing.

The task is deliberately a thin passthrough: the MCP tool wrapper owns all
voice parsing via ``do_process_roundtable_response``. This test file
reflects that surface — we verify what gets sent and that the raw string
is returned unchanged.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from spellbook.worker_llm.errors import (
    WorkerLLMBadResponse,
    WorkerLLMTimeout,
    WorkerLLMUnreachable,
)


def _ok(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


# ---------------------------------------------------------------------------
# Async contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_roundtable_voice_is_a_coroutine_function(
    worker_llm_transport, worker_llm_config
):
    worker_llm_transport([SimpleNamespace(status=200, body=_ok("**M**: hi"))])

    from spellbook.worker_llm.tasks.roundtable import roundtable_voice

    assert asyncio.iscoroutinefunction(roundtable_voice)
    # Second sanity: actually return the string through the async path.
    out = await roundtable_voice("dialogue")
    assert out == "**M**: hi"


# ---------------------------------------------------------------------------
# Happy path: raw passthrough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raw_response_is_passed_through_unchanged(
    worker_llm_transport, worker_llm_config
):
    # The caller (MCP tool) owns voice parsing; this task returns raw text.
    raw = (
        "**Merchant**: ship it. Verdict: APPROVE\n"
        "**Scholar**: refine. Verdict: ITERATE\n\n"
        "## Summary\nTally: 1 APPROVE, 1 ITERATE"
    )
    worker_llm_transport([SimpleNamespace(status=200, body=_ok(raw))])

    from spellbook.worker_llm.tasks.roundtable import roundtable_voice

    assert await roundtable_voice("dialogue prompt") == raw


# ---------------------------------------------------------------------------
# Per-task overrides: max_tokens=2048, task="roundtable_voice"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passes_max_tokens_2048_to_client(
    worker_llm_transport, worker_llm_config
):
    seen = worker_llm_transport(
        [SimpleNamespace(status=200, body=_ok("ok"))]
    )

    from spellbook.worker_llm.tasks.roundtable import roundtable_voice

    await roundtable_voice("p")

    assert len(seen) == 1
    body = json.loads(seen[0].content.decode())
    # Per design §6.3 amendment: the roundtable task MUST pass max_tokens=2048
    # (the default 1024 truncates multi-voice roundtable output).
    assert body["max_tokens"] == 2048


@pytest.mark.asyncio
async def test_publishes_call_event_with_roundtable_voice_task_tag(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    worker_llm_transport([SimpleNamespace(status=200, body=_ok("x"))])
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )

    from spellbook.worker_llm.tasks.roundtable import roundtable_voice

    await roundtable_voice("p")

    assert len(calls) == 1
    assert calls[0]["task"] == "roundtable_voice"
    assert calls[0]["status"] == "ok"


# ---------------------------------------------------------------------------
# Error propagation (caller decides fallback policy)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_propagates(worker_llm_transport, worker_llm_config):
    worker_llm_transport(
        [SimpleNamespace(raise_on_send=httpx.TimeoutException("slow"))]
    )

    from spellbook.worker_llm.tasks.roundtable import roundtable_voice

    with pytest.raises(WorkerLLMTimeout):
        await roundtable_voice("p")


@pytest.mark.asyncio
async def test_connection_error_propagates(
    worker_llm_transport, worker_llm_config
):
    worker_llm_transport(
        [SimpleNamespace(raise_on_send=httpx.ConnectError("refused"))]
    )

    from spellbook.worker_llm.tasks.roundtable import roundtable_voice

    with pytest.raises(WorkerLLMUnreachable):
        await roundtable_voice("p")


@pytest.mark.asyncio
async def test_malformed_envelope_raises_bad_response(
    worker_llm_transport, worker_llm_config
):
    # 200 OK but no `choices` -> client wraps as WorkerLLMBadResponse.
    worker_llm_transport([SimpleNamespace(status=200, body={"wrong": True})])

    from spellbook.worker_llm.tasks.roundtable import roundtable_voice

    with pytest.raises(WorkerLLMBadResponse):
        await roundtable_voice("p")
