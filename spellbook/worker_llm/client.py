"""Async httpx client for OpenAI-compatible ``/v1/chat/completions`` calls.

Single-shot (no retries) by design. Callers are responsible for fail-open or
surface-error policy based on the exception type raised. Every call — success
or failure — emits a ``publish_call`` event in the ``finally`` block.

Shared client: we cache one ``httpx.AsyncClient`` per running event loop so
HTTP keep-alive actually pools connections across rerank / harvest / tool
safety calls within the same loop. ``call_sync`` uses ``asyncio.run`` which
creates a fresh loop each invocation, so the sync path does not benefit from
pooling — but async callers (roundtable, future daemon integrations) do. The
per-loop cache avoids the classic footgun of binding a client to a loop that
has since been torn down.

Bigfoot's ``http`` plugin intercepts at the transport layer, so shared-client
lifetime does not affect test mocking.
"""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from typing import Any

import httpx

from spellbook.worker_llm.config import get_worker_config, is_configured
from spellbook.worker_llm.errors import (
    WorkerLLMBadResponse,
    WorkerLLMNotConfigured,
    WorkerLLMTimeout,
    WorkerLLMUnreachable,
)
from spellbook.worker_llm.events import publish_call

logger = logging.getLogger(__name__)


def _canonical_status(error: Exception | None) -> str:
    """Translate a call outcome to the canonical status vocabulary.

    The rest of the system (admin metrics in
    ``spellbook.admin.routes.worker_llm``, the threshold notifier in
    ``spellbook.worker_llm.observability``, the warm-probe gate in
    ``spellbook.worker_llm.tasks.tool_safety``, and the publish-route enum
    in ``spellbook.mcp.routes``) assumes the canonical set
    ``{success, error, timeout, fail_open, dropped}``. Emitting raw
    ``"ok"`` or ``type(e).__name__`` silently breaks every downstream
    aggregate because ``status == "success"`` is always False.

    This helper maps:
      - ``None`` (success)                -> ``"success"``
      - ``WorkerLLMTimeout``               -> ``"timeout"``
      - any other exception                -> ``"error"``

    The exception class name is preserved separately via the ``error``
    field on the event payload, so diagnosis information is not lost.
    """
    if error is None:
        return "success"
    if isinstance(error, WorkerLLMTimeout):
        return "timeout"
    return "error"


# Per-event-loop client cache. httpx.AsyncClient holds transport / pool state
# bound to the loop it was first used on; reusing it on a different (or
# closed) loop fails. ``WeakKeyDictionary`` keyed on the loop lets the entry
# drop automatically when the loop is garbage-collected.
_shared_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient]" = (
    weakref.WeakKeyDictionary()
)


def _get_shared_client() -> httpx.AsyncClient:
    """Return (and lazily create) the shared client for the current loop.

    MUST be called from inside a running event loop. Per-request timeouts
    are passed to each ``post`` call; the constructor's ``timeout`` acts as
    a generous upper bound so the client does not impose its own floor.
    """
    loop = asyncio.get_running_loop()
    cli = _shared_clients.get(loop)
    if cli is None or cli.is_closed:
        cli = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        _shared_clients[loop] = cli
    return cli


