"""Tests for worker_llm memory_rerank composition inside search_qmd.search_memories.

Covers D3 (rerank composition) and D7 (_MEMORY_RECALL_ERROR ContextVar +
``get_last_memory_recall_error`` public getter).

Contract under test:

- Feature OFF (``worker_llm_feature_memory_rerank=False``) or endpoint
  unconfigured -> ``search_memories`` returns baseline scores, no worker call.
- Feature ON + configured -> top-N candidates are blended with the LLM
  relevance score.
- Worker raises ``WorkerLLMError`` -> results still returned from baseline
  ranking, and ``get_last_memory_recall_error()`` returns a ``<worker-llm-error>``
  XML string.
- ``do_memory_recall`` surfaces the ContextVar as the ``worker_llm_error`` key
  on the response dict, and clears it between calls.
"""

from __future__ import annotations

import datetime
import os

import httpx
import pytest

from spellbook.memory.models import (
    MemoryFile,
    MemoryFrontmatter,
    MemoryResult,
)


def _fake_qmd_hit(path: str, score: float, snippet: str = ""):
    from spellbook.memory.search_qmd import QmdResult
    return QmdResult(path=path, score=score, snippet=snippet)


def _seed_memory_file(tmp_path, name: str, body: str, tags=None) -> str:
    """Write a minimally valid memory file and return its absolute path."""
    import yaml
    fm = {"type": "project", "created": datetime.date(2026, 4, 14)}
    if tags:
        fm["tags"] = list(tags)
    yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    path = tmp_path / name
    path.write_text(f"---\n{yaml_str}---\n\n{body}\n")
    return str(path)


# ---------------------------------------------------------------------------
# D3: rerank OFF baseline
# ---------------------------------------------------------------------------


class TestRerankDisabledBaseline:
    """Feature OFF -> no worker call, scores identical to pre-worker-llm baseline."""

    def test_rerank_off_is_byte_identical(self, tmp_path, monkeypatch, worker_llm_config):
        worker_llm_config["worker_llm_feature_memory_rerank"] = False

        a = _seed_memory_file(tmp_path, "a.md", "alpha body text")
        hits = [_fake_qmd_hit(a, 0.8, "snip-a")]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query",
            lambda *args, **kwargs: hits,
        )
        # Force compute_score to a known constant so arithmetic is deterministic.
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        def _boom(*args, **kwargs):
            raise AssertionError("worker_llm rerank MUST NOT be called when feature is OFF")

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank", _boom
        )

        from spellbook.memory.search_qmd import search_memories

        res = search_memories("query", [str(tmp_path)])
        assert len(res) == 1
        assert res[0].score == pytest.approx((0.8 + 0.6) / 2.0, abs=1e-9)

    def test_rerank_unconfigured_is_baseline(self, tmp_path, monkeypatch, worker_llm_config):
        # Feature flag True but endpoint not configured -> feature_enabled() False.
        worker_llm_config["worker_llm_feature_memory_rerank"] = True
        worker_llm_config["worker_llm_base_url"] = ""

        a = _seed_memory_file(tmp_path, "a.md", "alpha body text")
        hits = [_fake_qmd_hit(a, 0.8, "")]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        def _boom(*args, **kwargs):
            raise AssertionError("rerank MUST NOT run when endpoint is unconfigured")

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank", _boom
        )

        from spellbook.memory.search_qmd import search_memories

        res = search_memories("query", [str(tmp_path)])
        assert res[0].score == pytest.approx(0.7, abs=1e-9)


# ---------------------------------------------------------------------------
# D3: rerank ON happy path
# ---------------------------------------------------------------------------


