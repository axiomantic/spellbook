#!/usr/bin/env python3
"""session_pull.py — pull coding-agent session history + hidden context into a
portable format another assistant can pick up.

Bundled with the ``session-pull`` skill. Stdlib-only (argparse, json, sqlite3,
os, re, shutil, tempfile, datetime, pathlib) so it runs anywhere without a
runtime dependency. Precedent: ``skills/rounding-up-worktree-sessions/roundup.py``.

Supported sources (verified against live stores 2026-09-10):

==================  ==========================================================
source              storage
==================  ==========================================================
claude_code         ~/.claude/projects/<encoded-cwd>/<uuid>.jsonl plus
                    ~/.claude-work/projects (same layout). JSONL, typed
                    records. ALSO covers Claude Desktop *local* sessions,
                    which persist to the same store (only the remote
                    claude.ai cache in IndexedDB is out of scope).
opencode            ~/.local/share/opencode/opencode.db — SQLite with
                    session/message/part tables and JSON ``data`` columns.
                    Current schema ONLY: the legacy ``storage/`` JSON tree
                    is deliberately unsupported (operator decision).
aionui              ~/Library/Application Support/AionUi/aionui/
                    aionui-backend.db — conversations/messages/
                    assistant_sessions tables; ``messages.content`` is a
                    JSON blob and ``messages.hidden`` marks UI-hidden rows.
antigravity         ~/.gemini/antigravity/conversations/<uuid>.db —
                    per-conversation SQLite; ``steps.step_payload`` blobs
                    are protobuf WITHOUT a public schema, so extraction is
                    heuristic (generic wire-format walk + string carving).
                    Degrades gracefully; use ``debug-dump`` for archaeology.
==================  ==========================================================

Output contract
---------------
* ``sources`` / ``list`` / ``pull`` (modes ``compact``/``full``) print exactly
  one JSON object on stdout (``ensure_ascii=False``).
* ``pull --mode handoff`` prints a Markdown handoff document (nothing else) —
  that is the artifact to paste into / point the next assistant at.
* ``--out PATH`` writes 0600, refuses to overwrite without ``--force``.

Modes
-----
* ``full``    every reconstructed event, in source order.
* ``compact`` default. Latest compaction summary VERBATIM + all events after
              its boundary + todo/file-state snapshots + session metadata.
              With no compaction point this equals ``full``.
* ``handoff`` Markdown rendering of the compact view under a character
              budget (--budget-chars, default 50000), newest-first.

Safety
------
* Strictly read-only against every source store. SQLite sources are read
  through snapshot copies (db + -wal + -shm copied to a temp dir, copy
  removed afterwards); live WAL databases are never opened in place.
* ``--redact`` runs a best-effort secret pattern pass over all extracted
  text. It is a convenience, not a security boundary — review exports
  before sharing.
* Per-source parse failures degrade to ``warnings`` entries; a pull never
  aborts because one record could not be decoded.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

SOURCES = ("claude_code", "opencode", "aionui", "antigravity")

RUNNING_WINDOW_SECONDS = 120

DEFAULT_BUDGET_CHARS = 50_000

# --------------------------------------------------------------------------
# Root resolution. Everything is injectable: every parser takes explicit
# root paths so tests can point them at tmp_path fixtures. The CLI resolves
# defaults from $HOME, overridable per-source via env for operators whose
# stores live elsewhere (dotfiles-synced machines, sandboxes).
# --------------------------------------------------------------------------

_ROOT_ENV = {
    "claude_code": "SPELLBOOK_SESSION_PULL_CLAUDE_ROOT",
    "opencode": "SPELLBOOK_SESSION_PULL_OPENCODE_ROOT",
    "aionui": "SPELLBOOK_SESSION_PULL_AIONUI_ROOT",
    "antigravity": "SPELLBOOK_SESSION_PULL_ANTIGRAVITY_ROOT",
}


def claude_root() -> Path:
    env = os.environ.get(_ROOT_ENV["claude_code"])
    if env:
        return Path(env)
    home = Path(os.environ.get("HOME", str(Path.home())))
    return home / ".claude"


def claude_work_root() -> Path:
    home = Path(os.environ.get("HOME", str(Path.home())))
    return home / ".claude-work"


def opencode_root() -> Path:
    env = os.environ.get(_ROOT_ENV["opencode"])
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "opencode"
    home = Path(os.environ.get("HOME", str(Path.home())))
    return home / ".local" / "share" / "opencode"


def aionui_root() -> Path:
    env = os.environ.get(_ROOT_ENV["aionui"])
    if env:
        return Path(env)
    home = Path(os.environ.get("HOME", str(Path.home())))
    # macOS convention; Linux builds keep the same relative layout.
    return home / "Library" / "Application Support" / "AionUi" / "aionui"


def antigravity_root() -> Path:
    env = os.environ.get(_ROOT_ENV["antigravity"])
    if env:
        return Path(env)
    home = Path(os.environ.get("HOME", str(Path.home())))
    return home / ".gemini" / "antigravity"


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch_to_iso(ts: float | None) -> str | None:
    """Epoch seconds or milliseconds -> ISO-8601 Z. None stays None."""
    if ts is None:
        return None
    ts = float(ts)
    if ts > 1e12:  # milliseconds
        ts /= 1000.0
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def iso_to_epoch_ms(value: str | None) -> int | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)


def tolerant_json(raw: str | bytes | None) -> Any:
    """json.loads that returns the raw value instead of raising."""
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def emit(payload: Any, out: Any = None) -> None:
    """Print a JSON document. Always-JSON convention (see module docstring)."""
    target = out if out is not None else sys.stdout
    json.dump(payload, target, ensure_ascii=False, indent=2, default=str)
    target.write("\n")


def warn(envelope_warnings: list[str], message: str) -> None:
    if message not in envelope_warnings:
        envelope_warnings.append(message)


def looks_running(epoch_seconds: float | None) -> bool:
    if not epoch_seconds:
        return False
    now = datetime.now(UTC).timestamp()
    return 0 < now - epoch_seconds < RUNNING_WINDOW_SECONDS


# --------------------------------------------------------------------------
# Secret redaction (best-effort convenience pass)
# --------------------------------------------------------------------------

REDACT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("aws_access_key", r"AKIA[0-9A-Z]{16}"),
    ("anthropic_key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("openai_key", r"sk-[A-Za-z0-9_\-]{20,}"),
    ("github_token", r"gh[pousr]_[A-Za-z0-9]{36,}"),
    ("slack_token", r"xox[abprs]-[A-Za-z0-9\-]{10,}"),
    ("bearer", r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}"),
    ("private_key_block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("password_uri", r"://[^/\s:]+:[^@\s/]+@"),
)


def redact_text(text: str) -> tuple[str, list[str]]:
    """Replace secret-looking substrings. Returns (text, kinds_redacted)."""
    kinds: list[str] = []
    for kind, pattern in REDACT_PATTERNS:
        new = re.sub(pattern, f"[REDACTED:{kind}]", text)
        if new != text:
            kinds.append(kind)
            text = new
    return text, kinds


# --------------------------------------------------------------------------
# Canonical event model
# --------------------------------------------------------------------------


def make_event(
    seq: int,
    kind: str,
    *,
    ts: str | None = None,
    role: str | None = None,
    text: str | None = None,
    tool: str | None = None,
    meta: dict[str, Any] | None = None,
    hidden: bool = False,
    sidechain: bool = False,
) -> dict[str, Any]:
    ev: dict[str, Any] = {"seq": seq, "type": kind}
    if ts is not None:
        ev["ts"] = ts
    if role is not None:
        ev["role"] = role
    if text is not None:
        ev["text"] = text
    if tool is not None:
        ev["tool"] = tool
    if meta:
        ev["meta"] = meta
    if hidden:
        ev["hidden"] = True
    if sidechain:
        ev["sidechain"] = True
    return ev


def build_envelope(
    source: str,
    mode: str,
    session: dict[str, Any],
    events: list[dict[str, Any]],
    summary: dict[str, Any] | None,
    extras: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "source": source,
        "mode": mode,
        "session": session,
        "summary": summary,
        "events": events,
        "warnings": warnings,
    }
    if extras:
        envelope.update(extras)
    return envelope


# --------------------------------------------------------------------------
# SQLite snapshot reading
# --------------------------------------------------------------------------


class SqliteSnapshot:
    """Copy a live WAL-mode database and read the copy read-only.

    Source stores are held open by their apps in WAL mode. Opening them in
    place risks torn reads and lock contention; ``immutable=1`` risks missing
    recent committed frames. The safe pattern is copying db + -wal + -shm to
    a temp dir and reading the copy. The copy is removed on close.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.tmpdir: str | None = None
        self.conn: Any = None

    def __enter__(self) -> Any:
        if not self.db_path.exists():
            raise FileNotFoundError(str(self.db_path))
        self.tmpdir = tempfile.mkdtemp(prefix="session-pull-snapshot-")
        dest = Path(self.tmpdir) / "snapshot.db"
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(self.db_path) + suffix)
            if src.exists():
                shutil.copy2(src, Path(str(dest) + suffix))
        self.conn = sqlite3.connect(str(dest))
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        if self.tmpdir:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            self.tmpdir = None


