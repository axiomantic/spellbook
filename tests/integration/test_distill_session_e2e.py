"""
End-to-end integration tests for /distill-session command.
These tests verify the complete workflow from session discovery to output.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_claude_config(tmp_path):
    """Create mock ~/.claude directory structure."""
    config_dir = tmp_path / "claude"
    config_dir.mkdir()

    # Create scripts directory and symlink actual script
    scripts_dir = config_dir / "scripts"
    scripts_dir.mkdir()

    # Get path to actual script in repo
    repo_root = Path(__file__).parent.parent.parent
    actual_script = repo_root / "scripts" / "distill_session.py"
    if actual_script.exists():
        (scripts_dir / "distill_session.py").symlink_to(actual_script)

    # Create projects directory
    projects_dir = config_dir / "projects"
    projects_dir.mkdir()

    # Create distilled directory
    distilled_dir = config_dir / "distilled"
    distilled_dir.mkdir()

    return config_dir


def test_small_session_no_chunking(mock_claude_config):
    """Test distilling a small session that doesn't require chunking."""
    # Create a small test session
    project_dir = mock_claude_config / "projects" / "test-project"
    project_dir.mkdir()

    session_file = project_dir / "test-session.jsonl"
    messages = [
        {
            "uuid": "msg-1",
            "type": "user",
            "message": {"role": "user", "content": "Implement a fibonacci function"},
            "timestamp": "2025-01-01T10:00:00Z",
            "sessionId": "sess-1",
            "slug": "fibonacci"
        },
        {
            "uuid": "msg-2",
            "type": "assistant",
            "message": {"role": "assistant", "content": "I'll implement that for you..."},
            "timestamp": "2025-01-01T10:01:00Z",
            "sessionId": "sess-1"
        }
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    # Test list-sessions via CLI
    script_path = mock_claude_config / "scripts" / "distill_session.py"
    result = subprocess.run(
        ['python3', str(script_path), 'list-sessions', str(project_dir)],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, 'CLAUDE_CONFIG_DIR': str(mock_claude_config)}
    )

    assert result.returncode == 0
    sessions = json.loads(result.stdout)
    assert len(sessions) == 1
    assert sessions[0]['slug'] == 'fibonacci'
    assert sessions[0]['message_count'] == 2


def test_session_with_existing_compact(mock_claude_config):
    """Test distilling a session that has an existing compact boundary."""
    project_dir = mock_claude_config / "projects" / "compact-test"
    project_dir.mkdir()

    session_file = project_dir / "compacted-session.jsonl"
    messages = [
        {"uuid": "msg-1", "type": "user", "message": {"content": "Before compact"}},
        {
            "uuid": "boundary-1",
            "type": "system",
            "subtype": "compact_boundary",
            "content": "Conversation compacted",
            "timestamp": "2025-01-01T12:00:00Z"
        },
        {
            "uuid": "summary-1",
            "type": "user",
            "parentUuid": "boundary-1",
            "isCompactSummary": True,
            "message": {"content": "This is the compact summary"},
            "timestamp": "2025-01-01T12:00:01Z"
        },
        {"uuid": "msg-2", "type": "user", "message": {"content": "After compact"}, "slug": "compacted-session"}
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    # Test get-last-compact
    script_path = mock_claude_config / "scripts" / "distill_session.py"
    result = subprocess.run(
        ['python3', str(script_path), 'get-last-compact', str(session_file)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    compact_info = json.loads(result.stdout)
    assert compact_info is not None
    assert compact_info['line_number'] == 1
    assert 'compact summary' in compact_info['summary_content']


def test_large_session_chunking(mock_claude_config):
    """Test chunking calculation for a large session."""
    project_dir = mock_claude_config / "projects" / "large-test"
    project_dir.mkdir()

    session_file = project_dir / "large-session.jsonl"

    # Create a session with messages that will require chunking
    messages = []
    for i in range(20):
        msg = {
            "uuid": f"msg-{i}",
            "type": "user" if i % 2 == 0 else "assistant",
            "message": {"content": "x" * 50000},  # 50k chars each
            "timestamp": f"2025-01-01T10:{i:02d}:00Z",
            "slug": "large-session" if i == 0 else None
        }
        messages.append(msg)

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    # Test split-by-char-limit
    script_path = mock_claude_config / "scripts" / "distill_session.py"
    result = subprocess.run(
        ['python3', str(script_path), 'split-by-char-limit', str(session_file),
         '--start-line', '0', '--char-limit', '300000'],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    chunks = json.loads(result.stdout)
    assert len(chunks) > 1  # Should have multiple chunks

    # Verify chunks cover all messages
    total_messages = sum(end - start for start, end in chunks)
    assert total_messages == 20


def test_extract_chunk_range(mock_claude_config):
    """Test extracting a specific chunk range."""
    project_dir = mock_claude_config / "projects" / "extract-test"
    project_dir.mkdir()

    session_file = project_dir / "extract-session.jsonl"
    messages = [
        {"uuid": f"msg-{i}", "type": "user", "message": {"content": f"Message {i}"}}
        for i in range(10)
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    # Extract chunk from lines 3-7
    script_path = mock_claude_config / "scripts" / "distill_session.py"
    result = subprocess.run(
        ['python3', str(script_path), 'extract-chunk', str(session_file),
         '--start-line', '3', '--end-line', '7'],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    chunk = json.loads(result.stdout)
    assert len(chunk) == 4
    assert chunk[0]['uuid'] == 'msg-3'
    assert chunk[3]['uuid'] == 'msg-6'
