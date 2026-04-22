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
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from spellbook.worker_llm import client, prompts
from spellbook.worker_llm.auth import _load_bearer_token
from spellbook.worker_llm.config import get_worker_config
from spellbook.worker_llm.errors import WorkerLLMError
from spellbook.worker_llm.events import publish_call

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
# Warmup POST timeout. The enqueue POST is best-effort: if the daemon is
# slow, tool_safety must NOT block on it -- the whole point of the warm
# probe is to return fail-open fast. 0.5s is generous for a localhost
# enqueue and still short enough that a hanging daemon cannot wedge the
# PreToolUse hook.
_WARMUP_POST_TIMEOUT_S: float = 0.5
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


def _cold_threshold_s() -> float | None:
    """Return the cold-start threshold (seconds) from config, or ``None``.

    ``None`` disables the warm probe entirely: the configured key must be
    present AND numeric AND > 0 for the probe to fire. Zero / negative /
    missing / non-numeric values all short-circuit to ``None`` so the
    legacy path (always call the worker) is preserved for operators who
    have not opted in.
    """
    from spellbook.core.config import config_get

    raw = config_get("worker_llm_tool_safety_cold_threshold_s")
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if val <= 0:
        return None
    return val


def _trim_param_value(value: object) -> object:
    """Return a display-only copy of a tool_params value with long strings truncated.

    Recurses into ``dict`` and ``list`` structures so nested long strings —
    e.g. the ``Edit`` tool's ``edits: [{old_string, new_string}]`` or the
    ``NotebookEdit`` tool's ``cell_source`` — are truncated regardless of
    nesting depth. Without recursion, only top-level string values would be
    trimmed, and the worker would still prefill the full nested payload.

    Non-string leaves are returned as-is. Strings at or under
    ``_PARAM_VALUE_CAP`` are returned unchanged. Longer strings become
    ``head + elision marker + tail`` so the model can still see the start
    and end of the mutation.
    """
    if isinstance(value, str):
        if len(value) <= _PARAM_VALUE_CAP:
            return value
        head = value[:_PARAM_VALUE_HEAD_TAIL]
        tail = value[-_PARAM_VALUE_HEAD_TAIL:]
        elided = len(value) - 2 * _PARAM_VALUE_HEAD_TAIL
        return f"{head} ... [{elided} chars elided] ... {tail}"
    if isinstance(value, dict):
        return {k: _trim_param_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_trim_param_value(v) for v in value]
    if isinstance(value, tuple):
        # Tuples JSON-serialize as lists; keep the list shape the worker
        # already sees (json.dumps converts tuples to arrays anyway).
        return [_trim_param_value(v) for v in value]
    return value


def _trim_params_for_prompt(tool_params: dict) -> dict:
    """Display-only copy of ``tool_params`` with oversized strings truncated.

    Walks the structure recursively; see ``_trim_param_value``. The original
    ``tool_params`` is never mutated; it still drives the cache key in
    ``safety_cache.make_key`` so cached verdicts continue to reflect the
    real call, not the trimmed view.
    """
    return {k: _trim_param_value(v) for k, v in tool_params.items()}


def _last_success_age_s() -> float | None:
    """Return seconds since the last successful worker-LLM call.

    Reads ``MAX(timestamp) WHERE status='success'`` off the
    ``worker_llm_calls`` table. The query is indexed on ``timestamp`` and
    the table is size-bounded by the purge loop, so this is fast.

    Returns:
        The age in seconds (float) when a success row exists.
        ``None`` when the table is empty OR when the query errors for any
        reason -- the caller treats ``None`` as "cannot tell; assume warm"
        so observability read failures never degrade tool_safety.
    """
    try:
        # Late imports: keep the PreToolUse hot path from paying db-module
        # import cost until the cold-probe actually runs.
        from sqlalchemy import desc, select

        from spellbook.db.engines import get_spellbook_sync_session
        from spellbook.db.spellbook_models import WorkerLLMCall

        with get_spellbook_sync_session() as session:
            ts = session.execute(
                select(WorkerLLMCall.timestamp)
                .where(WorkerLLMCall.status == "success")
                .order_by(desc(WorkerLLMCall.timestamp))
                .limit(1),
            ).scalar_one_or_none()
        if ts is None:
            return None
        last = datetime.fromisoformat(ts)
        # Normalize naive timestamps to UTC so the subtraction is legal.
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - last).total_seconds())
    except Exception:  # noqa: BLE001 -- observability failures must not degrade tool_safety
        logger.debug(
            "tool_safety: _last_success_age_s read failed; treating as warm",
            exc_info=True,
        )
        return None


def _post_warmup_enqueue() -> bool:
    """POST a ``tool_safety_warmup`` task to the daemon enqueue endpoint.

    Best-effort: a short timeout, no retry, return False on any failure.
    When False is returned we still fail-open; the warmup is nice-to-have.
    """
    import urllib.error
    import urllib.request

    host = os.environ.get("SPELLBOOK_MCP_HOST", "127.0.0.1")
    port = os.environ.get("SPELLBOOK_MCP_PORT", "8765")
    host_part = f"[{host}]" if ":" in host else host
    url = f"http://{host_part}:{port}/api/worker-llm/enqueue"
    headers = {"Content-Type": "application/json"}
    token = _load_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(
        {"task_name": "tool_safety_warmup", "prompt": "ping"}
    ).encode()
    try:
        req = urllib.request.Request(
            url, data=body, headers=headers, method="POST",
        )
        with urllib.request.urlopen(req, timeout=_WARMUP_POST_TIMEOUT_S):
            return True
    except Exception:
        # Best-effort warmup: daemon may not be running, the route may be
        # missing, or the network stack may be unhappy. Log at DEBUG so
        # operators investigating a cold-start WARN can correlate, but
        # never surface to the user -- the fail-open verdict handles the
        # caller's UX.
        logger.debug(
            "tool_safety: warmup POST failed; falling back to cold-path",
            exc_info=True,
        )
        return False


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

    # Warm probe: if siesta is likely cold (last successful call older
    # than the threshold), fail open immediately and kick off a
    # background warmup via the async queue. This trades one cold-start
    # PreToolUse judgment for not paying 35-48s of wall time on every
    # Edit/Bash after siesta pauses.
    cold_threshold = _cold_threshold_s()
    age = _last_success_age_s()
    if cold_threshold is not None and age is not None and age > cold_threshold:
        warmup_posted = _post_warmup_enqueue()
        publish_call(
            task="tool_safety",
            model="",
            latency_ms=0,
            status="fail_open",
            prompt_len=0,
            response_len=0,
            error=(
                "cold_start_skipped"
                if warmup_posted
                else "cold_start_skipped; warmup_post_failed"
            ),
        )
        return _FAIL_OPEN

    cfg = get_worker_config()
    try:
        system, override = prompts.load("tool_safety")
    except (FileNotFoundError, OSError, ValueError) as e:
        # Packaging bug or unknown task name: still fail open rather than
        # crash the hook. Emit via the unified publish_call surface with
        # status='fail_open' so this branch lands on the observability
        # dashboard — client.call's finally-block event-emit never fires
        # here because we short-circuit before reaching the client.
        # TODO: Phase 2 subscriber audit
        publish_call(
            task="tool_safety",
            model="",
            latency_ms=0,
            status="fail_open",
            prompt_len=0,
            response_len=0,
            error=f"prompt_load_error: {e}",
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
