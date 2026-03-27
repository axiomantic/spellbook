"""Tests for compaction detector isCompactSummary detection.

The bug: check_for_compaction() checks msg.get('type') == 'summary' but
Claude Code uses isCompactSummary: true with type: "user". This test suite
verifies the fix detects the correct format.
"""

import json
import os

import bigfoot
import pytest

from spellbook.sessions.compaction import check_for_compaction, CompactionEvent


@pytest.fixture(autouse=True)
def mock_mcp_token():
    """Override the admin conftest autouse fixture (not needed for compaction tests)."""
    yield


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    """Use a temporary state file for each test."""
    state_file = tmp_path / "compaction_state.json"
    monkeypatch.setattr(
        "spellbook.sessions.compaction._get_state_file",
        lambda: state_file,
    )


@pytest.fixture
def session_dir(tmp_path):
    """Create a mock Claude session directory structure.

    Uses a fixed safe project name instead of encoding the real tmp_path,
    because on Windows the temp path contains colons (e.g. C:\\Users\\...)
    which are illegal in directory names and cause OSError.
    """
    project_path = str(tmp_path / "project")
    os.makedirs(project_path, exist_ok=True)
    # Use a safe, fixed encoded name rather than encoding the real path.
    # The compaction detector logic is tested via the mocked session dir,
    # so the encoded name only needs to be a valid directory name.
    session_base = tmp_path / ".claude" / "projects" / "test-project"
    session_base.mkdir(parents=True)
    return project_path, session_base


def _write_session_file(session_base, messages):
    """Write messages as JSONL to a session file."""
    session_file = session_base / "test-session.jsonl"
    with open(session_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    return session_file


class TestCompactionDetection:
    """Tests for the compaction detection logic in check_for_compaction()."""

    def test_detects_isCompactSummary_true(self, session_dir):
        """New-format compaction messages (isCompactSummary=True) must be detected."""
        project_path, session_base = session_dir
        messages = [
            {"type": "user", "content": "hello"},
            {
                "type": "user",
                "isCompactSummary": True,
                "summary": "Session summary here",
                "leafUuid": "abc-123",
            },
        ]
        _write_session_file(session_base, messages)

        session_dir_mock = bigfoot.mock(
            "spellbook.sessions.compaction:_get_claude_session_dir",
        ).returns(session_base)

        with bigfoot:
            event = check_for_compaction(project_path)

        session_dir_mock.assert_call(args=(project_path,))

        assert event is not None
        assert isinstance(event, CompactionEvent)
        assert event.session_id == "test-session"
        assert event.summary == "Session summary here"
        assert event.leaf_uuid == "abc-123"
        assert event.project_path == project_path
        assert event.injected is False

    def test_old_type_summary_not_detected(self, session_dir):
        """The old type=='summary' format is not used by Claude Code and should NOT be detected."""
        project_path, session_base = session_dir
        messages = [
            {"type": "summary", "summary": "Old format", "leafUuid": "old-123"},
        ]
        _write_session_file(session_base, messages)

        session_dir_mock = bigfoot.mock(
            "spellbook.sessions.compaction:_get_claude_session_dir",
        ).returns(session_base)

        with bigfoot:
            event = check_for_compaction(project_path)

        session_dir_mock.assert_call(args=(project_path,))

        assert event is None

    def test_isCompactSummary_false_not_detected(self, session_dir):
        """Messages with isCompactSummary=False must NOT be detected as compaction."""
        project_path, session_base = session_dir
        messages = [
            {"type": "user", "isCompactSummary": False, "content": "not a compaction"},
        ]
        _write_session_file(session_base, messages)

        session_dir_mock = bigfoot.mock(
            "spellbook.sessions.compaction:_get_claude_session_dir",
        ).returns(session_base)

        with bigfoot:
            event = check_for_compaction(project_path)

        session_dir_mock.assert_call(args=(project_path,))

        assert event is None

    def test_regular_messages_not_detected(self, session_dir):
        """Normal user/assistant messages without compaction markers must not trigger detection."""
        project_path, session_base = session_dir
        messages = [
            {"type": "user", "content": "just a normal message"},
            {"type": "assistant", "content": "response"},
        ]
        _write_session_file(session_base, messages)

        session_dir_mock = bigfoot.mock(
            "spellbook.sessions.compaction:_get_claude_session_dir",
        ).returns(session_base)

        with bigfoot:
            event = check_for_compaction(project_path)

        session_dir_mock.assert_call(args=(project_path,))

        assert event is None

    def test_realistic_compaction_shape(self, session_dir):
        """Realistic Claude Code compaction message with conversation history before it."""
        project_path, session_base = session_dir
        messages = [
            {"type": "user", "content": "start"},
            {"type": "assistant", "content": "ok"},
            {
                "type": "user",
                "isCompactSummary": True,
                "summary": "Detailed summary of prior conversation",
                "leafUuid": "leaf-uuid-456",
            },
        ]
        _write_session_file(session_base, messages)

        session_dir_mock = bigfoot.mock(
            "spellbook.sessions.compaction:_get_claude_session_dir",
        ).returns(session_base)

        with bigfoot:
            event = check_for_compaction(project_path)

        session_dir_mock.assert_call(args=(project_path,))

        assert event is not None
        assert isinstance(event, CompactionEvent)
        assert event.session_id == "test-session"
        assert event.summary == "Detailed summary of prior conversation"
        assert event.leaf_uuid == "leaf-uuid-456"
        assert event.project_path == project_path
        assert event.injected is False
