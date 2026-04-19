"""Rerank memory-recall candidate hits against a query.

The worker sees ``{"query": ..., "candidates": [{"id", "excerpt"}]}`` and
returns ``[{"id", "relevance_0_1"}]``. We realign the model output against
the caller's input list — missing entries default to ``0.0`` relevance, and
values outside ``[0, 1]`` are clamped so a drifty small model cannot
promote a candidate to 5x its neighbors.

Excerpts are capped at 600 characters upstream (see design doc §14 "600-
char excerpt cap") so the per-call budget stays predictable regardless of
the length of the underlying memory file.

See design doc §2.7 and impl plan Task C2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from spellbook.worker_llm import client, prompts
from spellbook.worker_llm.errors import WorkerLLMBadResponse


@dataclass
class ScoredCandidate:
    """Single reranked candidate.

    ``id`` is the memory path (matches the input ``{"id": ...}``).
    ``relevance`` is ``0.0..1.0`` (clamped; missing entries default to 0.0).
    """

    id: str
    relevance: float


_EXCERPT_CAP = 600


def memory_rerank(query: str, candidates: list[dict]) -> list[ScoredCandidate]:
    """Score each candidate's relevance to ``query``.

    Args:
        query: The user query the caller used for ``memory_recall``.
        candidates: A list of ``{"id": path, "excerpt": str}`` dicts with at
            most 20 items. Excerpts are truncated to 600 chars before being
            sent to the worker.

    Returns:
        A list of ``ScoredCandidate`` aligned to the input order. A candidate
        whose id does not appear in the worker response is assigned
        ``relevance=0.0``.

    Raises:
        WorkerLLMBadResponse: Response was non-JSON or the top-level JSON
            value was not an array.
        WorkerLLMTimeout, WorkerLLMUnreachable, WorkerLLMNotConfigured:
            Propagated from ``client.call_sync``.
    """
    if not candidates:
        # Short-circuit so callers can gate on `feature_enabled` + non-empty
        # input without double-checking, and so empty recalls never cost an
        # LLM round-trip.
        return []

    system, override = prompts.load("memory_rerank")
    user_prompt = json.dumps(
        {
            "query": query,
            "candidates": [
                {"id": c["id"], "excerpt": c["excerpt"][:_EXCERPT_CAP]}
                for c in candidates
            ],
        },
        ensure_ascii=False,
    )
    raw = client.call_sync(
        system_prompt=system,
        user_prompt=user_prompt,
        task="memory_rerank",
        override_loaded=override,
    )

    try:
        data = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError as e:
        raise WorkerLLMBadResponse(f"memory_rerank: non-JSON: {e}") from e
    if not isinstance(data, list):
        raise WorkerLLMBadResponse("memory_rerank: expected JSON array")

    by_id: dict[str, float] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id", ""))
        if not mid:
            continue
        try:
            rel = float(item.get("relevance_0_1", 0.0))
        except (TypeError, ValueError):
            rel = 0.0
        by_id[mid] = max(0.0, min(1.0, rel))

    return [
        ScoredCandidate(id=c["id"], relevance=by_id.get(c["id"], 0.0))
        for c in candidates
    ]


def _strip_code_fences(text: str) -> str:
    """Same helper as transcript_harvest; duplicated to keep modules independent."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    return s.strip()
