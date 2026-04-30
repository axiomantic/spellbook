"""Tests for UpdateWatcher daemon thread."""

import time
import bigfoot

from spellbook.updates.watcher import UpdateWatcher


class TestUpdateWatcherInit:
    """Tests for UpdateWatcher initialization."""

    def test_default_values(self, tmp_path):
        # auto_update_remote still lives in config; auto_update_branch moved to state.
        mock_cg = bigfoot.mock("spellbook.updates.watcher:config_get")
        mock_cg.returns(None)
        mock_gs = bigfoot.mock("spellbook.updates.watcher:get_state")
        mock_gs.returns(None)

        with bigfoot:
            watcher = UpdateWatcher(str(tmp_path))

        mock_cg.assert_call(args=("auto_update_remote",))
        mock_gs.assert_call(args=("auto_update_branch",))

        assert watcher.check_interval == 86400.0
        assert watcher.remote == "origin"
        # branch is None after init (lazy detection deferred to run())
        assert watcher.branch is None
        assert watcher._consecutive_failures == 0
        assert watcher.daemon is True

    def test_lazy_branch_detection(self, tmp_path):
        """Branch detection happens in run(), not __init__."""
        mock_cg = bigfoot.mock("spellbook.updates.watcher:config_get")
        mock_cg.returns(None)
        mock_gs = bigfoot.mock("spellbook.updates.watcher:get_state")
        mock_gs.returns(None)

        with bigfoot:
            watcher = UpdateWatcher(str(tmp_path))

        mock_cg.assert_call(args=("auto_update_remote",))
        mock_gs.assert_call(args=("auto_update_branch",))

        assert watcher.branch is None  # Not yet resolved

        mock_detect = bigfoot.mock.object(watcher, "_detect_default_branch")
        mock_detect.returns("main")
        mock_check = bigfoot.mock.object(watcher, "_check_for_update")
        mock_check.returns(None)

        with bigfoot:
            watcher._running = True
            watcher._shutdown.set()  # Prevent periodic loop from blocking
            watcher.run()

        mock_detect.assert_call()
        mock_check.assert_call()

        assert watcher.branch == "main"  # Now resolved

    def test_custom_values(self, tmp_path):
        mock_cg = bigfoot.mock("spellbook.updates.watcher:config_get")
        mock_cg.calls(lambda key: {"auto_update_remote": "upstream"}.get(key))
        mock_gs = bigfoot.mock("spellbook.updates.watcher:get_state")
        mock_gs.calls(lambda key: {"auto_update_branch": "develop"}.get(key))

        with bigfoot:
            watcher = UpdateWatcher(
                str(tmp_path),
                check_interval=3600.0,
            )

        mock_cg.assert_call(args=("auto_update_remote",))
        mock_gs.assert_call(args=("auto_update_branch",))

        assert watcher.check_interval == 3600.0
        assert watcher.remote == "upstream"
        assert watcher.branch == "develop"


class TestUpdateWatcherShutdown:
    """Tests for responsive shutdown."""

    def test_shutdown_responsive(self, tmp_path):
        """Event.wait() allows quick shutdown."""
        # Create watcher with explicit remote/branch to avoid config_get in __init__
        watcher = UpdateWatcher(
            str(tmp_path),
            check_interval=3600.0,  # 1 hour
            remote="origin",
            branch="main",
        )

        mock_check = bigfoot.mock.object(watcher, "_check_for_update")
        mock_check.returns(None)

        with bigfoot:
            watcher.start()
            time.sleep(0.1)  # Let it start
            watcher.stop()
            watcher.join(timeout=2.0)

        mock_check.assert_call()

        assert not watcher.is_alive()


class TestUpdateWatcherBackoff:
    """Tests for circuit breaker and backoff."""

    @staticmethod
    def _make_watcher(tmp_path):
        """Create a watcher bypassing config_get via explicit args."""
        return UpdateWatcher(
            str(tmp_path),
            remote="origin",
            branch="main",
        )

    def test_backoff_calculation(self, tmp_path):
        watcher = self._make_watcher(tmp_path)

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
        watcher = self._make_watcher(tmp_path)

        watcher._consecutive_failures = 100
        assert watcher._calculate_backoff() == 86400.0

    def test_failure_increments_failure_counter(self, tmp_path):
        """First check failure increments _consecutive_failures."""
        watcher = self._make_watcher(tmp_path)

        def mock_check_and_stop():
            watcher._shutdown.set()
            raise RuntimeError("simulated failure")

        mock_check = bigfoot.mock.object(watcher, "_check_for_update")
        mock_check.calls(mock_check_and_stop)
        mock_sset = bigfoot.mock("spellbook.updates.watcher:set_state")
        mock_sset.returns(None)

        with bigfoot:
            watcher._running = True
            watcher.run()

        mock_check.assert_call()
        mock_sset.assert_call(args=("update_check_failures", 1))
        bigfoot.log.assert_log(
            "WARNING",
            "Update check failed (1): simulated failure",
            "spellbook.updates.watcher",
        )

        # First check fails, increments counter
        assert watcher._consecutive_failures == 1

    def test_circuit_breaker_http_backoff_values(self, tmp_path):
        """Simulate 5+ failures via _check_for_update and verify backoff values."""
        watcher = self._make_watcher(tmp_path)

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
