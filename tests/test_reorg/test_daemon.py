"""Tests for spellbook.daemon module.

Verifies the daemon module interface contracts: manager, pid, and service.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest


class TestDaemonManagerImports:
    """Verify all manager functions are importable and callable."""

    def test_start_daemon_importable(self):
        from spellbook.daemon.manager import start_daemon
        assert callable(start_daemon)

    def test_stop_daemon_importable(self):
        from spellbook.daemon.manager import stop_daemon
        assert callable(stop_daemon)

    def test_restart_daemon_importable(self):
        from spellbook.daemon.manager import restart_daemon
        assert callable(restart_daemon)

    def test_daemon_status_importable(self):
        from spellbook.daemon.manager import daemon_status
        assert callable(daemon_status)

    def test_show_logs_importable(self):
        from spellbook.daemon.manager import show_logs
        assert callable(show_logs)

    def test_main_importable(self):
        from spellbook.daemon.manager import main
        assert callable(main)


class TestDaemonPidImports:
    """Verify all pid functions are importable and callable."""

    def test_read_pid_importable(self):
        from spellbook.daemon.pid import read_pid
        assert callable(read_pid)

    def test_write_pid_importable(self):
        from spellbook.daemon.pid import write_pid
        assert callable(write_pid)

    def test_remove_pid_importable(self):
        from spellbook.daemon.pid import remove_pid
        assert callable(remove_pid)

    def test_is_daemon_running_importable(self):
        from spellbook.daemon.pid import is_daemon_running
        assert callable(is_daemon_running)


class TestDaemonServiceImports:
    """Verify all service functions are importable and callable."""

    def test_generate_service_file_importable(self):
        from spellbook.daemon.service import generate_service_file
        assert callable(generate_service_file)

    def test_install_service_importable(self):
        from spellbook.daemon.service import install_service
        assert callable(install_service)

    def test_uninstall_service_importable(self):
        from spellbook.daemon.service import uninstall_service
        assert callable(uninstall_service)


class TestDaemonStatus:
    """Verify daemon_status() returns expected structure."""

    def test_daemon_status_returns_dict(self):
        from spellbook.daemon.manager import daemon_status
        # Mock out network/pid checks so we get a clean result
        with mock.patch("spellbook.daemon.manager.check_server_health", return_value=False), \
             mock.patch("spellbook.daemon.pid.read_pid", return_value=None), \
             mock.patch("spellbook.daemon.manager.is_service_installed", return_value=False), \
             mock.patch("spellbook.daemon.manager.is_service_running", return_value=False):
            result = daemon_status()

        assert isinstance(result, dict)
        assert "running" in result
        assert "pid" in result
        assert "port" in result
        assert "uptime" in result

    def test_daemon_status_running_is_bool(self):
        from spellbook.daemon.manager import daemon_status
        with mock.patch("spellbook.daemon.manager.check_server_health", return_value=False), \
             mock.patch("spellbook.daemon.pid.read_pid", return_value=None), \
             mock.patch("spellbook.daemon.manager.is_service_installed", return_value=False), \
             mock.patch("spellbook.daemon.manager.is_service_running", return_value=False):
            result = daemon_status()
        assert isinstance(result["running"], bool)

    def test_daemon_status_pid_none_when_not_running(self):
        from spellbook.daemon.manager import daemon_status
        with mock.patch("spellbook.daemon.manager.check_server_health", return_value=False), \
             mock.patch("spellbook.daemon.pid.read_pid", return_value=None), \
             mock.patch("spellbook.daemon.manager.is_service_installed", return_value=False), \
             mock.patch("spellbook.daemon.manager.is_service_running", return_value=False):
            result = daemon_status()
        assert result["pid"] is None


class TestPidOperations:
    """Verify PID file operations."""

    def test_read_pid_returns_none_when_no_file(self):
        from spellbook.daemon.pid import read_pid
        with mock.patch("spellbook.daemon.pid.get_pid_file") as mock_pf:
            mock_pf.return_value = Path("/tmp/nonexistent-spellbook-test.pid")
            result = read_pid()
        assert result is None

    def test_is_daemon_running_returns_bool(self):
        from spellbook.daemon.pid import is_daemon_running
        with mock.patch("spellbook.daemon.pid.read_pid", return_value=None):
            result = is_daemon_running()
        assert isinstance(result, bool)
        assert result is False

    def test_write_and_read_pid(self):
        from spellbook.daemon.pid import read_pid, write_pid, remove_pid
        with tempfile.NamedTemporaryFile(suffix=".pid", delete=False) as f:
            pid_path = Path(f.name)
        try:
            with mock.patch("spellbook.daemon.pid.get_pid_file", return_value=pid_path):
                # Write our own PID (guaranteed to exist)
                write_pid(os.getpid())
                result = read_pid()
                assert result == os.getpid()

                # Remove and verify gone
                remove_pid()
                assert not pid_path.exists()
        finally:
            pid_path.unlink(missing_ok=True)


class TestServiceGeneration:
    """Verify service file generation."""

    def test_generate_service_file_darwin(self):
        from spellbook.daemon.service import generate_service_file
        result = generate_service_file("darwin")
        assert isinstance(result, str)
        assert "spellbook" in result.lower()

    def test_generate_service_file_linux(self):
        from spellbook.daemon.service import generate_service_file
        result = generate_service_file("linux")
        assert isinstance(result, str)
        assert "spellbook" in result.lower()

    def test_generate_service_file_unsupported(self):
        from spellbook.daemon.service import generate_service_file
        with pytest.raises((ValueError, NotImplementedError)):
            generate_service_file("unsupported_platform")
