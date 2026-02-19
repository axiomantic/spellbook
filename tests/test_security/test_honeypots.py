"""Tests for honeypot MCP tool business logic.

Validates:
- do_honeypot_trigger() logs a CRITICAL security event via do_log_event
- Each honeypot tool returns a tool-specific fake "success" response
- Unknown tool names return a generic {"status": "ok"} fallback
- Invocation context is captured in the event detail
- Event type is always "honeypot_triggered" with severity "CRITICAL"
"""

import json

import pytest

from spellbook_mcp.db import close_all_connections, init_db


@pytest.fixture(autouse=True)
def _clean_connections():
    """Close cached DB connections after each test to avoid cross-contamination."""
    yield
    close_all_connections()


@pytest.fixture
def db_path(tmp_path):
    """Create and initialize a temporary database, return its path as string."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


# =============================================================================
# TestHoneypotDisableChecks
# =============================================================================


class TestHoneypotDisableChecks:
    """security_disable_all_checks honeypot returns fake disabled status."""

    def test_returns_fake_disabled_status(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger

        result = do_honeypot_trigger(
            tool_name="security_disable_all_checks",
            invocation_context={},
            db_path=db_path,
        )
        assert result["status"] == "disabled"
        assert result["message"] == "All security checks disabled"

    def test_logs_critical_event(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger, do_query_events

        do_honeypot_trigger(
            tool_name="security_disable_all_checks",
            invocation_context={},
            db_path=db_path,
        )
        events = do_query_events(
            event_type="honeypot_triggered",
            db_path=db_path,
        )
        assert events["count"] == 1
        assert events["events"][0]["severity"] == "CRITICAL"


# =============================================================================
# TestHoneypotSystemPrompt
# =============================================================================


class TestHoneypotSystemPrompt:
    """system_prompt_dump honeypot returns safe message."""

    def test_returns_safe_prompt_message(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger

        result = do_honeypot_trigger(
            tool_name="system_prompt_dump",
            invocation_context={},
            db_path=db_path,
        )
        assert result["prompt"] == "System prompt export not available"

    def test_logs_critical_event(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger, do_query_events

        do_honeypot_trigger(
            tool_name="system_prompt_dump",
            invocation_context={},
            db_path=db_path,
        )
        events = do_query_events(
            event_type="honeypot_triggered",
            db_path=db_path,
        )
        assert events["count"] == 1
        assert events["events"][0]["severity"] == "CRITICAL"


# =============================================================================
# TestHoneypotCredentialExport
# =============================================================================


class TestHoneypotCredentialExport:
    """credential_export honeypot returns empty credentials."""

    def test_returns_empty_credentials(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger

        result = do_honeypot_trigger(
            tool_name="credential_export",
            invocation_context={},
            db_path=db_path,
        )
        assert result["credentials"] == []

    def test_logs_critical_event(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger, do_query_events

        do_honeypot_trigger(
            tool_name="credential_export",
            invocation_context={},
            db_path=db_path,
        )
        events = do_query_events(
            event_type="honeypot_triggered",
            db_path=db_path,
        )
        assert events["count"] == 1
        assert events["events"][0]["severity"] == "CRITICAL"


# =============================================================================
# TestHoneypotEventLogging
# =============================================================================


class TestHoneypotEventLogging:
    """Verify event_type, severity, and detail content for honeypot events."""

    def test_event_type_is_honeypot_triggered(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger, do_query_events

        do_honeypot_trigger(
            tool_name="security_disable_all_checks",
            invocation_context={},
            db_path=db_path,
        )
        events = do_query_events(db_path=db_path)
        assert events["count"] >= 1
        event = events["events"][0]
        assert event["event_type"] == "honeypot_triggered"

    def test_severity_is_critical(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger, do_query_events

        do_honeypot_trigger(
            tool_name="system_prompt_dump",
            invocation_context={},
            db_path=db_path,
        )
        events = do_query_events(
            event_type="honeypot_triggered",
            db_path=db_path,
        )
        assert events["events"][0]["severity"] == "CRITICAL"

    def test_detail_contains_tool_name(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger, do_query_events

        do_honeypot_trigger(
            tool_name="credential_export",
            invocation_context={},
            db_path=db_path,
        )
        events = do_query_events(
            event_type="honeypot_triggered",
            db_path=db_path,
        )
        detail = json.loads(events["events"][0]["detail"])
        assert detail["tool_name"] == "credential_export"


# =============================================================================
# TestHoneypotContext
# =============================================================================


class TestHoneypotContext:
    """Verify invocation context is captured in event detail."""

    def test_context_captured_in_detail(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger, do_query_events

        ctx = {"session_id": "test-session-123", "source": "mcp_tool_call"}
        do_honeypot_trigger(
            tool_name="security_disable_all_checks",
            invocation_context=ctx,
            db_path=db_path,
        )
        events = do_query_events(
            event_type="honeypot_triggered",
            db_path=db_path,
        )
        detail = json.loads(events["events"][0]["detail"])
        assert detail["invocation_context"] == ctx

    def test_empty_context_captured(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger, do_query_events

        do_honeypot_trigger(
            tool_name="system_prompt_dump",
            invocation_context={},
            db_path=db_path,
        )
        events = do_query_events(
            event_type="honeypot_triggered",
            db_path=db_path,
        )
        detail = json.loads(events["events"][0]["detail"])
        assert detail["invocation_context"] == {}


# =============================================================================
# TestHoneypotGenericFallback
# =============================================================================


class TestHoneypotGenericFallback:
    """Unknown tool_name returns generic {"status": "ok"}."""

    def test_unknown_tool_returns_generic_ok(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger

        result = do_honeypot_trigger(
            tool_name="some_unknown_honeypot",
            invocation_context={},
            db_path=db_path,
        )
        assert result == {"status": "ok"}

    def test_unknown_tool_still_logs_event(self, db_path):
        from spellbook_mcp.security.tools import do_honeypot_trigger, do_query_events

        do_honeypot_trigger(
            tool_name="some_unknown_honeypot",
            invocation_context={},
            db_path=db_path,
        )
        events = do_query_events(
            event_type="honeypot_triggered",
            db_path=db_path,
        )
        assert events["count"] == 1
        assert events["events"][0]["severity"] == "CRITICAL"
