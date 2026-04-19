"""QMD search adapter for the file-based memory system.

Provides hybrid search (BM25 + vector + LLM re-ranking) via the QMD CLI.
QMD is a hard dependency; callers must ensure_memory_system_available()
before invoking these functions.

QMD is accessed via CLI subprocess, NOT via MCP-to-MCP.
"""

import hashlib
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass

from spellbook.memory.models import MemoryResult
from spellbook.memory.scoring import compute_score

logger = logging.getLogger(__name__)


@dataclass
class QmdResult:
    """A single result from a QMD search."""

    path: str
    score: float
    snippet: str = ""


def _parse_qmd_results(stdout: str) -> list[QmdResult]:
    """Parse JSON output from QMD CLI into QmdResult list."""
    data = json.loads(stdout)
    results: list[QmdResult] = []
    for item in data:
        results.append(
            QmdResult(
                path=item.get("path", ""),
                score=item.get("score", 0.0),
                snippet=item.get("snippet", ""),
            )
        )
    return results


def qmd_search(
    query: str,
    collections: list[str] | None = None,
    limit: int = 10,
) -> list[QmdResult]:
    """Run BM25-only search via qmd CLI.

    Args:
        query: Search text.
        collections: Optional list of QMD collection names to search.
        limit: Maximum results.

    Returns:
        List of QmdResult.

    Raises:
        subprocess.CalledProcessError: If qmd subprocess fails.
        subprocess.TimeoutExpired: If qmd times out.
        OSError: If qmd cannot be executed.
        json.JSONDecodeError: If qmd output is not valid JSON.
    """
    cmd = ["qmd", "search", query, "--limit", str(limit), "--json"]
    if collections:
        cmd.extend(["--collections", ",".join(collections)])

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return _parse_qmd_results(proc.stdout)


def qmd_query(
    query: str,
    collections: list[str] | None = None,
    limit: int = 10,
    rerank: bool = True,
) -> list[QmdResult]:
    """Run hybrid query (BM25 + vector, optional re-ranking) via qmd CLI.

    Args:
        query: Search text.
        collections: Optional list of QMD collection names.
        limit: Maximum results.
        rerank: Whether to use LLM re-ranking (Tier 3). False = Tier 2.

    Returns:
        List of QmdResult.

    Raises:
        subprocess.CalledProcessError: If qmd subprocess fails.
        subprocess.TimeoutExpired: If qmd times out.
        OSError: If qmd cannot be executed.
        json.JSONDecodeError: If qmd output is not valid JSON.
    """
    searches = json.dumps([
        {"type": "lex", "query": query},
        {"type": "vec", "query": query},
    ])

    cmd = ["qmd", "query", "--searches", searches]
    if rerank:
        cmd.append("--rerank")
    cmd.extend(["--limit", str(limit), "--json"])
    if collections:
        cmd.extend(["--collections", ",".join(collections)])

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return _parse_qmd_results(proc.stdout)


