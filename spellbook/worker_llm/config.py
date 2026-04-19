"""Typed config reader for the 14 flat ``worker_llm_*`` keys.

The surrounding codebase stores config as flat keys in ``spellbook.json``
(read via ``spellbook.core.config.config_get``). This module snapshots all
worker-related keys into a single immutable ``WorkerConfig`` so that callers
never re-read half-updated values mid-flight.
"""

from __future__ import annotations

from dataclasses import dataclass

from spellbook.core.config import config_get


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    base_url: str
    model: str
    api_key: str
    timeout_s: float
    max_tokens: int
    tool_safety_timeout_s: float
    transcript_harvest_mode: str        # "replace" | "merge"
    allow_prompt_overrides: bool
    read_claude_memory: bool
    feature_transcript_harvest: bool
    feature_roundtable: bool
    feature_memory_rerank: bool
    feature_tool_safety: bool


def get_worker_config() -> WorkerConfig:
    """Read all 14 keys in one pass and return an immutable snapshot."""
    return WorkerConfig(
        base_url=str(config_get("worker_llm_base_url") or ""),
        model=str(config_get("worker_llm_model") or ""),
        api_key=str(config_get("worker_llm_api_key") or ""),
        timeout_s=float(config_get("worker_llm_timeout_s") or 10.0),
        max_tokens=int(config_get("worker_llm_max_tokens") or 1024),
        tool_safety_timeout_s=float(
            config_get("worker_llm_tool_safety_timeout_s") or 1.5
        ),
        transcript_harvest_mode=str(
            config_get("worker_llm_transcript_harvest_mode") or "replace"
        ),
        allow_prompt_overrides=bool(
            config_get("worker_llm_allow_prompt_overrides")
            if config_get("worker_llm_allow_prompt_overrides") is not None
            else True
        ),
        # Default False: opt-in even when worker LLM is unconfigured; preserves
        # zero behavior change for existing users.
        read_claude_memory=bool(
            config_get("worker_llm_read_claude_memory")
            if config_get("worker_llm_read_claude_memory") is not None
            else False
        ),
        feature_transcript_harvest=bool(
            config_get("worker_llm_feature_transcript_harvest") or False
        ),
        feature_roundtable=bool(
            config_get("worker_llm_feature_roundtable") or False
        ),
        feature_memory_rerank=bool(
            config_get("worker_llm_feature_memory_rerank") or False
        ),
        feature_tool_safety=bool(
            config_get("worker_llm_feature_tool_safety") or False
        ),
    )


def is_configured(cfg: WorkerConfig | None = None) -> bool:
    """Return True iff both base_url and model are non-empty."""
    cfg = cfg or get_worker_config()
    return bool(cfg.base_url and cfg.model)


_FEATURE_ATTRS = {
    "transcript_harvest": "feature_transcript_harvest",
    "roundtable":         "feature_roundtable",
    "memory_rerank":      "feature_memory_rerank",
    "tool_safety":        "feature_tool_safety",
}


def feature_enabled(feature_name: str) -> bool:
    """Return True only if endpoint is configured AND the feature flag is on.

    Raises:
        ValueError: ``feature_name`` not in the known feature set.
    """
    cfg = get_worker_config()
    if not is_configured(cfg):
        return False
    attr = _FEATURE_ATTRS.get(feature_name)
    if attr is None:
        raise ValueError(f"Unknown worker-llm feature: {feature_name}")
    return getattr(cfg, attr)
