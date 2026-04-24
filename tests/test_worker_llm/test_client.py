"""Tests for ``spellbook.worker_llm.client``."""

from types import SimpleNamespace

import httpx
import pytest

from spellbook.worker_llm import client
from spellbook.worker_llm.errors import (
    WorkerLLMBadResponse,
    WorkerLLMNotConfigured,
    WorkerLLMTimeout,
    WorkerLLMUnreachable,
)


def _script(status=200, body=None, delay_s=0.0, raise_on_send=None):
    return SimpleNamespace(
        status=status,
        body=body if body is not None else {},
        delay_s=delay_s,
        raise_on_send=raise_on_send,
    )


@pytest.mark.asyncio
async def test_call_happy_path(worker_llm_transport, worker_llm_config, monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )
    requests = worker_llm_transport(
        [
            _script(
                status=200,
                body={"choices": [{"message": {"content": "hello"}}]},
            )
        ]
    )
    out = await client.call("sys", "usr", task="test")
    assert out == "hello"
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/chat/completions"
    assert len(calls) == 1
    assert calls[0]["task"] == "test"
    assert calls[0]["model"] == "test-model"
    assert calls[0]["status"] == "success"
    assert calls[0]["prompt_len"] == len("sys") + len("usr")
    assert calls[0]["response_len"] == len("hello")
    assert calls[0]["error"] is None
    assert calls[0]["override_loaded"] is False


@pytest.mark.asyncio
async def test_call_sends_model_and_messages(worker_llm_transport, worker_llm_config):
    import json

    requests = worker_llm_transport(
        [
            _script(
                status=200,
                body={"choices": [{"message": {"content": "ok"}}]},
            )
        ]
    )
    await client.call("sys-text", "usr-text", task="test", max_tokens=99)
    body = json.loads(requests[0].read())
    assert body == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "sys-text"},
            {"role": "user", "content": "usr-text"},
        ],
        "max_tokens": 99,
        "stream": False,
    }


@pytest.mark.asyncio
async def test_call_unconfigured_raises(monkeypatch):
    from spellbook.core import config as _cfg
    from spellbook.worker_llm import config as _wl_cfg

    monkeypatch.setattr(_cfg, "config_get", lambda k: None)
    monkeypatch.setattr(_wl_cfg, "config_get", lambda k: None)
    with pytest.raises(WorkerLLMNotConfigured) as excinfo:
        await client.call("s", "u", task="test")
    assert str(excinfo.value) == "worker_llm_base_url is not set"


@pytest.mark.asyncio
async def test_call_timeout_raises_timeout(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )
    worker_llm_transport(
        [_script(raise_on_send=httpx.ConnectTimeout("slow"))]
    )
    with pytest.raises(WorkerLLMTimeout) as excinfo:
        await client.call("s", "u", task="test")
    assert str(excinfo.value) == "test timed out after 2.0s"
    assert len(calls) == 1
    assert calls[0]["status"] == "timeout"
    assert calls[0]["error"] == "test timed out after 2.0s"
    assert calls[0]["response_len"] == 0


@pytest.mark.asyncio
async def test_call_5xx_raises_unreachable(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )
    worker_llm_transport([_script(status=503, body="unavailable")])
    with pytest.raises(WorkerLLMUnreachable) as excinfo:
        await client.call("s", "u", task="test")
    assert str(excinfo.value) == "test HTTP 503: unavailable"
    assert len(calls) == 1
    assert calls[0]["status"] == "error"


@pytest.mark.asyncio
async def test_call_4xx_raises_bad_response(worker_llm_transport, worker_llm_config):
    worker_llm_transport([_script(status=400, body="bad req")])
    with pytest.raises(WorkerLLMBadResponse) as excinfo:
        await client.call("s", "u", task="test")
    assert str(excinfo.value) == "test HTTP 400: bad req"


@pytest.mark.asyncio
async def test_call_bad_json_raises_bad_response(
    worker_llm_transport, worker_llm_config
):
    worker_llm_transport([_script(status=200, body="not-json")])
    with pytest.raises(WorkerLLMBadResponse) as excinfo:
        await client.call("s", "u", task="test")
    assert str(excinfo.value).startswith("test malformed response: ")


@pytest.mark.asyncio
async def test_call_missing_choices_raises_bad_response(
    worker_llm_transport, worker_llm_config
):
    worker_llm_transport([_script(status=200, body={"no_choices_here": True})])
    with pytest.raises(WorkerLLMBadResponse):
        await client.call("s", "u", task="test")


@pytest.mark.asyncio
async def test_call_connection_error_raises_unreachable(
    worker_llm_transport, worker_llm_config
):
    worker_llm_transport(
        [_script(raise_on_send=httpx.ConnectError("refused"))]
    )
    with pytest.raises(WorkerLLMUnreachable) as excinfo:
        await client.call("s", "u", task="test")
    assert str(excinfo.value) == "test connect failed: refused"


