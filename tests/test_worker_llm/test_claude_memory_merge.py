"""Tests for claude_memory merge gating in search_qmd.search_memories (D5).

Feature gate: ``worker_llm_read_claude_memory`` (default ``False``).
OFF -> Claude memories are NOT merged (zero behavior change).
ON  -> Claude memories are merged into the candidate pool, deduped by
       content hash with spellbook-native hits winning on collision.

Also covers the composed rerank + claude_memory flow (formerly F3):
rerank blends only spellbook-native top-20 scores; claude hits appear
post-rerank without double-counting.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

import pytest

from spellbook.memory.models import (
    MemoryFile,
    MemoryFrontmatter,
    MemoryResult,
)


def _fake_qmd_hit(path: str, score: float, snippet: str = ""):
    from spellbook.memory.search_qmd import QmdResult
    return QmdResult(path=path, score=score, snippet=snippet)


def _seed_spellbook_memory(tmp_path: Path, name: str, body: str) -> str:
    import yaml
    fm = {"type": "project", "created": datetime.date(2026, 4, 14)}
    yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    path = tmp_path / name
    path.write_text(f"---\n{yaml_str}---\n\n{body}\n")
    return str(path)


def _seed_claude_memory(home: Path, project_root: str, filename: str, body: str) -> str:
    encoded = project_root.lstrip("/").replace("/", "-")
    mem_dir = home / ".claude" / "projects" / encoded / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    path = mem_dir / filename
    path.write_text(
        f"---\nname: n\ndescription: d\ntype: feedback\n---\n{body}\n"
    )
    return str(path)


# ---------------------------------------------------------------------------
# Gating: default OFF means no claude merge
# ---------------------------------------------------------------------------


class TestClaudeMemoryMergeGating:
    def test_disabled_by_default_excludes_claude(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        # Default key state from the fixture is False. Explicit for clarity.
        worker_llm_config["worker_llm_read_claude_memory"] = False
        worker_llm_config["worker_llm_feature_memory_rerank"] = False

        # A spellbook-native hit (will be returned).
        sb_path = _seed_spellbook_memory(tmp_path, "sb.md", "spellbook body")
        hits = [_fake_qmd_hit(sb_path, 0.8)]
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.qmd_query", lambda *a, **k: hits
        )
        monkeypatch.setattr(
            "spellbook.memory.search_qmd.compute_score",
            lambda memory, query_terms, branch: 0.6,
        )

        # A claude memory that must NOT appear while gate is OFF.
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: home)
        monkeypatch.chdir(tmp_path)  # project_root for scan() defaults to cwd
        _seed_claude_memory(home, str(tmp_path), "cl.md", "claude body")

        # Also intercept the import site to catch accidental calls.
        from spellbook.memory import claude_memory
        calls = {"n": 0}
        orig_scan = claude_memory.scan

        def _tracking_scan(*a, **k):
            calls["n"] += 1
            return orig_scan(*a, **k)

        monkeypatch.setattr(claude_memory, "scan", _tracking_scan)

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("query", [str(tmp_path)])

        # Only the spellbook hit is returned.
        assert len(res) == 1
        assert res[0].memory.path == sb_path
        # Gate OFF -> scan was not invoked.
        assert calls["n"] == 0

    def test_enabled_merges_claude(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_read_claude_memory"] = True
        worker_llm_config["worker_llm_feature_memory_rerank"] = False

        sb_path = _seed_spellbook_memory(
            tmp_path, "sb.md", "spellbook body unique content"
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
        cl_path = _seed_claude_memory(
            home, str(tmp_path), "cl.md", "claude body distinct content"
        )

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("body", [str(tmp_path)])

        paths = {r.memory.path for r in res}
        assert sb_path in paths
        assert cl_path in paths
        assert len(res) == 2


# ---------------------------------------------------------------------------
# Dedup: identical content -> spellbook-native wins
# ---------------------------------------------------------------------------


class TestContentHashDedup:
    def test_identical_content_spellbook_wins(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_read_claude_memory"] = True
        worker_llm_config["worker_llm_feature_memory_rerank"] = False

        body = "exactly identical body content for dedup test"
        sb_path = _seed_spellbook_memory(tmp_path, "sb.md", body)
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
        _seed_claude_memory(home, str(tmp_path), "dupe.md", body)

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("body", [str(tmp_path)])

        # Exactly one result; it must be the spellbook-native file.
        assert len(res) == 1
        assert res[0].memory.path == sb_path


# ---------------------------------------------------------------------------
# Missing claude directory is graceful
# ---------------------------------------------------------------------------


class TestMissingClaudeDir:
    def test_merge_with_no_claude_dir_is_baseline(
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

        # Home has no .claude/projects/<enc>/memory/ at all.
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr("pathlib.Path.home", lambda: home)
        monkeypatch.chdir(tmp_path)

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("query", [str(tmp_path)])
        # Only the spellbook hit, no crash.
        assert len(res) == 1
        assert res[0].memory.path == sb_path


# ---------------------------------------------------------------------------
# Former F3: rerank + claude_memory compose without double-counting
# ---------------------------------------------------------------------------


class TestRerankAndClaudeMemoryCompose:
    def test_rerank_and_claude_memory_compose(
        self, tmp_path, monkeypatch, worker_llm_config
    ):
        worker_llm_config["worker_llm_feature_memory_rerank"] = True
        worker_llm_config["worker_llm_read_claude_memory"] = True

        sb_path = _seed_spellbook_memory(
            tmp_path, "sb.md", "spellbook body unique"
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
        cl_path = _seed_claude_memory(
            home, str(tmp_path), "cl.md", "claude body distinct"
        )

        from spellbook.worker_llm.tasks.memory_rerank import ScoredCandidate

        rerank_ids_seen: list[list[str]] = []

        def _fake_rerank(query, candidates):
            # Rerank MUST only see spellbook-native candidates (the
            # claude hits merge AFTER rerank so the LLM budget is not
            # wasted reranking claude-sourced content).
            rerank_ids_seen.append([c["id"] for c in candidates])
            return [ScoredCandidate(id=c["id"], relevance=0.9) for c in candidates]

        monkeypatch.setattr(
            "spellbook.worker_llm.tasks.memory_rerank.memory_rerank", _fake_rerank
        )

        from spellbook.memory.search_qmd import search_memories
        res = search_memories("body", [str(tmp_path)])

        # Rerank saw only spellbook; claude hit appears in the final list.
        assert rerank_ids_seen == [[sb_path]]
        by_path = {r.memory.path: r for r in res}
        assert sb_path in by_path
        assert cl_path in by_path
        # Spellbook score: blended (0.8 + 0.6 + 0.9) / 3.
        assert by_path[sb_path].score == pytest.approx(
            (0.8 + 0.6 + 0.9) / 3.0, abs=1e-9
        )
