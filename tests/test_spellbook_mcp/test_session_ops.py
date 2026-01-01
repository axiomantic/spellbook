"""Tests for session loading, metadata extraction, and chunking."""

import pytest
import json
from pathlib import Path


def test_load_jsonl_basic(tmp_path):
    """Test loading basic JSONL file."""
    from spellbook_mcp.session_ops import load_jsonl

    session_file = tmp_path / "test.jsonl"
    messages = [
        {"uuid": "msg-1", "type": "user", "message": {"content": "Hello"}},
        {"uuid": "msg-2", "type": "assistant", "message": {"content": "Hi"}}
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = load_jsonl(str(session_file))
    assert len(result) == 2
    assert result[0]['uuid'] == 'msg-1'
    assert result[1]['type'] == 'assistant'


def test_load_jsonl_with_empty_lines(tmp_path):
    """Test that empty lines are skipped."""
    from spellbook_mcp.session_ops import load_jsonl

    session_file = tmp_path / "test.jsonl"

    with open(session_file, 'w') as f:
        f.write('{"uuid": "msg-1"}\n')
        f.write('\n')
        f.write('{"uuid": "msg-2"}\n')

    result = load_jsonl(str(session_file))
    assert len(result) == 2


def test_load_jsonl_file_not_found():
    """Test error handling for missing file."""
    from spellbook_mcp.session_ops import load_jsonl

    with pytest.raises(FileNotFoundError) as exc_info:
        load_jsonl('/nonexistent/file.jsonl')

    assert 'Session file not found' in str(exc_info.value)


def test_load_jsonl_invalid_json(tmp_path):
    """Test error handling for malformed JSON."""
    from spellbook_mcp.session_ops import load_jsonl

    session_file = tmp_path / "bad.jsonl"

    with open(session_file, 'w') as f:
        f.write('{"valid": "json"}\n')
        f.write('invalid json here\n')

    with pytest.raises(json.JSONDecodeError) as exc_info:
        load_jsonl(str(session_file))

    assert 'line 2' in str(exc_info.value)


def test_find_last_compact_boundary():
    """Test finding last compact boundary in messages."""
    from spellbook_mcp.session_ops import find_last_compact_boundary

    messages = [
        {"uuid": "msg-1", "type": "user"},
        {"uuid": "boundary-1", "type": "system", "subtype": "compact_boundary"},
        {"uuid": "msg-2", "type": "user"},
        {"uuid": "boundary-2", "type": "system", "subtype": "compact_boundary"},
        {"uuid": "msg-3", "type": "user"}
    ]

    result = find_last_compact_boundary(messages)
    assert result == 3  # Index of boundary-2


def test_find_last_compact_boundary_none():
    """Test when no compact boundary exists."""
    from spellbook_mcp.session_ops import find_last_compact_boundary

    messages = [
        {"uuid": "msg-1", "type": "user"},
        {"uuid": "msg-2", "type": "assistant"}
    ]

    result = find_last_compact_boundary(messages)
    assert result is None


def test_find_last_compact_boundary_empty():
    """Test finding compact boundary in empty list."""
    from spellbook_mcp.session_ops import find_last_compact_boundary

    result = find_last_compact_boundary([])
    assert result is None


def test_extract_custom_title_found():
    """Test extracting custom title from messages."""
    from spellbook_mcp.session_ops import extract_custom_title

    messages = [
        {"type": "user", "message": {"content": "Hello"}},
        {"type": "custom-title", "customTitle": "big-kahuna", "sessionId": "abc123"},
        {"type": "assistant", "message": {"content": "Hi"}}
    ]

    result = extract_custom_title(messages)
    assert result == "big-kahuna"


def test_extract_custom_title_last_wins():
    """Test that last custom title wins when multiple exist."""
    from spellbook_mcp.session_ops import extract_custom_title

    messages = [
        {"type": "custom-title", "customTitle": "first-title", "sessionId": "abc123"},
        {"type": "user", "message": {"content": "Hello"}},
        {"type": "custom-title", "customTitle": "second-title", "sessionId": "abc123"}
    ]

    result = extract_custom_title(messages)
    assert result == "second-title"


def test_extract_custom_title_none():
    """Test when no custom title exists."""
    from spellbook_mcp.session_ops import extract_custom_title

    messages = [
        {"type": "user", "message": {"content": "Hello"}},
        {"type": "assistant", "message": {"content": "Hi"}}
    ]

    result = extract_custom_title(messages)
    assert result is None


def test_extract_custom_title_missing_field():
    """Test custom title extraction when customTitle field is missing."""
    from spellbook_mcp.session_ops import extract_custom_title

    messages = [
        {"type": "custom-title", "sessionId": "abc123"}  # Missing customTitle
    ]

    result = extract_custom_title(messages)
    assert result is None


def test_split_by_char_limit_single_chunk(tmp_path):
    """Test splitting when entire session fits in one chunk."""
    from spellbook_mcp.session_ops import split_by_char_limit

    session_file = tmp_path / "session.jsonl"
    messages = [
        {"uuid": "msg-1", "type": "user", "message": {"content": "A"}},
        {"uuid": "msg-2", "type": "assistant", "message": {"content": "B"}}
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = split_by_char_limit(str(session_file), start_line=0, char_limit=100000)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0] == [0, 2]


def test_split_by_char_limit_multiple_chunks(tmp_path):
    """Test splitting into multiple chunks."""
    from spellbook_mcp.session_ops import split_by_char_limit

    session_file = tmp_path / "session.jsonl"

    messages = [
        {"uuid": f"msg-{i}", "type": "user", "message": {"content": "x" * 50}}
        for i in range(10)
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = split_by_char_limit(str(session_file), start_line=0, char_limit=200)

    assert len(result) > 1
    for chunk in result:
        assert isinstance(chunk, list)
        assert len(chunk) == 2


def test_split_by_char_limit_invalid_start_line(tmp_path):
    """Test error handling for invalid start_line."""
    from spellbook_mcp.session_ops import split_by_char_limit

    session_file = tmp_path / "session.jsonl"
    with open(session_file, 'w') as f:
        f.write('{"uuid": "msg-1"}\n')

    with pytest.raises(ValueError) as exc_info:
        split_by_char_limit(str(session_file), start_line=10, char_limit=1000)

    assert "Invalid start_line" in str(exc_info.value)


def test_split_by_char_limit_invalid_char_limit(tmp_path):
    """Test error handling for invalid char_limit."""
    from spellbook_mcp.session_ops import split_by_char_limit

    session_file = tmp_path / "session.jsonl"
    with open(session_file, 'w') as f:
        f.write('{"uuid": "msg-1"}\n')

    with pytest.raises(ValueError) as exc_info:
        split_by_char_limit(str(session_file), start_line=0, char_limit=0)

    assert "Invalid char_limit" in str(exc_info.value)


def test_split_by_char_limit_single_message_exceeds_limit(tmp_path):
    """Test that at least one message per chunk even if it exceeds limit."""
    from spellbook_mcp.session_ops import split_by_char_limit

    session_file = tmp_path / "session.jsonl"
    large_message = {"uuid": "msg-1", "type": "user", "message": {"content": "x" * 1000}}

    with open(session_file, 'w') as f:
        f.write(json.dumps(large_message) + '\n')

    result = split_by_char_limit(str(session_file), start_line=0, char_limit=100)

    assert len(result) == 1
    assert result[0] == [0, 1]


def test_list_sessions_with_samples(tmp_path):
    """Test listing sessions with metadata and content samples."""
    from spellbook_mcp.session_ops import list_sessions_with_samples

    session1 = tmp_path / "session-1.jsonl"
    messages1 = [
        {"slug": "fuzzy-bear", "type": "user", "timestamp": "2026-01-01T10:00:00Z",
         "message": {"content": "First user message"}},
        {"type": "assistant", "timestamp": "2026-01-01T10:00:05Z",
         "message": {"content": "Response"}},
        {"type": "custom-title", "customTitle": "Test Session", "sessionId": "abc123"}
    ]

    with open(session1, 'w') as f:
        for msg in messages1:
            f.write(json.dumps(msg) + '\n')

    result = list_sessions_with_samples(str(tmp_path), limit=5)

    assert len(result) == 1
    session = result[0]
    assert session['slug'] == 'fuzzy-bear'
    assert session['custom_title'] == 'Test Session'
    assert session['message_count'] == 3
    assert session['first_user_message'] == 'First user message'
    # Verify values, not just existence
    assert session['path'] == str(session1)
    assert session['created'] == '2026-01-01T10:00:00Z'
    assert session['last_activity'] == '2026-01-01T10:00:05Z'


def test_list_sessions_with_samples_limit(tmp_path):
    """Test that limit parameter works correctly."""
    from spellbook_mcp.session_ops import list_sessions_with_samples

    for i in range(5):
        session = tmp_path / f"session-{i}.jsonl"
        messages = [
            {"slug": f"session-{i}", "type": "user",
             "timestamp": f"2026-01-01T10:{i:02d}:00Z",
             "message": {"content": f"Message {i}"}}
        ]
        with open(session, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

    result = list_sessions_with_samples(str(tmp_path), limit=3)
    assert len(result) == 3
    # Verify correct sessions returned (most recent by timestamp)
    assert [r['slug'] for r in result] == ['session-4', 'session-3', 'session-2']


def test_list_sessions_with_samples_empty_dir(tmp_path):
    """Test listing sessions in empty directory."""
    from spellbook_mcp.session_ops import list_sessions_with_samples

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = list_sessions_with_samples(str(empty_dir), limit=5)
    assert result == []


def test_list_sessions_sorted_by_activity(tmp_path):
    """Test that sessions are sorted by last_activity descending."""
    from spellbook_mcp.session_ops import list_sessions_with_samples

    for i in range(3):
        session = tmp_path / f"session-{i}.jsonl"
        with open(session, 'w') as f:
            f.write(json.dumps({
                "slug": f"session-{i}",
                "type": "user",
                "timestamp": f"2026-01-01T10:{i:02d}:00Z",
                "message": {"content": f"Message {i}"}
            }) + '\n')

    result = list_sessions_with_samples(str(tmp_path), limit=10)

    assert len(result) == 3
    assert result[0]['slug'] == 'session-2'
    assert result[1]['slug'] == 'session-1'
    assert result[2]['slug'] == 'session-0'