@pytest.mark.asyncio
async def test_call_sends_bearer_token_when_api_key_set(
    worker_llm_transport, monkeypatch
):
    from spellbook.core import config as _cfg
    from spellbook.worker_llm import config as _wl_cfg

    overrides = {
        "worker_llm_base_url": "http://test.local/v1",
        "worker_llm_model": "test-model",
        "worker_llm_api_key": "secret-token",
        "worker_llm_timeout_s": 2.0,
        "worker_llm_max_tokens": 64,
    }
    fake = lambda k: overrides.get(k)  # noqa: E731
    monkeypatch.setattr(_cfg, "config_get", fake)
    monkeypatch.setattr(_wl_cfg, "config_get", fake)
    requests = worker_llm_transport(
        [_script(status=200, body={"choices": [{"message": {"content": "ok"}}]})]
    )
    await client.call("s", "u", task="test")
    assert requests[0].headers["Authorization"] == "Bearer secret-token"


@pytest.mark.asyncio
async def test_call_omits_bearer_token_when_api_key_empty(
    worker_llm_transport, worker_llm_config
):
    requests = worker_llm_transport(
        [_script(status=200, body={"choices": [{"message": {"content": "ok"}}]})]
    )
    await client.call("s", "u", task="test")
    assert "Authorization" not in requests[0].headers


@pytest.mark.asyncio
async def test_call_publishes_event_on_success(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )
    worker_llm_transport(
        [_script(status=200, body={"choices": [{"message": {"content": "r"}}]})]
    )
    await client.call("s", "u", task="harvest", override_loaded=True)
    assert len(calls) == 1
    assert calls[0]["task"] == "harvest"
    assert calls[0]["override_loaded"] is True
    assert calls[0]["status"] == "success"
    assert calls[0]["response_len"] == 1


# ---------------------------------------------------------------------------
# Canonical status vocabulary (regression: publish_call must receive
# {success, error, timeout, fail_open, dropped} -- NOT "ok" or exception
# class names. Downstream aggregates filter on ``status == "success"`` and
# break silently otherwise.)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_call_uses_canonical_status_on_success(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )
    worker_llm_transport(
        [_script(status=200, body={"choices": [{"message": {"content": "r"}}]})]
    )
    await client.call("s", "u", task="test")
    assert len(calls) == 1
    assert calls[0]["status"] == "success"
    assert calls[0]["error"] is None


@pytest.mark.asyncio
async def test_publish_call_uses_canonical_status_on_timeout(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )
    worker_llm_transport([_script(raise_on_send=httpx.ConnectTimeout("slow"))])
    with pytest.raises(WorkerLLMTimeout):
        await client.call("s", "u", task="test")
    assert len(calls) == 1
    assert calls[0]["status"] == "timeout"
    # Exception class info is preserved via ``error`` -- not swallowed.
    assert calls[0]["error"] is not None


@pytest.mark.asyncio
async def test_publish_call_uses_canonical_status_on_unreachable(
    worker_llm_transport, worker_llm_config, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        "spellbook.worker_llm.client.publish_call",
        lambda **kw: calls.append(kw),
    )
    worker_llm_transport([_script(raise_on_send=httpx.ConnectError("refused"))])
    with pytest.raises(WorkerLLMUnreachable):
        await client.call("s", "u", task="test")
    assert len(calls) == 1
    assert calls[0]["status"] == "error"
    assert calls[0]["error"] is not None


def test_call_sync_runs_asyncio(monkeypatch):
    captured: list = []

    async def fake_call(*args, **kwargs):
        captured.append((args, kwargs))
        return "synchronously-returned"

    monkeypatch.setattr("spellbook.worker_llm.client.call", fake_call)
    out = client.call_sync(
        "sys", "usr", max_tokens=12, timeout_s=3.0, task="t", override_loaded=True
    )
    assert out == "synchronously-returned"
    assert captured == [
        (
            ("sys", "usr"),
            {
                "max_tokens": 12,
                "timeout_s": 3.0,
                "task": "t",
                "override_loaded": True,
            },
        )
    ]


# ---------------------------------------------------------------------------
# Regression: call_sync from inside a running event loop.
#
# Previous impl did ``asyncio.run(_run())`` unconditionally. When a daemon
# path offloads ``call_sync`` to a thread executor that also happens to
# have a running loop on the current thread (e.g. nested loops in certain
# MCP entrypoints), ``asyncio.run`` raises ``RuntimeError: cannot be
# called from a running event loop``. The fix detects a running loop and
# dispatches to a worker thread with its own fresh loop.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_sync_from_running_loop_does_not_raise(monkeypatch):
    """Invoking ``call_sync`` when a loop is running on this thread must not
    raise ``RuntimeError`` about ``asyncio.run`` — it must transparently
    dispatch the coroutine to a worker thread and return the result.
    """
    captured: list = []

    async def fake_call(*args, **kwargs):
        captured.append((args, kwargs))
        return "from-worker-thread"

    monkeypatch.setattr("spellbook.worker_llm.client.call", fake_call)

    # Sanity: the test itself runs in a live event loop (pytest-asyncio).
    # Previously, running ``call_sync`` here raised RuntimeError. After
    # the fix, hop to an executor so the sync wrapper runs on a thread
    # whose current thread also has a running loop reference... except
    # executor threads do NOT inherit the parent's loop. To reproduce
    # the original bug path, invoke ``call_sync`` directly inside the
    # coroutine (the running loop IS on this thread).
    out = client.call_sync(
        "sys", "usr", task="t_running_loop", override_loaded=False
    )
    assert out == "from-worker-thread"
    assert captured == [
        (
            ("sys", "usr"),
            {
                "max_tokens": None,
                "timeout_s": None,
                "task": "t_running_loop",
                "override_loaded": False,
            },
        )
    ]
