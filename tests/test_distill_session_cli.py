#!/usr/bin/env python3
"""
CLI tests for distill-session.py helper script.
"""

import subprocess
import json
import pytest
import os


def test_cli_list_sessions(tmp_path):
    """Test CLI for listing sessions."""
    session_dir = tmp_path / "project"
    session_dir.mkdir()
    session_file = session_dir / "test.jsonl"

    messages = [
        {
            "uuid": "msg-1",
            "type": "user",
            "message": {"content": "Test"},
            "timestamp": "2025-01-01T10:00:00Z",
            "slug": "test-session"
        }
    ]

    with open(session_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + '\n')

    script_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'scripts',
        'distill_session.py'
    )
    result = subprocess.run(
        ['python3', script_path, 'list-sessions', str(session_dir)],
        capture_output=True,
        text=True
    )

    # Debug output
    if result.returncode != 0:
        print(f"STDERR: {result.stderr}")
        print(f"STDOUT: {result.stdout}")

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert len(output) >= 1
    assert output[0]['slug'] == 'test-session'