class TestRerankEnabledHappyPath:
    """Feature ON -> top-N candidates blended with worker relevance."""

    def test_rerank_on_blends_three_scores(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        a = _seed_memory_file(tmp_path, "a.md", "alpha body text")
        hits = [_fake_qmd_hit(a, 0.8, "excerpt-a")]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *args, **kwargs: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        from spellbook.worker_llm.tasks.memory_rerank import ScoredCandidate

        def _fake_rerank(query, candidates):
            # Caller passes candidates shaped as {id, excerpt}.
            # Excerpt comes from the parsed body, capped at 600 chars upstream.
            assert len(candidates) == 1
            assert candidates[0]["id"] == a
            assert "alpha body text" in candidates[0]["excerpt"]
            return [ScoredCandidate(id=a, relevance=0.9)]

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank", _fake_rerank
        )

        from spellbook.memory.search_qmd import search_memories

        res = search_memories("query", [str(tmp_path)])
        assert len(res) == 1
        # Blend: (qmd 0.8 + custom 0.6 + llm 0.9) / 3
        assert res[0].score == pytest.approx((0.8 + 0.6 + 0.9) / 3.0, abs=1e-9)

    def test_rerank_only_affects_top_20(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        # Seed 22 memory files -> 22 QMD hits.
        paths = [
            _seed_memory_file(tmp_path, f"m{i}.md", f"body {i}") for i in range(22)
        ]
        hits = [_fake_qmd_hit(p, 1.0 - i * 0.01) for i, p in enumerate(paths)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.5,
        )

        from spellbook.worker_llm.tasks.memory_rerank import ScoredCandidate

        def _fake_rerank(query, candidates):
            # Top 20 -> first 20 paths ordered by (qmd + custom)/2 score desc.
            assert len(candidates) == 20
            return [ScoredCandidate(id=c["id"], relevance=1.0) for c in candidates]

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank", _fake_rerank
        )

        from spellbook.memory.search_qmd import search_memories

        res = search_memories("query", [str(tmp_path)], limit=22)
        # Each of top-20 should be blended to (qmd + 0.5 + 1.0)/3.
        # Items 20 and 21 (the two lowest qmd scores) should stay at (qmd+0.5)/2.
        top_20_paths = {
            r.memory.path for r in sorted(
                # Reconstruct top 20 by baseline score (qmd + custom)/2
                res, key=lambda r: r.score, reverse=True
            )[:20]
        }
        for r in res:
            qmd_score = next(h.score for h in hits if h.path == r.memory.path)
            if r.memory.path in top_20_paths:
                # Blended (exact arithmetic uses qmd stored before averaging).
                expected = (qmd_score + 0.5 + 1.0) / 3.0
            else:
                expected = (qmd_score + 0.5) / 2.0
            assert r.score == pytest.approx(expected, abs=1e-9)


# ---------------------------------------------------------------------------
# D7: ContextVar surfacing
# ---------------------------------------------------------------------------


