"""Integration tests for MCP server tools."""

import pytest
import json
import os
from pathlib import Path


def test_find_session_integration(tmp_path, monkeypatch):
    """Test find_session tool end-to-end."""
    from spellbook_mcp import server

    project_dir = tmp_path / "projects" / "test-project"
    project_dir.mkdir(parents=True)

    session1 = project_dir / "auth-flow.jsonl"
    with open(session1, 'w') as f:
        f.write(json.dumps({
            "slug": "auth-flow",
            "type": "user",
            "timestamp": "2026-01-01T10:00:00Z",
            "message": {"content": "Implement auth"}
        }) + '\n')

    session2 = project_dir / "api-design.jsonl"
    with open(session2, 'w') as f:
        f.write(json.dumps({
            "slug": "api-design",
            "type": "user",
            "timestamp": "2026-01-01T11:00:00Z",
            "message": {"content": "Design API"}
        }) + '\n')
        f.write(json.dumps({
            "type": "custom-title",
            "customTitle": "Authentication API",
            "sessionId": "xyz"
        }) + '\n')

    monkeypatch.setattr('spellbook_mcp.server.get_project_dir', lambda: project_dir)

    # Test search by slug (use .fn to access underlying function)
    result = server.find_session.fn(name="auth", limit=10)
    assert len(result) == 2
    # Verify correct sessions matched (both contain "auth")
    slugs = {r['slug'] for r in result}
    assert slugs == {'auth-flow', 'api-design'}

    # Test search by custom title only
    result = server.find_session.fn(name="Authentication API", limit=10)
    assert len(result) == 1
    assert result[0]['slug'] == 'api-design'
    assert result[0]['custom_title'] == "Authentication API"

    # Test empty search (returns all)
    result = server.find_session.fn(name="", limit=10)
    assert len(result) == 2
    slugs = {r['slug'] for r in result}
    assert slugs == {'auth-flow', 'api-design'}


def test_split_session_integration(tmp_path):
    """Test split_session tool end-to-end."""
    from spellbook_mcp import server

    session_file = tmp_path / "test.jsonl"
    messages = [
        {"uuid": f"msg-{i}", "type": "user", "message": {"content": "x" * 100}}
        for i in range(10)
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = server.split_session.fn(
        session_path=str(session_file),
        start_line=0,
        char_limit=500
    )

    # Verify we got multiple chunks
    assert len(result) > 1, "Should produce multiple chunks"

    # Verify first chunk starts at start_line
    assert result[0][0] == 0, "First chunk must start at 0"

    # Verify last chunk ends at total message count
    assert result[-1][1] == 10, "Last chunk must end at message count"

    # Verify chunks are contiguous
    for i in range(len(result) - 1):
        assert result[i][1] == result[i + 1][0], \
            f"Gap between chunk {i} and {i + 1}"

    # Verify each chunk boundary is valid
    for start, end in result:
        assert 0 <= start < end <= 10, f"Invalid chunk [{start}, {end}]"


def test_list_sessions_integration(tmp_path, monkeypatch):
    """Test list_sessions tool end-to-end."""
    from spellbook_mcp import server

    project_dir = tmp_path / "projects" / "test-project"
    project_dir.mkdir(parents=True)

    session = project_dir / "test-session.jsonl"
    with open(session, 'w') as f:
        f.write(json.dumps({
            "slug": "test-session",
            "type": "user",
            "timestamp": "2026-01-01T10:00:00Z",
            "message": {"content": "First message"}
        }) + '\n')
        f.write(json.dumps({
            "type": "system",
            "subtype": "compact_boundary",
            "timestamp": "2026-01-01T10:30:00Z"
        }) + '\n')
        f.write(json.dumps({
            "isCompactSummary": True,
            "message": {"content": "Summary of session"}
        }) + '\n')
        f.write(json.dumps({
            "type": "custom-title",
            "customTitle": "My Test Session",
            "sessionId": "abc"
        }) + '\n')

    monkeypatch.setattr('spellbook_mcp.server.get_project_dir', lambda: project_dir)

    result = server.list_sessions.fn(limit=5)

    assert len(result) == 1
    assert result[0]['slug'] == 'test-session'
    assert result[0]['custom_title'] == 'My Test Session'
    assert result[0]['compact_count'] == 1
    assert result[0]['last_compact_summary'] == 'Summary of session'
    assert result[0]['first_user_message'] == 'First message'


def test_find_session_empty_project(tmp_path, monkeypatch):
    """Test find_session with non-existent project directory."""
    from spellbook_mcp import server

    non_existent = tmp_path / "nonexistent"
    monkeypatch.setattr('spellbook_mcp.server.get_project_dir', lambda: non_existent)

    result = server.find_session.fn(name="anything", limit=10)
    assert result == []


def test_list_sessions_empty_project(tmp_path, monkeypatch):
    """Test list_sessions with non-existent project directory."""
    from spellbook_mcp import server

    non_existent = tmp_path / "nonexistent"
    monkeypatch.setattr('spellbook_mcp.server.get_project_dir', lambda: non_existent)

    result = server.list_sessions.fn(limit=5)
    assert result == []


def test_split_session_file_not_found():
    """Test split_session with non-existent file."""
    from spellbook_mcp import server

    with pytest.raises(FileNotFoundError):
        server.split_session.fn(
            session_path="/nonexistent/file.jsonl",
            start_line=0,
            char_limit=1000
        )
