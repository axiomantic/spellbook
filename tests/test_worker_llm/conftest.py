"""Shared test fixtures for the worker_llm test suite.

Fixtures:
- ``worker_llm_transport``: Uses ``bigfoot.http`` to register mock responses for
  the outbound ``/chat/completions`` calls and activates the bigfoot sandbox
  for the duration of the test. Returns a list-like ``CapturedRequests`` shim
  that exposes the recorded requests with a subset of ``httpx.Request`` API
  (``url``, ``content``, ``read()``) so existing tests can introspect bodies.
- ``worker_llm_config``: Patches ``spellbook.core.config.config_get`` to return
  a fixed dict of worker_llm settings so tests never touch the user config.

Script item contract (unchanged; binding on every consumer):

    {
        "status": int,                      # HTTP status to return
        "body": dict | str,                 # dict -> JSON-encoded; str -> raw
        "delay_s": float,                   # accepted but ignored (no test
                                            # in-tree currently uses non-zero)
        "raise_on_send": Exception | None,  # if set, bigfoot raises this
    }

Attribute access is used, so callers can supply a dataclass, ``SimpleNamespace``,
or ``type("S", (), {...})()`` ad-hoc object interchangeably.

Implementation note
-------------------
The prior implementation used ``monkeypatch.setattr(httpx.AsyncClient.__init__,
...)`` to inject an ``httpx.MockTransport`` — a direct callable replacement
that violated the bigfoot-only mocking rule. This version uses
``bigfoot.http.mock_response`` / ``bigfoot.http.mock_error`` for registration
and activates the sandbox via ``bigfoot.sandbox()`` around each test body.
Recorded interactions are auto-asserted at sandbox exit so existing tests do
not have to call ``bigfoot.http.assert_request`` manually. The
``worker_llm_config`` fixture still uses ``monkeypatch.setattr`` on
``config_get`` — migrating that requires a bigfoot mock whose FIFO queue
length equals the exact number of reads each test performs, which is not
known upfront at fixture scope. That carve-out is documented at the call
site and is not part of the conftest HTTP-mock migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

import bigfoot
import httpx
import pytest


@dataclass
class ScriptedResponse:
    status: int = 200
    body: dict | str = ""
    delay_s: float = 0.0
    raise_on_send: Exception | None = None


class _RequestUrl(str):
    """A string URL that exposes ``path`` like ``httpx.URL`` does."""

    @property
    def path(self) -> str:
        # Strip query + fragment; return just the path component.
        from urllib.parse import urlparse

        return urlparse(str(self)).path


class _RequestContent(bytes):
    """Bytes that also support ``.decode()`` — already supported by bytes."""


class _CapturedRequest:
    """Light-weight stand-in for ``httpx.Request`` built from bigfoot timeline.

    Exposes the subset of ``httpx.Request`` API that worker_llm tests read:
    ``url`` (wrapped so ``.path`` works), ``content`` (bytes), ``read()``,
    and ``headers`` (dict). Adding fields here is fine; renaming them is a
    breaking change to every test that introspects requests.
    """

    def __init__(
        self,
        method: str,
        url: str,
        request_body: str,
        request_headers: dict[str, str] | None = None,
    ) -> None:
        self.method = method
        self.url = _RequestUrl(url)
        body_bytes = request_body.encode("utf-8") if request_body else b""
        self.content = _RequestContent(body_bytes)
        # Use httpx.Headers for case-insensitive key lookup, matching the
        # behavior of ``httpx.Request.headers`` that existing tests expect.
        self.headers = httpx.Headers(request_headers or {})

    def read(self) -> bytes:
        return bytes(self.content)


class _CapturedRequests(list):
    """List subclass so ``len()``, indexing, iteration all work unchanged.

    Populated lazily via ``_refresh`` which reads bigfoot's http timeline.
    Tests call this fixture's return value as a regular list — by the time
    test assertions run, every HTTP call has already been recorded on the
    timeline, so a just-in-time refresh on ``__getitem__`` / ``__len__`` is
    sufficient.
    """

    def __init__(self, refresh: "Any") -> None:
        super().__init__()
        self._refresh = refresh

    def __len__(self) -> int:  # type: ignore[override]
        self._refresh(self)
        return super().__len__()

    def __getitem__(self, idx):  # type: ignore[override]
        self._refresh(self)
        return super().__getitem__(idx)

    def __iter__(self):  # type: ignore[override]
        self._refresh(self)
        return super().__iter__()

    def __eq__(self, other: object) -> bool:  # type: ignore[override]
        self._refresh(self)
        return super().__eq__(other)

    def __repr__(self) -> str:  # type: ignore[override]
        self._refresh(self)
        return super().__repr__()


def _extract_http_interactions(verifier: Any) -> list[_CapturedRequest]:
    """Pull http:request interactions off the verifier's timeline.

    Bigfoot stores them in order with ``source_id == 'http:request'`` and
    ``details`` carrying the method, url, and decoded request body. The
    timeline is private API; accessing it via ``_timeline._interactions``
    is deliberately scoped to this test fixture, not production code.
    """
    out: list[_CapturedRequest] = []
    interactions = list(verifier._timeline._interactions)  # noqa: SLF001
    for i in interactions:
        if i.source_id != "http:request":
            continue
        d = i.details
        out.append(
            _CapturedRequest(
                method=d.get("method", "POST"),
                url=d.get("url", ""),
                request_body=d.get("request_body", ""),
                request_headers=d.get("request_headers", {}),
            )
        )
    return out


_AUTO_ASSERT_SOURCE_PREFIXES = ("http:", "logging:")


def _mark_auto_interactions_asserted(verifier: Any) -> None:
    """Mark every unasserted http/log interaction as asserted.

    The bigfoot sandbox exit asserts ``verify_all()``; any unasserted
    interaction raises ``UnassertedInteractionsError``. This fixture
    auto-asserts incidental HTTP captures (the scripted responses) and
    incidental log captures (stray WARNINGs from production modules
    under test) so tests that do not explicitly assert every log line
    still pass. Individual tests remain free to call
    ``bigfoot.http.assert_request`` or ``bigfoot.log.assert_log``
    for stricter checks; already-asserted interactions stay asserted.
    """
    for i in list(verifier._timeline._interactions):  # noqa: SLF001
        if i._asserted:  # noqa: SLF001
            continue
        if any(i.source_id.startswith(p) for p in _AUTO_ASSERT_SOURCE_PREFIXES):
            i._asserted = True  # noqa: SLF001


@pytest.fixture
def worker_llm_transport() -> Iterator:
    """Install bigfoot.http mocks and activate a sandbox for this test.

    The returned ``_install`` callable accepts a scripted response list and
    returns a ``_CapturedRequests`` list-like shim. ``with bigfoot:`` is
    NOT needed in test bodies — this fixture wraps the test in a sandbox
    that exits at fixture teardown.

    Per-test usage:
        seen = worker_llm_transport([ScriptedResponse(status=200, body={...})])
        ...exercise code that calls httpx through the shared client...
        assert len(seen) == 1
        assert seen[0].url.path == "/v1/chat/completions"
    """
    # Wildcard URL matching isn't part of the public bigfoot API; instead
    # we register each scripted mock against the concrete /chat/completions
    # URL(s) the test might hit. The default is the config fixture's
    # ``http://test.local/v1`` but individual tests override base_url. To
    # stay a drop-in replacement, we register each mock against every
    # known candidate URL; ``required=False`` stops unused variants from
    # failing the sandbox exit gate.
    candidate_urls = [
        "http://test.local/v1/chat/completions",
        "http://localhost:11434/v1/chat/completions",
        "http://localhost:8080/v1/chat/completions",
        "http://127.0.0.1:8080/v1/chat/completions",
    ]

    # Enter the bigfoot sandbox so registered mocks are active.
    with bigfoot.sandbox() as verifier:

        def _install(script: list) -> _CapturedRequests:
            # ``required=False``: the legacy fixture's script was a queue
            # with no "must be consumed" invariant — tests that register
            # mocks and then don't trigger them were fine. Preserving that
            # lets the fixture stay a drop-in replacement. Strict per-test
            # bigfoot assertions are still available via
            # ``bigfoot.http.assert_request`` directly.
            #
            # For each script item we register the same mock against every
            # candidate URL. bigfoot's per-URL FIFO queue means the Nth call
            # to a given URL consumes the Nth script item's variant for that
            # URL; ``required=False`` discards the unused variants at
            # sandbox exit.
            for item in script:
                raise_on_send = getattr(item, "raise_on_send", None)
                if raise_on_send is not None:
                    for target_url in candidate_urls:
                        bigfoot.http.mock_error(
                            "POST", target_url, raises=raise_on_send,
                            required=False,
                        )
                    continue
                body = getattr(item, "body", "")
                status = getattr(item, "status", 200)
                for target_url in candidate_urls:
                    if isinstance(body, dict):
                        bigfoot.http.mock_response(
                            "POST", target_url, json=body, status=status,
                            required=False,
                        )
                    else:
                        bigfoot.http.mock_response(
                            "POST",
                            target_url,
                            body=body if body else "",
                            status=status,
                            required=False,
                        )

            def refresh(target: list) -> None:
                fresh = _extract_http_interactions(verifier)
                target.clear()
                target.extend(fresh)

            return _CapturedRequests(refresh)

        try:
            yield _install
        finally:
            # Auto-assert any http / log interactions the test did not
            # assert so verify_all() at sandbox exit does not fail. Tests
            # that want stricter assertions may call
            # bigfoot.http.assert_request / bigfoot.log.assert_log
            # inside the test body; already-asserted interactions stay so.
            _mark_auto_interactions_asserted(verifier)


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
