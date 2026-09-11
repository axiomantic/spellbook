"""Tests for the session-pull bundled script.

Fixtures are synthetic stores built in tmp_path (JSONL for claude_code,
SQLite for opencode/aionui/antigravity). No real user stores are touched;
roots are injected via env overrides (monkeypatch.setenv — the sanctioned
use) or direct root arguments.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

_SKILL_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "session-pull"
    / "session_pull.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("session_pull", _SKILL_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _claude_record(
    rtype: str,
    content: Any,
    *,
    ts: str = "2026-09-10T10:00:00.000Z",
    **extra: Any,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "type": rtype,
        "timestamp": ts,
        "sessionId": "11111111-2222-3333-4444-555555555555",
        "cwd": "/repo",
        "gitBranch": "main",
        "version": "2.0.0",
    }
    if rtype in ("user", "assistant"):
        rec["message"] = {"role": rtype, "content": content}
    rec.update(extra)
    return rec


def _write_claude_session(
    root: Path, cwd: str, session_id: str, records: list[dict[str, Any]]
) -> Path:
    project = root / "projects" / _load_module().encode_cwd_literal(cwd)
    project.mkdir(parents=True, exist_ok=True)
    path = project / f"{session_id}.jsonl"
    lines = [json.dumps(r) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _make_opencode_db(root: Path) -> None:
    """Create an opencode-shaped db with the verified schema."""
    root.mkdir(parents=True, exist_ok=True)
    db = root / "opencode.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE project (id TEXT PRIMARY KEY, worktree TEXT);
        CREATE TABLE session (
            id TEXT PRIMARY KEY, project_id TEXT, workspace_id TEXT,
            parent_id TEXT, slug TEXT, directory TEXT, path TEXT,
            title TEXT, version TEXT, share_url TEXT,
            summary_additions TEXT, summary_deletions TEXT, summary_files TEXT,
            metadata TEXT, cost TEXT, tokens_input INTEGER, tokens_output INTEGER,
            tokens_reasoning INTEGER, tokens_cache INTEGER,
            revert TEXT, permission TEXT, agent TEXT, model TEXT,
            time_created INTEGER, time_updated INTEGER,
            time_compacting INTEGER, time_archived INTEGER
        );
        CREATE TABLE message (
            id TEXT, session_id TEXT, time_created INTEGER,
            time_updated INTEGER, data TEXT
        );
        CREATE TABLE part (
            id TEXT, message_id TEXT, session_id TEXT, data TEXT,
            time_created INTEGER, time_updated INTEGER
        );
        """
    )
    conn.execute("INSERT INTO project VALUES ('proj1', '/repo')")
    conn.commit()
    conn.close()
    return {}


def _insert_opencode_session(
    root: Path,
    session_id: str,
    title: str,
    parts: list[tuple[str, int, dict[str, Any]]],
    *,
    time_compacting: int | None = None,
    directory: str = "/repo",
) -> None:
    """parts: (message_id, epoch_ms, part_data)."""
    conn = sqlite3.connect(root / "opencode.db")
    conn.execute(
        "INSERT INTO session (id, project_id, slug, directory, path, title, "
        "model, agent, time_created, time_updated, time_compacting) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            session_id, "proj1", title, directory, title, title,
            "test/model", "build",
            parts[0][1] if parts else 0, parts[-1][1] if parts else 0,
            time_compacting,
        ),
    )
    for i, (mid, ts, pdata) in enumerate(parts):
        msg_key = f"{session_id}:{mid}"
        if not conn.execute(
            "SELECT 1 FROM message WHERE id = ?", (msg_key,)
        ).fetchone():
            conn.execute(
                "INSERT INTO message VALUES (?,?,?,?,?)",
                (msg_key, session_id, ts, ts,
                 json.dumps({"id": mid, "role": "user"})),
            )
        conn.execute(
            "INSERT INTO part VALUES (?,?,?,?,?,?)",
            (f"p{i}", f"{session_id}:{mid}", session_id, json.dumps(pdata),
             ts, ts),
        )
    conn.commit()
    conn.close()


