"""Async httpx client for OpenAI-compatible ``/v1/chat/completions`` calls.

Single-shot (no retries) by design. Callers are responsible for fail-open or
surface-error policy based on the exception type raised. Every call — success
or failure — emits a ``publish_call`` event in the ``finally`` block.
"""

from __future__ import annotations

import asyncio
import logging
import time
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
    status = "ok"
    response_text = ""
    error: Exception | None = None

    try:
        async with httpx.AsyncClient(timeout=eff_timeout) as http:
            try:
                r = await http.post(url, headers=headers, json=body)
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
        status = type(e).__name__
        error = e
        raise
    finally:
        latency_ms = int((time.monotonic() - started) * 1000)
        publish_call(
            task=task,
            model=cfg.model,
            latency_ms=latency_ms,
            status=status,
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
    """Sync wrapper over ``call``. Safe from sync hook handlers."""
    return asyncio.run(
        call(
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            task=task,
            override_loaded=override_loaded,
        )
    )
