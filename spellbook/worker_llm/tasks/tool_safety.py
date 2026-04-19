"""PreToolUse safety judgment for Bash/Write/Edit tool calls.

Returns a ``SafetyVerdict`` of OK / WARN / BLOCK. The worker inspects the
imminent tool call plus the last ~4 KB of transcript context and responds
with a short JSON verdict.

**Fail-open inside the task.** Any failure mode — timeout, connection
error, malformed response, invalid verdict string — returns
``SafetyVerdict(verdict="OK", reasoning="error; fail-open")`` rather than
raising. Two reasons:

1. The PreToolUse hook MUST never block a legitimate user action because
   of a transient worker outage. The fail-open contract lives in ONE
   place (here) instead of being duplicated in every call site.
2. Unknown verdict tokens from drifty small models (``SAFE``,
   ``APPROVE``, empty string) are treated the same as a failure rather
   than propagated — the only verdicts the integration knows how to
   render are OK / WARN / BLOCK.

**SC1 cache integration.** Reads through on entry and writes through on
successful parse. Fail-open results are intentionally NOT cached so a
transient worker outage cannot poison a 5-minute TTL with a bogus OK
verdict that survives the outage.

See design doc §2.7, §4.4, §5.2 and impl plan Task C4.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from spellbook.worker_llm import client, prompts
from spellbook.worker_llm.config import get_worker_config
from spellbook.worker_llm.errors import WorkerLLMError


@dataclass
class SafetyVerdict:
    """Worker LLM verdict on an imminent tool call.

    ``verdict`` is one of ``"OK"`` | ``"WARN"`` | ``"BLOCK"``.
    ``reasoning`` is the short model rationale (or ``"error; fail-open"``
    when the task bailed out on a worker failure).
    """

    verdict: str
    reasoning: str


_VALID_VERDICTS = frozenset({"OK", "WARN", "BLOCK"})
_RECENT_CONTEXT_BYTES = 4000
_FAIL_OPEN = SafetyVerdict(verdict="OK", reasoning="error; fail-open")


def tool_safety(
    tool_name: str, tool_params: dict, recent_context: str
) -> SafetyVerdict:
    """Ask the worker for a safety judgment on an imminent tool call.

    Args:
        tool_name: The name of the tool about to execute (Bash/Write/Edit).
        tool_params: The parameters the tool will receive.
        recent_context: Transcript tail; the last 4000 chars are forwarded.

    Returns:
        A ``SafetyVerdict``. On any worker failure or malformed response,
        returns the fail-open verdict (``OK`` + ``"error; fail-open"``).

    Never raises: every exception path collapses into the fail-open result.
    """
    # Lazy import to avoid a circular reference when safety_cache first
    # imports SafetyVerdict from this module at package-init time.
    from spellbook.worker_llm import safety_cache

    cache_key = safety_cache.make_key(tool_name, tool_params)
    cached = safety_cache.get_cached_verdict(cache_key)
    if cached is not None:
        return cached

    cfg = get_worker_config()
    try:
        system, override = prompts.load("tool_safety")
    except (FileNotFoundError, OSError, ValueError):
        # Packaging bug or unknown task name: still fail open rather than
        # crash the hook.
        return _FAIL_OPEN

    user_prompt = json.dumps(
        {
            "tool_name": tool_name,
            "tool_params": tool_params,
            "recent_context": recent_context[-_RECENT_CONTEXT_BYTES:],
        },
        ensure_ascii=False,
    )

    try:
        raw = client.call_sync(
            system_prompt=system,
            user_prompt=user_prompt,
            max_tokens=256,
            timeout_s=cfg.tool_safety_timeout_s,
            task="tool_safety",
            override_loaded=override,
        )
    except WorkerLLMError:
        return _FAIL_OPEN
    except Exception:
        # Paranoid catch: any unexpected exception must not block the user.
        return _FAIL_OPEN

    verdict = _parse_verdict(raw)
    if verdict is None:
        return _FAIL_OPEN

    safety_cache.cache_verdict(cache_key, verdict)
    return verdict


def _parse_verdict(raw: str) -> SafetyVerdict | None:
    """Parse the worker response into a ``SafetyVerdict`` or ``None`` on drift.

    Returning ``None`` (not raising) lets ``tool_safety`` centralize the
    fail-open handoff in one place.
    """
    try:
        data = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    verdict = str(data.get("verdict", "")).upper()
    if verdict not in _VALID_VERDICTS:
        return None
    return SafetyVerdict(
        verdict=verdict,
        reasoning=str(data.get("reasoning", "")),
    )


def _strip_code_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()
