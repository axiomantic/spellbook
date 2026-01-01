# tests/test_distill_session.py
import pytest
import sys
import os
import json

# Add scripts directory to path
sys.path.insert(0, os.path.expanduser('~/.claude/scripts'))

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
