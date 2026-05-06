"""Tests for scripts/analyze_yolo_transcripts.py.

Covers extraction, classification, mutating-command rejection, subagent
discovery, failed-command filtering, days filter, and JSON output.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "analyze_yolo_transcripts.py"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "yolo_transcripts"


def _load_analyzer():
    """Load the analyzer module from its file path (it lives in scripts/, not a package)."""
    spec = importlib.util.spec_from_file_location("analyze_yolo_transcripts", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["analyze_yolo_transcripts"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def analyzer():
    return _load_analyzer()


def _patterns_in_categories(proposed: dict) -> set[str]:
    """Return all allowlist patterns across non-rejected categories."""
    patterns: set[str] = set()
    for entries in proposed["categories"].values():
        for entry in entries:
            patterns.add(entry["pattern"])
    return patterns


def _rejected_patterns(proposed: dict) -> set[str]:
    return {e["pattern"] for e in proposed["rejected_mutating"]}


def _run_full(analyzer, roots, since=None, output_path=None, include_mutating=False):
    """Run extract + classify + render, returning the proposed dict."""
    if since is None:
        since = datetime(2000, 1, 1, tzinfo=timezone.utc)
    records = []
    for root in roots:
        records.extend(analyzer.extract_bash_commands(root, since=since))
    categorized = analyzer.bucket_and_classify(records)
    proposed = analyzer.render_proposed_list(
        categorized,
        scanned_roots=[str(r) for r in roots],
        since=since,
        days=30,
        include_mutating=include_mutating,
    )
    if output_path is not None:
        analyzer.write_proposed_list(proposed, output_path)
    return proposed


def test_analyzer_extracts_readonly_safe_commands(analyzer):
    proposed = _run_full(analyzer, [FIXTURE_ROOT])
    patterns = _patterns_in_categories(proposed)
    assert "Bash(git status:*)" in patterns
    assert "Bash(ls:*)" in patterns
    assert "Bash(grep:*)" in patterns


def test_analyzer_excludes_mutating_commands(analyzer):
    proposed = _run_full(analyzer, [FIXTURE_ROOT])
    allow = _patterns_in_categories(proposed)
    rejected = _rejected_patterns(proposed)
    assert "Bash(git push:*)" not in allow
    assert "Bash(gh pr merge:*)" not in allow
    assert "Bash(git push:*)" in rejected
    assert "Bash(gh pr merge:*)" in rejected
    # Four-word acli mutating forms must reject, not promote into search_inspect
    # via the ``acli jira`` prefix loop. Regression guard for the spec violation
    # where ``acli jira workitem transition`` was bucketed as the three-word
    # ``acli jira workitem`` and reached SEARCH_INSPECT.
    assert "Bash(acli jira workitem transition:*)" not in allow
    assert "Bash(acli jira workitem edit:*)" not in allow
    assert "Bash(acli jira workitem transition:*)" in rejected
    assert "Bash(acli jira workitem edit:*)" in rejected


def test_analyzer_classifies_acli_workitem_view_as_search_inspect(analyzer):
    """Positive case: read-only four-word acli forms remain allowlisted.

    Locks in the non-regression direction of the four-word runner fix —
    ``view`` is a read-only inspection command and must land in
    ``search_inspect``, not be rejected as mutating.
    """
    proposed = _run_full(analyzer, [FIXTURE_ROOT])
    search_inspect = {
        e["pattern"] for e in proposed["categories"].get("search_inspect", [])
    }
    assert "Bash(acli jira workitem view:*)" in search_inspect


def test_analyzer_includes_subagent_commands(analyzer):
    proposed = _run_full(analyzer, [FIXTURE_ROOT])
    patterns = _patterns_in_categories(proposed)
    assert "Bash(pytest:*)" in patterns


def test_analyzer_filters_failed_commands(analyzer, tmp_path):
    """A Bash command paired with is_error=true must NOT be counted."""
    project = tmp_path / "-Users-fake-fail"
    project.mkdir()
    session = project / "session-fail.jsonl"
    records = [
        {
            "type": "assistant",
            "sessionId": "session-fail",
            "isSidechain": False,
            "timestamp": "2026-05-01T00:00:00.000Z",
            "uuid": "a1",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_x",
                        "name": "Bash",
                        "input": {"command": "rustc --version"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "sessionId": "session-fail",
            "isSidechain": False,
            "timestamp": "2026-05-01T00:00:01.000Z",
            "uuid": "u1",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_x",
                        "content": "command not found",
                        "is_error": True,
                    }
                ],
            },
        },
    ]
    with session.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    proposed = _run_full(analyzer, [tmp_path])
    patterns = _patterns_in_categories(proposed) | _rejected_patterns(proposed)
    assert "Bash(rustc:*)" not in patterns


def test_analyzer_excludes_unpaired_bash_invocations(analyzer, tmp_path):
    """A Bash tool_use with NO matching tool_result must be dropped.

    Interrupted sessions can leave an assistant tool_use without any user-side
    confirmation. Without an explicit ``is_error=False`` pairing, we cannot
    confirm the command actually ran successfully, so it must NOT seed the
    allowlist.
    """
    project = tmp_path / "-Users-fake-unpaired"
    project.mkdir()
    session = project / "session-unpaired.jsonl"
    records = [
        # Paired success — should be yielded.
        {
            "type": "assistant",
            "sessionId": "session-unpaired",
            "isSidechain": False,
            "timestamp": "2026-05-01T00:00:00.000Z",
            "uuid": "a-paired",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_paired",
                        "name": "Bash",
                        "input": {"command": "git status"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "sessionId": "session-unpaired",
            "isSidechain": False,
            "timestamp": "2026-05-01T00:00:01.000Z",
            "uuid": "u-paired",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_paired",
                        "content": "clean",
                        "is_error": False,
                    }
                ],
            },
        },
        # Unpaired tool_use — interrupted session, no tool_result.
        {
            "type": "assistant",
            "sessionId": "session-unpaired",
            "isSidechain": False,
            "timestamp": "2026-05-01T00:01:00.000Z",
            "uuid": "a-unpaired",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_unpaired",
                        "name": "Bash",
                        "input": {"command": "danger --do-bad-thing"},
                    }
                ],
            },
        },
    ]
    with session.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    proposed = _run_full(analyzer, [tmp_path])
    patterns = _patterns_in_categories(proposed) | _rejected_patterns(proposed)
    assert "Bash(git status:*)" in patterns
    assert "Bash(danger:*)" not in patterns


def test_analyzer_respects_days_filter(analyzer, tmp_path):
    """Records older than --days N are excluded."""
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=60)).isoformat().replace("+00:00", "Z")
    old_ts_result = (now - timedelta(days=60) + timedelta(seconds=1)).isoformat().replace(
        "+00:00", "Z"
    )
    new_ts = (now - timedelta(days=5)).isoformat().replace("+00:00", "Z")
    new_ts_result = (now - timedelta(days=5) + timedelta(seconds=1)).isoformat().replace(
        "+00:00", "Z"
    )
    project = tmp_path / "-Users-fake-days"
    project.mkdir()
    session = project / "session-days.jsonl"
    records = [
        {
            "type": "assistant",
            "sessionId": "s",
            "isSidechain": False,
            "timestamp": old_ts,
            "uuid": "old",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_old",
                        "name": "Bash",
                        "input": {"command": "stat oldfile"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "sessionId": "s",
            "isSidechain": False,
            "timestamp": old_ts_result,
            "uuid": "old-r",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_old",
                        "content": "ok",
                        "is_error": False,
                    }
                ],
            },
        },
        {
            "type": "assistant",
            "sessionId": "s",
            "isSidechain": False,
            "timestamp": new_ts,
            "uuid": "new",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_new",
                        "name": "Bash",
                        "input": {"command": "wc -l newfile"},
                    }
                ],
            },
        },
        {
            "type": "user",
            "sessionId": "s",
            "isSidechain": False,
            "timestamp": new_ts_result,
            "uuid": "new-r",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_new",
                        "content": "12 newfile",
                        "is_error": False,
                    }
                ],
            },
        },
    ]
    with session.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    since = now - timedelta(days=30)
    proposed = _run_full(analyzer, [tmp_path], since=since)
    patterns = _patterns_in_categories(proposed)
    assert "Bash(wc:*)" in patterns
    assert "Bash(stat:*)" not in patterns


def test_analyzer_never_writes_settings_json(analyzer):
    """The analyzer must NOT import or invoke any settings.json writer."""
    import ast

    tree = ast.parse(SCRIPT_PATH.read_text())

    # No imports of any settings-writing helper.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            assert "install_permissions" not in module
            assert "settings_writer" not in module
            for alias in node.names:
                assert "install_permissions" not in alias.name

    # No calls to install_permissions(...) anywhere.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            assert name != "install_permissions"

    # No Path(...) or open(...) call that has a settings.json string literal
    # as its first arg.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                assert "settings.json" not in first.value


def test_analyzer_writes_proposed_list_json(analyzer, tmp_path):
    output_path = tmp_path / "proposed_allow_list.json"
    proposed = _run_full(analyzer, [FIXTURE_ROOT], output_path=output_path)
    assert output_path.exists()
    written = json.loads(output_path.read_text())
    assert "categories" in written
    assert "rejected_mutating" in written
    assert "generated_at" in written
    assert "scanned_roots" in written
    assert written["categories"] == proposed["categories"]
