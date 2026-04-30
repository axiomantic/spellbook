"""Tests for the QMD search adapter.

Covers: QmdResult dataclass, subprocess command construction, JSON
result parsing, and error propagation.

QMD is a hard dependency of the memory system; there is no fallback
path to test. Tests that invoke the real qmd binary are marked
`requires_memory_tools` so they auto-skip when QMD is not installed.
"""

import json
import subprocess

import tripwire
import pytest


# ---------------------------------------------------------------------------
# QmdResult dataclass
# ---------------------------------------------------------------------------


class TestQmdResult:
    """Test QmdResult data model construction and defaults."""

    def test_qmd_result_all_fields(self):
        from spellbook.memory.search_qmd import QmdResult

        r = QmdResult(path="/tmp/memories/project/retry.md", score=0.85, snippet="matched text")
        assert r == QmdResult(
            path="/tmp/memories/project/retry.md",
            score=0.85,
            snippet="matched text",
        )

    def test_qmd_result_default_snippet(self):
        from spellbook.memory.search_qmd import QmdResult

        r = QmdResult(path="/tmp/test.md", score=0.5)
        assert r == QmdResult(path="/tmp/test.md", score=0.5, snippet="")


# ---------------------------------------------------------------------------
# _parse_qmd_results: JSON parsing
# ---------------------------------------------------------------------------


class TestParseQmdResults:
    """Test JSON output parsing into QmdResult list."""

    def test_parse_empty_list(self):
        from spellbook.memory.search_qmd import _parse_qmd_results

        assert _parse_qmd_results("[]") == []

    def test_parse_results(self):
        from spellbook.memory.search_qmd import QmdResult, _parse_qmd_results

        stdout = json.dumps([
            {"path": "/a.md", "score": 0.9, "snippet": "text"},
            {"path": "/b.md", "score": 0.3, "snippet": ""},
        ])
        results = _parse_qmd_results(stdout)
        assert results == [
            QmdResult(path="/a.md", score=0.9, snippet="text"),
            QmdResult(path="/b.md", score=0.3, snippet=""),
        ]

    def test_parse_missing_fields_uses_defaults(self):
        from spellbook.memory.search_qmd import QmdResult, _parse_qmd_results

        stdout = json.dumps([{"path": "/x.md"}])
        assert _parse_qmd_results(stdout) == [
            QmdResult(path="/x.md", score=0.0, snippet=""),
        ]

    def test_parse_invalid_json_raises(self):
        from spellbook.memory.search_qmd import _parse_qmd_results

        with pytest.raises(json.JSONDecodeError):
            _parse_qmd_results("not valid json{{{")


# ---------------------------------------------------------------------------
# qmd_search: BM25 command construction
# ---------------------------------------------------------------------------


class TestQmdSearch:
    """Test QMD BM25 search command construction and error propagation."""

    @pytest.mark.allow("subprocess")
    def test_basic_search_command(self):
        """Verify qmd_search builds the correct subprocess command."""
        qmd_output = json.dumps([
            {"path": "/tmp/mem/project/retry.md", "score": 0.9, "snippet": "exponential backoff"},
            {"path": "/tmp/mem/project/deploy.md", "score": 0.3, "snippet": "deploy process"},
        ])

        tripwire.subprocess.mock_run(
            command=["qmd", "search", "retry backoff", "--limit", "10", "--json"],
            returncode=0,
            stdout=qmd_output,
        )

        from spellbook.memory.search_qmd import QmdResult, qmd_search

        with tripwire:
            results = qmd_search("retry backoff")

        assert results == [
            QmdResult(path="/tmp/mem/project/retry.md", score=0.9, snippet="exponential backoff"),
            QmdResult(path="/tmp/mem/project/deploy.md", score=0.3, snippet="deploy process"),
        ]
        tripwire.subprocess.assert_run(
            command=["qmd", "search", "retry backoff", "--limit", "10", "--json"],
            returncode=0,
            stdout=qmd_output,
            stderr="",
        )

    @pytest.mark.allow("subprocess")
    def test_search_with_collections(self):
        """Verify collection flags are passed correctly."""
        qmd_output = json.dumps([])

        tripwire.subprocess.mock_run(
            command=[
                "qmd", "search", "query text",
                "--limit", "5",
                "--json",
                "--collections", "memories,global",
            ],
            returncode=0,
            stdout=qmd_output,
        )

        from spellbook.memory.search_qmd import qmd_search

        with tripwire:
            results = qmd_search("query text", collections=["memories", "global"], limit=5)

        assert results == []
        tripwire.subprocess.assert_run(
            command=[
                "qmd", "search", "query text",
                "--limit", "5",
                "--json",
                "--collections", "memories,global",
            ],
            returncode=0,
            stdout=qmd_output,
            stderr="",
        )

    @pytest.mark.allow("subprocess")
    def test_search_raises_on_subprocess_error(self):
        """On subprocess failure, qmd_search raises CalledProcessError."""
        tripwire.subprocess.mock_run(
            command=["qmd", "search", "broken query", "--limit", "10", "--json"],
            raises=subprocess.CalledProcessError(
                returncode=1,
                cmd=["qmd", "search", "broken query", "--limit", "10", "--json"],
                stderr="Error: index not found",
            ),
        )

        from spellbook.memory.search_qmd import qmd_search

        with tripwire, pytest.raises(subprocess.CalledProcessError):
            qmd_search("broken query")

        tripwire.subprocess.assert_run(
            command=["qmd", "search", "broken query", "--limit", "10", "--json"],
            returncode=0,
            stdout="",
            stderr="",
        )

    @pytest.mark.allow("subprocess")
    def test_search_raises_on_timeout(self):
        """On timeout, qmd_search raises TimeoutExpired."""
        tripwire.subprocess.mock_run(
            command=["qmd", "search", "slow query", "--limit", "10", "--json"],
            raises=subprocess.TimeoutExpired(cmd="qmd", timeout=10),
        )

        from spellbook.memory.search_qmd import qmd_search

        with tripwire, pytest.raises(subprocess.TimeoutExpired):
            qmd_search("slow query")

        tripwire.subprocess.assert_run(
            command=["qmd", "search", "slow query", "--limit", "10", "--json"],
            returncode=0,
            stdout="",
            stderr="",
        )


