"""Distill a long assistant transcript into structured memory candidates.

Output contract: a list of ``Candidate`` records. Empty list when the worker
sees nothing worth capturing (the model returns ``[]``). A malformed response
raises ``WorkerLLMBadResponse`` so callers can fail loudly rather than
silently drop signal.

See design doc §2.7 and impl plan Task C1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from spellbook.worker_llm import client, prompts
from spellbook.worker_llm.errors import WorkerLLMBadResponse


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