def _make_aionui_db(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "aionui-backend.db")
    conn.executescript(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY, user_id TEXT, name TEXT, type TEXT,
            extra TEXT, model TEXT, status TEXT, source TEXT,
            channel_chat_id TEXT, pinned INTEGER, pinned_at INTEGER,
            created_at INTEGER, updated_at INTEGER, project_id TEXT,
            folder_id TEXT, name_source TEXT, archived_at INTEGER
        );
        CREATE TABLE messages (
            id TEXT PRIMARY KEY, conversation_id TEXT, msg_id TEXT,
            type TEXT, content TEXT, position INTEGER, status TEXT,
            hidden INTEGER, created_at INTEGER, backend_turn_id TEXT
        );
        CREATE TABLE assistant_sessions (
            id TEXT PRIMARY KEY, user_id TEXT, agent_type TEXT,
            conversation_id TEXT, workspace TEXT, chat_id TEXT,
            created_at INTEGER, last_activity INTEGER
        );
        CREATE TABLE conversation_artifacts (
            id TEXT PRIMARY KEY, conversation_id TEXT, kind TEXT, path TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO conversations (id, user_id, name, type, extra, model, "
        "status, source, created_at, updated_at) VALUES "
        "('conv1','u1','Test conversation','agent','{}','m1','ok',"
        "'local',1757400000000,1757401000000)"
    )
    conn.commit()
    conn.close()


def _aionui_msg(
    conversation_id: str,
    mtype: str,
    content: dict[str, Any],
    position: int,
    *,
    hidden: int = 0,
    created_at: int = 1757400000000,
) -> tuple[str, str, int, str, int, int]:
    return (
        f"m{position}", conversation_id, f"msg{position}", mtype,
        json.dumps(content), position, "finish", hidden, created_at, None,
    )


def _make_antigravity_db(root: Path, conversation_id: str) -> None:
    (root / "conversations").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "conversations" / f"{conversation_id}.db")
    conn.executescript(
        """
        CREATE TABLE steps (
            idx INTEGER PRIMARY KEY, step_type INTEGER, status INTEGER,
            has_subtrajectory INTEGER, metadata BLOB, error_details BLOB,
            permissions BLOB, task_details BLOB, render_info BLOB,
            step_payload BLOB, step_format INTEGER
        );
        """
    )
    conn.commit()
    conn.close()


def _pb_len_field(field_no: int, payload: bytes) -> bytes:
    """Encode one length-delimited protobuf field."""
    key = (field_no << 3) | 2
    return bytes([key, len(payload)]) + payload


# ---------------------------------------------------------------------------
# claude_code
# ---------------------------------------------------------------------------


