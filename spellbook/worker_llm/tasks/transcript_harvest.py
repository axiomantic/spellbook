"""Distill a long assistant transcript into structured memory candidates.

Output contract: a list of ``Candidate`` records. Empty list when the worker
sees nothing worth capturing (the model returns ``[]``). A malformed response
raises ``WorkerLLMBadResponse`` so callers can fail loudly rather than
silently drop signal.

Both the sync and the async (queue-consumer) entry points go through
``parse_candidates`` so parsing behavior stays identical across the two
paths -- any tolerance tweak (fence stripping, tag coercion) is made in
one place.

See design doc §2.7 and impl plan Task C1.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from spellbook.worker_llm import client, prompts
from spellbook.worker_llm.errors import WorkerLLMBadResponse
from spellbook.worker_llm.queue import WorkerResult

log = logging.getLogger(__name__)


@dataclass
class Candidate:
    """A single memory candidate emitted by the worker.

    ``type`` is one of ``"feedback"`` | ``"project"`` | ``"user"`` |
    ``"reference"``. The task does not enforce this set at parse time —
    downstream consumers validate — so that a future additional type emitted
    by the worker does not force a parse failure here.
    """

    type: str
    content: str
    tags: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)


def transcript_harvest(transcript_text: str) -> list[Candidate]:
    """Extract memory candidates from assistant transcript text.

    Args:
        transcript_text: Raw transcript text (typically the last assistant
            message plus a handful of surrounding turns).

    Returns:
        A list of ``Candidate`` records. Empty when the model returned ``[]``
        or when every item failed shape validation.

    Raises:
        WorkerLLMBadResponse: Response was non-JSON or the top-level JSON
            value was not an array.
        WorkerLLMTimeout, WorkerLLMUnreachable, WorkerLLMNotConfigured:
            Propagated from ``client.call_sync``.
    """
    system, override = prompts.load("transcript_harvest")
    raw = client.call_sync(
        system_prompt=system,
        user_prompt=transcript_text,
        task="transcript_harvest",
        override_loaded=override,
    )
    return parse_candidates(raw)


def parse_candidates(raw: str) -> list[Candidate]:
    """Parse a worker response into a list of ``Candidate`` records.

    Shared by the sync and the queue-consumer paths so parsing tolerance
    (code-fence stripping, type/content required, tag coercion) lives in
    exactly one place.

    Raises:
        WorkerLLMBadResponse: Response was non-JSON or the top-level JSON
            value was not an array.
    """
    try:
        data = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError as e:
        raise WorkerLLMBadResponse(f"transcript_harvest: non-JSON: {e}") from e
    if not isinstance(data, list):
        raise WorkerLLMBadResponse("transcript_harvest: expected JSON array")

    out: list[Candidate] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        t = str(item.get("type", "")).strip()
        c = str(item.get("content", "")).strip()
        if not t or not c:
            continue
        out.append(
            Candidate(
                type=t,
                content=c,
                tags=_as_str_list(item.get("tags")),
                citations=_as_str_list(item.get("citations")),
            )
        )
    return out


def write_candidates_to_memory(
    *,
    namespace: str,
    branch: str,
    candidates: list[Candidate],
    session_id: str = "",
    source: str = "stop_hook",
) -> int:
    """Persist worker-harvested candidates as raw unconsolidated events.

    Extracted helper so both the sync path (future use) and the async
    queue consumer write via the same code, matching the behavior of the
    hook's ``_post_unconsolidated`` endpoint (``/api/memory/unconsolidated``)
    but in-process (we are already inside the daemon here).

    Args:
        namespace: Project-encoded namespace (memory bucket).
        branch: Git branch string (may be empty).
        candidates: Parsed ``Candidate`` records.
        session_id: Optional session id carried through to the raw event.
        source: Label for the ``tool_name`` column (default ``stop_hook``).

    Returns:
        The number of candidates successfully written.
    """
    if not namespace or not candidates:
        return 0
    # Local import: ``log_raw_event`` imports sqlite utilities; deferring
    # keeps the worker-LLM task module cheap to import from the hook
    # subprocess path.
    from spellbook.core.db import get_db_path
    from spellbook.memory.store import log_raw_event

    db_path = str(get_db_path())
    written = 0
    for cand in candidates:
        citations = ",".join(cand.citations)
        combined_tags = ",".join(
            t for t in [
                "self-nominated",
                f"type:{cand.type}",
                ",".join(cand.tags),
            ] if t
        )[:500]
        try:
            log_raw_event(
                db_path=db_path,
                session_id=session_id[:200] if session_id else "",
                project=namespace[:500],
                event_type="memory_candidate",
                tool_name=source[:100],
                subject=citations[:1000],
                summary=cand.content[:5000],
                tags=combined_tags,
                branch=(branch or "")[:200],
            )
            written += 1
        except Exception:  # noqa: BLE001 -- best-effort per candidate
            log.warning(
                "transcript_harvest write_candidates: log_raw_event raised",
                exc_info=True,
            )
    return written


async def async_consumer_callback(result: WorkerResult) -> None:
    """Queue consumer callback for ``task_name == 'transcript_harvest'``.

    Invoked by ``spellbook.worker_llm.queue._consumer_loop`` with a
    ``WorkerResult``. On success, parses the response and writes
    candidates via ``write_candidates_to_memory`` using the
    ``namespace`` / ``branch`` / ``session_id`` supplied in
    ``result.context``. On worker error the callback logs and returns;
    the ``client.call`` path has already published its ``call_failed``
    event so observability is intact.

    Never raises: the consumer isolates callback exceptions, but we
    additionally guard inside to keep the callback's own scope small.
    """
    if result.error is not None:
        log.debug(
            "transcript_harvest async callback: worker error %s",
            type(result.error).__name__,
        )
        return
    try:
        cands = parse_candidates(result.text or "")
    except WorkerLLMBadResponse:
        log.warning(
            "transcript_harvest async callback: bad worker response",
            exc_info=True,
        )
        return
    if not cands:
        return
    ctx = result.context or {}
    namespace = str(ctx.get("namespace", ""))
    branch = str(ctx.get("branch", ""))
    session_id = str(ctx.get("session_id", ""))
    if not namespace:
        log.debug("transcript_harvest async callback: missing namespace; skipping write")
        return
    # ``write_candidates_to_memory`` does sync sqlite writes; offload to
    # a thread so the daemon event loop is not blocked by DB I/O.
    import asyncio as _asyncio
    await _asyncio.to_thread(
        write_candidates_to_memory,
        namespace=namespace,
        branch=branch,
        candidates=cands,
        session_id=session_id,
        source="stop_hook_async",
    )


def _strip_code_fences(text: str) -> str:
    """Tolerate ``` ```json ... ``` ``` wrapping common in 7B models.

    Only the outermost fence is stripped; inner fences (rare) are preserved
    because the JSON decoder will reject them loudly.
    """
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()


def _as_str_list(v: Any) -> list[str]:
    """Coerce tags/citations into a clean list of non-empty strings.

    Accepts ``None`` (returns ``[]``), a comma-separated string, or a list
    of arbitrary scalars. Anything else returns ``[]`` to avoid propagating
    small-model shape drift.
    """
    if v is None:
        return []
    if isinstance(v, str):
        return [p.strip() for p in v.split(",") if p.strip()]
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return []
