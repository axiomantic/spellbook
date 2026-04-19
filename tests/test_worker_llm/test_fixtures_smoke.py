"""Smoke tests for the worker_llm conftest fixtures."""

from __future__ import annotations

import httpx
import pytest


def test_worker_llm_config_returns_deterministic_snapshot(worker_llm_config):
    assert worker_llm_config["worker_llm_base_url"] == "http://test.local/v1"
    assert worker_llm_config["worker_llm_model"] == "test-model"
    assert worker_llm_config["worker_llm_api_key"] == ""
    assert worker_llm_config["worker_llm_timeout_s"] == 2.0
    assert worker_llm_config["worker_llm_max_tokens"] == 64
    assert worker_llm_config["worker_llm_tool_safety_timeout_s"] == 0.5
    assert worker_llm_config["worker_llm_transcript_harvest_mode"] == "replace"
    assert worker_llm_config["worker_llm_allow_prompt_overrides"] is True
    assert worker_llm_config["worker_llm_read_claude_memory"] is False
    assert worker_llm_config["worker_llm_feature_transcript_harvest"] is True
    assert worker_llm_config["worker_llm_feature_roundtable"] is True
    assert worker_llm_config["worker_llm_feature_memory_rerank"] is True
    assert worker_llm_config["worker_llm_feature_tool_safety"] is True
    assert worker_llm_config["worker_llm_safety_cache_ttl_s"] == 300


def test_worker_llm_config_patches_config_get(worker_llm_config):
    from spellbook.core import config as _cfg

    assert _cfg.config_get("worker_llm_model") == "test-model"
    assert _cfg.config_get("worker_llm_base_url") == "http://test.local/v1"
    assert _cfg.config_get("not_a_worker_key") is None


def test_transport_empty_script_returns_empty_request_list(worker_llm_transport):
    seen = worker_llm_transport([])
    assert seen == []


@pytest.mark.asyncio
async def test_transport_replays_scripted_response(worker_llm_transport):
    from types import SimpleNamespace

    seen = worker_llm_transport(
        [SimpleNamespace(status=200, body={"ok": True}, delay_s=0.0, raise_on_send=None)]
    )
    async with httpx.AsyncClient() as http:
        r = await http.post("http://test.local/v1/anything", json={"x": 1})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert len(seen) == 1
    assert str(seen[0].url) == "http://test.local/v1/anything"


@pytest.mark.asyncio
async def test_transport_raises_when_raise_on_send_set(worker_llm_transport):
    from types import SimpleNamespace

    worker_llm_transport(
        [
            SimpleNamespace(
                status=0,
                body="",
                delay_s=0.0,
                raise_on_send=httpx.ConnectError("refused"),
            )
        ]
    )
    with pytest.raises(httpx.ConnectError):
        async with httpx.AsyncClient() as http:
            await http.get("http://test.local/v1/models")


@pytest.mark.asyncio
async def test_transport_raises_when_script_exhausted(worker_llm_transport):
    worker_llm_transport([])
    with pytest.raises(RuntimeError) as excinfo:
        async with httpx.AsyncClient() as http:
            await http.get("http://test.local/v1/models")
    assert str(excinfo.value) == "worker_llm_transport: script exhausted"
