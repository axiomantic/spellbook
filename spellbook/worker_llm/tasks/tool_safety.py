"""PreToolUse safety judgment for Bash/Write/Edit tool calls.

Returns a ``SafetyVerdict`` of OK / WARN / BLOCK. The worker inspects the
imminent tool call plus the trailing slice of transcript context and
responds with a short JSON verdict.

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
import logging
from dataclasses import dataclass

from spellbook.worker_llm import client, prompts
from spellbook.worker_llm.config import get_worker_config
from spellbook.worker_llm.errors import WorkerLLMError
from spellbook.worker_llm.events import publish_fail_open

logger = logging.getLogger(__name__)


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
# Transcript tail forwarded to the worker. Safety judgments rarely benefit
# from more than the immediate prior turn -- the 4000-char legacy cap was
# most of the user prompt by volume and the prefill cost dominates wall
# time on a small local model. 1500 chars keeps the "what did the user just
# ask / what was the previous tool call" signal.
_RECENT_CONTEXT_BYTES = 1500
# Cap per-string value inside tool_params before serializing. Bash commands
# express their destructive verb in the first ~100 chars; Edit/Write blobs
# become unbounded when users paste files. Keep head+tail so the shape of
# the mutation is still visible to the model without paying the prefill
# cost of the whole payload. Only applied to the prompt view -- the cache
# key uses the untrimmed params so verdicts remain keyed on true content.
_PARAM_VALUE_CAP = 800
_PARAM_VALUE_HEAD_TAIL = 300
_FAIL_OPEN = SafetyVerdict(verdict="OK", reasoning="error; fail-open")


def _trim_param_value(value: object) -> object:
    """Return a display-only copy of a tool_params value with long strings truncated.

    Non-strings are returned as-is. Strings at or under ``_PARAM_VALUE_CAP``
    are returned unchanged. Longer strings become ``head + elision marker +
    tail`` so the model can still see the start and end of the mutation.
    """
    if not isinstance(value, str):
        return value
    if len(value) <= _PARAM_VALUE_CAP:
        return value
    head = value[:_PARAM_VALUE_HEAD_TAIL]
    tail = value[-_PARAM_VALUE_HEAD_TAIL:]
    elided = len(value) - 2 * _PARAM_VALUE_HEAD_TAIL
    return f"{head} ... [{elided} chars elided] ... {tail}"


def _trim_params_for_prompt(tool_params: dict) -> dict:
    """Shallow copy of ``tool_params`` with oversized string values truncated.

    The original ``tool_params`` is never mutated; it still drives the cache
    key in ``safety_cache.make_key`` so cached verdicts continue to reflect
    the real call, not the trimmed view.
    """
    return {k: _trim_param_value(v) for k, v in tool_params.items()}


def tool_safety(
    tool_name: str, tool_params: dict, recent_context: str
) -> SafetyVerdict:
    """Ask the worker for a safety judgment on an imminent tool call.

    Args:
        tool_name: The name of the tool about to execute (Bash/Write/Edit).
        tool_params: The parameters the tool will receive.
        recent_context: Transcript tail; the last ``_RECENT_CONTEXT_BYTES``
            chars are forwarded. Oversized string values inside
            ``tool_params`` are head/tail-trimmed via
            ``_trim_params_for_prompt`` before serialization; the cache key
            still sees the untrimmed ``tool_params``.

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
    except (FileNotFoundError, OSError, ValueError) as e:
        # Packaging bug or unknown task name: still fail open rather than
        # crash the hook. Emit an explicit fail_open event so this branch
        # is observable — client.call's finally-block event-emit never
        # fires here because we short-circuit before reaching the client.
        publish_fail_open(
            task="tool_safety",
            reason="prompt_load_error",
            error=str(e),
        )
        return _FAIL_OPEN

    user_prompt = json.dumps(
        {
            "tool_name": tool_name,
            "tool_params": _trim_params_for_prompt(tool_params),
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
    except WorkerLLMError as e:
        logger.warning("worker_llm tool_safety failed open: %s", e)
        return _FAIL_OPEN
    except Exception as e:
        # Paranoid catch: any unexpected exception must not block the user.
        logger.warning(
            "worker_llm tool_safety failed open (unexpected %s): %s",
            type(e).__name__,
            e,
        )
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
