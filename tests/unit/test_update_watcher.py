"""Tests for UpdateWatcher daemon thread."""

import threading
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call


class TestUpdateWatcherInit:
    """Tests for UpdateWatcher initialization."""

    def test_default_values(self, tmp_path):
        from spellbook_mcp.update_watcher import UpdateWatcher

        with patch("spellbook_mcp.update_watcher.config_get") as mock_cg:
            mock_cg.return_value = None
            watcher = UpdateWatcher(str(tmp_path))

        assert watcher.check_interval == 86400.0
        assert watcher.remote == "origin"
        # branch is None after init (lazy detection deferred to run())
        assert watcher.branch is None
        assert watcher._consecutive_failures == 0
        assert watcher.daemon is True

    def test_lazy_branch_detection(self, tmp_path):
        """Branch detection happens in run(), not __init__."""
        from spellbook_mcp.update_watcher import UpdateWatcher

        with patch("spellbook_mcp.update_watcher.config_get") as mock_cg:
            mock_cg.return_value = None
            watcher = UpdateWatcher(str(tmp_path))

        assert watcher.branch is None  # Not yet resolved

        with patch.object(watcher, "_detect_default_branch", return_value="main"), \
             patch.object(watcher, "_check_for_update"):
            watcher._running = True
            watcher._shutdown.set()  # Prevent periodic loop from blocking
            watcher.run()

        assert watcher.branch == "main"  # Now resolved

    def test_custom_values(self, tmp_path):
        from spellbook_mcp.update_watcher import UpdateWatcher

        with patch("spellbook_mcp.update_watcher.config_get") as mock_cg:
            mock_cg.side_effect = lambda key: {
                "auto_update_remote": "upstream",
                "auto_update_branch": "develop",
            }.get(key)

            watcher = UpdateWatcher(
                str(tmp_path),
                check_interval=3600.0,
            )

        assert watcher.check_interval == 3600.0
        assert watcher.remote == "upstream"
        assert watcher.branch == "develop"


class TestUpdateWatcherShutdown:
    """Tests for responsive shutdown."""

    def test_shutdown_responsive(self, tmp_path):
        """Event.wait() allows quick shutdown."""
        from spellbook_mcp.update_watcher import UpdateWatcher

        with patch("spellbook_mcp.update_watcher.config_get") as mock_cg:
            mock_cg.return_value = None
            with patch.object(UpdateWatcher, "_detect_default_branch", return_value="main"):
                watcher = UpdateWatcher(
                    str(tmp_path),
                    check_interval=3600.0,  # 1 hour
                )

        with patch.object(watcher, "_check_for_update"):
            watcher.start()
            time.sleep(0.1)  # Let it start
            watcher.stop()
            watcher.join(timeout=2.0)

        assert not watcher.is_alive()


class TestUpdateWatcherBackoff:
    """Tests for circuit breaker and backoff."""

    def test_backoff_calculation(self, tmp_path):
        from spellbook_mcp.update_watcher import UpdateWatcher

        with patch("spellbook_mcp.update_watcher.config_get") as mock_cg:
            mock_cg.return_value = None
            with patch.object(UpdateWatcher, "_detect_default_branch", return_value="main"):
                watcher = UpdateWatcher(str(tmp_path))

        # No failures: normal interval
        watcher._consecutive_failures = 0
        assert watcher._calculate_backoff() == watcher.check_interval

        # 1 failure: 1h
        watcher._consecutive_failures = 1
        assert watcher._calculate_backoff() == 3600.0

        # 2 failures: 2h
        watcher._consecutive_failures = 2
        assert watcher._calculate_backoff() == 7200.0

        # 3 failures: 4h
        watcher._consecutive_failures = 3
        assert watcher._calculate_backoff() == 14400.0

    def test_backoff_cap(self, tmp_path):
        """Backoff never exceeds 24h cap."""
        from spellbook_mcp.update_watcher import UpdateWatcher

        with patch("spellbook_mcp.update_watcher.config_get") as mock_cg:
            mock_cg.return_value = None
            with patch.object(UpdateWatcher, "_detect_default_branch", return_value="main"):
                watcher = UpdateWatcher(str(tmp_path))

        watcher._consecutive_failures = 100
        assert watcher._calculate_backoff() == 86400.0

    def test_failure_increments_failure_counter(self, tmp_path):
        """First check failure increments _consecutive_failures."""
        from spellbook_mcp.update_watcher import UpdateWatcher

        with patch("spellbook_mcp.update_watcher.config_get") as mock_cg:
            mock_cg.return_value = None
            with patch.object(UpdateWatcher, "_detect_default_branch", return_value="main"):
                watcher = UpdateWatcher(str(tmp_path))

        fail_count = {"n": 0}

        def mock_check():
            fail_count["n"] += 1
            raise RuntimeError("simulated failure")

        # Stop the watcher after the first check to prevent the HTTP loop
        def mock_check_and_stop():
            watcher._shutdown.set()
            mock_check()

        with patch.object(watcher, "_check_for_update", side_effect=mock_check_and_stop):
            watcher._running = True
            watcher.run()

        # First check fails, increments counter
        assert watcher._consecutive_failures == 1

    def test_circuit_breaker_http_backoff_values(self, tmp_path):
        """Simulate 5+ failures via _check_for_update and verify backoff values."""
        from spellbook_mcp.update_watcher import UpdateWatcher

        with patch("spellbook_mcp.update_watcher.config_get") as mock_cg:
            mock_cg.return_value = None
            with patch.object(UpdateWatcher, "_detect_default_branch", return_value="main"):
                watcher = UpdateWatcher(str(tmp_path))

        # Simulate consecutive failures and check backoff at each level
        expected_backoffs = [
            (0, watcher.check_interval),  # No failures: normal interval
            (1, 3600.0),                   # 1h
            (2, 7200.0),                   # 2h
            (3, 14400.0),                  # 4h
            (4, 28800.0),                  # 8h
            (5, 57600.0),                  # 16h
            (6, 86400.0),                  # 24h (capped)
            (10, 86400.0),                 # Still capped at 24h
        ]

        for failures, expected in expected_backoffs:
            watcher._consecutive_failures = failures
            assert watcher._calculate_backoff() == expected, \
                f"With {failures} failures, expected {expected}s backoff"
