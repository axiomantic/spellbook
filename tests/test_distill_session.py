# tests/test_distill_session.py
import pytest
import sys
import os
import json

# Add scripts directory to path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, 'scripts'))

def test_imports():
    """Test that all required modules can be imported."""
    import distill_session
    assert hasattr(distill_session, '__version__')


def test_load_jsonl(tmp_path):
    """Test shared helper: load_jsonl."""
    import distill_session

    session_file = tmp_path / "test.jsonl"
    messages = [
        {"uuid": "msg-1", "type": "user", "message": {"content": "Test"}},
        {"uuid": "msg-2", "type": "assistant", "message": {"content": "Response"}}
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = distill_session.load_jsonl(str(session_file))
    assert len(result) == 2
    assert result[0]['uuid'] == 'msg-1'


def test_find_last_compact_boundary(tmp_path):
    """Test shared helper: find_last_compact_boundary."""
    import distill_session

    messages = [
        {"uuid": "msg-1", "type": "user"},
        {"uuid": "boundary-1", "type": "system", "subtype": "compact_boundary"},
        {"uuid": "msg-2", "type": "user"},
        {"uuid": "boundary-2", "type": "system", "subtype": "compact_boundary"},
        {"uuid": "msg-3", "type": "user"}
    ]

    result = distill_session.find_last_compact_boundary(messages)
    assert result == 3  # Index of boundary-2


def test_get_content_after_line(tmp_path):
    """Test extracting content after specific line."""
    import distill_session

    session_file = tmp_path / "session.jsonl"

    messages = [
        {"uuid": "msg-1", "type": "user", "message": {"content": "First"}},
        {"uuid": "msg-2", "type": "assistant", "message": {"content": "Second"}},
        {"uuid": "msg-3", "type": "user", "message": {"content": "Third"}},
        {"uuid": "msg-4", "type": "assistant", "message": {"content": "Fourth"}}
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = distill_session.get_content_after_line(str(session_file), start_line=1)
    result_data = json.loads(result)

    assert len(result_data) == 2
    assert result_data[0]['message']['content'] == 'Third'
    assert result_data[1]['message']['content'] == 'Fourth'


def test_get_content_from_start(tmp_path):
    """Test extracting all content from start."""
    import distill_session

    session_file = tmp_path / "session.jsonl"

    messages = [
        {"uuid": "msg-1", "type": "user", "message": {"content": "First"}},
        {"uuid": "msg-2", "type": "assistant", "message": {"content": "Second"}}
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = distill_session.get_content_from_start(str(session_file))
    result_data = json.loads(result)

    assert len(result_data) == 2
    assert result_data[0]['message']['content'] == 'First'


def test_get_last_compact_summary(tmp_path):
    """Test extracting last compact summary."""
    import distill_session

    session_file = tmp_path / "session.jsonl"

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
            "message": {"content": "This is the compact summary content"},
            "timestamp": "2025-01-01T12:00:01Z"
        },
        {"uuid": "msg-2", "type": "user", "message": {"content": "After compact"}}
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = distill_session.get_last_compact_summary(str(session_file))

    assert result is not None
    assert result['line_number'] == 1  # Index of boundary
    assert 'compact summary content' in result['summary_content']
    assert result['timestamp'] == '2025-01-01T12:00:00Z'


def test_extract_chunk(tmp_path):
    """Test extracting specific chunk range."""
    import distill_session

    session_file = tmp_path / "session.jsonl"

    messages = [
        {"uuid": "msg-1", "type": "user", "message": {"content": "First"}},
        {"uuid": "msg-2", "type": "assistant", "message": {"content": "Second"}},
        {"uuid": "msg-3", "type": "user", "message": {"content": "Third"}},
        {"uuid": "msg-4", "type": "assistant", "message": {"content": "Fourth"}}
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = distill_session.extract_chunk(str(session_file), start_line=1, end_line=3)
    result_data = json.loads(result)

    assert len(result_data) == 2
    assert result_data[0]['message']['content'] == 'Second'
    assert result_data[1]['message']['content'] == 'Third'


def test_list_sessions_with_samples(tmp_path):
    """Test listing sessions with metadata and samples."""
    import distill_session

    # Create mock session file
    session_dir = tmp_path / "project"
    session_dir.mkdir()
    session_file = session_dir / "test-session.jsonl"

    messages = [
        {
            "uuid": "msg-1",
            "type": "user",
            "message": {"role": "user", "content": "First user message with sample content"},
            "timestamp": "2025-01-01T10:00:00Z",
            "sessionId": "sess-1",
            "slug": "test-session"
        },
        {
            "uuid": "msg-2",
            "type": "assistant",
            "message": {"role": "assistant", "content": "Response"},
            "timestamp": "2025-01-01T10:01:00Z",
            "sessionId": "sess-1"
        }
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    result = distill_session.list_sessions_with_samples(str(session_dir), limit=5)

    assert len(result) == 1
    assert result[0]['slug'] == 'test-session'
    assert result[0]['message_count'] == 2
    assert result[0]['first_user_message'] is not None
    assert 'First user message' in result[0]['first_user_message']


def test_split_by_char_limit(tmp_path):
    """Test chunking by character limit."""
    import distill_session

    session_file = tmp_path / "session.jsonl"

    # Create messages with known sizes
    messages = []
    for i in range(10):
        msg = {
            "uuid": f"msg-{i}",
            "type": "user",
            "message": {"content": "x" * 50000}  # ~50k chars each
        }
        messages.append(msg)

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    # Split with 300k char limit (should get ~6 messages per chunk)
    result = distill_session.split_by_char_limit(str(session_file), start_line=0, char_limit=300000)

    assert len(result) > 1  # Should have multiple chunks
    for start, end in result:
        chunk_size = end - start
        assert chunk_size > 0
