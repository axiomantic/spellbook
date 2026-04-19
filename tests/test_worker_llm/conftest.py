"""Shared test fixtures for the worker_llm test suite.

Fixtures:
- ``worker_llm_transport``: Installs an httpx MockTransport that replays a
  scripted list of responses (one per outbound call). Returns the list of
  captured ``httpx.Request`` objects so tests can assert on URLs and bodies.
- ``worker_llm_config``: Patches ``spellbook.core.config.config_get`` to return
  a fixed dict of worker_llm settings so tests never touch the user config.

Script item contract (binding on every consumer):

    {
        "status": int,                      # HTTP status to return
        "body": dict | str,                 # dict -> JSON-encoded; str -> raw
        "delay_s": float,                   # simulated latency before response
        "raise_on_send": Exception | None,  # if set, raise from transport
    }

Attribute access is used, so callers can supply a dataclass, ``SimpleNamespace``,
or ``type("S", (), {...})()`` ad-hoc object interchangeably.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import httpx
import pytest


@dataclass
class ScriptedResponse:
    status: int = 200
    body: dict | str = ""
    delay_s: float = 0.0
    raise_on_send: Exception | None = None


@pytest.fixture
def worker_llm_transport(monkeypatch):
    """Install an httpx MockTransport and replay a scripted response list.

    Usage:
        seen = worker_llm_transport([ScriptedResponse(status=200, body={...})])
        # ... exercise code that calls httpx.AsyncClient ...
        assert len(seen) == 1
    """

    def _install(script: list) -> list[httpx.Request]:
        seen: list[httpx.Request] = []
        queue = list(script)

        async def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            if not queue:
                raise RuntimeError("worker_llm_transport: script exhausted")
            item = queue.pop(0)
            raise_on_send = getattr(item, "raise_on_send", None)
            if raise_on_send is not None:
                raise raise_on_send
            delay_s = getattr(item, "delay_s", 0.0)
            if delay_s:
                await asyncio.sleep(delay_s)
            body = getattr(item, "body", "")
            if isinstance(body, dict):
                content = json.dumps(body)
            else:
                content = body
            status = getattr(item, "status", 200)
            return httpx.Response(
                status,
                content=content,
                headers={"Content-Type": "application/json"},
            )

        orig_init = httpx.AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            orig_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
        return seen

    return _install


@pytest.fixture
def worker_llm_config(monkeypatch):
    """Patch ``spellbook.core.config.config_get`` with a deterministic snapshot."""
    overrides: dict = {
        "worker_llm_base_url": "http://test.local/v1",
        "worker_llm_model": "test-model",
        "worker_llm_api_key": "",
        "worker_llm_timeout_s": 2.0,
        "worker_llm_max_tokens": 64,
        "worker_llm_tool_safety_timeout_s": 0.5,
        "worker_llm_transcript_harvest_mode": "replace",
        "worker_llm_allow_prompt_overrides": True,
        "worker_llm_read_claude_memory": False,
        "worker_llm_feature_transcript_harvest": True,
        "worker_llm_feature_roundtable": True,
        "worker_llm_feature_memory_rerank": True,
        "worker_llm_feature_tool_safety": True,
        "worker_llm_safety_cache_ttl_s": 300,
    }
    from spellbook.core import config as _cfg
    from spellbook.worker_llm import config as _wl_cfg

    fake = lambda k: overrides.get(k)  # noqa: E731
    monkeypatch.setattr(_cfg, "config_get", fake)
    # ``spellbook.worker_llm.config`` did ``from spellbook.core.config import
    # config_get``, so the name ``config_get`` in that module is a local
    # reference that must be patched separately.
    monkeypatch.setattr(_wl_cfg, "config_get", fake)
    return overrides
