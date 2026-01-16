"""Tests for MCP tool injection decorator."""

import pytest
import json


class TestShouldInject:
    """Tests for should_inject() function."""

    def test_should_inject_first_call_after_compaction(self):
        """Test injection triggers on first call after compaction."""
        from spellbook_mcp.injection import should_inject, _reset_state, _set_pending_compaction

        _reset_state()

        # Simulate pending compaction
        _set_pending_compaction(True)

        assert should_inject() is True

    def test_should_inject_every_10th_call(self):
        """Test injection triggers every 10th call."""
        from spellbook_mcp.injection import should_inject, _reset_state

        _reset_state()

        # First 9 calls should not inject
        for i in range(9):
            assert should_inject() is False, f"Call {i + 1} should not inject"

        # 10th call should inject
        assert should_inject() is True, "10th call should inject"

        # Next 9 should not
        for i in range(9):
            assert should_inject() is False, f"Call {i + 11} should not inject"

        # 20th should inject
        assert should_inject() is True, "20th call should inject"

    def test_should_inject_compaction_resets_counter(self):
        """Test that compaction detection resets the call counter."""
        from spellbook_mcp.injection import should_inject, _reset_state, _set_pending_compaction

        _reset_state()

        # Make 5 calls (counter at 5)
        for _ in range(5):
            should_inject()

        # Set pending compaction
        _set_pending_compaction(True)

        # Next call should inject AND reset counter
        assert should_inject() is True

        # Need 9 more calls before next injection (counter reset to 0, then 1-9)
        for i in range(9):
            assert should_inject() is False, f"Call {i + 1} after reset should not inject"

        # 10th call after reset should inject
        assert should_inject() is True

    def test_should_inject_clears_pending_flag(self):
        """Test that pending compaction flag is cleared after injection."""
        from spellbook_mcp.injection import should_inject, _reset_state, _set_pending_compaction

        _reset_state()
        _set_pending_compaction(True)

        # First call consumes the flag and injects
        assert should_inject() is True

        # Second call should NOT inject (flag cleared, counter at 1)
        assert should_inject() is False


class TestWrapWithReminder:
    """Tests for wrap_with_reminder() function."""

    def test_wrap_with_reminder_string(self):
        """Test wrapping string result with reminder."""
        from spellbook_mcp.injection import wrap_with_reminder

        result = "Original result"
        context = "Test context"

        wrapped = wrap_with_reminder(result, context)

        assert isinstance(wrapped, str)
        assert "<system-reminder>" in wrapped
        assert "</system-reminder>" in wrapped
        assert "Test context" in wrapped
        assert "Original result" in wrapped
        # Reminder should come first
        assert wrapped.index("<system-reminder>") < wrapped.index("Original result")

    def test_wrap_with_reminder_dict(self):
        """Test wrapping dict result with reminder."""
        from spellbook_mcp.injection import wrap_with_reminder

        result = {"status": "ok", "data": "test"}
        context = "Test context"

        wrapped = wrap_with_reminder(result, context)

        assert isinstance(wrapped, dict)
        assert "__system_reminder" in wrapped
        assert "<system-reminder>" in wrapped["__system_reminder"]
        assert "Test context" in wrapped["__system_reminder"]
        # Original keys preserved
        assert wrapped["status"] == "ok"
        assert wrapped["data"] == "test"

    def test_wrap_with_reminder_list(self):
        """Test wrapping list result with reminder."""
        from spellbook_mcp.injection import wrap_with_reminder

        result = [{"id": 1}, {"id": 2}]
        context = "Test context"

        wrapped = wrap_with_reminder(result, context)

        assert isinstance(wrapped, dict)
        assert "__system_reminder" in wrapped
        assert "items" in wrapped
        assert wrapped["items"] == result
        assert "Test context" in wrapped["__system_reminder"]

    def test_wrap_with_reminder_empty_context(self):
        """Test that empty context returns original result."""
        from spellbook_mcp.injection import wrap_with_reminder

        result = {"status": "ok"}

        # Empty string
        assert wrap_with_reminder(result, "") == result
        # None
        assert wrap_with_reminder(result, None) == result

    def test_wrap_with_reminder_other_types(self):
        """Test wrapping non-standard types (fallback to string)."""
        from spellbook_mcp.injection import wrap_with_reminder

        # Integer
        wrapped = wrap_with_reminder(42, "Test context")
        assert isinstance(wrapped, str)
        assert "42" in wrapped
        assert "<system-reminder>" in wrapped

        # None value
        wrapped = wrap_with_reminder(None, "Test context")
        assert isinstance(wrapped, str)
        assert "None" in wrapped
        assert "<system-reminder>" in wrapped


