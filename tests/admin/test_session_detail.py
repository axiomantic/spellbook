"""Tests for session detail and messages endpoints.

TDD: Tests written before implementation. Each test targets one behavior.
"""

import json
import tempfile
from pathlib import Path

import bigfoot
import pytest


def _write_session_file(project_dir: Path, session_id: str, messages: list[dict]) -> Path:
    """Write a JSONL session file for testing."""
    jsonl_path = project_dir / f"{session_id}.jsonl"
    with open(jsonl_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    return jsonl_path


# ---------------------------------------------------------------------------
# Helper: _validate_path_segment
# ---------------------------------------------------------------------------
class TestValidatePathSegment:
    def test_valid_segment(self):
        from spellbook.admin.routes.sessions import _validate_path_segment

        assert _validate_path_segment("Users-test-myproject") is True

    def test_rejects_double_dot(self):
        from spellbook.admin.routes.sessions import _validate_path_segment

        assert _validate_path_segment("..") is False

    def test_rejects_embedded_double_dot(self):
        from spellbook.admin.routes.sessions import _validate_path_segment

        assert _validate_path_segment("foo/../bar") is False

    def test_rejects_forward_slash(self):
        from spellbook.admin.routes.sessions import _validate_path_segment

        assert _validate_path_segment("foo/bar") is False

    def test_rejects_backslash(self):
        from spellbook.admin.routes.sessions import _validate_path_segment

        assert _validate_path_segment("foo\\bar") is False

    def test_rejects_null_byte(self):
        from spellbook.admin.routes.sessions import _validate_path_segment

        assert _validate_path_segment("foo\x00bar") is False

    def test_accepts_dashes_and_alphanumeric(self):
        from spellbook.admin.routes.sessions import _validate_path_segment

        assert _validate_path_segment("abc-123-def") is True


# ---------------------------------------------------------------------------
# Helper: _decode_project_path
# ---------------------------------------------------------------------------
class TestDecodeProjectPath:
    def test_decodes_project_encoded_path(self):
        from spellbook.admin.routes.sessions import _decode_project_path

        assert _decode_project_path("Users-test-myproject") == "/Users/test/myproject"

    def test_prepends_slash(self):
        from spellbook.admin.routes.sessions import _decode_project_path

        assert _decode_project_path("home-user-code") == "/home/user/code"

    def test_single_segment(self):
        from spellbook.admin.routes.sessions import _decode_project_path

        assert _decode_project_path("root") == "/root"


# ---------------------------------------------------------------------------
# Helper: _normalize_message
# ---------------------------------------------------------------------------
class TestNormalizeMessage:
    def test_user_message_string_content(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "user",
            "timestamp": "2026-03-14T10:00:00Z",
            "message": {"content": "Hello world"},
        }
        result = _normalize_message(entry, 1)
        assert result == {
            "line_number": 1,
            "type": "user",
            "timestamp": "2026-03-14T10:00:00Z",
            "content": "Hello world",
            "is_compact_summary": False,
            "raw": entry,
        }

    def test_user_message_list_content(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "user",
            "timestamp": "2026-03-14T10:00:00Z",
            "message": {
                "content": [
                    {"type": "text", "text": "Line 1"},
                    {"type": "text", "text": "Line 2"},
                ]
            },
        }
        result = _normalize_message(entry, 5)
        assert result == {
            "line_number": 5,
            "type": "user",
            "timestamp": "2026-03-14T10:00:00Z",
            "content": "Line 1\nLine 2",
            "is_compact_summary": False,
            "raw": entry,
        }

    def test_assistant_message_string_content(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "assistant",
            "timestamp": "2026-03-14T10:01:00Z",
            "message": {"content": "I can help with that"},
        }
        result = _normalize_message(entry, 2)
        assert result == {
            "line_number": 2,
            "type": "assistant",
            "timestamp": "2026-03-14T10:01:00Z",
            "content": "I can help with that",
            "is_compact_summary": False,
            "raw": entry,
        }

    def test_assistant_message_list_content(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "assistant",
            "timestamp": "2026-03-14T10:01:00Z",
            "message": {
                "content": [
                    {"type": "text", "text": "Part 1"},
                    {"type": "text", "text": "Part 2"},
                    {"type": "text", "text": "Part 3"},
                ]
            },
        }
        result = _normalize_message(entry, 3)
        assert result == {
            "line_number": 3,
            "type": "assistant",
            "timestamp": "2026-03-14T10:01:00Z",
            "content": "Part 1\nPart 2\nPart 3",
            "is_compact_summary": False,
            "raw": entry,
        }

    def test_custom_title_message(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "custom-title",
            "customTitle": "My Session Title",
        }
        result = _normalize_message(entry, 3)
        assert result == {
            "line_number": 3,
            "type": "custom-title",
            "timestamp": None,
            "content": "My Session Title",
            "is_compact_summary": False,
            "raw": entry,
        }

    def test_progress_message(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "progress",
            "timestamp": "2026-03-14T10:02:00Z",
            "message": "Processing step 3 of 5",
        }
        result = _normalize_message(entry, 4)
        assert result == {
            "line_number": 4,
            "type": "progress",
            "timestamp": "2026-03-14T10:02:00Z",
            "content": "Processing step 3 of 5",
            "is_compact_summary": False,
            "raw": entry,
        }

    def test_system_message_string_content(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "system",
            "timestamp": "2026-03-14T10:00:00Z",
            "message": {"content": "System initialized"},
        }
        result = _normalize_message(entry, 1)
        assert result == {
            "line_number": 1,
            "type": "system",
            "timestamp": "2026-03-14T10:00:00Z",
            "content": "System initialized",
            "is_compact_summary": False,
            "raw": entry,
        }

    def test_system_message_list_content(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "system",
            "timestamp": "2026-03-14T10:00:00Z",
            "message": {
                "content": [
                    {"type": "text", "text": "System part 1"},
                    {"type": "text", "text": "System part 2"},
                ]
            },
        }
        result = _normalize_message(entry, 1)
        assert result == {
            "line_number": 1,
            "type": "system",
            "timestamp": "2026-03-14T10:00:00Z",
            "content": "System part 1\nSystem part 2",
            "is_compact_summary": False,
            "raw": entry,
        }

    def test_unknown_type_falls_back_to_json(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "tool_result",
            "timestamp": "2026-03-14T10:03:00Z",
            "data": {"key": "value"},
        }
        result = _normalize_message(entry, 7)
        # The fallback serializes the full entry as JSON, truncated to 500 chars
        expected_content = json.dumps(entry, default=str)[:500]
        assert result == {
            "line_number": 7,
            "type": "tool_result",
            "timestamp": "2026-03-14T10:03:00Z",
            "content": expected_content,
            "is_compact_summary": False,
            "raw": entry,
        }

    def test_compact_summary_flag(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {
            "type": "user",
            "timestamp": "2026-03-14T10:00:00Z",
            "message": {"content": "Compacted content", "isCompactSummary": True},
        }
        result = _normalize_message(entry, 1)
        assert result == {
            "line_number": 1,
            "type": "user",
            "timestamp": "2026-03-14T10:00:00Z",
            "content": "Compacted content",
            "is_compact_summary": True,
            "raw": entry,
        }

    def test_missing_type_defaults_to_unknown(self):
        from spellbook.admin.routes.sessions import _normalize_message

        entry = {"timestamp": "2026-03-14T10:00:00Z", "data": "something"}
        result = _normalize_message(entry, 1)
        expected_content = json.dumps(entry, default=str)[:500]
        assert result == {
            "line_number": 1,
            "type": "unknown",
            "timestamp": "2026-03-14T10:00:00Z",
            "content": expected_content,
            "is_compact_summary": False,
            "raw": entry,
        }


# ---------------------------------------------------------------------------
# Helper: _read_session_metadata
# ---------------------------------------------------------------------------
class TestReadSessionMetadata:
    def test_reads_metadata_from_session_file(self):
        from spellbook.admin.routes.sessions import _read_session_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "Users-test-myproject"
            project_dir.mkdir()
            file_path = _write_session_file(project_dir, "sess-abc", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "Hello world"}, "slug": "my-session"},
                {"type": "assistant", "timestamp": "2026-03-14T10:01:00Z",
                 "message": {"content": "Hi there"}},
                {"type": "custom-title", "customTitle": "Test Session"},
            ])
            result = _read_session_metadata(file_path)
            assert result == {
                "id": "sess-abc",
                "project": "Users-test-myproject",
                "project_decoded": "/Users/test/myproject",
                "slug": "my-session",
                "custom_title": "Test Session",
                "created_at": "2026-03-14T10:00:00Z",
                "last_activity": "2026-03-14T10:01:00Z",
                "message_count": 3,
                "size_bytes": file_path.stat().st_size,
                "first_user_message": "Hello world",
            }

    def test_handles_no_user_messages(self):
        from spellbook.admin.routes.sessions import _read_session_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "Users-test-proj"
            project_dir.mkdir()
            file_path = _write_session_file(project_dir, "sess-no-user", [
                {"type": "system", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": "System msg"}},
            ])
            result = _read_session_metadata(file_path)
            assert result == {
                "id": "sess-no-user",
                "project": "Users-test-proj",
                "project_decoded": "/Users/test/proj",
                "slug": None,
                "custom_title": None,
                "created_at": "2026-03-14T10:00:00Z",
                "last_activity": "2026-03-14T10:00:00Z",
                "message_count": 1,
                "size_bytes": file_path.stat().st_size,
                "first_user_message": None,
            }

    def test_handles_list_content_for_first_user_message(self):
        from spellbook.admin.routes.sessions import _read_session_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "Users-test-proj"
            project_dir.mkdir()
            file_path = _write_session_file(project_dir, "sess-list", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": [{"type": "text", "text": "List content"}]}},
            ])
            result = _read_session_metadata(file_path)
            assert result == {
                "id": "sess-list",
                "project": "Users-test-proj",
                "project_decoded": "/Users/test/proj",
                "slug": None,
                "custom_title": None,
                "created_at": "2026-03-14T10:00:00Z",
                "last_activity": "2026-03-14T10:00:00Z",
                "message_count": 1,
                "size_bytes": file_path.stat().st_size,
                "first_user_message": "List content",
            }

    def test_skips_malformed_json_lines(self):
        from spellbook.admin.routes.sessions import _read_session_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "Users-test-proj"
            project_dir.mkdir()
            file_path = project_dir / "sess-malformed.jsonl"
            with open(file_path, "w") as f:
                f.write(json.dumps({"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                                    "message": {"content": "Good line"}}) + "\n")
                f.write("not valid json\n")
                f.write(json.dumps({"type": "assistant", "timestamp": "2026-03-14T10:01:00Z",
                                    "message": {"content": "Also good"}}) + "\n")
            result = _read_session_metadata(file_path)
            assert result == {
                "id": "sess-malformed",
                "project": "Users-test-proj",
                "project_decoded": "/Users/test/proj",
                "slug": None,
                "custom_title": None,
                "created_at": "2026-03-14T10:00:00Z",
                "last_activity": "2026-03-14T10:01:00Z",
                "message_count": 2,
                "size_bytes": file_path.stat().st_size,
                "first_user_message": "Good line",
            }

    def test_first_user_message_is_not_truncated(self):
        """Unlike list_sessions which truncates to 200 chars, detail returns full."""
        from spellbook.admin.routes.sessions import _read_session_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "Users-test-proj"
            project_dir.mkdir()
            long_msg = "A" * 500
            file_path = _write_session_file(project_dir, "sess-long", [
                {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                 "message": {"content": long_msg}},
            ])
            result = _read_session_metadata(file_path)
            assert result["first_user_message"] == long_msg


# ---------------------------------------------------------------------------
# Helper: _read_messages_page
# ---------------------------------------------------------------------------
class TestReadMessagesPage:
    def _make_session_file(self, tmpdir: str, count: int) -> Path:
        """Create a session file with `count` user messages."""
        project_dir = Path(tmpdir) / "Users-test-proj"
        project_dir.mkdir(exist_ok=True)
        messages = [
            {"type": "user", "timestamp": f"2026-03-14T10:{i:02d}:00Z",
             "message": {"content": f"Message {i}"}}
            for i in range(count)
        ]
        return _write_session_file(project_dir, "sess-paged", messages)

    def test_first_page(self):
        from spellbook.admin.routes.sessions import _read_messages_page

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = self._make_session_file(tmpdir, 5)
            result = _read_messages_page(file_path, page=1, per_page=2)
            assert result["total_lines"] == 5
            assert result["page"] == 1
            assert result["per_page"] == 2
            assert result["pages"] == 3
            assert len(result["messages"]) == 2
            msg0 = result["messages"][0]
            assert msg0["line_number"] == 1
            assert msg0["type"] == "user"
            assert msg0["timestamp"] == "2026-03-14T10:00:00Z"
            assert msg0["content"] == "Message 0"
            assert msg0["is_compact_summary"] is False
            assert msg0["raw"] == {
                "type": "user", "timestamp": "2026-03-14T10:00:00Z",
                "message": {"content": "Message 0"},
            }
            msg1 = result["messages"][1]
            assert msg1["line_number"] == 2
            assert msg1["type"] == "user"
            assert msg1["timestamp"] == "2026-03-14T10:01:00Z"
            assert msg1["content"] == "Message 1"
            assert msg1["is_compact_summary"] is False
            assert msg1["raw"] == {
                "type": "user", "timestamp": "2026-03-14T10:01:00Z",
                "message": {"content": "Message 1"},
            }

    def test_middle_page(self):
        from spellbook.admin.routes.sessions import _read_messages_page

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = self._make_session_file(tmpdir, 5)
            result = _read_messages_page(file_path, page=2, per_page=2)
            assert result["total_lines"] == 5
            assert result["page"] == 2
            assert result["pages"] == 3
            assert len(result["messages"]) == 2
            msg0 = result["messages"][0]
            assert msg0["line_number"] == 3
            assert msg0["type"] == "user"
            assert msg0["timestamp"] == "2026-03-14T10:02:00Z"
            assert msg0["content"] == "Message 2"
            assert msg0["is_compact_summary"] is False
            assert msg0["raw"] == {
                "type": "user", "timestamp": "2026-03-14T10:02:00Z",
                "message": {"content": "Message 2"},
            }
            msg1 = result["messages"][1]
            assert msg1["line_number"] == 4
            assert msg1["type"] == "user"
            assert msg1["timestamp"] == "2026-03-14T10:03:00Z"
            assert msg1["content"] == "Message 3"
            assert msg1["is_compact_summary"] is False
            assert msg1["raw"] == {
                "type": "user", "timestamp": "2026-03-14T10:03:00Z",
                "message": {"content": "Message 3"},
            }

    def test_last_page_partial(self):
        from spellbook.admin.routes.sessions import _read_messages_page

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = self._make_session_file(tmpdir, 5)
            result = _read_messages_page(file_path, page=3, per_page=2)
            assert result["total_lines"] == 5
            assert result["page"] == 3
            assert result["pages"] == 3
            assert len(result["messages"]) == 1
            msg0 = result["messages"][0]
            assert msg0["line_number"] == 5
            assert msg0["type"] == "user"
            assert msg0["timestamp"] == "2026-03-14T10:04:00Z"
            assert msg0["content"] == "Message 4"
            assert msg0["is_compact_summary"] is False
            assert msg0["raw"] == {
                "type": "user", "timestamp": "2026-03-14T10:04:00Z",
                "message": {"content": "Message 4"},
            }

    def test_single_page_all_messages(self):
        from spellbook.admin.routes.sessions import _read_messages_page

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = self._make_session_file(tmpdir, 3)
            result = _read_messages_page(file_path, page=1, per_page=100)
            assert result["total_lines"] == 3
            assert result["page"] == 1
            assert result["pages"] == 1
            assert len(result["messages"]) == 3

    def test_malformed_line_becomes_error_entry(self):
        from spellbook.admin.routes.sessions import _read_messages_page

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "Users-test-proj"
            project_dir.mkdir(exist_ok=True)
            file_path = project_dir / "sess-bad.jsonl"
            with open(file_path, "w") as f:
                f.write(json.dumps({"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                                    "message": {"content": "Good"}}) + "\n")
                f.write("not valid json\n")
                f.write(json.dumps({"type": "user", "timestamp": "2026-03-14T10:01:00Z",
                                    "message": {"content": "Also good"}}) + "\n")
            result = _read_messages_page(file_path, page=1, per_page=100)
            assert result["total_lines"] == 3
            assert len(result["messages"]) == 3
            assert result["messages"][0]["content"] == "Good"
            assert result["messages"][1] == {
                "line_number": 2,
                "type": "error",
                "timestamp": None,
                "content": "[Malformed JSONL line]",
                "is_compact_summary": False,
                "raw": None,
            }
            assert result["messages"][2]["content"] == "Also good"

    def test_empty_lines_are_skipped(self):
        from spellbook.admin.routes.sessions import _read_messages_page

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "Users-test-proj"
            project_dir.mkdir(exist_ok=True)
            file_path = project_dir / "sess-empty-lines.jsonl"
            with open(file_path, "w") as f:
                f.write(json.dumps({"type": "user", "timestamp": "2026-03-14T10:00:00Z",
                                    "message": {"content": "First"}}) + "\n")
                f.write("\n")
                f.write("   \n")
                f.write(json.dumps({"type": "user", "timestamp": "2026-03-14T10:01:00Z",
                                    "message": {"content": "Second"}}) + "\n")
            result = _read_messages_page(file_path, page=1, per_page=100)
            assert result["total_lines"] == 2
            assert len(result["messages"]) == 2
            assert result["messages"][0]["content"] == "First"
            assert result["messages"][1]["content"] == "Second"


# ---------------------------------------------------------------------------
# Endpoint: GET /{project}/{session_id}
# ---------------------------------------------------------------------------
class TestGetSessionDetail:
    def _setup_session(self, tmpdir: str) -> tuple[Path, Path]:
        """Create the .claude/projects structure with a test session."""
        claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
        claude_projects.mkdir(parents=True)
        project_dir = claude_projects / "Users-test-myproject"
        project_dir.mkdir()
        _write_session_file(project_dir, "sess-abc", [
            {"type": "user", "timestamp": "2026-03-14T10:00:00Z",
             "message": {"content": "Hello world"}, "slug": "test-slug"},
            {"type": "assistant", "timestamp": "2026-03-14T10:01:00Z",
             "message": {"content": "Hi there"}},
        ])
        return claude_projects, project_dir

    def test_returns_session_metadata(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects, project_dir = self._setup_session(tmpdir)
            file_path = project_dir / "sess-abc.jsonl"

            mock_home = bigfoot.mock("spellbook.admin.routes.sessions:Path.home")
            mock_home.returns(Path(tmpdir) / "fakehome")

            with bigfoot:
                response = client.get("/api/sessions/Users-test-myproject/sess-abc")

            mock_home.assert_call()
            assert response.status_code == 200
            data = response.json()
            assert data == {
                "id": "sess-abc",
                "project": "Users-test-myproject",
                "project_decoded": "/Users/test/myproject",
                "slug": "test-slug",
                "custom_title": None,
                "created_at": "2026-03-14T10:00:00Z",
                "last_activity": "2026-03-14T10:01:00Z",
                "message_count": 2,
                "size_bytes": file_path.stat().st_size,
                "first_user_message": "Hello world",
            }

    def test_returns_404_for_missing_project(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
            claude_projects.mkdir(parents=True)

            mock_home = bigfoot.mock("spellbook.admin.routes.sessions:Path.home")
            mock_home.returns(Path(tmpdir) / "fakehome")

            with bigfoot:
                response = client.get("/api/sessions/nonexistent-project/sess-abc")

            mock_home.assert_call()
            assert response.status_code == 404
            data = response.json()
            assert data == {"error": {"code": "NOT_FOUND", "message": "Project not found"}}

    def test_returns_404_for_missing_session(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
            claude_projects.mkdir(parents=True)
            project_dir = claude_projects / "Users-test-myproject"
            project_dir.mkdir()

            mock_home = bigfoot.mock("spellbook.admin.routes.sessions:Path.home")
            mock_home.returns(Path(tmpdir) / "fakehome")

            with bigfoot:
                response = client.get("/api/sessions/Users-test-myproject/nonexistent")

            mock_home.assert_call()
            assert response.status_code == 404
            data = response.json()
            assert data == {"error": {"code": "NOT_FOUND", "message": "Session not found"}}

    def test_rejects_path_traversal_in_project(self, client):
        """Validate that _validate_path_segment rejects '..' in project name.

        NOTE: Starlette decodes %2F to / in path params, so encoded-slash
        traversal is handled by the routing layer. This test validates
        the dot-dot check in our code for segments without slashes.
        """
        response = client.get("/api/sessions/foo..bar/sess-abc")

        assert response.status_code == 400
        data = response.json()
        assert data == {"error": {"code": "BAD_REQUEST", "message": "Invalid path segment"}}

    def test_rejects_path_traversal_in_session_id(self, client):
        """Validate that _validate_path_segment rejects '..' in session_id."""
        response = client.get("/api/sessions/Users-test-myproject/foo..bar")

        assert response.status_code == 400
        data = response.json()
        assert data == {"error": {"code": "BAD_REQUEST", "message": "Invalid path segment"}}

    def test_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get("/api/sessions/Users-test-proj/sess-abc")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Endpoint: GET /{project}/{session_id}/messages
# ---------------------------------------------------------------------------
class TestGetSessionMessages:
    def _setup_session(self, tmpdir: str, msg_count: int = 5) -> tuple[Path, Path]:
        """Create the .claude/projects structure with a test session."""
        claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
        claude_projects.mkdir(parents=True)
        project_dir = claude_projects / "Users-test-myproject"
        project_dir.mkdir()
        messages = [
            {"type": "user", "timestamp": f"2026-03-14T10:{i:02d}:00Z",
             "message": {"content": f"Message {i}"}}
            for i in range(msg_count)
        ]
        _write_session_file(project_dir, "sess-abc", messages)
        return claude_projects, project_dir

    def test_returns_first_page_of_messages(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._setup_session(tmpdir, msg_count=5)

            mock_home = bigfoot.mock("spellbook.admin.routes.sessions:Path.home")
            mock_home.returns(Path(tmpdir) / "fakehome")

            with bigfoot:
                response = client.get(
                    "/api/sessions/Users-test-myproject/sess-abc/messages?page=1&per_page=2"
                )

            mock_home.assert_call()
            assert response.status_code == 200
            data = response.json()
            assert data["total_lines"] == 5
            assert data["page"] == 1
            assert data["per_page"] == 2
            assert data["pages"] == 3
            assert len(data["messages"]) == 2
            msg0 = data["messages"][0]
            assert msg0["line_number"] == 1
            assert msg0["type"] == "user"
            assert msg0["timestamp"] == "2026-03-14T10:00:00Z"
            assert msg0["content"] == "Message 0"
            assert msg0["is_compact_summary"] is False
            assert msg0["raw"] == {
                "type": "user", "timestamp": "2026-03-14T10:00:00Z",
                "message": {"content": "Message 0"},
            }
            msg1 = data["messages"][1]
            assert msg1["line_number"] == 2
            assert msg1["type"] == "user"
            assert msg1["timestamp"] == "2026-03-14T10:01:00Z"
            assert msg1["content"] == "Message 1"
            assert msg1["is_compact_summary"] is False
            assert msg1["raw"] == {
                "type": "user", "timestamp": "2026-03-14T10:01:00Z",
                "message": {"content": "Message 1"},
            }

    def test_returns_second_page(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._setup_session(tmpdir, msg_count=5)

            mock_home = bigfoot.mock("spellbook.admin.routes.sessions:Path.home")
            mock_home.returns(Path(tmpdir) / "fakehome")

            with bigfoot:
                response = client.get(
                    "/api/sessions/Users-test-myproject/sess-abc/messages?page=2&per_page=2"
                )

            mock_home.assert_call()
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 2
            assert len(data["messages"]) == 2
            msg0 = data["messages"][0]
            assert msg0["line_number"] == 3
            assert msg0["type"] == "user"
            assert msg0["timestamp"] == "2026-03-14T10:02:00Z"
            assert msg0["content"] == "Message 2"
            assert msg0["is_compact_summary"] is False
            assert msg0["raw"] == {
                "type": "user", "timestamp": "2026-03-14T10:02:00Z",
                "message": {"content": "Message 2"},
            }
            msg1 = data["messages"][1]
            assert msg1["line_number"] == 4
            assert msg1["type"] == "user"
            assert msg1["timestamp"] == "2026-03-14T10:03:00Z"
            assert msg1["content"] == "Message 3"
            assert msg1["is_compact_summary"] is False
            assert msg1["raw"] == {
                "type": "user", "timestamp": "2026-03-14T10:03:00Z",
                "message": {"content": "Message 3"},
            }

    def test_default_pagination(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._setup_session(tmpdir, msg_count=3)

            mock_home = bigfoot.mock("spellbook.admin.routes.sessions:Path.home")
            mock_home.returns(Path(tmpdir) / "fakehome")

            with bigfoot:
                response = client.get(
                    "/api/sessions/Users-test-myproject/sess-abc/messages"
                )

            mock_home.assert_call()
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 1
            assert data["per_page"] == 100
            assert data["pages"] == 1
            assert len(data["messages"]) == 3

    def test_returns_404_for_missing_project(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
            claude_projects.mkdir(parents=True)

            mock_home = bigfoot.mock("spellbook.admin.routes.sessions:Path.home")
            mock_home.returns(Path(tmpdir) / "fakehome")

            with bigfoot:
                response = client.get("/api/sessions/nonexistent/sess-abc/messages")

            mock_home.assert_call()
            assert response.status_code == 404
            data = response.json()
            assert data == {"error": {"code": "NOT_FOUND", "message": "Project not found"}}

    def test_returns_404_for_missing_session(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_projects = Path(tmpdir) / "fakehome" / ".claude" / "projects"
            claude_projects.mkdir(parents=True)
            project_dir = claude_projects / "Users-test-myproject"
            project_dir.mkdir()

            mock_home = bigfoot.mock("spellbook.admin.routes.sessions:Path.home")
            mock_home.returns(Path(tmpdir) / "fakehome")

            with bigfoot:
                response = client.get("/api/sessions/Users-test-myproject/nonexistent/messages")

            mock_home.assert_call()
            assert response.status_code == 404
            data = response.json()
            assert data == {"error": {"code": "NOT_FOUND", "message": "Session not found"}}

    def test_rejects_path_traversal(self, client):
        """Validate that _validate_path_segment rejects '..' in session_id for messages."""
        response = client.get(
            "/api/sessions/Users-test-myproject/foo..bar/messages"
        )

        assert response.status_code == 400
        data = response.json()
        assert data == {"error": {"code": "BAD_REQUEST", "message": "Invalid path segment"}}

    def test_session_messages_beyond_last_page(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._setup_session(tmpdir, msg_count=5)

            mock_home = bigfoot.mock("spellbook.admin.routes.sessions:Path.home")
            mock_home.returns(Path(tmpdir) / "fakehome")

            with bigfoot:
                response = client.get(
                    "/api/sessions/Users-test-myproject/sess-abc/messages?page=10&per_page=2"
                )

            mock_home.assert_call()
            assert response.status_code == 200
            data = response.json()
            assert data["messages"] == []
            assert data["total_lines"] == 5
            assert data["page"] == 10
            assert data["per_page"] == 2
            assert data["pages"] == 3

    def test_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get(
            "/api/sessions/Users-test-proj/sess-abc/messages"
        )
        assert response.status_code == 401