# ---------------------------------------------------------------------------
# qmd_query: hybrid search command construction
# ---------------------------------------------------------------------------


class TestQmdQuery:
    """Test QMD hybrid query command construction."""

    @pytest.mark.allow("subprocess")
    def test_hybrid_query_command(self):
        """Verify qmd_query builds the correct subprocess command with rerank."""
        expected_searches = json.dumps([
            {"type": "lex", "query": "api design"},
            {"type": "vec", "query": "api design"},
        ])

        qmd_output = json.dumps([
            {"path": "/tmp/mem/reference/api.md", "score": 0.95, "snippet": "REST endpoint"},
        ])

        tripwire.subprocess.mock_run(
            command=[
                "qmd", "query",
                "--searches", expected_searches,
                "--rerank",
                "--limit", "10",
                "--json",
            ],
            returncode=0,
            stdout=qmd_output,
        )

        from spellbook.memory.search_qmd import QmdResult, qmd_query

        with tripwire:
            results = qmd_query("api design")

        assert results == [
            QmdResult(path="/tmp/mem/reference/api.md", score=0.95, snippet="REST endpoint"),
        ]
        tripwire.subprocess.assert_run(
            command=[
                "qmd", "query",
                "--searches", expected_searches,
                "--rerank",
                "--limit", "10",
                "--json",
            ],
            returncode=0,
            stdout=qmd_output,
            stderr="",
        )

    @pytest.mark.allow("subprocess")
    def test_query_without_rerank(self):
        """Verify qmd_query without rerank omits --rerank flag."""
        expected_searches = json.dumps([
            {"type": "lex", "query": "logging"},
            {"type": "vec", "query": "logging"},
        ])

        tripwire.subprocess.mock_run(
            command=[
                "qmd", "query",
                "--searches", expected_searches,
                "--limit", "10",
                "--json",
            ],
            returncode=0,
            stdout="[]",
        )

        from spellbook.memory.search_qmd import qmd_query

        with tripwire:
            results = qmd_query("logging", rerank=False)

        assert results == []
        tripwire.subprocess.assert_run(
            command=[
                "qmd", "query",
                "--searches", expected_searches,
                "--limit", "10",
                "--json",
            ],
            returncode=0,
            stdout="[]",
            stderr="",
        )

    @pytest.mark.allow("subprocess")
    def test_query_raises_on_subprocess_error(self):
        """On failure qmd_query raises; no fallback path exists."""
        expected_searches = json.dumps([
            {"type": "lex", "query": "q"},
            {"type": "vec", "query": "q"},
        ])

        cmd = [
            "qmd", "query",
            "--searches", expected_searches,
            "--rerank",
            "--limit", "10",
            "--json",
        ]
        tripwire.subprocess.mock_run(
            command=cmd,
            raises=subprocess.CalledProcessError(
                returncode=2,
                cmd=cmd,
                stderr="boom",
            ),
        )

        from spellbook.memory.search_qmd import qmd_query

        with tripwire, pytest.raises(subprocess.CalledProcessError):
            qmd_query("q")

        tripwire.subprocess.assert_run(
            command=cmd,
            returncode=0,
            stdout="",
            stderr="",
        )


# ---------------------------------------------------------------------------
# Real-tool integration (skipped unless QMD is installed)
# ---------------------------------------------------------------------------


@pytest.mark.requires_memory_tools
@pytest.mark.allow("subprocess")
class TestQmdRealIntegration:
    """Smoke-test against the real QMD binary. Skipped when QMD missing."""

    def test_qmd_version_is_callable(self):
        import shutil as _shutil

        assert _shutil.which("qmd") is not None
        proc = subprocess.run(
            ["qmd", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0 or proc.stdout or proc.stderr