class TestWorkerLLMErrorContextVar:
    """Worker failure -> error marker stored in ContextVar, baseline results survive."""

    def test_worker_error_sets_contextvar(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        a = _seed_memory_file(tmp_path, "a.md", "alpha body text")
        hits = [_fake_qmd_hit(a, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        from spellbook.worker_llm.errors import WorkerLLMUnreachable

        def _boom(query, candidates):
            raise WorkerLLMUnreachable("connection refused")

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank", _boom
        )

        from spellbook.memory.tools import (
            _MEMORY_RECALL_ERROR,
            get_last_memory_recall_error,
        )
        from spellbook.memory.search_qmd import search_memories

        # Clear any prior state.
        _MEMORY_RECALL_ERROR.set(None)

        res = search_memories("query", [str(tmp_path)])
        # Results must survive on baseline scoring.
        assert len(res) == 1
        assert res[0].score == pytest.approx((0.8 + 0.6) / 2.0, abs=1e-9)

        err = get_last_memory_recall_error()
        assert err is not None
        assert "<worker-llm-error>" in err
        assert "memory_rerank" in err
        assert "connection refused" in err

    def test_worker_success_leaves_contextvar_none(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        a = _seed_memory_file(tmp_path, "a.md", "alpha body text")
        hits = [_fake_qmd_hit(a, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        from spellbook.worker_llm.tasks.memory_rerank import ScoredCandidate

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank",
            lambda q, c: [ScoredCandidate(id=c[0]["id"], relevance=0.9)],
        )

        from spellbook.memory.tools import (
            _MEMORY_RECALL_ERROR,
            get_last_memory_recall_error,
        )
        from spellbook.memory.search_qmd import search_memories

        _MEMORY_RECALL_ERROR.set(None)
        search_memories("query", [str(tmp_path)])
        assert get_last_memory_recall_error() is None


# ---------------------------------------------------------------------------
# D7: do_memory_recall response surfacing
# ---------------------------------------------------------------------------


class TestDoMemoryRecallSurfacesWorkerError:
    """do_memory_recall includes/omits ``worker_llm_error`` based on ContextVar."""

    def test_memory_recall_surfaces_worker_error(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        # Bypass QMD system check.
        monkeypatch.setattr(
            "spellbook.memory.tools.ensure_memory_system_available",
            lambda: None,
        )

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )
        os.makedirs(memory_dir, exist_ok=True)
        path = _seed_memory_file(
            tmp_path / "memories", "mem.md", "stuff about the topic of interest"
        )

        hits = [_fake_qmd_hit(path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )

        from spellbook.worker_llm.errors import WorkerLLMTimeout

        def _boom(query, candidates):
            raise WorkerLLMTimeout("budget exhausted")

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank", _boom
        )

        from spellbook.memory.tools import do_memory_recall

        result = do_memory_recall(query="topic", namespace="/fake", limit=10)
        assert "worker_llm_error" in result
        assert "<worker-llm-error>" in result["worker_llm_error"]
        assert "WorkerLLMTimeout" not in result["worker_llm_error"] or "budget exhausted" in result["worker_llm_error"]
        # Memories must still be present.
        assert result["count"] >= 1

    def test_memory_recall_omits_key_on_success(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        monkeypatch.setattr(
            "spellbook.memory.tools.ensure_memory_system_available",
            lambda: None,
        )

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )
        os.makedirs(memory_dir, exist_ok=True)
        path = _seed_memory_file(
            tmp_path / "memories", "mem.md", "stuff about the topic of interest"
        )

        hits = [_fake_qmd_hit(path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )

        from spellbook.worker_llm.tasks.memory_rerank import ScoredCandidate

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank",
            lambda q, c: [ScoredCandidate(id=c[0]["id"], relevance=0.9)],
        )

        from spellbook.memory.tools import do_memory_recall

        result = do_memory_recall(query="topic", namespace="/fake", limit=10)
        assert "worker_llm_error" not in result
        assert result["count"] >= 1

    def test_memory_recall_clears_contextvar_between_calls(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        """First call errors; second call succeeds -> no leaked worker_llm_error."""
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        monkeypatch.setattr(
            "spellbook.memory.tools.ensure_memory_system_available",
            lambda: None,
        )

        memory_dir = str(tmp_path / "memories")
        monkeypatch.setattr(
            "spellbook.memory.tools._get_memory_dir",
            lambda ns, scope="project": memory_dir,
        )
        os.makedirs(memory_dir, exist_ok=True)
        path = _seed_memory_file(
            tmp_path / "memories", "mem.md", "stuff about the topic of interest"
        )

        hits = [_fake_qmd_hit(path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )

        from spellbook.worker_llm.errors import WorkerLLMUnreachable
        from spellbook.worker_llm.tasks.memory_rerank import ScoredCandidate

        call_count = {"n": 0}

        def _sometimes_boom(query, candidates):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise WorkerLLMUnreachable("refused")
            return [ScoredCandidate(id=c["id"], relevance=0.9) for c in candidates]

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank", _sometimes_boom
        )

        from spellbook.memory.tools import do_memory_recall

        first = do_memory_recall(query="topic", namespace="/fake", limit=10)
        assert "worker_llm_error" in first

        second = do_memory_recall(query="topic", namespace="/fake", limit=10)
        assert "worker_llm_error" not in second