class TestBuildRecoveryContext:
    """Tests for build_recovery_context() function."""

    def test_build_recovery_context_with_full_soul(self, tmp_path):
        """Test building recovery context from database with all fields."""
        from spellbook_mcp.injection import build_recovery_context
        from spellbook_mcp.db import init_db, get_connection, close_all_connections

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert test soul
        conn = get_connection(db_path)
        conn.execute(
            """
            INSERT INTO souls (id, project_path, persona, active_skill, todos, exact_position)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                "soul-1",
                "/test/project",
                "fun:Detective",
                "writing-plans",
                json.dumps(
                    [
                        {
                            "content": "Task 1",
                            "status": "in_progress",
                            "activeForm": "Doing task 1",
                        }
                    ]
                ),
                json.dumps(
                    [
                        {
                            "tool": "Read",
                            "primary_arg": "/file.py",
                            "timestamp": "2026-01-16T10:00:00Z",
                        }
                    ]
                ),
            ),
        )
        conn.commit()

        context = build_recovery_context(db_path, "/test/project")

        assert context is not None
        assert "Active TODOs" in context
        assert "Task 1" in context
        assert "Active Skill" in context
        assert "writing-plans" in context
        assert "Session Persona" in context
        assert "Detective" in context
        assert "Last Actions" in context
        assert "Read" in context

        close_all_connections()

    def test_build_recovery_context_no_soul(self, tmp_path):
        """Test building context when no soul exists for project."""
        from spellbook_mcp.injection import build_recovery_context
        from spellbook_mcp.db import init_db, close_all_connections

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        context = build_recovery_context(db_path, "/nonexistent/project")

        assert context is None

        close_all_connections()

    def test_build_recovery_context_partial_soul(self, tmp_path):
        """Test building context with only some fields populated."""
        from spellbook_mcp.injection import build_recovery_context
        from spellbook_mcp.db import init_db, get_connection, close_all_connections

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert soul with only active_skill
        conn = get_connection(db_path)
        conn.execute(
            """
            INSERT INTO souls (id, project_path, active_skill)
            VALUES (?, ?, ?)
        """,
            ("soul-1", "/test/project", "debugging"),
        )
        conn.commit()

        context = build_recovery_context(db_path, "/test/project")

        assert context is not None
        assert "Active Skill" in context
        assert "debugging" in context
        # These should NOT appear
        assert "Active TODOs" not in context
        assert "Session Persona" not in context

        close_all_connections()

    def test_build_recovery_context_truncation(self, tmp_path):
        """Test that context is truncated when exceeding max_tokens."""
        from spellbook_mcp.injection import build_recovery_context
        from spellbook_mcp.db import init_db, get_connection, close_all_connections

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert soul with many todos to create long context
        long_todos = [
            {"content": f"Task number {i} with lots of extra text", "status": "pending", "activeForm": f"Doing {i}"}
            for i in range(50)
        ]

        conn = get_connection(db_path)
        conn.execute(
            """
            INSERT INTO souls (id, project_path, todos)
            VALUES (?, ?, ?)
        """,
            ("soul-1", "/test/project", json.dumps(long_todos)),
        )
        conn.commit()

        # Use very small token limit
        context = build_recovery_context(db_path, "/test/project", max_tokens=20)

        assert context is not None
        # Should be truncated (20 tokens * 4 chars = 80 chars max)
        assert len(context) <= 80 + 3  # +3 for "..."
        assert context.endswith("...")

        close_all_connections()

    def test_build_recovery_context_empty_json_fields(self, tmp_path):
        """Test handling of empty JSON arrays."""
        from spellbook_mcp.injection import build_recovery_context
        from spellbook_mcp.db import init_db, get_connection, close_all_connections

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert soul with empty arrays
        conn = get_connection(db_path)
        conn.execute(
            """
            INSERT INTO souls (id, project_path, todos, recent_files, exact_position)
            VALUES (?, ?, ?, ?, ?)
        """,
            ("soul-1", "/test/project", "[]", "[]", "[]"),
        )
        conn.commit()

        # Should return None since all fields are empty
        context = build_recovery_context(db_path, "/test/project")

        assert context is None

        close_all_connections()


class TestInjectRecoveryContextDecorator:
    """Tests for inject_recovery_context decorator."""

    def test_decorator_without_injection(self, tmp_path, monkeypatch):
        """Test decorator passes through result when no injection needed."""
        from spellbook_mcp.injection import inject_recovery_context, _reset_state
        from spellbook_mcp.db import init_db, close_all_connections

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        _reset_state()

        # Mock get_db_path to use test database
        monkeypatch.setattr("spellbook_mcp.injection.get_db_path", lambda: tmp_path / "test.db")

        @inject_recovery_context
        def my_tool():
            return {"status": "ok"}

        # First 9 calls should not inject
        for _ in range(9):
            result = my_tool()
            assert result == {"status": "ok"}
            assert "__system_reminder" not in result

        close_all_connections()

    def test_decorator_with_injection_on_10th_call(self, tmp_path, monkeypatch):
        """Test decorator injects on 10th call."""
        from spellbook_mcp.injection import inject_recovery_context, _reset_state
        from spellbook_mcp.db import init_db, get_connection, close_all_connections

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert a soul
        conn = get_connection(db_path)
        conn.execute(
            """
            INSERT INTO souls (id, project_path, active_skill)
            VALUES (?, ?, ?)
        """,
            ("soul-1", str(tmp_path), "test-skill"),
        )
        # Also insert fresh heartbeat
        from datetime import datetime

        conn.execute(
            "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
            (datetime.now().isoformat(),),
        )
        conn.commit()

        _reset_state()

        # Mock get_db_path and getcwd
        monkeypatch.setattr("spellbook_mcp.injection.get_db_path", lambda: tmp_path / "test.db")
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

        @inject_recovery_context
        def my_tool():
            return {"status": "ok"}

        # Make 9 calls
        for _ in range(9):
            my_tool()

        # 10th call should inject
        result = my_tool()
        assert "__system_reminder" in result
        assert "test-skill" in result["__system_reminder"]

        close_all_connections()

    def test_decorator_with_compaction_flag(self, tmp_path, monkeypatch):
        """Test decorator injects when compaction flag is set."""
        from spellbook_mcp.injection import (
            inject_recovery_context,
            _reset_state,
            _set_pending_compaction,
        )
        from spellbook_mcp.db import init_db, get_connection, close_all_connections
        from datetime import datetime

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert a soul and heartbeat
        conn = get_connection(db_path)
        conn.execute(
            """
            INSERT INTO souls (id, project_path, active_skill)
            VALUES (?, ?, ?)
        """,
            ("soul-1", str(tmp_path), "compaction-skill"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO heartbeat (id, timestamp) VALUES (1, ?)",
            (datetime.now().isoformat(),),
        )
        conn.commit()

        _reset_state()
        _set_pending_compaction(True)

        monkeypatch.setattr("spellbook_mcp.injection.get_db_path", lambda: tmp_path / "test.db")
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

        @inject_recovery_context
        def my_tool():
            return "simple result"

        result = my_tool()
        assert "<system-reminder>" in result
        assert "compaction-skill" in result

        close_all_connections()

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""
        from spellbook_mcp.injection import inject_recovery_context, _reset_state

        _reset_state()

        @inject_recovery_context
        def my_documented_tool():
            """This is the docstring."""
            return "result"

        assert my_documented_tool.__name__ == "my_documented_tool"
        assert my_documented_tool.__doc__ == "This is the docstring."

    def test_decorator_no_injection_without_heartbeat(self, tmp_path, monkeypatch):
        """Test decorator does not inject when heartbeat is stale."""
        from spellbook_mcp.injection import (
            inject_recovery_context,
            _reset_state,
            _set_pending_compaction,
        )
        from spellbook_mcp.db import init_db, get_connection, close_all_connections

        db_path = str(tmp_path / "test.db")
        init_db(db_path)

        # Insert a soul but NO heartbeat
        conn = get_connection(db_path)
        conn.execute(
            """
            INSERT INTO souls (id, project_path, active_skill)
            VALUES (?, ?, ?)
        """,
            ("soul-1", str(tmp_path), "some-skill"),
        )
        conn.commit()

        _reset_state()
        _set_pending_compaction(True)  # Trigger injection attempt

        monkeypatch.setattr("spellbook_mcp.injection.get_db_path", lambda: tmp_path / "test.db")
        monkeypatch.setattr("os.getcwd", lambda: str(tmp_path))

        @inject_recovery_context
        def my_tool():
            return {"status": "ok"}

        result = my_tool()
        # Should not inject because heartbeat is missing/stale
        assert result == {"status": "ok"}

        close_all_connections()