async def aclose_shared_client() -> None:
    """Close the shared client for the current loop.

    Safe to call during daemon shutdown; a no-op if no client was ever
    created on this loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    cli = _shared_clients.pop(loop, None)
    if cli is not None and not cli.is_closed:
        await cli.aclose()


def close_all_shared_clients_sync() -> None:
    """Close every shared client, including ones bound to non-running loops.

    Wired into the MCP ``atexit`` shutdown path so pooled sockets get closed
    on process exit. Uses ``asyncio.run`` only if the loop is still alive;
    otherwise the client and its transport are dropped — the GC will close
    the underlying sockets.
    """
    for loop, cli in list(_shared_clients.items()):
        if cli.is_closed:
            _shared_clients.pop(loop, None)
            continue
        if loop.is_closed():
            # Loop is gone; we cannot await aclose. Drop the reference and
            # let finalizers clean up.
            _shared_clients.pop(loop, None)
            continue
        try:
            # Best-effort: drive the loop to close the client cleanly.
            if loop.is_running():
                # Another task is driving this loop; schedule the close and
                # move on. We cannot block here.
                asyncio.run_coroutine_threadsafe(cli.aclose(), loop)
            else:
                loop.run_until_complete(cli.aclose())
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "worker_llm: failed to close shared client: %s: %s",
                type(e).__name__,
                e,
            )
        finally:
            _shared_clients.pop(loop, None)


async def call(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
    timeout_s: float | None = None,
    *,
    task: str = "unknown",
    override_loaded: bool = False,
) -> str:
    """Single-shot ``/v1/chat/completions`` call.

    Args:
        system_prompt: System role content.
        user_prompt: User role content.
        max_tokens: Override ``worker_llm_max_tokens`` (default 1024).
        timeout_s: Override ``worker_llm_timeout_s`` (default 10.0). Tool-safety
            integration passes its own short budget.
        task: Observability tag (e.g. ``"transcript_harvest"``).
        override_loaded: True if prompt was loaded from the user override file.

    Returns:
        The assistant message content (``choices[0].message.content``).

    Raises:
        WorkerLLMNotConfigured: ``worker_llm_base_url`` empty.
        WorkerLLMTimeout: Request exceeded timeout.
        WorkerLLMUnreachable: Connection refused / DNS failure / 5xx.
        WorkerLLMBadResponse: 200 OK but schema does not match OpenAI shape.
    """
    cfg = get_worker_config()
    if not is_configured(cfg):
        raise WorkerLLMNotConfigured("worker_llm_base_url is not set")

    eff_timeout = timeout_s if timeout_s is not None else cfg.timeout_s
    eff_max_tokens = max_tokens if max_tokens is not None else cfg.max_tokens

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    body: dict[str, Any] = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": eff_max_tokens,
        "stream": False,
    }

    url = f"{cfg.base_url.rstrip('/')}/chat/completions"
    started = time.monotonic()
    response_text = ""
    error: Exception | None = None

    try:
        http = _get_shared_client()
        try:
            r = await http.post(
                url, headers=headers, json=body, timeout=eff_timeout
            )
        except httpx.TimeoutException as e:
            raise WorkerLLMTimeout(
                f"{task} timed out after {eff_timeout}s"
            ) from e
        except httpx.HTTPError as e:
            raise WorkerLLMUnreachable(f"{task} connect failed: {e}") from e

        if r.status_code >= 500:
            raise WorkerLLMUnreachable(
                f"{task} HTTP {r.status_code}: {r.text[:200]}"
            )
        if r.status_code >= 400:
            raise WorkerLLMBadResponse(
                f"{task} HTTP {r.status_code}: {r.text[:200]}"
            )

        try:
            payload = r.json()
            response_text = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise WorkerLLMBadResponse(
                f"{task} malformed response: {e}"
            ) from e

        if not isinstance(response_text, str):
            raise WorkerLLMBadResponse(f"{task} content not a string")
        return response_text
    except Exception as e:
        error = e
        raise
    finally:
        latency_ms = int((time.monotonic() - started) * 1000)
        publish_call(
            task=task,
            model=cfg.model,
            latency_ms=latency_ms,
            status=_canonical_status(error),
            prompt_len=len(system_prompt) + len(user_prompt),
            response_len=len(response_text),
            error=str(error) if error else None,
            override_loaded=override_loaded,
        )


def call_sync(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
    timeout_s: float | None = None,
    *,
    task: str = "unknown",
    override_loaded: bool = False,
) -> str:
    """Sync wrapper over ``call``. Safe from sync hook handlers.

    ``asyncio.run`` creates and tears down a fresh loop per invocation, so
    the shared client cached inside ``call`` is loop-scoped and closed
    here to release pooled sockets rather than leaking per-call.
    """

    async def _run() -> str:
        try:
            return await call(
                system_prompt,
                user_prompt,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                task=task,
                override_loaded=override_loaded,
            )
        finally:
            await aclose_shared_client()

    return asyncio.run(_run())