def qmd_setup_collection(name: str, path: str, mask: str = "**/*.md") -> bool:
    """Set up a QMD collection for memory indexing.

    NOTE: This is user-initiated only, never automatic.

    Args:
        name: Collection name.
        path: Directory path to index.
        mask: Glob pattern for files to include.

    Returns:
        True on success, False on failure.
    """
    cmd = [
        "qmd", "collection", "add", path,
        "--name", name,
        "--mask", mask,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            logger.warning("qmd collection add failed (rc=%d): %s", proc.returncode, proc.stderr)
            return False
        return True
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning("qmd collection add error: %s", e)
        return False


def qmd_reindex() -> bool:
    """Trigger QMD re-indexing.

    NOTE: This is user-initiated only, never automatic.

    Returns:
        True on success, False on failure.
    """
    cmd = ["qmd", "update"]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            logger.warning("qmd update failed (rc=%d): %s", proc.returncode, proc.stderr)
            return False
        return True
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning("qmd update error: %s", e)
        return False


def search_memories(
    query: str,
    memory_dirs: list[str],
    tags: list[str] | None = None,
    file_path: str | None = None,
    limit: int = 10,
    rerank: bool = True,
    branch: str | None = None,
) -> list[MemoryResult]:
    """Search memories via QMD hybrid search.

    Uses qmd_query (BM25 + vector, optional re-rank). After QMD results:
    reads full memory files to apply custom scoring (temporal decay,
    branch multiplier). Filters by tags/file_path post-search since QMD
    cannot do structured frontmatter filtering.

    Args:
        query: Search text.
        memory_dirs: List of memory directory paths (currently unused by QMD
            but retained for API symmetry and future filtering).
        tags: Filter by tags (post-search).
        file_path: Filter by citation file path (post-search).
        limit: Maximum results.
        rerank: Whether to use LLM re-ranking.
        branch: Current git branch for branch-weighted scoring.

    Returns:
        List of MemoryResult sorted by score descending.
    """
    from spellbook.memory.frontmatter import parse_frontmatter
    from spellbook.memory.models import MemoryFile

    qmd_results = qmd_query(query, rerank=rerank, limit=limit)

    query_terms = [t.lower() for t in query.split() if t.strip()] if query else []

    # ``pre_scored`` preserves the per-hit ``(qr.score, custom_score)`` pair so
    # the worker-LLM rerank branch below can re-blend those components with
    # the LLM relevance as ``(qr + custom + llm) / 3`` instead of
    # ``(combined + llm) / 2`` (which would double-weight the QMD/custom
    # components).
    pre_scored: list[tuple[MemoryResult, tuple[float, float]]] = []

    for qr in qmd_results:
        if not os.path.exists(qr.path):
            continue
        try:
            fm, body = parse_frontmatter(qr.path)
        except (ValueError, OSError):
            continue

        mf = MemoryFile(path=qr.path, frontmatter=fm, content=body)

        # Post-filter by tags
        if tags:
            fm_tags_lower = {t.lower() for t in fm.tags}
            if not any(t.lower() in fm_tags_lower for t in tags):
                continue

        # Post-filter by citation file path
        if file_path:
            cited_files = {c.file for c in fm.citations}
            if file_path not in cited_files:
                continue

        custom_score = compute_score(mf, query_terms, branch) if query_terms else 1.0
        combined_score = (qr.score + custom_score) / 2.0
        context = qr.snippet if qr.snippet else None
        pre_scored.append(
            (
                MemoryResult(memory=mf, score=combined_score, match_context=context),
                (qr.score, custom_score),
            )
        )

    # D3: worker-LLM rerank composition (top-20 of the candidate pool).
    # Gated on `worker_llm_feature_memory_rerank` AND endpoint configured
    # (feature_enabled() enforces both). Worker failures set the shared
    # ``_MEMORY_RECALL_ERROR`` ContextVar and otherwise fall through to the
    # baseline scoring — never raised.
    _apply_worker_rerank(query, query_terms, pre_scored)

    scored: list[MemoryResult] = [mr for (mr, _) in pre_scored]
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:limit]


def _apply_worker_rerank(
    query: str,
    query_terms: list[str],
    pre_scored: list[tuple[MemoryResult, tuple[float, float]]],
) -> None:
    """Mutate ``pre_scored`` entries in place with blended LLM relevance scores.

    Only runs when ``worker_llm_feature_memory_rerank`` is enabled AND the
    endpoint is configured (see ``worker_llm.config.feature_enabled``). On
    any ``WorkerLLMError`` the entries are left untouched and a
    ``<worker-llm-error>`` XML marker is stored in ``_MEMORY_RECALL_ERROR``
    so the MCP tool boundary can surface it. No exception escapes.
    """
    # Deferred imports: avoids a hard load-time dependency on the worker-LLM
    # package and keeps `search_qmd` importable in environments where the
    # worker is not configured.
    from spellbook.worker_llm import errors as _wl_errors
    from spellbook.worker_llm.config import feature_enabled as _wl_feature_enabled

    if not query_terms or not pre_scored:
        return
    if not _wl_feature_enabled("memory_rerank"):
        return

    # Top-20 ranked by baseline score. Hits beyond top-20 stay at baseline.
    top_n = sorted(pre_scored, key=lambda p: p[0].score, reverse=True)[:20]
    candidates = [
        {"id": mr.memory.path, "excerpt": mr.memory.content[:600]}
        for (mr, _) in top_n
    ]

    # Import lazily so callers that stub ``memory_rerank`` via monkeypatch see
    # the patched name even when it happens after module import.
    from spellbook.worker_llm.tasks import memory_rerank as _mr_module

    try:
        scored = _mr_module.memory_rerank(query, candidates)
    except _wl_errors.WorkerLLMError as e:
        marker = (
            f"<worker-llm-error>"
            f"<task>memory_rerank</task>"
            f"<type>{type(e).__name__}</type>"
            f"<message>{str(e)[:500]}</message>"
            f"</worker-llm-error>"
        )
        print(f"[worker-llm] memory_rerank: {e}", file=sys.stderr)
        # Deferred import avoids a tools.py <-> search_qmd.py cycle at load.
        from spellbook.memory.tools import _MEMORY_RECALL_ERROR
        _MEMORY_RECALL_ERROR.set(marker)
        return

    by_id = {s.id: s.relevance for s in scored}
    for (mr, (qr_score, custom_score)) in top_n:
        llm = by_id.get(mr.memory.path)
        if llm is None:
            continue
        mr.score = (qr_score + custom_score + llm) / 3.0
