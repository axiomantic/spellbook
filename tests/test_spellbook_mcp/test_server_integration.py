"""Integration tests for MCP server tools."""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_context_for_path():
    """Create a mock context that returns a specific project directory."""
    def _make_mock(project_dir):
        mock_root = MagicMock()
        mock_root.uri = f'file://{project_dir}'
        mock_ctx = MagicMock()
        mock_ctx.list_roots = AsyncMock(return_value=[mock_root])
        return mock_ctx
    return _make_mock


@pytest.fixture
def spellbook_config_dir(tmp_path, monkeypatch):
    """Set up a temporary spellbook config directory."""
    config_dir = tmp_path / "spellbook-config"
    config_dir.mkdir()
    monkeypatch.setenv('SPELLBOOK_CONFIG_DIR', str(config_dir))
    return config_dir


@pytest.mark.asyncio
async def test_find_session_integration(tmp_path, mock_context_for_path, spellbook_config_dir):
    """Test find_session tool end-to-end."""
    from spellbook_mcp import server
    from spellbook_mcp.path_utils import encode_cwd

    # Simulate a project at /Users/test/myproject
    fake_project_path = "/Users/test/myproject"
    encoded = encode_cwd(fake_project_path)

    # Create the session storage directory under spellbook config
    session_dir = spellbook_config_dir / "projects" / encoded
    session_dir.mkdir(parents=True)

    session1 = session_dir / "auth-flow.jsonl"
    with open(session1, 'w') as f:
        f.write(json.dumps({
            "slug": "auth-flow",
            "type": "user",
            "timestamp": "2026-01-01T10:00:00Z",
            "message": {"content": "Implement auth"}
        }) + '\n')

    session2 = session_dir / "api-design.jsonl"
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

    # Mock context returns the fake project path
    mock_ctx = mock_context_for_path(fake_project_path)

    # Test search by slug (use .fn to access underlying function)
    result = await server.find_session.fn(ctx=mock_ctx, name="auth", limit=10)
    assert len(result) == 2
    # Verify correct sessions matched (both contain "auth")
    slugs = {r['slug'] for r in result}
    assert slugs == {'auth-flow', 'api-design'}

    # Test search by custom title only
    result = await server.find_session.fn(ctx=mock_ctx, name="Authentication API", limit=10)
    assert len(result) == 1
    assert result[0]['slug'] == 'api-design'
    assert result[0]['custom_title'] == "Authentication API"

    # Test empty search (returns all)
    result = await server.find_session.fn(ctx=mock_ctx, name="", limit=10)
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


@pytest.mark.asyncio
async def test_list_sessions_integration(tmp_path, mock_context_for_path, spellbook_config_dir):
    """Test list_sessions tool end-to-end."""
    from spellbook_mcp import server
    from spellbook_mcp.path_utils import encode_cwd

    # Simulate a project at /Users/test/myproject
    fake_project_path = "/Users/test/myproject"
    encoded = encode_cwd(fake_project_path)

    # Create the session storage directory under spellbook config
    session_dir = spellbook_config_dir / "projects" / encoded
    session_dir.mkdir(parents=True)

    session = session_dir / "test-session.jsonl"
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

    mock_ctx = mock_context_for_path(fake_project_path)

    result = await server.list_sessions.fn(ctx=mock_ctx, limit=5)

    assert len(result) == 1
    assert result[0]['slug'] == 'test-session'
    assert result[0]['custom_title'] == 'My Test Session'
    assert result[0]['compact_count'] == 1
    assert result[0]['last_compact_summary'] == 'Summary of session'
    assert result[0]['first_user_message'] == 'First message'


@pytest.mark.asyncio
async def test_find_session_empty_project(tmp_path, mock_context_for_path, spellbook_config_dir):
    """Test find_session with non-existent project directory."""
    from spellbook_mcp import server

    # Use a path that won't have any session storage created
    non_existent = "/nonexistent/project"
    mock_ctx = mock_context_for_path(non_existent)

    result = await server.find_session.fn(ctx=mock_ctx, name="anything", limit=10)
    assert result == []


@pytest.mark.asyncio
async def test_list_sessions_empty_project(tmp_path, mock_context_for_path, spellbook_config_dir):
    """Test list_sessions with non-existent project directory."""
    from spellbook_mcp import server

    # Use a path that won't have any session storage created
    non_existent = "/nonexistent/project"
    mock_ctx = mock_context_for_path(non_existent)

    result = await server.list_sessions.fn(ctx=mock_ctx, limit=5)
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