# --------------------------------------------------------------------------
# claude_code source
# --------------------------------------------------------------------------


def encode_cwd_literal(path: str) -> str:
    """Claude Code encodes a project cwd by replacing every non-alphanumeric
    character with '-'. Verified against ~/.claude/projects layout
    (2026-09-10), matching roundup.py's rule."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def claude_project_dirs(root: Path) -> list[Path]:
    projects = root / "projects"
    if not projects.is_dir():
        return []
    return sorted(p for p in projects.iterdir() if p.is_dir())


def claude_session_files(root: Path) -> list[Path]:
    """All conversation JSONL files across project dirs, newest first.

    Only ``<uuid>.jsonl`` conversation files count. roundup.py documented
    that sidecar per-session directories and ``agent-*.jsonl`` subagent
    transcripts live beside them; those are deliberately excluded here.
    """
    files: list[Path] = []
    for project_dir in claude_project_dirs(root):
        for entry in project_dir.iterdir():
            if entry.is_file() and entry.name.endswith(".jsonl") and not (
                entry.name.startswith("agent-")
            ):
                files.append(entry)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def claude_title_scan(jsonl_path: Path) -> dict[str, Any]:
    """Light scan: title + timestamps without a full parse.

    Reads the first 64KiB and last 32KiB of the file. Title precedence
    (verified in roundup.py): customTitle > agentName > aiTitle > first
    user text. Compact detection from any scanned record.
    """
    info: dict[str, Any] = {"title": None, "first_ts": None, "last_ts": None,
                            "compacted": False, "git_branch": None}
    size = jsonl_path.stat().st_size
    with jsonl_path.open("rb") as fh:
        head = fh.read(65536)
        if size > 65536:
            fh.seek(max(0, size - 32768))
            tail = fh.read()
        else:
            tail = b""
    candidate: str | None = None
    for chunk in (head, tail):
        for line in chunk.splitlines():
            if not line.strip():
                continue
            rec = tolerant_json(line)
            if not isinstance(rec, dict):
                continue
            if rec.get("type") == "summary" and rec.get("summary"):
                info["title"] = info["title"] or rec["summary"]
            for key in ("customTitle", "agentName", "aiTitle"):
                if rec.get(key):
                    info["title"] = rec[key]
                    break
            if info["git_branch"] is None and rec.get("gitBranch"):
                info["git_branch"] = rec["gitBranch"]
            if rec.get("timestamp"):
                if info["first_ts"] is None and chunk is head:
                    info["first_ts"] = rec["timestamp"]
                info["last_ts"] = rec["timestamp"]
            if rec.get("isCompactSummary"):
                info["compacted"] = True
            if (
                candidate is None
                and rec.get("type") == "user"
                and not rec.get("isMeta")
                and not rec.get("isSidechain")
            ):
                content = (rec.get("message") or {}).get("content")
                if isinstance(content, str) and content.strip():
                    candidate = content.strip()
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            candidate = block.get("text")
                            break
            if info["title"] is None and candidate:
                info["title"] = candidate.splitlines()[0][:120]
    return info


def claude_session_id(jsonl_path: Path) -> str:
    return jsonl_path.stem


def claude_todo_paths(root: Path, session_id: str) -> list[Path]:
    """Todo snapshots live in ~/.claude/todos/<sessionId>*.json (verified:
    2026-09-10; the directory may be absent entirely)."""
    todo_dir = root / "todos"
    if not todo_dir.is_dir():
        return []
    return sorted(todo_dir.glob(f"{session_id}*.json"))


def claude_file_state(root: Path, session_id: str) -> list[dict[str, Any]]:
    """file-history/<uuid>/ holds per-session file snapshots (verified:
    2026-09-10). We list tracked file names; contents are NOT copied."""
    hist = root / "file-history" / session_id
    if not hist.is_dir():
        return []
    entries = []
    for p in sorted(hist.rglob("*")):
        if p.is_file():
            entries.append({
                "path": str(p.relative_to(hist)),
                "bytes": p.stat().st_size,
            })
    return entries


def claude_todo_items(root: Path, session_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in claude_todo_paths(root, session_id):
        data = tolerant_json(path.read_text(encoding="utf-8", errors="replace"))
        rows = data if isinstance(data, list) else (data or {}).get("todos", [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    items.append({
                        "content": row.get("content") or row.get("subject") or "",
                        "status": row.get("status") or "pending",
                    })
    return items


def _claude_block_events(
    blocks: Any,
    seq: int,
    ts: str | None,
    role: str,
    sidechain: bool,
    warnings: list[str],
) -> Iterator[dict[str, Any]]:
    """Yield canonical events for one Claude message content payload."""
    if isinstance(blocks, str):
        if blocks.strip():
            yield make_event(seq, "message", ts=ts, role=role, text=blocks,
                             sidechain=sidechain)
        return
    if not isinstance(blocks, list):
        warn(warnings, f"unrecognized message content type: {type(blocks).__name__}")
        return
    for block in blocks:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                yield make_event(seq, "message", ts=ts, role=role, text=text,
                                 sidechain=sidechain)
        elif btype == "thinking":
            text = block.get("thinking") or block.get("text")
            if isinstance(text, str) and text.strip():
                yield make_event(seq, "thinking", ts=ts, text=text,
                                 sidechain=sidechain)
        elif btype == "tool_use":
            yield make_event(seq, "tool_call", ts=ts, tool=block.get("name"),
                             meta={"input": block.get("input")},
                             sidechain=sidechain)
        elif btype == "tool_result":
            content = block.get("content")
            if isinstance(content, list):
                parts = [
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                text = "\n".join(parts)
            elif isinstance(content, str):
                text = content
            else:
                text = tolerant_json(json.dumps(block.get("content")))
                text = text if isinstance(text, str) else json.dumps(
                    block.get("content"), default=str
                )
            yield make_event(
                seq, "tool_result", ts=ts, text=text or None,
                meta={"tool_use_id": block.get("tool_use_id"),
                      "is_error": bool(block.get("is_error"))},
                sidechain=sidechain,
            )
        elif btype == "image":
            yield make_event(seq, "meta", ts=ts,
                             meta={"image_block": True}, sidechain=sidechain)
        else:
            warn(warnings, f"unknown claude content block type: {btype!r}")


def parse_claude_session(
    jsonl_path: Path,
    mode: str,
    root: Path,
    warnings: list[str],
    include_thinking: bool = False,
) -> dict[str, Any]:
    """Parse one Claude Code conversation JSONL into the canonical envelope.

    Record kinds handled (verified against live files 2026-09-10):
    * ``type=user`` / ``type=assistant`` — message envelope; ``message.content``
      is a string or a block list (text / thinking / tool_use / tool_result).
    * ``isCompactSummary: true`` — compaction boundary record (summary text).
    * ``type=summary`` — title summary records (also used as compaction
      anchors when no isCompactSummary exists in compact mode).
    * ``isSidechain`` — subagent traffic, tagged, excluded in compact mode.
    * ``isMeta`` — harness-inserted rows (e.g. queued commands), tagged meta.
    """
    session_id = claude_session_id(jsonl_path)
    events: list[dict[str, Any]] = []
    compaction_idx: int | None = None
    compaction_text: str | None = None
    compaction_ts: str | None = None
    summary_records: list[str] = []
    session_meta: dict[str, Any] = {}
    seq = 0
    raw_records: list[tuple[str | None, dict[str, Any] | None, str | None]] = []

    with jsonl_path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = tolerant_json(line)
            if not isinstance(rec, dict):
                warn(warnings, "claude_code: undecodable JSONL line skipped")
                continue
            rtype = rec.get("type")
            ts = rec.get("timestamp")
            if rtype == "summary" and rec.get("summary"):
                summary_records.append(rec["summary"])
                continue
            if rec.get("isCompactSummary"):
                text = None
                content = (rec.get("message") or {}).get("content")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts = [
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                    text = "\n".join(parts)
                if text:
                    compaction_idx = len(raw_records)
                    compaction_text = text
                    compaction_ts = ts
                continue
            raw_records.append((rtype, rec, ts))

    # Title precedence mirrors roundup.py.
    title = None
    for rtype, rec, _ts in raw_records:
        for key in ("customTitle", "agentName", "aiTitle"):
            if rec and rec.get(key):
                title = rec[key]
                break
        if title:
            break
    if not title and summary_records:
        title = summary_records[-1]
    if not title:
        for rtype, rec, _ts in raw_records:
            if rtype == "user" and rec and not rec.get("isMeta"):
                content = (rec.get("message") or {}).get("content")
                text = None
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text")
                            break
                if text and text.strip():
                    title = text.strip().splitlines()[0][:120]
                    break

    # Compact mode drops everything strictly before the compaction anchor.
    start = 0
    if mode == "compact" and compaction_idx is not None:
        start = compaction_idx

    for idx in range(start, len(raw_records)):
        rtype, rec, ts = raw_records[idx]
        if rec is None:
            continue
        sidechain = bool(rec.get("isSidechain"))
        if sidechain and mode == "compact":
            continue
        message = rec.get("message") or {}
        role = message.get("role") or ("user" if rtype == "user" else rtype)
        if rtype in ("user", "assistant"):
            blocks = message.get("content")
            for ev in _claude_block_events(
                blocks, seq, ts, role or "", sidechain, warnings
            ):
                if ev["type"] == "thinking" and not include_thinking:
                    continue
                events.append(ev)
                seq += 1
        elif rtype == "system":
            text = rec.get("content") or rec.get("text")
            if isinstance(text, str) and text.strip():
                events.append(make_event(seq, "meta", ts=ts, text=text))
                seq += 1
        if rec.get("cwd") and "cwd" not in session_meta:
            session_meta["cwd"] = rec["cwd"]
        if rec.get("gitBranch") and "git_branch" not in session_meta:
            session_meta["git_branch"] = rec["gitBranch"]
        if rec.get("version") and "app_version" not in session_meta:
            session_meta["app_version"] = rec["version"]
        if rec.get("slug"):
            session_meta["slug"] = rec["slug"]

    if compaction_idx is not None and mode != "full":
        events.insert(
            0,
            make_event(-1, "compaction", ts=compaction_ts, text=compaction_text,
                        meta={"anchor": True, "source_record": "isCompactSummary"}),
        )

    info = claude_title_scan(jsonl_path)
    stat = jsonl_path.stat()
    session = {
        "id": session_id,
        "title": title or info["title"],
        "cwd": session_meta.get("cwd"),
        "git_branch": session_meta.get("git_branch") or info["git_branch"],
        "created_at": info["first_ts"],
        "last_activity": info["last_ts"],
        "compacted": compaction_idx is not None or info["compacted"],
        "appears_running": looks_running(stat.st_mtime),
        "size_bytes": stat.st_size,
    }
    todos = claude_todo_items(root, session_id)
    file_state = claude_file_state(root, session_id)
    summary = None
    if compaction_text:
        summary = {
            "text": compaction_text,
            "timestamp": compaction_ts,
            "boundary_seq": compaction_idx,
        }
    elif summary_records and mode == "compact":
        # Older-style /title-only summaries still give the next agent a hook.
        summary = {"text": summary_records[-1], "timestamp": None,
                   "boundary_seq": None}
    extras = {"todos": todos, "file_state": file_state}
    if session_meta.get("slug"):
        session["slug"] = session_meta["slug"]
    return build_envelope("claude_code", mode, session, events, summary,
                          extras, warnings)


def list_claude_sessions(
    root: Path, cwd: str | None, warnings: list[str]
) -> list[dict[str, Any]]:
    sessions = []
    for path in claude_session_files(root):
        project_dir = path.parent
        if cwd is not None:
            encoded = encode_cwd_literal(cwd)
            if project_dir.name != encoded and not project_dir.name.startswith(
                encoded + "-"
            ):
                # Worktrees encode as <repo-path>-<worktree-name>.
                continue
        info = claude_title_scan(path)
        stat = path.stat()
        sessions.append({
            "id": path.stem,
            "source": "claude_code",
            "title": info["title"],
            "cwd": None,  # full parse resolves cwd; dir name is the hint
            "project_dir": project_dir.name,
            "git_branch": info["git_branch"],
            "last_activity": info["last_ts"],
            "compacted": info["compacted"],
            "appears_running": looks_running(stat.st_mtime),
            "size_bytes": stat.st_size,
            "mtime": epoch_to_iso(stat.st_mtime),
        })
    return sessions


# --------------------------------------------------------------------------
# opencode source (current SQLite schema only)
# --------------------------------------------------------------------------


def opencode_db_path(root: Path) -> Path:
    return root / "opencode.db"


def list_opencode_sessions(
    root: Path, cwd: str | None, warnings: list[str]
) -> list[dict[str, Any]]:
    db = opencode_db_path(root)
    if not db.exists():
        warn(warnings, f"opencode: no db at {db} (legacy storage/ layout is "
                       "deliberately unsupported)")
        return []
    rows: list[dict[str, Any]] = []
    with SqliteSnapshot(db) as conn:
        query = (
            "SELECT s.id, s.slug, s.directory, s.title, s.model, s.agent, "
            "s.time_created, s.time_updated, s.time_compacting, "
            "s.time_archived, p.worktree "
            "FROM session s LEFT JOIN project p ON p.id = s.project_id"
        )
        try:
            cursor = conn.execute(query)
        except sqlite3.Error as exc:
            warn(warnings, f"opencode: session query failed: {exc}")
            return []
        for row in cursor:
            directory = row["directory"] or row["worktree"]
            if cwd is not None and directory and directory != cwd:
                continue
            counts = {"messages": 0}
            try:
                counts["messages"] = conn.execute(
                    "SELECT count(*) FROM message WHERE session_id = ?",
                    (row["id"],),
                ).fetchone()[0]
            except sqlite3.Error:
                pass
            updated = epoch_to_iso(row["time_updated"])
            running = False
            if row["time_updated"]:
                running = looks_running(float(row["time_updated"]) / 1000.0)
            rows.append({
                "id": row["id"],
                "source": "opencode",
                "title": row["title"] or row["slug"],
                "cwd": directory,
                "git_branch": None,
                "last_activity": updated,
                "compacted": row["time_compacting"] is not None,
                "appears_running": running,
                "message_count": counts["messages"],
                "model": row["model"],
                "archived": row["time_archived"] is not None,
            })
    return rows


def _oc_part_events(
    part_data: dict[str, Any],
    seq: int,
    ts: str | None,
    include_thinking: bool,
    warnings: list[str],
) -> Iterator[dict[str, Any]]:
    ptype = part_data.get("type")
    if ptype == "text":
        text = part_data.get("text")
        if isinstance(text, str) and text.strip():
            yield make_event(seq, "message", ts=ts, text=text)
    elif ptype == "tool":
        state = part_data.get("state") or {}
        status = state.get("status")
        output = state.get("output")
        if isinstance(output, dict):
            out_text = output.get("output")
            out_title = output.get("title")
        else:
            out_text = output
            out_title = None
        if isinstance(out_text, (dict, list)):
            out_text = json.dumps(out_text, default=str)
        if status == "pending":
            yield make_event(seq, "tool_call", ts=ts, tool=part_data.get("tool"),
                             meta={"input": state.get("input"),
                                   "call_id": part_data.get("callID")})
        else:
            yield make_event(
                seq, "tool_result", ts=ts, tool=part_data.get("tool"),
                text=out_text if isinstance(out_text, str) else None,
                meta={"status": status, "title": out_title,
                      "call_id": part_data.get("callID")},
            )
    elif ptype == "reasoning":
        if include_thinking:
            text = part_data.get("text")
            if isinstance(text, str) and text.strip():
                yield make_event(seq, "thinking", ts=ts, text=text)
    elif ptype in ("step-start", "step-finish"):
        pass  # harness scaffolding, not content
    elif ptype == "compaction":
        text = part_data.get("text") or ""
        meta = {k: v for k, v in part_data.items() if k not in ("type", "text")}
        yield make_event(seq, "compaction", ts=ts,
                         text=text if isinstance(text, str) and text else None,
                         meta={"anchor": True, **meta})
    elif ptype == "snapshot":
        yield make_event(seq, "file_state", ts=ts,
                         meta={"snapshot": part_data.get("snapshot")})
    elif ptype == "agent":
        yield make_event(seq, "meta", ts=ts, meta={"agent": part_data.get("name")})
    elif ptype == "file":
        yield make_event(seq, "file_state", ts=ts, meta={"file": part_data.get("mime")})
    else:
        warn(warnings, f"opencode: unknown part type {ptype!r} (kept as meta)")
        yield make_event(seq, "meta", ts=ts,
                         meta={"part_type": ptype,
                               "data": {k: v for k, v in part_data.items()
                                        if k != "type"}})


def parse_opencode_session(
    root: Path,
    session_id: str,
    mode: str,
    warnings: list[str],
    include_thinking: bool = False,
) -> dict[str, Any]:
    db = opencode_db_path(root)
    session_row: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    compaction_event_idx: int | None = None
    seq = 0
    with SqliteSnapshot(db) as conn:
        row = conn.execute(
            "SELECT * FROM session WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            warn(warnings, f"opencode: session {session_id!r} not found")
            return build_envelope("opencode", mode, {"id": session_id}, events,
                                  None, None, warnings)
        session_row = dict(row)
        rows = conn.execute(
            "SELECT m.time_created AS m_time, m.data AS m_data, "
            "p.data AS p_data, p.time_created AS p_time "
            "FROM message m LEFT JOIN part p ON p.message_id = m.id "
            "WHERE m.session_id = ? ORDER BY m.time_created, p.time_created",
            (session_id,),
        ).fetchall()
        message_roles: dict[str, str] = {}
        for mrow in rows:
            mdata = tolerant_json(mrow["m_data"]) or {}
            message_roles[mdata.get("id", "")] = mdata.get("role") or ""
        compaction_epoch = session_row.get("time_compacting")
        for mrow in rows:
            mdata = tolerant_json(mrow["m_data"]) or {}
            role = mdata.get("role")
            # Part time beats message time: parts carry their own clocks
            # and the compaction boundary is per-part (verified 2026-09-10).
            ts = epoch_to_iso(mrow["p_time"] or mrow["m_time"])
            pdata = tolerant_json(mrow["p_data"])
            if pdata is None:
                continue
            if pdata.get("type") == "compaction":
                compaction_event_idx = seq
            for ev in _oc_part_events(pdata, seq, ts, include_thinking, warnings):
                if role:
                    ev["role"] = ev.get("role", role)
                events.append(ev)
                seq += 1

    if mode == "compact" and compaction_event_idx is not None:
        anchor = next(
            (e for e in events if e.get("seq") == compaction_event_idx), None
        )
        if anchor is not None:
            anchor_ts = anchor.get("ts")
            kept = [e for e in events
                    if e.get("type") == "compaction" or
                    (anchor_ts and e.get("ts") and e["ts"] >= anchor_ts)]
            events = kept

    if mode == "compact" and compaction_epoch and compaction_event_idx is None:
        warn(warnings, "opencode: session has time_compacting but no "
                       "compaction part survived; falling back to full order")

    session = {
        "id": session_id,
        "title": session_row.get("title") or session_row.get("slug"),
        "cwd": session_row.get("directory") or session_row.get("worktree"),
        "git_branch": None,
        "created_at": epoch_to_iso(session_row.get("time_created")),
        "last_activity": epoch_to_iso(session_row.get("time_updated")),
        "compacted": compaction_epoch is not None,
        "appears_running": (
            looks_running(float(session_row["time_updated"]) / 1000.0)
            if session_row.get("time_updated") else False
        ),
        "model": session_row.get("model"),
        "agent": session_row.get("agent"),
        "tokens_input": session_row.get("tokens_input"),
        "tokens_output": session_row.get("tokens_output"),
    }
    summary = None
    compactions = [e for e in events if e["type"] == "compaction"]
    if compactions:
        last = compactions[-1]
        summary = {"text": last.get("text"),
                   "timestamp": last.get("ts"),
                   "boundary_seq": last["seq"]}
    return build_envelope("opencode", mode, session, events, summary, None,
                          warnings)


# --------------------------------------------------------------------------
# aionui source
# --------------------------------------------------------------------------


def aionui_db_path(root: Path) -> Path:
    return root / "aionui-backend.db"


def _aionui_project_paths(conn: Any, conversation_id: str) -> list[str]:
    """Best-effort workspace paths for a conversation.

    Sources tried in order (verified 2026-09-10):
    * assistant_sessions.workspace (agent-backed conversations)
    * conversations.extra JSON (path-shaped values)
    """
    paths: list[str] = []
    try:
        for row in conn.execute(
            "SELECT workspace FROM assistant_sessions WHERE conversation_id = ?",
            (conversation_id,),
        ):
            if row["workspace"]:
                paths.append(row["workspace"])
    except sqlite3.Error:
        pass
    try:
        row = conn.execute(
            "SELECT extra FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        extra = tolerant_json(row["extra"]) if row and row["extra"] else None
        if isinstance(extra, dict):
            for value in extra.values():
                if isinstance(value, str) and value.startswith(os.sep):
                    paths.append(value)
                elif isinstance(value, dict):
                    for inner in value.values():
                        if isinstance(inner, str) and inner.startswith(os.sep):
                            paths.append(inner)
    except sqlite3.Error:
        pass
    # Deduplicate preserving order.
    seen: set[str] = set()
    unique = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def list_aionui_sessions(
    root: Path, cwd: str | None, warnings: list[str]
) -> list[dict[str, Any]]:
    db = aionui_db_path(root)
    if not db.exists():
        warn(warnings, f"aionui: no db at {db}")
        return []
    rows: list[dict[str, Any]] = []
    with SqliteSnapshot(db) as conn:
        try:
            cursor = conn.execute(
                "SELECT c.id, c.name, c.type, c.model, c.status, c.created_at, "
                "c.updated_at, c.archived_at "
                "FROM conversations c ORDER BY c.updated_at DESC"
            )
        except sqlite3.Error as exc:
            warn(warnings, f"aionui: conversations query failed: {exc}")
            return []
        for row in cursor:
            paths = _aionui_project_paths(conn, row["id"])
            if cwd is not None and not any(
                    p == cwd or p.startswith(cwd + os.sep) or
                    cwd.startswith(p + os.sep)
                    for p in paths
            ):
                continue
            try:
                msg_count = conn.execute(
                    "SELECT count(*) FROM messages WHERE conversation_id = ?",
                    (row["id"],),
                ).fetchone()[0]
            except sqlite3.Error:
                msg_count = 0
            agent_types: list[str] = []
            try:
                agent_types = [
                    r[0] for r in conn.execute(
                        "SELECT DISTINCT agent_type FROM assistant_sessions "
                        "WHERE conversation_id = ?",
                        (row["id"],),
                    )
                ]
            except sqlite3.Error:
                pass
            last_iso = epoch_to_iso(row["updated_at"])
            running = False
            if row["updated_at"]:
                running = looks_running(float(row["updated_at"]) / 1000.0)
            rows.append({
                "id": row["id"],
                "source": "aionui",
                "title": (row["name"] or "").splitlines()[0][:120] or None,
                "cwd": paths[0] if paths else None,
                "workspaces": paths,
                "agent_types": agent_types,
                "last_activity": last_iso,
                "appears_running": running,
                "message_count": msg_count,
                "model": row["model"],
                "conversation_type": row["type"],
                "archived": row["archived_at"] is not None,
            })
    return rows


def _aionui_content_events(
    msg_type: str,
    content: dict[str, Any],
    seq: int,
    ts: str | None,
    hidden: bool,
    warnings: list[str],
) -> Iterator[dict[str, Any]]:
    """Map one aionui ``messages`` row to canonical events.

    Row ``type`` column is the discriminator (verified 2026-09-10):
    * ``text``      -> {content} — chat message. NOTE: the store carries NO
                       user/assistant marker on text rows, so role is
                       unknown and left unset; position order is the flow.
    * ``thinking``  -> {content, status, duration_ms} — model reasoning.
    * ``tool_call`` -> {call_id, name, args, status, input, output} — one row
                       holds both the call and (once finished) its output.
    * ``tips``      -> {content, type, code, params, supersedes_key, error} —
                       harness status notes (success/error), mapped to meta.
    """
    text = content.get("content")
    if msg_type == "thinking" and isinstance(text, str) and text.strip():
        yield make_event(seq, "thinking", ts=ts, text=text, hidden=hidden)
        return
    if msg_type == "tips":
        tip = {"content": text} if isinstance(text, str) else {}
        tip.update({k: content.get(k) for k in ("type", "code", "params",
                                                "supersedes_key", "error")
                    if content.get(k) is not None})
        if tip:
            yield make_event(seq, "meta", ts=ts,
                             text=tip.get("content"),
                             meta={"kind": "aionui_tip", **{
                                 k: v for k, v in tip.items()
                                 if k != "content"}}, hidden=hidden)
            return
    if msg_type == "tool_call" or content.get("name"):
        name = content.get("name")
        call_input = (content.get("args")
                      if content.get("args") is not None
                      else content.get("input"))
        meta: dict[str, Any] = {"call_id": content.get("call_id"),
                                "status": content.get("status")}
        if isinstance(call_input, (dict, list)):
            meta["input"] = call_input
        elif isinstance(call_input, str):
            meta["input_raw"] = call_input
        if name:
            yield make_event(seq, "tool_call", ts=ts, tool=name, meta=meta,
                             hidden=hidden)
        output = content.get("output")
        if output is not None:
            if isinstance(output, dict):
                output_text = output.get("output") or json.dumps(
                    output, default=str)
            elif isinstance(output, str):
                output_text = output
            else:
                output_text = json.dumps(output, default=str)
            yield make_event(
                seq, "tool_result", ts=ts, tool=name,
                text=output_text if isinstance(output_text, str) else None,
                meta={"call_id": content.get("call_id"),
                      "error": content.get("error")}, hidden=hidden,
            )
        error = content.get("error")
        if error and not name:
            yield make_event(seq, "meta", ts=ts, text=str(error),
                             meta={"kind": "error"}, hidden=hidden)
        return
    # text (and anything unknown): chat message; no role marker exists.
    if isinstance(text, str) and text.strip():
        yield make_event(seq, "message", ts=ts, text=text, hidden=hidden)
    elif not content:
        # Unknown content shape — keep it visible rather than dropping data.
        warn(warnings,
             f"aionui: message row type {msg_type!r} has empty content")


def parse_aionui_session(
    root: Path,
    session_id: str,
    mode: str,
    warnings: list[str],
    include_thinking: bool = False,
) -> dict[str, Any]:
    db = aionui_db_path(root)
    events: list[dict[str, Any]] = []
    seq = 0
    conv_row: dict[str, Any] = {}
    with SqliteSnapshot(db) as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            warn(warnings, f"aionui: conversation {session_id!r} not found")
            return build_envelope("aionui", mode, {"id": session_id}, events,
                                  None, None, warnings)
        conv_row = dict(row)
        try:
            rows = conn.execute(
                "SELECT type, content, hidden, created_at, position, status "
                "FROM messages WHERE conversation_id = ? "
                "ORDER BY position, created_at",
                (session_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            warn(warnings, f"aionui: messages query failed: {exc}")
            rows = []
        for mrow in rows:
            content = tolerant_json(mrow["content"])
            if not isinstance(content, dict):
                content = {}
            ts = epoch_to_iso(mrow["created_at"])
            hidden = bool(mrow["hidden"])
            for ev in _aionui_content_events(
                mrow["type"], content, seq, ts, hidden, warnings
            ):
                events.append(ev)
                seq += 1
        agent_types: list[str] = []
        try:
            agent_types = [
                r[0] for r in conn.execute(
                    "SELECT DISTINCT agent_type FROM assistant_sessions "
                    "WHERE conversation_id = ?",
                    (session_id,),
                )
            ]
        except sqlite3.Error:
            pass
        artifacts: list[dict[str, Any]] = []
        try:
            for arow in conn.execute(
                "SELECT * FROM conversation_artifacts WHERE conversation_id = ?",
                (session_id,),
            ):
                artifacts.append({
                    k: arow[idx] for idx, k in enumerate(arow.keys())
                })
        except sqlite3.Error:
            pass

    compaction = None  # aionui has no first-class compaction records
    if mode == "compact":
        warn(warnings, "aionui: no compaction records in store; compact mode "
                       "equals full mode")
    workspaces = _aionui_workspaces(db, session_id)
    session = {
        "id": session_id,
        "title": (conv_row.get("name") or "").splitlines()[0][:120] or None,
        "cwd": None,
        "workspaces": workspaces,
        "created_at": epoch_to_iso(conv_row.get("created_at")),
        "last_activity": epoch_to_iso(conv_row.get("updated_at")),
        "compacted": False,
        "appears_running": (
            looks_running(float(conv_row["updated_at"]) / 1000.0)
            if conv_row.get("updated_at") else False
        ),
        "model": conv_row.get("model"),
        "agent_types": agent_types,
        "conversation_type": conv_row.get("type"),
    }
    extras = None
    if artifacts:
        extras = {"artifacts": artifacts}
    return build_envelope("aionui", mode, session, events, compaction, extras,
                          warnings)


def _aionui_workspaces(db_path: Path, session_id: str) -> list[str]:
    try:
        with SqliteSnapshot(db_path) as conn:
            return _aionui_project_paths(conn, session_id)
    except (FileNotFoundError, sqlite3.Error):
        return []


# --------------------------------------------------------------------------
# antigravity source (reverse-engineered)
# --------------------------------------------------------------------------


def antigravity_conversation_dbs(root: Path) -> list[Path]:
    conv_dir = root / "conversations"
    if not conv_dir.is_dir():
        return []
    return sorted(conv_dir.glob("*.db"), key=lambda p: p.stat().st_mtime,
                  reverse=True)


def _pb_read_varint(blob: bytes, pos: int) -> tuple[int, int] | None:
    """Read a varint; returns (value, new_pos) or None on malformed input."""
    result = 0
    shift = 0
    start = pos
    while pos < len(blob):
        byte = blob[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 63 or pos - start > 10:
            return None
    return None


def pb_walk(blob: bytes, depth: int = 0) -> list[tuple[int, int, Any]]:
    """Generic protobuf wire-format walk (tolerant, schema-less).

    Returns (field_number, wire_type, value) triples; length-delimited
    values are raw bytes. Stops cleanly on malformed tails — Antigravity
    blobs are protobuf without a public schema (verified 2026-09-10), so
    this walk plus string carving is the extraction strategy.
    """
    fields: list[tuple[int, int, Any]] = []
    pos = 0
    n = len(blob)
    while pos < n:
        header = _pb_read_varint(blob, pos)
        if header is None:
            break
        key, pos = header
        field_no = key >> 3
        wire = key & 0x07
        if field_no == 0 or field_no > 100_000:
            break
        if wire == 0:  # varint
            val = _pb_read_varint(blob, pos)
            if val is None:
                break
            value, pos = val
            fields.append((field_no, wire, value))
        elif wire == 1:  # 64-bit
            if pos + 8 > n:
                break
            fields.append((field_no, wire, blob[pos:pos + 8]))
            pos += 8
        elif wire == 2:  # length-delimited
            ln = _pb_read_varint(blob, pos)
            if ln is None:
                break
            length, pos = ln
            if length > n - pos:
                break
            fields.append((field_no, wire, blob[pos:pos + length]))
            pos += length
        elif wire == 5:  # 32-bit
            if pos + 4 > n:
                break
            fields.append((field_no, wire, blob[pos:pos + 4]))
            pos += 4
        else:
            break  # groups (3/4) are deprecated; stop rather than guess
    return fields


def _pb_collect_strings(blob: bytes, depth: int = 0,
                        max_depth: int = 6) -> list[str]:
    """Recursively collect UTF-8-decodable strings from a protobuf blob.

    Nested length-delimited fields that are NOT printable text are walked as
    nested messages (bounded depth). Critically, a decoded string that ITSELF
    parses as a nested protobuf message with high byte coverage is recursed
    into rather than emitted — Antigravity nests text one wire level below a
    wrapper, and the wrapper's length byte is otherwise glued onto the text
    as a stray leading character (verified: 2026-09-10).
    """
    out: list[str] = []
    fields = pb_walk(blob)
    if not fields:
        return out
    # How much of the blob did the wire walk explain? High coverage on a
    # printable-decoding blob means it is actually a nested message.
    covered = 0
    for field_no, wire, value in fields:
        if wire == 0:
            covered += 1
        elif wire == 1:
            covered += 10
        elif wire == 5:
            covered += 5
        elif isinstance(value, bytes):
            covered += len(value) + 1
    if covered / max(len(blob), 1) < 0.5:
        # Not protobuf-shaped: harvest printable runs directly.
        for run in re.findall(rb"[\x20-\x7e]{10,}", blob):
            out.append(run.decode("ascii", "replace"))
        return out
    for _field, _wire, value in fields:
        if not isinstance(value, bytes):
            continue
        try:
            text = value.decode("utf-8")
        except UnicodeDecodeError:
            if depth < max_depth:
                out.extend(_pb_collect_strings(value, depth + 1, max_depth))
            continue
        if not text:
            continue
        printable = sum(1 for c in text if c.isprintable())
        if printable / len(text) < 0.95:
            if depth < max_depth and len(value) >= 8:
                out.extend(_pb_collect_strings(value, depth + 1, max_depth))
            continue
        # Printable, but is it a nested message in disguise?
        if depth < max_depth and len(value) >= 8:
            nested = pb_walk(value)
            if nested:
                nested_covered = 0
                for _n, w, v in nested:
                    if w == 0:
                        nested_covered += 1
                    elif w == 1:
                        nested_covered += 10
                    elif w == 5:
                        nested_covered += 5
                    elif isinstance(v, bytes):
                        nested_covered += len(v) + 1
                if nested_covered / len(value) >= 0.5:
                    out.extend(
                        _pb_collect_strings(value, depth + 1, max_depth)
                    )
                    continue
        out.append(text)
    return out


_MESSAGE_TS_RE = re.compile(r"\[Message\] timestamp=([\dT:.\-]+Z?) sender=(\S+)")
_CALL_ID_RE = re.compile(r"^call_[0-9A-Za-z_\-]+$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_TOOL_NAME_RE = re.compile(r"^[a-z][a-z_]{2,40}$")

# Calibration (debug-dump against live dbs, 2026-09-10). Antigravity writes
# each trajectory step with a ``step_type`` code; observed meanings:
AGY_STEP_TYPE_USER = 14       # user prompt row
AGY_STEP_TYPE_TASK_NOTE = 101  # task notifications ([Message] records)


def _looks_like_natural_text(text: str) -> bool:
    if len(text) < 12:
        return False
    letters = sum(1 for c in text if c.isalpha())
    spaces = sum(1 for c in text if c.isspace())
    return (letters + spaces) / len(text) >= 0.55


def _agy_clean_message(text: str) -> str:
    """Strip carving noise from a message body.

    A message body is one string among carved runs; binary header bytes
    sometimes survive as short junk lines (e.g. a lone 'H') or as stray
    leading whitespace. Drop lines that are trivially short and re-join.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    kept = [ln for ln in lines if len(ln) > 2]
    return "\n".join(kept).strip()


