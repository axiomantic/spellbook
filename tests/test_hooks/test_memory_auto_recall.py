"""Tests for automatic memory recall on hook events.

Covers UserPromptSubmit and PreToolUse auto-injection, keyword extraction,
budget enforcement, dedup log behavior, config gate, and XML formatting
for the new filestore MemoryResult shape.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Ensure hooks/ is on sys.path so we can import spellbook_hook directly.
HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import spellbook_hook  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dedup_log_path(tmp_path, monkeypatch):
    """Point the dedup log at a temporary file."""
    log_path = tmp_path / "recent-memory-injections.json"
    monkeypatch.setattr(spellbook_hook, "DEDUP_LOG_PATH", log_path)
    return log_path


@pytest.fixture
def config_enabled(monkeypatch):
    """Force memory.auto_recall config to True."""
    def fake_config_value(key, default=None):
        if key == "memory.auto_recall":
            return True
        return default
    monkeypatch.setattr(spellbook_hook, "_get_config_value", fake_config_value)


@pytest.fixture
def config_disabled(monkeypatch):
    """Force memory.auto_recall config to False."""
    def fake_config_value(key, default=None):
        if key == "memory.auto_recall":
            return False
        return default
    monkeypatch.setattr(spellbook_hook, "_get_config_value", fake_config_value)


@pytest.fixture
def mock_http(monkeypatch):
    """Capture all _http_post calls. Used for tests that exercise paths
    beyond /api/memory/recall (e.g. /api/hook-log routed through
    _log_hook_error)."""
    class Controller:
        def __init__(self):
            self.calls: list[dict] = []
            self.responses: dict[str, object] = {}

        def set_response(self, url_suffix: str, response: object) -> None:
            self.responses[url_suffix] = response

    controller = Controller()

    def fake_http_post(url, payload, timeout=5):
        controller.calls.append({"url": url, "payload": payload, "timeout": timeout})
        for suffix, resp in controller.responses.items():
            if url.endswith(suffix):
                return resp
        return None

    monkeypatch.setattr(spellbook_hook, "_http_post", fake_http_post)
    return controller


@pytest.fixture
def mock_recall(monkeypatch):
    """Mock the HTTP call to /api/memory/recall.

    Returns the captured-request/response controller object so tests can
    stage response payloads and inspect request bodies.
    """
    class Controller:
        def __init__(self):
            self.calls: list[dict] = []
            self.response: dict = {"memories": [], "count": 0}

        def set_response(self, response: dict) -> None:
            self.response = response

        def set_memories(self, memories: list[dict]) -> None:
            self.response = {"memories": memories, "count": len(memories)}

    controller = Controller()

    def fake_http_post(url, payload, timeout=5):
        controller.calls.append({"url": url, "payload": payload})
        if url.endswith("/api/memory/recall"):
            return controller.response
        return None

    monkeypatch.setattr(spellbook_hook, "_http_post", fake_http_post)
    return controller


def _mem(path: str, body: str = "memory body", mtype: str = "project",
         confidence: str = "high", created: str = "2026-04-01",
         last_verified: str | None = None, score: float = 1.0,
         match_context: str = "") -> dict:
    """Build a MemoryResult-shaped dict as returned by the rewired recall route."""
    return {
        "path": path,
        "score": score,
        "match_context": match_context,
        "frontmatter": {
            "type": mtype,
            "confidence": confidence,
            "created": created,
            "last_verified": last_verified,
        },
        "body": body,
    }


# ---------------------------------------------------------------------------
# UserPromptSubmit behavior: short prompt / slash command skip
# ---------------------------------------------------------------------------


class TestUserPromptSkipConditions:
    def test_short_prompt_skipped(self, mock_recall, dedup_log_path, config_enabled):
        result = spellbook_hook._memory_recall_for_prompt("hi", cwd="/tmp/x")
        assert result is None
        assert mock_recall.calls == []

    def test_slash_command_skipped(self, mock_recall, dedup_log_path, config_enabled):
        result = spellbook_hook._memory_recall_for_prompt(
            "/commit some long slash command that exceeds ten chars",
            cwd="/tmp/x",
        )
        assert result is None
        assert mock_recall.calls == []

    def test_config_disabled_skips_all_injection(
        self, mock_recall, dedup_log_path, config_disabled,
    ):
        # UserPromptSubmit path
        prompt_out = spellbook_hook._memory_recall_for_prompt(
            "investigate the authentication module bug",
            cwd="/tmp/x",
        )
        # PreToolUse path
        tool_out = spellbook_hook._memory_recall_for_tool(
            "Edit",
            {"file_path": "/repo/spellbook/memory/filestore.py"},
            cwd="/tmp/x",
        )
        # File-read inject path (PostToolUse existing path)
        file_out = spellbook_hook._memory_inject(
            "Read",
            {"tool_input": {"file_path": "/repo/x.py"}, "cwd": "/tmp/x"},
        )
        assert prompt_out is None
        assert tool_out is None
        assert file_out is None
        assert mock_recall.calls == []


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------


class TestKeywordExtraction:
    def test_keyword_extraction_filters_stopwords(self):
        result = spellbook_hook._extract_keywords(
            "the authentication module is broken and the tests were failing"
        )
        assert result == [
            "authentication", "module", "broken", "tests", "failing",
        ]

    def test_keyword_extraction_captures_identifiers(self):
        result = spellbook_hook._extract_keywords(
            "CamelCase fooBar snake_case path/to/file.py"
        )
        assert result == [
            "CamelCase", "fooBar", "snake_case", "path/to/file.py",
        ]

    def test_keyword_extraction_keeps_alphanumeric_tokens(self):
        """Digit-bearing tokens like ``gap3``, ``py314``, ``ody0042`` must survive."""
        result = spellbook_hook._extract_keywords(
            "investigate gap3 regression in py314 for ticket ody0042"
        )
        assert result == [
            "investigate", "gap3", "regression", "py314", "ticket", "ody0042",
        ]


# ---------------------------------------------------------------------------
# Budget enforcement
# ---------------------------------------------------------------------------


class TestBudget:
    def test_budget_caps_memory_count(self):
        # 20 short memories, budget=5 count, 500 tokens
        mems = [_mem(path=f"/m/{i}.md", body="short body") for i in range(20)]
        capped = spellbook_hook._apply_memory_budget(
            mems, max_count=5, max_tokens=500,
        )
        assert capped == mems[:5]

    def test_budget_caps_total_tokens(self):
        # Each memory body is ~400 chars (~100 tokens); 3 fit in 500 tokens
        body = "x" * 400  # len/4 = 100 tokens
        mems = [_mem(path=f"/m/{i}.md", body=body) for i in range(10)]
        capped = spellbook_hook._apply_memory_budget(
            mems, max_count=5, max_tokens=500,
        )
        # Cumulative 100, 200, 300, 400, 500 -> 5 fit (<=500). 6th would push to 600.
        assert capped == mems[:5]

    def test_budget_stops_when_next_memory_would_exceed(self):
        mems = [
            _mem(path="/m/0.md", body="x" * 1200),  # 300 tokens
            _mem(path="/m/1.md", body="x" * 800),   # 200 tokens  (sum=500)
            _mem(path="/m/2.md", body="x" * 4),     # 1 token     (would push to 501)
        ]
        capped = spellbook_hook._apply_memory_budget(
            mems, max_count=5, max_tokens=500,
        )
        assert capped == mems[:2]


# ---------------------------------------------------------------------------
# Dedup log
# ---------------------------------------------------------------------------


class TestDedupLog:
    def test_dedup_skips_recent_memories(self, dedup_log_path, config_enabled):
        now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        recent = (now - timedelta(minutes=5)).isoformat()
        dedup_log_path.parent.mkdir(parents=True, exist_ok=True)
        dedup_log_path.write_text(json.dumps({
            "/mem/a.md": recent,
        }))

        mems = [
            _mem(path="/mem/a.md", body="body a"),
            _mem(path="/mem/b.md", body="body b"),
        ]
        log = spellbook_hook._load_dedup_log(now=now)
        filtered = spellbook_hook._filter_memories_by_dedup(mems, log)
        assert filtered == [mems[1]]

    def test_dedup_ttl_expires(self, dedup_log_path, config_enabled):
        now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        old = (now - timedelta(minutes=20)).isoformat()
        dedup_log_path.parent.mkdir(parents=True, exist_ok=True)
        dedup_log_path.write_text(json.dumps({
            "/mem/a.md": old,
        }))

        mems = [_mem(path="/mem/a.md", body="body a")]
        log = spellbook_hook._load_dedup_log(now=now)
        # Old entry should be dropped from the log after load.
        assert log == {}
        filtered = spellbook_hook._filter_memories_by_dedup(mems, log)
        assert filtered == mems

    def test_touch_dedup_writes_timestamps(self, dedup_log_path, config_enabled):
        now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        spellbook_hook._touch_dedup_log(
            ["/mem/a.md", "/mem/b.md"],
            now=now,
        )
        written = json.loads(dedup_log_path.read_text())
        assert written == {
            "/mem/a.md": now.isoformat(),
            "/mem/b.md": now.isoformat(),
        }

    def test_existing_file_read_injection_writes_dedup_log(
        self, mock_recall, dedup_log_path, config_enabled, monkeypatch,
    ):
        """The existing _memory_inject path must record into the dedup log."""
        now = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(spellbook_hook, "_utcnow", lambda: now)

        mock_recall.set_memories([
            _mem(path="/mem/x.md", body="x body"),
            _mem(path="/mem/y.md", body="y body"),
        ])
        # Ensure a namespace is derived: pass a cwd that looks like a project.
        monkeypatch.setattr(
            spellbook_hook,
            "_resolve_git_context",
            lambda cwd: (cwd, "main"),
        )

        out = spellbook_hook._memory_inject(
            "Read",
            {"tool_input": {"file_path": "/repo/file.py"}, "cwd": "/repo"},
        )
        assert out is not None
        written = json.loads(dedup_log_path.read_text())
        assert written == {
            "/mem/x.md": now.isoformat(),
            "/mem/y.md": now.isoformat(),
        }


# ---------------------------------------------------------------------------
# PreToolUse path extraction
# ---------------------------------------------------------------------------


class TestPreToolUseExtraction:
    def test_pretooluse_bash_extracts_paths(self):
        paths = spellbook_hook._extract_tool_paths(
            "Bash",
            {"command": "cat /etc/hosts && vim src/main.py"},
        )
        assert paths == ["/etc/hosts", "src/main.py"]

    def test_pretooluse_write_extracts_file_path(self):
        paths = spellbook_hook._extract_tool_paths(
            "Write",
            {"file_path": "/repo/output.txt", "content": "hello"},
        )
        assert paths == ["/repo/output.txt"]

    def test_pretooluse_edit_extracts_file_path(self):
        paths = spellbook_hook._extract_tool_paths(
            "Edit",
            {"file_path": "/repo/module.py", "old_string": "a", "new_string": "b"},
        )
        assert paths == ["/repo/module.py"]


# ---------------------------------------------------------------------------
# Formatter: new MemoryResult shape
# ---------------------------------------------------------------------------


class TestFormatter:
    def test_format_memory_xml_new_shape(self):
        mems = [
            _mem(
                path="/mem/a.md",
                body="first body",
                mtype="project",
                confidence="high",
                created="2026-04-01",
                last_verified="2026-04-10",
                score=0.75,
                match_context="match line",
            ),
            _mem(
                path="/mem/b.md",
                body="second body",
                mtype="user",
                confidence="medium",
                created="2026-03-15",
                last_verified=None,
                score=0.5,
                match_context="",
            ),
        ]
        out = spellbook_hook._format_memory_xml(mems)
        expected = (
            "<spellbook-memory-context>\n"
            '  <memory path="/mem/a.md" type="project" confidence="high"'
            ' created="2026-04-01" last_verified="2026-04-10" score="0.75">\n'
            "    first body\n"
            "  </memory>\n"
            '  <memory path="/mem/b.md" type="user" confidence="medium"'
            ' created="2026-03-15" last_verified="" score="0.50">\n'
            "    second body\n"
            "  </memory>\n"
            "</spellbook-memory-context>"
        )
        assert out == expected


class TestLoadDedupLogLogging:
    """I8: distinguish FileNotFoundError from other OSError when loading dedup."""

    def test_load_dedup_log_logs_unexpected_oserror(
        self, mock_http, tmp_path, monkeypatch, dedup_log_path,
    ):
        # Seed the dedup log so .exists() returns True.
        dedup_log_path.parent.mkdir(parents=True, exist_ok=True)
        dedup_log_path.write_text("{}")

        # Force read_text to raise a non-FileNotFoundError OSError — only
        # for the dedup log path, not for every Path in the process.
        orig_read_text = Path.read_text

        def selective_raise(self, *a, **kw):
            if Path(self) == Path(dedup_log_path):
                raise PermissionError("denied")
            return orig_read_text(self, *a, **kw)

        monkeypatch.setattr(Path, "read_text", selective_raise)

        # Freeze datetime.now(timezone.utc) inside the hook module so we can
        # assert exact payload equality and pin the log format.
        import datetime as _dt
        frozen = _dt.datetime(2026, 4, 14, 12, 0, 0, tzinfo=_dt.timezone.utc)

        class _FrozenDT(_dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return frozen if tz is None else frozen.astimezone(tz)

        monkeypatch.setattr(spellbook_hook, "datetime", _FrozenDT)

        result = spellbook_hook._load_dedup_log()
        assert result == {}

        # Exactly one POST to /api/hook-log routed via _log_hook_error.
        hook_log_calls = [
            c for c in mock_http.calls if c["url"].endswith("/api/hook-log")
        ]
        assert len(hook_log_calls) == 1
        payload = hook_log_calls[0]["payload"]
        assert payload["timestamp"] == frozen.isoformat()
        assert payload["event"] == f"memory_dedup_load:{dedup_log_path}"
        assert payload["traceback"].strip().endswith(
            "PermissionError: denied"
        )

    def test_load_dedup_log_silent_on_missing_file(
        self, mock_http, tmp_path, monkeypatch,
    ):
        """A genuinely missing file is NOT logged — that's the normal cold path."""
        missing = tmp_path / "no-such-file.json"
        monkeypatch.setattr(spellbook_hook, "DEDUP_LOG_PATH", missing)

        result = spellbook_hook._load_dedup_log()
        assert result == {}
        hook_log_calls = [
            c for c in mock_http.calls if c["url"].endswith("/api/hook-log")
        ]
        assert hook_log_calls == []


