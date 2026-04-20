"""F5: end-to-end integration tests for worker_llm memory paths.

Spans the full stack from ``search_qmd.search_memories`` through the real
``memory_rerank`` task (httpx transport mocked at the HTTP boundary) and
the ``claude_memory`` scanner. Complements the unit-level coverage in
``test_memory_rerank_search.py``, ``test_claude_memory.py``, and
``test_claude_memory_merge.py`` by verifying the composed pipeline
behaves correctly under realistic worker responses, timeouts, and
connection failures.

Scenarios covered:

  1. Rerank disabled (flag off)        -> baseline scoring, no HTTP.
  2. Rerank enabled + happy response   -> blended score; 1 HTTP call.
  3. Rerank timeout                    -> baseline results; ContextVar set;
                                          get_last_memory_recall_error() surfaces.
  4. Rerank unreachable                -> same as timeout, different type.
  5. claude_memory gate OFF            -> zero claude hits.
  6. claude_memory gate ON + rerank ON -> both present; rerank sees only
                                          spellbook-native candidates.
  7. Fresh call after failure          -> ContextVar cleared at
                                          do_memory_recall entry.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

import httpx
import pytest

from spellbook.memory.models import MemoryFile, MemoryFrontmatter, MemoryResult
from spellbook.worker_llm.errors import (
    WorkerLLMTimeout,
    WorkerLLMUnreachable,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_qmd_hit(path: str, score: float, snippet: str = ""):
    from spellbook.memory.search_qmd import QmdResult
    return QmdResult(path=path, score=score, snippet=snippet)


def _seed_spellbook_memory(tmp_path: Path, name: str, body: str) -> str:
    import yaml
    fm = {"type": "project", "created": datetime.date(2026, 4, 14)}
    yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    p = tmp_path / name
    p.write_text(f"---\n{yaml_str}---\n\n{body}\n")
    return str(p)


def _seed_claude_memory(
    home: Path, project_root: str, filename: str, body: str
) -> str:
    encoded = project_root.lstrip("/").replace("/", "-")
    mem_dir = home / ".claude" / "projects" / encoded / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    p = mem_dir / filename
    p.write_text(
        f"---\nname: n\ndescription: d\ntype: feedback\n---\n{body}\n"
    )
    return str(p)


def _ok(content: str) -> dict:
    """Build an OpenAI-compat successful response wrapper."""
    return {"choices": [{"message": {"content": content}}]}


def _scripted(*items):
    """Build the scripted-response list used by the worker_llm_transport fixture."""
    return [
        type("S", (), {
            "status": it.get("status", 200),
            "body": it.get("body", ""),
            "delay_s": it.get("delay_s", 0.0),
            "raise_on_send": it.get("raise", None),
        })()
        for it in items
    ]


# ---------------------------------------------------------------------------
# Rerank composition end-to-end
# ---------------------------------------------------------------------------


class TestRerankComposition:
    """memory_rerank task invoked through the real httpx client boundary."""

    def test_rerank_disabled_skips_http(
        self, tmp_path, monkeypatch, worker_llm_transport, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = False
        seen = worker_llm_transport([])  # empty script: any HTTP call fails

        path = _seed_spellbook_memory(tmp_path, "a.md", "alpha body here")
        hits = [_fake_qmd_hit(path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("query", [str(tmp_path)])

        assert len(res) == 1
        assert res[0].score == pytest.approx(0.7, abs=1e-9)
        # No HTTP call was dispatched.
        assert seen == []

    def test_rerank_enabled_happy_path(
        self, tmp_path, monkeypatch, worker_llm_transport, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        path = _seed_spellbook_memory(tmp_path, "a.md", "alpha body here")
        hits = [_fake_qmd_hit(path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        # Real memory_rerank task + mock transport returning relevance=0.9.
        # json.dumps escapes backslashes in Windows paths (e.g. ``C:\Users\...``)
        # so they survive the rerank worker's JSON parser.
        content = json.dumps([{"id": path, "relevance_0_1": 0.9}])
        seen = worker_llm_transport(_scripted({"status": 200, "body": _ok(content)}))

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("query", [str(tmp_path)])

        assert len(res) == 1
        assert res[0].score == pytest.approx((0.8 + 0.6 + 0.9) / 3.0, abs=1e-9)
        # Exactly one HTTP call was dispatched.
        assert len(seen) == 1

    def test_rerank_timeout_falls_back(
        self, tmp_path, monkeypatch, worker_llm_transport, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True
        # Force a short timeout so the delayed response aborts fast.
        worker_llm_config["worker_llm_timeout_s"] = 0.05

        path = _seed_spellbook_memory(tmp_path, "a.md", "alpha body here")
        hits = [_fake_qmd_hit(path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        # Transport raises TimeoutException -> translated to WorkerLLMTimeout.
        worker_llm_transport(
            _scripted({"raise": httpx.TimeoutException("slow")})
        )

        from spellbook.memory.tools import (
            _MEMORY_RECALL_ERROR,
            get_last_memory_recall_error,
        )
        _MEMORY_RECALL_ERROR.set(None)

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("query", [str(tmp_path)])

        # Baseline result survives.
        assert len(res) == 1
        assert res[0].score == pytest.approx(0.7, abs=1e-9)

        err = get_last_memory_recall_error()
        assert err is not None
        assert "<worker-llm-error>" in err
        assert "memory_rerank" in err
        assert "WorkerLLMTimeout" in err

    def test_rerank_unreachable_falls_back(
        self, tmp_path, monkeypatch, worker_llm_transport, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        path = _seed_spellbook_memory(tmp_path, "a.md", "alpha body here")
        hits = [_fake_qmd_hit(path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        worker_llm_transport(
            _scripted({"raise": httpx.ConnectError("refused")})
        )

        from spellbook.memory.tools import (
            _MEMORY_RECALL_ERROR,
            get_last_memory_recall_error,
        )
        _MEMORY_RECALL_ERROR.set(None)

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("query", [str(tmp_path)])
        assert len(res) == 1

        err = get_last_memory_recall_error()
        assert err is not None
        assert "WorkerLLMUnreachable" in err


# ---------------------------------------------------------------------------
# Claude-memory scanner: end-to-end behavior visible from search_memories
# ---------------------------------------------------------------------------


class TestClaudeMemoryScanner:
    """Cover scanner invariants that are observable through the merge path."""

    def test_missing_dir_no_crash(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_read_claude_memory"] = True
        worker_llm_config["worker_llm_feature_memory_rerank"] = False

        path = _seed_spellbook_memory(tmp_path, "a.md", "alpha body here")
        hits = [_fake_qmd_hit(path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )
        # Home has no .claude directory at all.
        home = tmp_path / "home_no_claude"
        home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: home)
        monkeypatch.chdir(tmp_path)

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("query", [str(tmp_path)])
        assert len(res) == 1
        assert res[0].memory.path == path

    def test_malformed_frontmatter_file_skipped(
        self, tmp_path, monkeypatch, worker_llm_config, caplog
    ):
        worker_llm_config["worker_llm_read_claude_memory"] = True
        worker_llm_config["worker_llm_feature_memory_rerank"] = False

        sb_path = _seed_spellbook_memory(
            tmp_path, "sb.md", "spellbook body distinct"
        )
        hits = [_fake_qmd_hit(sb_path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: home)
        monkeypatch.chdir(tmp_path)

        encoded = str(tmp_path).lstrip("/").replace("/", "-")
        mem_dir = home / ".claude" / "projects" / encoded / "memory"
        mem_dir.mkdir(parents=True)
        # Broken: no frontmatter delimiters.
        (mem_dir / "broken.md").write_text("just body no frontmatter")
        # Valid Claude file alongside.
        cl_path = _seed_claude_memory(
            home, str(tmp_path), "ok.md", "claude body with body term"
        )

        from spellbook.memory.search_qmd import search_memories
        with caplog.at_level("WARNING"):
            res = search_memories("body", [str(tmp_path)])

        paths = {r.memory.path for r in res}
        assert sb_path in paths
        assert cl_path in paths
        # Broken file was NOT returned.
        assert not any("broken.md" in p for p in paths)
        # Warning recorded.
        assert any("broken.md" in rec.message for rec in caplog.records)

    def test_project_encoded_path_is_per_project(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_read_claude_memory"] = True
        worker_llm_config["worker_llm_feature_memory_rerank"] = False

        sb_path = _seed_spellbook_memory(tmp_path, "sb.md", "spellbook body")
        hits = [_fake_qmd_hit(sb_path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: home)

        # Seed a Claude memory under a DIFFERENT project encoding — it
        # must NOT be found when cwd is ``tmp_path``.
        other_project = "/Users/other/project"
        _seed_claude_memory(
            home, other_project, "wrong_project.md", "unrelated body"
        )

        monkeypatch.chdir(tmp_path)

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("body", [str(tmp_path)])

        # Only the spellbook-native hit from this project.
        assert len(res) == 1
        assert res[0].memory.path == sb_path


# ---------------------------------------------------------------------------
# Merge gating end-to-end
# ---------------------------------------------------------------------------


class TestMergeGatingEndToEnd:
    def test_gate_off_excludes_claude(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_read_claude_memory"] = False
        worker_llm_config["worker_llm_feature_memory_rerank"] = False

        sb_path = _seed_spellbook_memory(tmp_path, "sb.md", "spellbook body")
        hits = [_fake_qmd_hit(sb_path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: home)
        monkeypatch.chdir(tmp_path)
        _seed_claude_memory(home, str(tmp_path), "cl.md", "claude body")

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("body", [str(tmp_path)])
        paths = {r.memory.path for r in res}
        assert paths == {sb_path}

    def test_gate_on_merges_with_rerank_covering_only_native(
        self, tmp_path, monkeypatch, worker_llm_transport, worker_llm_config
    ):
        worker_llm_config["worker_llm_read_claude_memory"] = True
        worker_llm_config["worker_llm_feature_memory_rerank"] = True

        sb_path = _seed_spellbook_memory(tmp_path, "sb.md", "spellbook body")
        hits = [_fake_qmd_hit(sb_path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: home)
        monkeypatch.chdir(tmp_path)
        cl_path = _seed_claude_memory(
            home, str(tmp_path), "cl.md", "claude body distinct"
        )

        # Rerank returns 0.9 for the spellbook hit. json.dumps escapes
        # backslashes in Windows paths so the worker can parse the response.
        content = json.dumps([{"id": sb_path, "relevance_0_1": 0.9}])
        seen = worker_llm_transport(_scripted({"status": 200, "body": _ok(content)}))

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("body", [str(tmp_path)])

        by_path = {r.memory.path: r for r in res}
        assert sb_path in by_path
        assert cl_path in by_path
        assert by_path[sb_path].score == pytest.approx(
            (0.8 + 0.6 + 0.9) / 3.0, abs=1e-9
        )
        # Rerank HTTP round-trip happened exactly once (only native candidate).
        assert len(seen) == 1


# ---------------------------------------------------------------------------
# ContextVar lifecycle through do_memory_recall
# ---------------------------------------------------------------------------


class TestContextVarLifecycle:
    def test_fresh_call_resets_stale_error(
        self, tmp_path, monkeypatch, worker_llm_transport, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True
        worker_llm_config["worker_llm_timeout_s"] = 0.05

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
        path = _seed_spellbook_memory(
            tmp_path / "memories", "m.md", "memory body content"
        )

        hits = [_fake_qmd_hit(path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )

        # First call: transport raises -> WorkerLLMUnreachable.
        # Second call: transport returns a valid rerank response. json.dumps
        # escapes backslashes in Windows paths for correct round-trip.
        content = json.dumps([{"id": path, "relevance_0_1": 0.9}])
        worker_llm_transport(
            _scripted(
                {"raise": httpx.ConnectError("refused")},
                {"status": 200, "body": _ok(content)},
            )
        )

        from spellbook.memory.tools import (
            do_memory_recall,
            get_last_memory_recall_error,
        )

        first = do_memory_recall(query="memory", namespace="/fake", limit=10)
        assert "worker_llm_error" in first
        assert "<worker-llm-error>" in first["worker_llm_error"]

        second = do_memory_recall(query="memory", namespace="/fake", limit=10)
        assert "worker_llm_error" not in second
        # The ContextVar should also reflect the clean state.
        assert get_last_memory_recall_error() is None