def _agy_extract_step(
    step_type: int,
    strings: list[str],
    seq: int,
    warnings: list[str],
    vocab: set[str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Turn the carved strings of one Antigravity step into canonical events.

    Calibration (2026-09-10, live dbs):
    * Tool steps carry ``call_<id>``, a snake_case tool name and a JSON args
      dict — across several step_type codes (5/7/8/21/132), so detection is
      per-string, not per-step-type.
    * Task notifications use ``[Message] timestamp=... sender=...`` records.
    * step_type 14 rows hold the user prompt.
    * State-marker rows (sessionID + UUIDs + opaque keys) are skipped.
    """
    # Filter carving noise: UUIDs, call ids, lone field labels.
    texts = [
        s for s in strings
        if not _UUID_RE.match(s.strip())
        and not _CALL_ID_RE.match(s.strip())
        and s.strip() not in ("sessionID", "session_id")
        and not re.fullmatch(r"-?\d+", s.strip())
    ]
    call_ids = [s for s in strings if _CALL_ID_RE.match(s.strip())]

    # Task notifications ([Message] records) outrank tool detection: their
    # blobs also embed call ids.
    note_records = [s for s in texts if "[Message]" in s]
    if note_records:
        for record in note_records:
            ts_match = _MESSAGE_TS_RE.search(record)
            # Body: everything after the priority token, or after the
            # sender when no priority token is present.
            body = record.split("priority=", 1)[-1]
            if "priority=" in record:
                body = body.split(" ", 1)[-1]
            yield make_event(
                seq, "message",
                ts=ts_match.group(1) if ts_match else None,
                text=_agy_clean_message(body),
                meta={"record": "task_notification"},
            )
        return

    if call_ids:
        tool = max(
            (s.strip() for s in texts
             if _TOOL_NAME_RE.match(s.strip()) and not s.strip().startswith("call_")),
            key=len,
            default=None,
        )
        args_json = next(
            (s for s in texts if s.strip().startswith("{")
             or s.strip().startswith("[")),
            None,
        )
        args = tolerant_json(args_json) if args_json else None
        if tool:
            tool = _agy_repair_tool_name(tool, vocab)
            meta: dict[str, Any] = {"call_id": call_ids[0]}
            if isinstance(args, dict):
                meta["input"] = args
            elif args_json:
                meta["input_raw"] = args_json
            yield make_event(seq, "tool_call", tool=tool.strip(), meta=meta)
            return

    messages = [s for s in texts if _looks_like_natural_text(s)]
    if not messages:
        return

    if step_type == AGY_STEP_TYPE_USER:
        body = max(messages, key=len)
        yield make_event(seq, "message", role="user",
                         text=_agy_clean_message(body))
        return

    # Assistant/other natural text: role unknown (no reliable marker in the
    # blobs) — emitted honestly as unattributed messages.
    body = max(messages, key=len)
    yield make_event(seq, "message", text=_agy_clean_message(body))


def _agy_repair_tool_name(name: str, vocab: set[str] | None) -> str:
    """Repair a fragmentary carved tool name against known names.

    E.g. 'anag' is a fragment of 'manage_task' seen complete in sibling
    rows. Single-fragment, substring-superstring only; never invents names.
    """
    if not vocab:
        return name
    for candidate in vocab:
        if candidate != name and name in candidate:
            return candidate
    return name


def _agy_emit_events(
    step_rows: list[tuple[int, list[str]]],
    vocab: set[str],
    seq: int,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    for step_type, strings in step_rows:
        for ev in _agy_extract_step(step_type, strings, seq, warnings, vocab):
            events.append(ev)
            seq += 1
    return events, seq


def parse_antigravity_session(
    root: Path,
    session_id: str,
    mode: str,
    warnings: list[str],
    include_thinking: bool = False,
) -> dict[str, Any]:
    db = root / "conversations" / f"{session_id}.db"
    if not db.exists():
        warn(warnings, f"antigravity: no conversation db at {db}")
        return build_envelope("antigravity", mode, {"id": session_id}, [],
                              None, None, warnings)
    events: list[dict[str, Any]] = []
    seq = 0
    step_rows: list[tuple[int, list[str]]] = []
    with SqliteSnapshot(db) as conn:
        try:
            rows = conn.execute(
                "SELECT idx, step_type, step_format, step_payload "
                "FROM steps ORDER BY idx"
            ).fetchall()
        except sqlite3.Error as exc:
            warn(warnings, f"antigravity: steps query failed: {exc}")
            rows = []
        step_formats: dict[int, int] = {}
        for row in rows:
            sf = row["step_format"]
            step_formats[sf] = step_formats.get(sf, 0) + 1
            blob = row["step_payload"]
            if not blob:
                continue
            strings = _pb_collect_strings(blob)
            if not strings:
                continue
            step_rows.append((row["step_type"], strings))
        # Conversation-local tool-name vocabulary: fragments carved from
        # nested payloads get repaired against complete names seen in other
        # rows (best-effort; verified 2026-09-10).
        vocab: set[str] = set()
        for _stype, strings in step_rows:
            for s in strings:
                if _TOOL_NAME_RE.match(s.strip()) and "_" in s:
                    vocab.add(s.strip())
        events, seq = _agy_emit_events(step_rows, vocab, seq, warnings)
    session = {
        "id": session_id,
        "title": None,
        "cwd": None,
        "created_at": None,
        "last_activity": epoch_to_iso(db.stat().st_mtime),
        "compacted": False,
        "appears_running": looks_running(db.stat().st_mtime),
        "step_formats": step_formats,
    }
    if mode == "compact":
        warn(warnings, "antigravity: no compaction markers are recoverable "
                       "from protobuf blobs; compact mode equals full mode")
    return build_envelope("antigravity", mode, session, events, None, None,
                          warnings)


def debug_dump_antigravity(
    root: Path, session_id: str, warnings: list[str]
) -> dict[str, Any]:
    """Schema archaeology for one conversation db.

    Emits per-step-type/step-format histograms and sample carved strings so
    field meanings can be pinned and the classifier constants updated with
    evidence. Read-only.
    """
    db = root / "conversations" / f"{session_id}.db"
    if not db.exists():
        warn(warnings, f"antigravity: no conversation db at {db}")
        return {"warnings": warnings, "session_id": session_id}
    dump: dict[str, Any] = {"session_id": session_id, "tables": {},
                            "steps": []}
    with SqliteSnapshot(db) as conn:
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        ]
        for table in tables:
            try:
                count = conn.execute(
                    f"SELECT count(*) FROM \"{table}\""
                ).fetchone()[0]
                cols = [
                    r[1] for r in conn.execute(
                        f'PRAGMA table_info("{table}")'
                    )
                ]
                dump["tables"][table] = {"rows": count, "columns": cols}
            except sqlite3.Error:
                continue
        try:
            rows = conn.execute(
                "SELECT idx, step_type, status, step_format, "
                "length(step_payload) AS payload_len, step_payload "
                "FROM steps ORDER BY idx LIMIT 200"
            ).fetchall()
        except sqlite3.Error as exc:
            warn(warnings, f"antigravity: steps query failed: {exc}")
            rows = []
        for row in rows:
            blob = row["step_payload"] or b""
            strings = _pb_collect_strings(blob)[:8]
            dump["steps"].append({
                "idx": row["idx"],
                "step_type": row["step_type"],
                "status": row["status"],
                "step_format": row["step_format"],
                "payload_len": row["payload_len"],
                "carved_strings": [s[:160] for s in strings],
            })
    dump["warnings"] = warnings
    return dump


# --------------------------------------------------------------------------
# Handoff renderer (Markdown)
# --------------------------------------------------------------------------


HANDOFF_HEADER = """# Session handoff — {title}

- **Source**: {source} (`{session_id}`)
- **Workspace**: {cwd}
- **Branch**: {branch}
- **Exported**: {generated_at}
- **Mode**: {mode}

{stats_line}
"""


def render_handoff(envelope: dict[str, Any], budget_chars: int) -> str:
    """Render the canonical envelope as a Markdown handoff document.

    Structure follows the assembling-context convention (Position →
    Pending work → Active decisions → Key learnings → Verification
    commands → Recent transcript). Inclusion is newest-first under the
    budget; elided content is marked, never silently dropped.
    """
    session = envelope.get("session") or {}
    summary = envelope.get("summary") or {}
    todos = envelope.get("todos") or []
    events = envelope.get("events") or []
    lines: list[str] = []
    title = session.get("title") or session.get("id") or "exported session"
    lines.append(HANDOFF_HEADER.format(
        title=(title or "untitled session").replace("\n", " ")[:120],
        source=envelope.get("source", "?"),
        session_id=session.get("id", "?"),
        cwd=session.get("cwd") or session.get("workspaces") or "unknown",
        branch=session.get("git_branch") or "n/a",
        generated_at=envelope.get("generated_at", "?"),
        mode=envelope.get("mode", "?"),
        stats_line=(
            f"{len(events)} events included; "
            f"compaction anchor: {'yes' if summary else 'none'}"
        ),
    ).rstrip())

    if summary and summary.get("text"):
        lines.append("## Position (latest compaction summary)\n")
        lines.append(str(summary.get("text")).strip())
        lines.append("")

    if todos:
        lines.append("## Pending work (todos)\n")
        for todo in todos:
            status = todo.get("status", "pending")
            mark = {"completed": "x", "in_progress": "~"}.get(status, " ")
            lines.append(f"- [{mark}] {todo.get('content', '')}")
        lines.append("")

    if summary and summary.get("boundary_seq") is not None:
        lines.append(
            "> Note: transcript below starts at the latest compaction "
            "boundary; earlier turns are summarized in Position above.\n"
        )

    lines.append("## Recent transcript (newest first)\n")
    used = 0
    included = 0
    elided = 0
    rendered: list[str] = []
    for ev in reversed(events):
        if ev.get("type") == "compaction":
            continue
        text = ev.get("text")
        tool = ev.get("tool")
        meta = ev.get("meta") or {}
        if ev["type"] == "tool_call":
            chunk = f"**tool_call** `{tool}`\n```json\n{json.dumps(meta.get('input') or {}, indent=2, default=str)[:1500]}\n```"
        elif ev["type"] == "tool_result":
            body = (text or "")[:3000]
            chunk = f"**tool_result** `{tool}`\n```\n{body}\n```"
        elif ev["type"] in ("message", "thinking", "meta"):
            chunk = f"**{ev['type']}**{(' [' + str(ev['role']) + ']') if ev.get('role') else ''}\n{(text or '')}"
        else:
            chunk = f"**{ev['type']}**\n{(text or json.dumps(meta, default=str)[:1500])}"
        chunk = chunk.strip()
        if used + len(chunk) > budget_chars:
            elided += 1
            continue
        used += len(chunk)
        rendered.append(f"### seq {ev.get('seq')}\n\n{chunk}")
        included += 1
    if elided:
        rendered.append(
            f"_(… {elided} older event(s) elided by the "
            f"{budget_chars}-char budget; rerun with --mode full for "
            "everything)_"
        )
    if rendered:
        lines.extend(rendered)
    else:
        lines.append("_(no events recovered)_")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Source registry / CLI plumbing
# --------------------------------------------------------------------------


def source_status(root_override: dict[str, Path] | None = None) -> list[dict[str, Any]]:
    def root_for(source: str) -> Path:
        if root_override and source in root_override:
            return root_override[source]
        return {
            "claude_code": claude_root(),
            "opencode": opencode_root(),
            "aionui": aionui_root(),
            "antigravity": antigravity_root(),
        }[source]

    statuses = []
    cc = root_for("claude_code")
    sessions = cc / "projects"
    oc = root_for("opencode")
    aion = root_for("aionui")
    agy = root_for("antigravity")
    statuses.append({
        "source": "claude_code",
        "store": str(cc),
        "available": sessions.is_dir() and any(sessions.iterdir()) if sessions.is_dir() else False,
        "covers": "Claude Code CLI + Claude Code Desktop (local sessions)",
        "notes": [
            "Claude Desktop remote (claude.ai) chats are out of scope by design",
        ],
    })
    legacy = oc / "storage"
    statuses.append({
        "source": "opencode",
        "store": str(opencode_db_path(oc)),
        "available": opencode_db_path(oc).exists(),
        "covers": "OpenCode (current SQLite schema)",
        "notes": (["Legacy storage/ JSON tree unsupported (by decision)"]
                  if legacy.exists() else []),
    })
    statuses.append({
        "source": "aionui",
        "store": str(aionui_db_path(aion)),
        "available": aionui_db_path(aion).exists(),
        "covers": "AionUi conversations + agent sessions (assistant_sessions)",
        "notes": [
            "Installer-platform support for AionUi is a separate, deferred workstream",
        ],
    })
    statuses.append({
        "source": "antigravity",
        "store": str(agy / "conversations"),
        "available": bool(antigravity_conversation_dbs(agy)),
        "covers": "Antigravity conversations (reverse-engineered protobuf "
                  "blobs — best effort)",
        "notes": [
            ("Payloads are protobuf without a public schema; extraction degrades "
             "to carved strings. debug-dump for archaeology"),
        ],
    })
    return statuses


def write_out(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"refusing to overwrite {path} (use --force)")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)


def apply_redaction(
    envelope: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Run the best-effort secret pass over all text-bearing fields.

    Returns a NEW envelope plus the redaction kinds hit; the original is
    left untouched.
    """
    kinds: set[str] = set()

    def scrub(value: Any) -> Any:
        if isinstance(value, str):
            new, hit = redact_text(value)
            kinds.update(hit)
            return new
        if isinstance(value, dict):
            return {k: scrub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [scrub(v) for v in value]
        return value

    cleaned = scrub(envelope)
    return cleaned, sorted(kinds)


def dispatch_pull(args: argparse.Namespace) -> int:
    warnings: list[str] = []
    mode = args.mode
    if args.source == "claude_code":
        envelope = parse_claude_session(
            _find_claude_file(args.id, warnings),
            mode, claude_root(), warnings,
            include_thinking=args.include_thinking,
        )
    elif args.source == "opencode":
        envelope = parse_opencode_session(
            opencode_root(), args.id, mode, warnings,
            include_thinking=args.include_thinking,
        )
    elif args.source == "aionui":
        envelope = parse_aionui_session(
            aionui_root(), args.id, mode, warnings,
            include_thinking=args.include_thinking,
        )
    elif args.source == "antigravity":
        envelope = parse_antigravity_session(
            antigravity_root(), args.id, mode, warnings,
            include_thinking=args.include_thinking,
        )
    else:
        raise SystemExit(f"unknown source: {args.source}")

    if getattr(args, "redact", False):
        envelope, kinds = apply_redaction(envelope)
        envelope["redacted"] = True
        if kinds:
            envelope["redaction_kinds"] = kinds
    envelope["warnings"] = warnings

    if mode == "handoff":
        content = render_handoff(envelope, args.budget_chars)
        envelope["handoff_md"] = content
        if args.out:
            write_out(Path(args.out), content, args.force)
            emit({"written": str(args.out),
                  "bytes": len(content.encode("utf-8")),
                  "warnings": warnings})
        else:
            sys.stdout.write(content)
        return 0

    payload = json.dumps(envelope, indent=2, ensure_ascii=False, default=str)
    if args.out:
        write_out(Path(args.out), payload, args.force)
        emit({"written": str(args.out),
              "bytes": len(payload.encode("utf-8")),
              "warnings": warnings})
    else:
        emit(envelope)
    return 0


def _find_claude_file(session_id: str, warnings: list[str]) -> Path:
    matches = [
        p for p in claude_session_files(claude_root())
        if p.stem == session_id
    ]
    if not matches:
        work = claude_work_root()
        if work.is_dir():
            matches = [p for p in claude_session_files(work)
                       if p.stem == session_id]
    if not matches:
        raise SystemExit(
            f"claude_code: no session file for id {session_id!r}"
        )
    return matches[0]


def dispatch_list(args: argparse.Namespace) -> int:
    warnings: list[str] = []
    since_ms: int | None = None
    if args.since:
        since_ms = iso_to_epoch_ms(args.since)
        if since_ms is None:
            raise SystemExit(f"unparseable --since: {args.since}")
    elif args.lookback_hours:
        since_ms = int(
            (datetime.now(UTC).timestamp() - args.lookback_hours * 3600)
            * 1000
        )
    wanted = (
        SOURCES if args.source == "all" else (args.source,)
    )
    collected: dict[str, list[dict[str, Any]]] = {}
    for source in wanted:
        if source == "claude_code":
            sessions = list_claude_sessions(claude_root(), args.cwd, warnings)
            for s in sessions:
                s["_sort_ms"] = iso_to_epoch_ms(s.get("last_activity")) or 0
        elif source == "opencode":
            sessions = list_opencode_sessions(opencode_root(), args.cwd, warnings)
            for s in sessions:
                s["_sort_ms"] = iso_to_epoch_ms(s.get("last_activity")) or 0
        elif source == "aionui":
            sessions = list_aionui_sessions(aionui_root(), args.cwd, warnings)
            for s in sessions:
                s["_sort_ms"] = iso_to_epoch_ms(s.get("last_activity")) or 0
        elif source == "antigravity":
            sessions = []
            warn(warnings, "antigravity: listing is best-effort; sessions are "
                           "identified by db file id only. Use pull --source "
                           "antigravity --id <file stem>.")
            for db_path in antigravity_conversation_dbs(antigravity_root()):
                sessions.append({
                    "id": db_path.stem,
                    "source": "antigravity",
                    "title": None,
                    "cwd": None,
                    "last_activity": epoch_to_iso(db_path.stat().st_mtime),
                    "appears_running": looks_running(db_path.stat().st_mtime),
                    "size_bytes": db_path.stat().st_size,
                })
            for s in sessions:
                s["_sort_ms"] = iso_to_epoch_ms(s.get("last_activity")) or 0
        else:
            raise SystemExit(f"unknown source: {source}")
        if since_ms is not None:
            sessions = [s for s in sessions if s["_sort_ms"] >= since_ms]
        sessions.sort(key=lambda s: s["_sort_ms"], reverse=True)
        collected[source] = [
            {k: v for k, v in s.items() if k != "_sort_ms"}
            for s in sessions[: args.limit]
        ]

    emit({
        "generated_at": now_iso(),
        "cwd": args.cwd,
        "sources": {k: v for k, v in collected.items() if v or args.source != "all"},
        "warnings": warnings,
    })
    return 0


def dispatch_sources(_args: argparse.Namespace) -> int:
    emit({
        "generated_at": now_iso(),
        "sources": source_status(),
    })
    return 0


def dispatch_debug_dump(args: argparse.Namespace) -> int:
    warnings: list[str] = []
    if args.source != "antigravity":
        raise SystemExit("debug-dump currently supports --source antigravity only")
    dump = debug_dump_antigravity(antigravity_root(), args.id, warnings)
    emit(dump)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session_pull.py",
        description="Pull coding-agent session history + hidden context "
                    "into a portable format for another assistant.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sources = sub.add_parser("sources", help="detect available sources")
    p_sources.set_defaults(func=dispatch_sources)

    p_list = sub.add_parser("list", help="discover sessions per source")
    p_list.add_argument("--source", default="all",
                        help=f"one of {SOURCES} or 'all'")
    p_list.add_argument("--cwd", default=None,
                        help="filter to sessions whose workspace matches")
    p_list.add_argument("--since", default=None,
                        help="ISO-8601 lower bound on last activity")
    p_list.add_argument("--lookback-hours", type=float, default=None)
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=dispatch_list)

    p_pull = sub.add_parser("pull", help="export one session")
    p_pull.add_argument("--source", required=True, choices=SOURCES)
    p_pull.add_argument("--id", required=True)
    p_pull.add_argument("--mode", default="compact",
                        choices=("compact", "full", "handoff"))
    p_pull.add_argument("--budget-chars", type=int, default=DEFAULT_BUDGET_CHARS)
    p_pull.add_argument("--out", default=None)
    p_pull.add_argument("--force", action="store_true")
    p_pull.add_argument("--redact", action="store_true")
    p_pull.add_argument("--include-thinking", action="store_true")
    p_pull.set_defaults(func=dispatch_pull)

    p_dump = sub.add_parser("debug-dump",
                            help="antigravity schema archaeology")
    p_dump.add_argument("--source", default="antigravity")
    p_dump.add_argument("--id", required=True)
    p_dump.set_defaults(func=dispatch_debug_dump)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())