def test_claude_compact_mode_uses_latest_boundary(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "claude"
    records = [
        _claude_record("user", "first request", ts="2026-09-10T10:00:00Z"),
        _claude_record("assistant", "working", ts="2026-09-10T10:00:05Z"),
        _claude_record(
            "user", "summary of earlier work",
            ts="2026-09-10T10:01:00Z", isCompactSummary=True,
            isMeta=True,
        ),
        _claude_record("assistant", "post-compact work",
                       ts="2026-09-10T10:02:00Z"),
        _claude_record(
            "assistant",
            [{"type": "tool_use", "name": "Bash",
              "input": {"command": "pytest"}}],
            ts="2026-09-10T10:02:10Z",
        ),
        _claude_record("user", "subagent traffic", isSidechain=True),
    ]
    _write_claude_session(root, "/repo", "sid-1", records)

    warnings: list[str] = []
    envelope = sp.parse_claude_session(
        root / "projects" / sp.encode_cwd_literal("/repo") / "sid-1.jsonl",
        "compact", root, warnings,
    )
    assert envelope["source"] == "claude_code"
    assert envelope["session"]["compacted"] is True
    assert envelope["summary"] is not None
    assert envelope["summary"]["text"] == "summary of earlier work"
    texts = [e.get("text", "") for e in envelope["events"]]
    assert "working" not in texts, "pre-compact events must be dropped"
    assert "post-compact work" in texts
    kinds = [e["type"] for e in envelope["events"]]
    assert "compaction" in kinds, "anchor must be re-injected first"
    assert envelope["events"][0]["type"] == "compaction"
    tool_calls = [e for e in envelope["events"] if e["type"] == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool"] == "Bash"
    assert "subagent traffic excluded" not in " ".join(texts)
    assert warnings == []


def test_claude_full_mode_keeps_everything(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "claude"
    records = [
        _claude_record("user", "early", ts="2026-09-10T10:00:00Z"),
        _claude_record(
            "user", "summary text", ts="2026-09-10T10:01:00Z",
            isCompactSummary=True, isMeta=True,
        ),
        _claude_record("user", "subagent", isSidechain=True),
    ]
    _write_claude_session(root, "/repo", "sid-2", records)
    warnings: list[str] = []
    envelope = sp.parse_claude_session(
        root / "projects" / sp.encode_cwd_literal("/repo") / "sid-2.jsonl",
        "full", root, warnings,
    )
    texts = [e.get("text", "") for e in envelope["events"]]
    assert "early" in texts
    assert "subagent" in texts
    # The compaction record itself must survive in full mode too — the
    # envelope claims every reconstructed event.
    kinds = [e["type"] for e in envelope["events"]]
    assert "compaction" in kinds


def test_claude_work_root_resolves_sidecar_state(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    """A session under ~/.claude-work must resolve todos from the SAME root,
    not from ~/.claude (regression: dispatch_pull used to hard-code the
    default root regardless of where the transcript came from)."""
    sp = _load_module()
    work_root = tmp_path / "home" / ".claude-work"
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = work_root / "projects" / sp.encode_cwd_literal("/repo")
    project.mkdir(parents=True)
    (project / "wk-1.jsonl").write_text(
        json.dumps(_claude_record("user", "worktree session")) + "\n",
        encoding="utf-8",
    )
    todos = work_root / "todos"
    todos.mkdir(parents=True)
    (todos / "wk-1-agent-todo.json").write_text(
        json.dumps([{"content": "wt todo", "status": "pending"}]),
        encoding="utf-8",
    )
    assert sp.main(["pull", "--source", "claude_code", "--id", "wk-1"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["todos"] == [{"content": "wt todo", "status": "pending"}]
    assert envelope["session"]["id"] == "wk-1"


def test_claude_list_filters_by_cwd(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "claude"
    _write_claude_session(root, "/repo", "s-a", [_claude_record("user", "a")])
    _write_claude_session(root, "/other", "s-b", [_claude_record("user", "b")])
    warnings: list[str] = []
    sessions = sp.list_claude_sessions(root, "/repo", warnings)
    assert [s["id"] for s in sessions] == ["s-a"]
    assert sessions[0]["title"] == "a"


def test_claude_todo_and_title_precedence(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "claude"
    records = [
        {"type": "summary", "summary": "older title",
         "timestamp": "2026-09-10T10:00:00Z"},
        _claude_record("user", "first user message"),
        _claude_record("assistant", "reply", customTitle="Custom Name"),
    ]
    _write_claude_session(root, "/repo", "sid-3", records)
    todos_dir = root / "todos"
    todos_dir.mkdir()
    (todos_dir / "sid-3-agent-todo.json").write_text(
        json.dumps([{"content": "ship it", "status": "in_progress"}]),
        encoding="utf-8",
    )
    warnings: list[str] = []
    envelope = sp.parse_claude_session(
        root / "projects" / sp.encode_cwd_literal("/repo") / "sid-3.jsonl",
        "compact", root, warnings,
    )
    assert envelope["session"]["title"] == "Custom Name"
    assert envelope["todos"] == [{"content": "ship it",
                                  "status": "in_progress"}]


def test_claude_title_custom_beats_ai_regardless_of_order(tmp_path: Path) -> None:
    """customTitle outranks aiTitle even when the aiTitle record comes first.

    Precedence is enforced by key rank, not record order (roundup.py
    verification); before the rank fix the first title-bearing record won.
    """
    sp = _load_module()
    root = tmp_path / "claude"
    records = [
        _claude_record("assistant", "reply", aiTitle="AI Generated"),
        _claude_record("user", "later", customTitle="Pinned Name"),
    ]
    _write_claude_session(root, "/repo", "sid-a", records)
    warnings: list[str] = []
    path = root / "projects" / sp.encode_cwd_literal("/repo") / "sid-a.jsonl"
    envelope = sp.parse_claude_session(path, "compact", root, warnings)
    assert envelope["session"]["title"] == "Pinned Name"
    # The lightweight list scan must agree with the full parse.
    sessions = sp.list_claude_sessions(root, "/repo", warnings)
    assert sessions[0]["title"] == "Pinned Name"


def test_claude_title_custom_first_beats_later_ai(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "claude"
    records = [
        _claude_record("user", "hi", customTitle="Pinned Name"),
        _claude_record("assistant", "reply", aiTitle="AI Generated"),
    ]
    _write_claude_session(root, "/repo", "sid-b", records)
    warnings: list[str] = []
    path = root / "projects" / sp.encode_cwd_literal("/repo") / "sid-b.jsonl"
    envelope = sp.parse_claude_session(path, "compact", root, warnings)
    assert envelope["session"]["title"] == "Pinned Name"
    sessions = sp.list_claude_sessions(root, "/repo", warnings)
    assert sessions[0]["title"] == "Pinned Name"


# ---------------------------------------------------------------------------
# opencode
# ---------------------------------------------------------------------------


def test_opencode_compact_boundary(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "opencode"
    _make_opencode_db(root)
    sid = "ses_test1"
    compact_ms = 1757400100000
    _insert_opencode_session(
        root, sid, "My session",
        [
            ("m1", 1757400000000,
             {"type": "text", "text": "pre-compact question"}),
            ("m1", 1757400000001, {"type": "step-start"}),
            ("m1", 1757400000002,
             {"type": "tool", "tool": "bash", "callID": "c1",
              "state": {"status": "completed",
                        "output": {"title": "ran", "output": "ok"}}}),
            ("m1", compact_ms,
             {"type": "compaction", "text": "everything before is summarized"}),
            ("m2", compact_ms + 1000, {"type": "text", "text": "after"}),
        ],
        time_compacting=compact_ms,
        directory="/repo",
    )
    warnings: list[str] = []
    envelope = sp.parse_opencode_session(root, sid, "compact", warnings)
    assert envelope["session"]["title"] == "My session"
    assert envelope["summary"]["text"] == "everything before is summarized"
    texts = [e.get("text", "") for e in envelope["events"]]
    assert "pre-compact question" not in texts
    assert "after" in texts
    assert envelope["warnings"] == []


def test_opencode_tool_string_output(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "opencode"
    _make_opencode_db(root)
    _insert_opencode_session(
        root, "ses_s", "t",
        [
            ("m1", 1757400000000,
             {"type": "tool", "tool": "read", "callID": "c9",
              "state": {"status": "completed", "output": "plain string"}}),
        ],
        directory="/repo",
    )
    warnings: list[str] = []
    envelope = sp.parse_opencode_session(root, "ses_s", "full", warnings)
    results = [e for e in envelope["events"] if e["type"] == "tool_result"]
    assert results and results[0]["text"] == "plain string"


def test_opencode_thinking_excluded_by_default(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "opencode"
    _make_opencode_db(root)
    _insert_opencode_session(
        root, "ses_th", "t",
        [
            ("m1", 1757400000000,
             {"type": "reasoning", "text": "deep thought"}),
            ("m1", 1757400000001, {"type": "text", "text": "answer"}),
        ],
    )
    envelope = sp.parse_opencode_session(root, "ses_th", "full", [], False)
    assert [e["type"] for e in envelope["events"]] == ["message"]
    envelope = sp.parse_opencode_session(root, "ses_th", "full", [], True)
    kinds = [e["type"] for e in envelope["events"]]
    assert kinds == ["thinking", "message"]


# ---------------------------------------------------------------------------
# aionui
# ---------------------------------------------------------------------------


def test_aionui_event_mapping(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "aionui"
    _make_aionui_db(root)
    conn = sqlite3.connect(root / "aionui-backend.db")
    rows = [
        _aionui_msg("conv1", "text", {"content": "hello"}, 0),
        _aionui_msg("conv1", "thinking", {"content": "hmm"}, 1),
        _aionui_msg("conv1", "tool_call",
                    {"call_id": "c1", "name": "run", "args": {"x": 1},
                     "output": "done"}, 2),
        _aionui_msg("conv1", "tips",
                    {"content": "success", "type": "info"}, 3),
        _aionui_msg("conv1", "text", {"content": "hidden note"}, 4, hidden=1),
    ]
    conn.executemany("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    warnings: list[str] = []
    # Default drops thinking rows, matching the claude/opencode parsers.
    events = sp.parse_aionui_session(root, "conv1", "compact", warnings)["events"]
    assert [e["type"] for e in events] == [
        "message", "tool_call", "tool_result", "meta", "message"]

    envelope = sp.parse_aionui_session(root, "conv1", "compact", warnings,
                                       include_thinking=True)
    events = envelope["events"]
    kinds = [e["type"] for e in events]
    assert kinds == ["message", "thinking", "tool_call", "tool_result",
                     "meta", "message"]
    assert events[0].get("role") is None, "aionui text rows carry no role"
    assert events[1]["type"] == "thinking"
    assert events[2]["tool"] == "run"
    assert events[2]["meta"]["input"] == {"x": 1}
    assert events[3]["text"] == "done"
    assert events[4]["meta"]["kind"] == "aionui_tip"
    assert events[5].get("hidden") is True


def test_aionui_workspace_and_listing(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "aionui"
    _make_aionui_db(root)
    conn = sqlite3.connect(root / "aionui-backend.db")
    conn.execute(
        "INSERT INTO assistant_sessions VALUES "
        "('as1','u1','aionrs','conv1','/repo','chat',NULL,NULL)"
    )
    conn.commit()
    conn.close()
    warnings: list[str] = []
    sessions = sp.list_aionui_sessions(root, "/repo", warnings)
    assert len(sessions) == 1
    assert sessions[0]["workspaces"] == ["/repo"]
    miss = sp.list_aionui_sessions(root, "/elsewhere", warnings)
    assert miss == []


def test_aionui_root_env_override(tmp_path: Path, monkeypatch) -> None:
    sp = _load_module()
    monkeypatch.setenv("SPELLBOOK_SESSION_PULL_AIONUI_ROOT",
                       str(tmp_path / "custom"))
    assert sp.aionui_root() == tmp_path / "custom"


def test_aionui_root_os_aware_default(tmp_path: Path, monkeypatch) -> None:
    """Default root mirrors installer/config.py per-OS Electron layout."""
    sp = _load_module()
    monkeypatch.delenv("SPELLBOOK_SESSION_PULL_AIONUI_ROOT", raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    if sp.sys.platform == "darwin":
        monkeypatch.delenv("APPDATA", raising=False)
        expected = (home / "Library" / "Application Support" / "AionUi"
                    / "aionui")
    elif sp.sys.platform == "win32":
        monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
        expected = home / "AppData" / "Roaming" / "AionUi" / "aionui"
    else:
        expected = home / ".config" / "AionUi" / "aionui"
    assert sp.aionui_root() == expected


# ---------------------------------------------------------------------------
# antigravity
# ---------------------------------------------------------------------------


def test_pb_walk_roundtrip_and_malformed_tail() -> None:
    sp = _load_module()
    payload = _pb_len_field(1, b"hello world") + _pb_len_field(2, b"x" * 5)
    fields = sp.pb_walk(payload)
    assert [(f, w) for f, w, _v in fields] == [(1, 2), (2, 2)]
    assert fields[0][2] == b"hello world"
    # Truncated varint tail must stop cleanly, not raise.
    fields = sp.pb_walk(b"\x0a\x80")
    assert fields == []


def test_pb_collect_strings_unwraps_nested_message() -> None:
    sp = _load_module()
    # field 3 wraps a nested message whose field 1 wraps the text — the
    # length byte (0x48='H') must NOT survive glued onto the text.
    inner = _pb_len_field(1, b"code review the changes pls")
    wrapper = _pb_len_field(3, inner)
    blob = bytes([0x0A, len(wrapper)]) + wrapper
    strings = sp._pb_collect_strings(blob)
    assert "code review the changes pls" in strings
    assert not any(s.startswith("H") for s in strings)


def test_antigravity_extraction(tmp_path: Path) -> None:
    sp = _load_module()
    root = tmp_path / "antigravity"
    _make_antigravity_db(root, "agy1")
    conn = sqlite3.connect(root / "conversations" / "agy1.db")
    steps = [
        # user prompt (step_type 14)
        (0, 14, 0, _agy_user_prompt_step("run the tests and fix failures")),
        # state marker row: skipped
        (1, 15, 0, _pb_len_field(1, b"sessionID") ),
        # tool call row (call id + tool name + JSON args)
        (2, 21, 0,
         bytes([0x0A, 0x09]) + b"call_1145"
         + bytes([0x12, 11]) + b"run_command"
         + bytes([0x1A, len(b'{"Cwd":"/repo","Cmd":"pytest"}')])
         + b'{"Cwd":"/repo","Cmd":"pytest"}'),
        # task notification row
        (3, 101, 0,
         _pb_len_field(
             1,
             b"[Message] timestamp=2026-09-10T12:00:00Z sender=agy "
             b"priority=MESSAGE_PRIORITY_NORMAL Run pytest finished",
         )),
    ]
    for idx, stype, sfmt, payload in steps:
        conn.execute(
            "INSERT INTO steps VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (idx, stype, 3, 0, None, None, None, None, None, payload, sfmt),
        )
    conn.commit()
    conn.close()

    warnings: list[str] = []
    envelope = sp.parse_antigravity_session(root, "agy1", "compact", warnings)
    events = envelope["events"]
    kinds = [e["type"] for e in events]
    assert kinds == ["message", "tool_call", "message"]
    assert events[0]["role"] == "user"
    assert events[0]["text"] == "run the tests and fix failures"
    tool = events[1]
    assert tool["meta"]["call_id"] == "call_1145"
    assert tool["meta"]["input"] == {"Cwd": "/repo", "Cmd": "pytest"}
    assert events[2]["meta"]["record"] == "task_notification"
    assert events[2]["text"] == "Run pytest finished"
    assert envelope["warnings"], "antigravity must warn about best-effort"


def _agy_user_prompt_step(text: str) -> bytes:
    return _pb_len_field(1, _pb_len_field(1, text.encode()))


# ---------------------------------------------------------------------------
# envelope / output contract
# ---------------------------------------------------------------------------


def test_redaction_patterns() -> None:
    sp = _load_module()
    envelope = {
        "events": [
            {"type": "message", "text": "key AKIAIOSFODNN7EXAMPLE and "
                                        "sk-ant-abc123def456ghi789jkl"},
        ],
        "warnings": [],
    }
    cleaned, kinds = sp.apply_redaction(envelope)
    text = cleaned["events"][0]["text"]
    assert "AKIAIOSFODNN7EXAMPLE" not in text
    assert "[REDACTED:aws_access_key]" in text
    assert "sk-ant-abc123def456ghi789jkl" not in text
    assert "aws_access_key" in kinds


def test_write_out_permissions_and_overwrite_guard(tmp_path: Path) -> None:
    sp = _load_module()
    out = tmp_path / "export.json"
    sp.write_out(out, "one", force=False)
    if os.name != "nt":
        # Windows does not honor POSIX file modes; st_mode is always 0o666.
        mode = out.stat().st_mode & 0o777
        assert mode == 0o600, "exports must not be group/world readable"
    try:
        sp.write_out(out, "two", force=False)
    except SystemExit as exc:
        assert "refusing to overwrite" in str(exc)
    else:
        raise AssertionError("overwrite must be refused without --force")
    sp.write_out(out, "two", force=True)
    assert out.read_text(encoding="utf-8") == "two"


def test_handoff_budget_elides_and_marks(tmp_path: Path) -> None:
    sp = _load_module()
    events = [
        {"seq": i, "type": "message", "text": f"turn {i} " + "x" * 500}
        for i in range(10)
    ]
    envelope = {
        "source": "claude_code", "mode": "compact",
        "generated_at": "2026-09-10T00:00:00Z",
        "session": {"id": "s", "title": "T", "cwd": "/repo",
                    "git_branch": "main"},
        "summary": None, "events": events, "todos": [],
        "warnings": [],
    }
    md = sp.render_handoff(envelope, budget_chars=2000)
    assert "## Recent transcript" in md
    assert "elided by the" in md, "truncation must be explicit"
    assert "turn 9" in md, "newest events are included first"


def test_handoff_includes_summary_and_todos() -> None:
    sp = _load_module()
    envelope = {
        "source": "opencode", "mode": "compact",
        "generated_at": "2026-09-10T00:00:00Z",
        "session": {"id": "s", "title": "T", "cwd": "/repo",
                    "git_branch": "feat"},
        "summary": {"text": "We migrated the parser.",
                    "boundary_seq": 3},
        "events": [{"seq": 4, "type": "message", "text": "next steps"}],
        "todos": [{"content": "ship it", "status": "in_progress"}],
        "warnings": [],
    }
    md = sp.render_handoff(envelope, budget_chars=10000)
    assert "## Position (latest compaction summary)" in md
    assert "We migrated the parser." in md
    assert "- [~] ship it" in md
    assert "latest compaction boundary" in md


# ---------------------------------------------------------------------------
# CLI dispatch (in-process; env-rooted fixtures)
# ---------------------------------------------------------------------------


def test_cli_sources_and_list_via_env_roots(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    sp = _load_module()
    monkeypatch.setenv("SPELLBOOK_SESSION_PULL_CLAUDE_ROOT", str(tmp_path / "c"))
    monkeypatch.setenv(
        "SPELLBOOK_SESSION_PULL_OPENCODE_ROOT", str(tmp_path / "o")
    )
    monkeypatch.setenv(
        "SPELLBOOK_SESSION_PULL_AIONUI_ROOT", str(tmp_path / "a")
    )
    monkeypatch.setenv(
        "SPELLBOOK_SESSION_PULL_ANTIGRAVITY_ROOT", str(tmp_path / "g")
    )
    assert sp.main(["sources"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sources"][0]["source"] == "claude_code"
    assert payload["sources"][0]["available"] is False

    # claude session in the fixture root
    root = tmp_path / "c"
    _write_claude_session(root, "/repo", "cli-1", [_claude_record("user", "hi")])
    assert sp.main(["list", "--source", "claude_code", "--cwd", "/repo"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sources"]["claude_code"][0]["id"] == "cli-1"

    assert sp.main(["pull", "--source", "claude_code", "--id", "cli-1",
                    "--mode", "compact"]) == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["session"]["id"] == "cli-1"
    assert envelope["events"][0]["text"] == "hi"


def test_cli_out_flag_routes_to_file(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    sp = _load_module()
    monkeypatch.setenv("SPELLBOOK_SESSION_PULL_CLAUDE_ROOT", str(tmp_path / "c"))
    root = tmp_path / "c"
    _write_claude_session(root, "/repo", "out-1", [_claude_record("user", "hi")])
    out_path = tmp_path / "export.json"
    assert sp.main(["pull", "--source", "claude_code", "--id", "out-1",
                    "--mode", "compact", "--out", str(out_path)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["written"] == str(out_path)
    if os.name != "nt":
        assert (out_path.stat().st_mode & 0o777) == 0o600
    envelope = json.loads(out_path.read_text(encoding="utf-8"))
    assert envelope["source"] == "claude_code"

    assert sp.main(["pull", "--source", "claude_code", "--id", "out-1",
                    "--mode", "handoff", "--out", str(tmp_path / "h.md")]) == 0
    handoff_summary = json.loads(capsys.readouterr().out)
    assert handoff_summary["bytes"] > 0
    assert "# Session handoff" in (tmp_path / "h.md").read_text(
        encoding="utf-8"
    )


def test_cli_unknown_source_fails(tmp_path: Path) -> None:
    sp = _load_module()
    try:
        sp.main(["pull", "--source", "nope", "--id", "x"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("argparse must reject unknown sources")


def test_sqlite_snapshot_is_read_only_and_cleans_up(
    tmp_path: Path, monkeypatch: Any
) -> None:
    sp = _load_module()
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    db = tmp_path / "live.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    before = db.read_bytes()
    with sp.SqliteSnapshot(db) as snap:
        rows = snap.execute("SELECT x FROM t").fetchall()
        assert rows[0][0] == 1
        # Writes must not reach the original.
        snap.execute("INSERT INTO t VALUES (2)")
        snap.commit()
    after = db.read_bytes()
    assert before == after
    leftovers = list(tmp_path.glob("session-pull-snapshot-*"))
    assert leftovers == [], "snapshot temp dirs must be removed"