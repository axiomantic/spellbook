"""Tests for spellbook.mcp.state module.

Verifies that shared MCP server state variables are importable and have
the expected types and default values.
"""

import pytest


class TestMcpStateImports:
    """Test that spellbook.mcp.state is importable with expected exports."""

    def test_server_start_time_exists_and_is_float(self):
        from spellbook.mcp.state import server_start_time

        assert isinstance(server_start_time, float)

    def test_first_health_check_done_exists(self):
        from spellbook.mcp.state import first_health_check_done

        assert isinstance(first_health_check_done, bool)
        assert first_health_check_done is False

    def test_last_full_health_check_time_exists(self):
        from spellbook.mcp.state import last_full_health_check_time

        assert isinstance(last_full_health_check_time, float)
        assert last_full_health_check_time == 0.0

    def test_full_health_check_interval_seconds_exists(self):
        from spellbook.mcp.state import FULL_HEALTH_CHECK_INTERVAL_SECONDS

        assert isinstance(FULL_HEALTH_CHECK_INTERVAL_SECONDS, float)
        assert FULL_HEALTH_CHECK_INTERVAL_SECONDS == 300.0

    def test_watcher_slot_exists_and_is_none(self):
        from spellbook.mcp.state import watcher

        assert watcher is None

    def test_update_watcher_slot_exists_and_is_none(self):
        from spellbook.mcp.state import update_watcher

        assert update_watcher is None
