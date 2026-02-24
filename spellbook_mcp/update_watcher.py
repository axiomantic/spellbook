"""Background watcher for spellbook update detection.

Follows the SessionWatcher pattern from spellbook_mcp/watcher.py:
daemon thread, Event.wait() for responsive shutdown, circuit breaker.

Checks at startup + configurable interval (long-lived HTTP daemon).
"""

import logging
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from spellbook_mcp.config_tools import config_get, config_set

logger = logging.getLogger(__name__)


class UpdateWatcher(threading.Thread):
    """Background thread that checks for spellbook updates.

    Detection is read-only: git fetch + git show to compare .version files.
    Application is delegated to update_tools.apply_update() which runs
    as a subprocess.
    """

    def __init__(
        self,
        spellbook_dir: str,
        check_interval: float = 86400.0,  # 24 hours
        remote: Optional[str] = None,
        branch: Optional[str] = None,
    ):
        """Initialize UpdateWatcher.

        Args:
            spellbook_dir: Path to the spellbook git repository
            check_interval: Seconds between periodic update checks
            remote: Git remote name (from config or default "origin")
            branch: Git branch name (from config or auto-detected)
        """
        super().__init__(daemon=True)
        self.spellbook_dir = Path(spellbook_dir)
        self.check_interval = check_interval
        self.remote = remote or config_get("auto_update_remote") or "origin"
        # Lazy evaluation: store branch from config/arg, defer network detection to run()
        # This prevents network I/O during server startup.
        self.branch = branch or config_get("auto_update_branch")
        self._running = False
        self._shutdown = threading.Event()

        # Backoff state
        self._consecutive_failures = 0
        self._max_failures = 5  # Circuit breaker threshold
        self._backoff_base = 3600.0  # 1 hour
        self._backoff_cap = 86400.0  # 24 hours
        self._last_check_time: float = 0.0

    def is_running(self) -> bool:
        """Check if watcher is currently running."""
        return self._running

    def start(self) -> threading.Thread:
        """Start the watcher thread."""
        self._running = True
        super().start()
        return self

    def stop(self):
        """Stop the watcher thread gracefully."""
        self._running = False
        self._shutdown.set()

    def run(self):
        """Main watcher loop.

        Checks at startup, then sleeps for check_interval between checks.
        Circuit breaker with exponential backoff on consecutive failures.
        """
        # Lazy branch detection: deferred from __init__ to avoid network I/O at startup
        self.branch = self.branch or self._detect_default_branch()

        # First check
        try:
            self._check_for_update()
            self._consecutive_failures = 0
            self._last_check_time = time.time()
        except Exception as e:
            self._consecutive_failures += 1
            config_set("update_check_failures", self._consecutive_failures)
            logger.warning(f"Update check failed ({self._consecutive_failures}): {e}")

        # Periodic checks
        while not self._shutdown.is_set():
            interval = self._calculate_backoff()
            self._shutdown.wait(interval)

            if self._shutdown.is_set():
                break

            try:
                self._check_for_update()
                self._consecutive_failures = 0
                self._last_check_time = time.time()
            except Exception as e:
                self._consecutive_failures += 1
                config_set("update_check_failures", self._consecutive_failures)
                logger.warning(
                    f"Update check failed ({self._consecutive_failures}/{self._max_failures}): {e}"
                )
                if self._consecutive_failures >= self._max_failures:
                    logger.error(
                        f"Circuit breaker tripped after {self._max_failures} consecutive failures. "
                        f"Will retry in {self._calculate_backoff()} seconds (half-open)."
                    )
                    # Half-open: wait for max backoff period, then try once more
                    self._shutdown.wait(self._calculate_backoff())
                    if self._shutdown.is_set():
                        break
                    # Reset for the half-open attempt
                    continue

    def _check_for_update(self):
        """Perform a single update check.

        Runs git fetch, reads remote .version, compares to local, and
        handles the result (auto-apply or store state).
        """
        # Runtime check: respect config changes after watcher has started
        if config_get("auto_update") is False:
            return  # Disabled at runtime

        from spellbook_mcp.update_tools import check_for_updates

        result = check_for_updates(self.spellbook_dir)

        if result.get("error"):
            raise RuntimeError(result["error"])

        # Store last check time
        config_set("last_update_check", datetime.now().isoformat())
        config_set("update_check_failures", 0)

        if not result.get("update_available"):
            return

        remote_version = result["remote_version"]
        is_major = result.get("is_major_bump", False)

        self._on_update_detected(remote_version, is_major)

    def _on_update_detected(self, remote_version: str, is_major: bool):
        """Handle a detected update.

        Major bumps are stored as pending (never auto-applied).
        Minor/patch bumps are auto-applied if auto_update is enabled
        and not paused.

        Args:
            remote_version: The available remote version
            is_major: True if this is a major version bump
        """
        from spellbook_mcp.update_tools import apply_update

        if is_major:
            config_set("pending_major_update", {
                "version": remote_version,
                "detected_at": datetime.now().isoformat(),
            })
            logger.info(f"Major update {remote_version} detected, requires confirmation")
            return

        auto_update = config_get("auto_update")
        auto_update_paused = config_get("auto_update_paused")

        if auto_update and not auto_update_paused:
            result = apply_update(self.spellbook_dir)
            if result["success"]:
                logger.info(f"Auto-updated to {result['new_version']}")
            else:
                logger.warning(f"Auto-update failed: {result['error']}")
        else:
            config_set("available_update", {
                "version": remote_version,
                "detected_at": datetime.now().isoformat(),
            })

    def _calculate_backoff(self) -> float:
        """Calculate next backoff interval.

        Returns normal check_interval when no failures. Uses exponential
        backoff (base * 2^(failures - 1)) capped at backoff_cap.

        Returns:
            Seconds to wait before next check
        """
        if self._consecutive_failures == 0:
            return self.check_interval

        backoff = self._backoff_base * (2 ** (self._consecutive_failures - 1))
        return min(backoff, self._backoff_cap)

    def _detect_default_branch(self) -> str:
        """Detect the default branch from the remote.

        Runs ``git remote show -n <remote>`` and parses the HEAD branch line.
        The ``-n`` flag avoids contacting the network (uses cached info).
        Caches result in config. Falls back to "main" on failure.

        Returns:
            Branch name string
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(self.spellbook_dir), "remote", "show", "-n", self.remote],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "HEAD branch:" in line:
                        branch = line.split(":")[-1].strip()
                        config_set("auto_update_branch", branch)
                        return branch
        except (subprocess.TimeoutExpired, OSError):
            pass

        return "main"