# ---------------------------------------------------------------------------
# Dedup log: exclusive-lock serialization
# ---------------------------------------------------------------------------


class TestDedupLogLocking:
    def test_dedup_log_lock_serializes_concurrent_writes(
        self, dedup_log_path, monkeypatch,
    ):
        """Two threads touching disjoint paths must both land entries in the log.

        Before the lock was added, the read-modify-write race allowed one
        thread to overwrite the other's new entry (last-writer-wins), losing
        entries with identical timestamps.
        """
        import sys as _sys
        if _sys.platform == "win32":
            pytest.skip(
                "fcntl-based serialization is POSIX-only; on Windows the "
                "dedup log falls back to last-writer-wins (documented)."
            )
        import threading

        barrier = threading.Barrier(2)

        def writer(paths):
            barrier.wait()
            # Force a handful of interleavings.
            for _ in range(25):
                spellbook_hook._touch_dedup_log(paths)

        t1 = threading.Thread(target=writer, args=(["project/alpha.md"],))
        t2 = threading.Thread(target=writer, args=(["project/beta.md"],))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        written = json.loads(dedup_log_path.read_text())
        assert set(written.keys()) == {"project/alpha.md", "project/beta.md"}

    def test_dedup_log_lock_timeout_falls_back_gracefully(
        self, mock_http, dedup_log_path, monkeypatch,
    ):
        """When fcntl.flock is permanently contended, the write degrades safely."""
        import sys as _sys
        if _sys.platform == "win32":
            pytest.skip("fcntl is POSIX-only; lock fallback path is a no-op on Windows")
        import fcntl

        def always_block(fd, op):
            raise BlockingIOError("locked")

        monkeypatch.setattr(fcntl, "flock", always_block)

        # Must not raise; must not block indefinitely.
        spellbook_hook._touch_dedup_log(["project/alpha.md"])

        # Because flock was monkeypatched to always fail, we fell back to
        # the unlocked last-writer-wins path. The entry should still land.
        written = json.loads(dedup_log_path.read_text())
        assert list(written.keys()) == ["project/alpha.md"]

        # And the diagnostic must have been logged via _log_hook_error so
        # operators can spot contention in the daemon's hook-log stream.
        hook_log_calls = [
            c for c in mock_http.calls if c["url"].endswith("/api/hook-log")
        ]
        assert len(hook_log_calls) == 1
        payload = hook_log_calls[0]["payload"]
        assert payload["event"] == f"memory_dedup_lock_timeout:{dedup_log_path}"
