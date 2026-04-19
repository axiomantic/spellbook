"""Tests for ``spellbook.worker_llm.probe``."""

import httpx
import pytest

from spellbook.worker_llm import probe


def _install_transport(monkeypatch, handler):
    orig = httpx.AsyncClient.__init__

    def patched(self, *a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        orig(self, *a, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)


@pytest.mark.asyncio
async def test_probe_one_reachable_returns_models(monkeypatch):
    async def handler(req):
        return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}]})

    _install_transport(monkeypatch, handler)
    ep = await probe._probe_one(11434, "Ollama", 0.5)
    assert ep.reachable is True
    assert ep.label == "Ollama"
    assert ep.base_url == "http://localhost:11434/v1"
    assert ep.models == ["m1", "m2"]
    assert ep.error is None


@pytest.mark.asyncio
async def test_probe_one_http_error_not_reachable(monkeypatch):
    async def handler(req):
        return httpx.Response(503, text="down")

    _install_transport(monkeypatch, handler)
    ep = await probe._probe_one(11434, "Ollama", 0.5)
    assert ep.reachable is False
    assert ep.error == "HTTP 503"
    assert ep.models == []


@pytest.mark.asyncio
async def test_probe_one_exception_records_error(monkeypatch):
    async def handler(req):
        raise httpx.ConnectError("refused")

    _install_transport(monkeypatch, handler)
    ep = await probe._probe_one(11434, "Ollama", 0.5)
    assert ep.reachable is False
    assert ep.error == "ConnectError: refused"
    assert ep.models == []


@pytest.mark.asyncio
async def test_probe_one_filters_blank_model_ids(monkeypatch):
    async def handler(req):
        return httpx.Response(
            200, json={"data": [{"id": "keep"}, {"id": ""}, {"other": "x"}]}
        )

    _install_transport(monkeypatch, handler)
    ep = await probe._probe_one(1234, "LM Studio", 0.5)
    assert ep.reachable is True
    assert ep.models == ["keep"]


@pytest.mark.asyncio
async def test_probe_all_returns_only_reachable_endpoints(monkeypatch):
    async def handler(req):
        if ":1234/" in str(req.url):
            return httpx.Response(200, json={"data": [{"id": "lm-a"}]})
        return httpx.Response(503, text="down")

    _install_transport(monkeypatch, handler)
    eps = await probe.probe_all(timeout_total_s=1.0)
    assert len(eps) == 1
    assert eps[0].label == "LM Studio"
    assert eps[0].base_url == "http://localhost:1234/v1"
    assert eps[0].models == ["lm-a"]


@pytest.mark.asyncio
async def test_probe_all_all_unreachable_returns_empty(monkeypatch):
    async def handler(req):
        raise httpx.ConnectError("refused")

    _install_transport(monkeypatch, handler)
    eps = await probe.probe_all(timeout_total_s=1.0)
    assert eps == []


@pytest.mark.asyncio
async def test_probe_all_returns_multiple_reachable(monkeypatch):
    async def handler(req):
        url = str(req.url)
        if ":11434/" in url:
            return httpx.Response(200, json={"data": [{"id": "ollama-m"}]})
        if ":8000/" in url:
            return httpx.Response(200, json={"data": [{"id": "vllm-m"}]})
        return httpx.Response(503, text="down")

    _install_transport(monkeypatch, handler)
    eps = await probe.probe_all(timeout_total_s=1.0)
    labels = sorted(e.label for e in eps)
    assert labels == ["Ollama", "vLLM"]


def test_common_ports_contains_expected_five():
    assert probe.COMMON_PORTS == [
        (11434, "Ollama"),
        (1234, "LM Studio"),
        (8080, "llama.cpp/mlx"),
        (8000, "vLLM"),
        (4000, "LiteLLM"),
    ]
