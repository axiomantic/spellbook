"""Tests for installer/compat.py cross-platform compatibility layer.

Tests are organized by component (Tasks 0.1-0.7 of the Windows support plan).
Each test class covers one public function or class from compat.py.
"""

import errno
import json
import logging
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Task 0.1: Platform enum + get_platform()
# ---------------------------------------------------------------------------


class TestPlatformEnum:
    """Platform enum has the expected members."""

    def test_macos_value(self):
        from installer.compat import Platform

        assert Platform.MACOS.value == "macos"

    def test_linux_value(self):
        from installer.compat import Platform

        assert Platform.LINUX.value == "linux"

    def test_windows_value(self):
        from installer.compat import Platform

        assert Platform.WINDOWS.value == "windows"

    def test_enum_members_count(self):
        from installer.compat import Platform

        assert len(Platform) == 3


class TestGetPlatform:
    """get_platform() maps platform.system() to Platform enum."""

    def test_returns_platform_enum_instance(self):
        from installer.compat import Platform, get_platform

        result = get_platform()
        assert isinstance(result, Platform)

    @patch("installer.compat.platform.system", return_value="Darwin")
    def test_darwin_returns_macos(self, _mock):
        from installer.compat import Platform, get_platform

        assert get_platform() == Platform.MACOS

    @patch("installer.compat.platform.system", return_value="Linux")
    def test_linux_returns_linux(self, _mock):
        from installer.compat import Platform, get_platform

        assert get_platform() == Platform.LINUX

    @patch("installer.compat.platform.system", return_value="Windows")
    def test_windows_returns_windows(self, _mock):
        from installer.compat import Platform, get_platform

        assert get_platform() == Platform.WINDOWS

    @patch("installer.compat.platform.system", return_value="FreeBSD")
    def test_unsupported_raises_error(self, _mock):
        from installer.compat import UnsupportedPlatformError, get_platform

        with pytest.raises(UnsupportedPlatformError, match="(?i)freebsd"):
            get_platform()


class TestExceptions:
    """Custom exceptions exist and are proper subclasses."""

    def test_unsupported_platform_error_is_exception(self):
        from installer.compat import UnsupportedPlatformError

        assert issubclass(UnsupportedPlatformError, Exception)

    def test_lock_held_error_is_exception(self):
        from installer.compat import LockHeldError

        assert issubclass(LockHeldError, Exception)


# ---------------------------------------------------------------------------
# Task 0.2: LinkResult + create_link()
# ---------------------------------------------------------------------------


class TestLinkResult:
    """LinkResult dataclass has all required fields."""

    def test_construction(self, tmp_path):
        from installer.compat import LinkResult

        result = LinkResult(
            source=tmp_path / "src",
            target=tmp_path / "tgt",
            success=True,
            action="created",
            link_mode="symlink",
            message="ok",
        )
        assert result.source == tmp_path / "src"
        assert result.target == tmp_path / "tgt"
        assert result.success is True
        assert result.action == "created"
        assert result.link_mode == "symlink"
        assert result.message == "ok"


class TestCreateLink:
    """create_link() creates links with proper fallback behaviour."""

    def test_source_not_exist_returns_failure(self, tmp_path):
        from installer.compat import create_link

        result = create_link(tmp_path / "nonexistent", tmp_path / "link")
        assert not result.success
        assert result.action == "failed"
        assert result.link_mode == "none"
        assert "does not exist" in result.message.lower()

    def test_dry_run_new_target(self, tmp_path):
        from installer.compat import create_link

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "link"

        result = create_link(source, target, dry_run=True)
        assert result.success
        assert result.action == "created"
        assert not target.exists()  # Nothing actually created

    def test_dry_run_existing_target(self, tmp_path):
        from installer.compat import create_link

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "link"
        target.symlink_to(source)

        result = create_link(source, target, dry_run=True)
        assert result.success
        assert result.action == "updated"

    def test_creates_symlink_for_directory(self, tmp_path):
        from installer.compat import create_link

        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("hello")
        target = tmp_path / "link"

        result = create_link(source, target)
        assert result.success
        assert result.link_mode == "symlink"
        assert result.action == "created"
        assert target.is_symlink()
        assert (target / "file.txt").read_text() == "hello"

    def test_creates_symlink_for_file(self, tmp_path):
        from installer.compat import create_link

        source = tmp_path / "source.txt"
        source.write_text("content")
        target = tmp_path / "link.txt"

        result = create_link(source, target)
        assert result.success
        assert result.link_mode == "symlink"
        assert target.is_symlink()
        assert target.read_text() == "content"

    def test_updates_existing_symlink(self, tmp_path):
        from installer.compat import create_link

        source1 = tmp_path / "source1"
        source1.mkdir()
        source2 = tmp_path / "source2"
        source2.mkdir()
        target = tmp_path / "link"
        target.symlink_to(source1)

        result = create_link(source2, target)
        assert result.success
        assert result.action == "updated"
        assert target.resolve() == source2.resolve()

    def test_creates_parent_directories(self, tmp_path):
        from installer.compat import create_link

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "deep" / "nested" / "link"

        result = create_link(source, target)
        assert result.success
        assert target.is_symlink()

    def test_non_empty_dir_target_fails(self, tmp_path):
        from installer.compat import create_link

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "link"
        target.mkdir()
        (target / "blocker.txt").write_text("blocking")

        result = create_link(source, target)
        assert not result.success
        assert result.action == "failed"
        assert "non-empty" in result.message.lower()

    def test_empty_dir_target_with_remove_flag(self, tmp_path):
        from installer.compat import create_link

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "link"
        target.mkdir()  # empty dir

        result = create_link(source, target, remove_empty_dirs=True)
        assert result.success
        assert result.action == "updated"
        assert target.is_symlink()

    def test_empty_dir_target_without_remove_flag_fails(self, tmp_path):
        from installer.compat import create_link

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "link"
        target.mkdir()  # empty dir

        result = create_link(source, target, remove_empty_dirs=False)
        assert not result.success
        assert result.action == "failed"

    def test_replaces_existing_file_target(self, tmp_path):
        from installer.compat import create_link

        source = tmp_path / "source.txt"
        source.write_text("new content")
        target = tmp_path / "link.txt"
        target.write_text("old content")

        result = create_link(source, target)
        assert result.success
        assert result.action == "updated"
        assert target.is_symlink()


class TestCreateLinkWindowsFallback:
    """create_link() Windows fallback chain: symlink -> junction -> copy."""

    @patch("installer.compat.get_platform")
    @patch("installer.compat.is_junction", return_value=False)
    def test_copy_fallback_for_files(self, _mock_junction, mock_plat, tmp_path):
        from installer.compat import Platform, create_link

        mock_plat.return_value = Platform.WINDOWS
        source = tmp_path / "source.txt"
        source.write_text("content")
        target = tmp_path / "link.txt"

        with patch.object(Path, "symlink_to", side_effect=OSError(errno.EPERM, "Not permitted")):
            result = create_link(source, target)

        assert result.success
        assert result.link_mode == "copy"
        assert target.read_text() == "content"

    @patch("installer.compat.get_platform")
    @patch("installer.compat.is_junction", return_value=False)
    def test_copy_fallback_for_directories(self, _mock_junction, mock_plat, tmp_path):
        from installer.compat import Platform, create_link

        mock_plat.return_value = Platform.WINDOWS
        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("hello")
        target = tmp_path / "link"

        with patch.object(Path, "symlink_to", side_effect=OSError(errno.EPERM, "Not permitted")):
            with patch("installer.compat._create_junction", return_value=False):
                result = create_link(source, target)

        assert result.success
        assert result.link_mode == "copy"
        assert (target / "file.txt").read_text() == "hello"

    @patch("installer.compat.get_platform")
    @patch("installer.compat.is_junction", return_value=False)
    def test_junction_fallback_for_directories(self, _mock_junction, mock_plat, tmp_path):
        from installer.compat import Platform, create_link

        mock_plat.return_value = Platform.WINDOWS
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "link"

        with patch.object(Path, "symlink_to", side_effect=OSError(errno.EPERM, "Not permitted")):
            with patch("installer.compat._create_junction", return_value=True):
                result = create_link(source, target)

        assert result.success
        assert result.link_mode == "junction"

    @patch("installer.compat.get_platform")
    def test_unix_symlink_failure_is_not_caught(self, mock_plat, tmp_path):
        """On Unix, symlink OSError is re-raised (no fallback chain)."""
        from installer.compat import Platform, create_link

        mock_plat.return_value = Platform.LINUX
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "link"

        with patch.object(Path, "symlink_to", side_effect=OSError(errno.EIO, "IO error")):
            result = create_link(source, target)

        # On Unix, non-EPERM errors propagate and get caught by outer handler
        assert not result.success
        assert result.action == "failed"

    @patch("installer.compat.get_platform")
    @patch("installer.compat.is_junction", return_value=False)
    def test_copy_mode_message_mentions_re_run(self, _mock_junction, mock_plat, tmp_path):
        """Copy mode result message should warn about re-running installer."""
        from installer.compat import Platform, create_link

        mock_plat.return_value = Platform.WINDOWS
        source = tmp_path / "source.txt"
        source.write_text("content")
        target = tmp_path / "link.txt"

        with patch.object(Path, "symlink_to", side_effect=OSError(errno.EPERM, "Not permitted")):
            result = create_link(source, target)

        assert "re-running" in result.message.lower() or "re-running" in result.message


# ---------------------------------------------------------------------------
# Task 0.3: remove_link(), is_junction(), normalize_path_for_comparison()
# ---------------------------------------------------------------------------


class TestRemoveLink:
    """remove_link() handles all link types created by create_link()."""

    def test_removes_symlink(self, tmp_path):
        from installer.compat import remove_link

        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "link"
        target.symlink_to(source)

        assert remove_link(target) is True
        assert not target.exists()
        assert not target.is_symlink()

    def test_removes_regular_file(self, tmp_path):
        from installer.compat import remove_link

        target = tmp_path / "file.txt"
        target.write_text("hello")

        assert remove_link(target) is True
        assert not target.exists()

    def test_removes_directory(self, tmp_path):
        from installer.compat import remove_link

        target = tmp_path / "dir"
        target.mkdir()
        (target / "file.txt").write_text("nested")

        assert remove_link(target) is True
        assert not target.exists()

    def test_nonexistent_returns_false(self, tmp_path):
        from installer.compat import remove_link

        assert remove_link(tmp_path / "nonexistent") is False


class TestIsJunction:
    """is_junction() detects Windows junction points."""

    def test_returns_false_on_non_windows(self, tmp_path):
        """On macOS/Linux, junctions don't exist so always False."""
        from installer.compat import is_junction

        assert is_junction(tmp_path) is False

    def test_returns_false_for_regular_file(self, tmp_path):
        from installer.compat import is_junction

        f = tmp_path / "file.txt"
        f.write_text("hello")
        assert is_junction(f) is False

    def test_returns_false_for_symlink(self, tmp_path):
        from installer.compat import is_junction

        source = tmp_path / "source"
        source.mkdir()
        link = tmp_path / "link"
        link.symlink_to(source)
        assert is_junction(link) is False


class TestNormalizePathForComparison:
    """normalize_path_for_comparison() resolves paths for cross-platform comparison."""

    def test_returns_resolved_path_string(self, tmp_path):
        from installer.compat import normalize_path_for_comparison

        result = normalize_path_for_comparison(tmp_path)
        assert result == str(tmp_path.resolve())

    def test_returns_string_type(self, tmp_path):
        from installer.compat import normalize_path_for_comparison

        result = normalize_path_for_comparison(tmp_path)
        assert isinstance(result, str)

    @patch("installer.compat.get_platform")
    def test_windows_casefolds(self, mock_plat, tmp_path):
        from installer.compat import Platform, normalize_path_for_comparison

        mock_plat.return_value = Platform.WINDOWS
        result = normalize_path_for_comparison(tmp_path)
        # On Windows normalization, result should be case-folded
        assert result == result.casefold()

    @patch("installer.compat.get_platform")
    def test_windows_uses_forward_slashes(self, mock_plat, tmp_path):
        from installer.compat import Platform, normalize_path_for_comparison

        mock_plat.return_value = Platform.WINDOWS
        result = normalize_path_for_comparison(tmp_path)
        assert "\\" not in result


# ---------------------------------------------------------------------------
# Task 0.4: CrossPlatformLock
# ---------------------------------------------------------------------------


class TestCrossPlatformLock:
    """CrossPlatformLock provides cross-platform file locking."""

    def test_acquire_returns_true(self, tmp_path):
        from installer.compat import CrossPlatformLock

        lock = CrossPlatformLock(tmp_path / "test.lock")
        assert lock.acquire() is True
        lock.release()

    def test_release_cleans_up(self, tmp_path):
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "test.lock"
        lock = CrossPlatformLock(lock_path)
        lock.acquire()
        lock.release()
        assert lock._fd is None

    def test_context_manager_acquires_and_releases(self, tmp_path):
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "test.lock"
        with CrossPlatformLock(lock_path) as lock:
            assert lock._fd is not None
        assert lock._fd is None

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows file locking prevents concurrent lock fd access")
    def test_context_manager_raises_on_held_lock(self, tmp_path):
        """Context manager raises LockHeldError when lock cannot be acquired."""
        from installer.compat import CrossPlatformLock, LockHeldError

        lock_path = tmp_path / "test.lock"
        lock1 = CrossPlatformLock(lock_path)
        assert lock1.acquire()

        try:
            # Mock acquire to return False, simulating a held lock
            lock2 = CrossPlatformLock(lock_path)
            with patch.object(lock2, "acquire", return_value=False):
                with pytest.raises(LockHeldError):
                    with lock2:
                        pass  # Should not reach here
        finally:
            lock1.release()

    def test_lock_writes_pid_info(self, tmp_path):
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "test.lock"
        lock = CrossPlatformLock(lock_path)
        lock.acquire()

        # Read the lock file to verify PID is written
        with open(lock_path) as f:
            data = json.loads(f.read())
        assert data["pid"] == os.getpid()
        assert "timestamp" in data

        lock.release()

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows file locking prevents stale lock recovery without OS-level lock")
    def test_stale_lock_with_dead_pid(self, tmp_path):
        """Lock with a dead PID and old timestamp should be acquirable."""
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "test.lock"
        # Write fake lock data with very unlikely PID
        lock_path.write_text(json.dumps({
            "pid": 2147483647,
            "timestamp": 0,
        }))

        lock = CrossPlatformLock(lock_path, stale_seconds=0)
        assert lock.acquire() is True
        lock.release()

    def test_shared_lock_parameter_accepted(self, tmp_path):
        """shared parameter should be accepted (degrades to exclusive on Windows)."""
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "test.lock"
        lock = CrossPlatformLock(lock_path, shared=True)
        assert lock.acquire() is True
        lock.release()

    def test_creates_parent_directory(self, tmp_path):
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "deep" / "nested" / "test.lock"
        lock = CrossPlatformLock(lock_path)
        assert lock.acquire() is True
        lock.release()

    def test_shared_lock_windows_logs_debug(self, tmp_path, caplog):
        """On Windows, shared=True should log a debug message about degradation."""
        from installer.compat import CrossPlatformLock

        mock_msvcrt = MagicMock()
        mock_msvcrt.LK_NBLCK = 2
        mock_msvcrt.LK_LOCK = 1
        mock_msvcrt.LK_UNLCK = 0

        with patch("installer.compat.sys") as mock_sys, \
             patch.dict("sys.modules", {"msvcrt": mock_msvcrt}):
            mock_sys.platform = "win32"
            mock_sys.executable = sys.executable

            lock = CrossPlatformLock(tmp_path / "test.lock", shared=True)
            assert lock.shared is True

            with caplog.at_level(logging.DEBUG, logger="installer.compat"):
                lock.acquire()

            lock.release()

        assert any("shared lock degrades" in r.message.lower() for r in caplog.records)

    def test_blocking_true_acquires_available_lock(self, tmp_path):
        """blocking=True should acquire an available lock successfully."""
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "test.lock"
        lock = CrossPlatformLock(lock_path, blocking=True)
        assert lock.acquire() is True
        assert lock._fd is not None
        lock.release()

    @pytest.mark.skipif(sys.platform == "win32", reason="fcntl not available on Windows")
    def test_blocking_true_uses_blocking_os_call(self, tmp_path):
        """blocking=True should use the blocking variant of the OS lock call."""
        import fcntl as real_fcntl
        from installer.compat import CrossPlatformLock

        lock_path = tmp_path / "test.lock"
        lock = CrossPlatformLock(lock_path, blocking=True)

        flock_calls = []
        original_flock = real_fcntl.flock

        def tracking_flock(fd, flag):
            flock_calls.append(flag)
            return original_flock(fd, flag)

        with patch.object(real_fcntl, "flock", side_effect=tracking_flock):
            lock.acquire()

        # Verify flock was called WITHOUT LOCK_NB (blocking mode)
        assert len(flock_calls) >= 1
        assert flock_calls[0] == real_fcntl.LOCK_EX  # No LOCK_NB bit
        lock.release()


# ---------------------------------------------------------------------------
# Task 0.5: ServiceManager
# ---------------------------------------------------------------------------


class TestServiceManager:
    """ServiceManager provides cross-platform daemon management."""

    def test_construction(self, tmp_path):
        from installer.compat import ServiceManager

        mgr = ServiceManager(tmp_path, 8765, "127.0.0.1")
        assert mgr.spellbook_dir == tmp_path
        assert mgr.port == 8765
        assert mgr.host == "127.0.0.1"

    def test_has_required_methods(self, tmp_path):
        from installer.compat import ServiceManager

        mgr = ServiceManager(tmp_path, 8765, "127.0.0.1")
        assert callable(mgr.install)
        assert callable(mgr.uninstall)
        assert callable(mgr.start)
        assert callable(mgr.stop)
        assert callable(mgr.is_installed)
        assert callable(mgr.is_running)

    def test_class_constants(self):
        from installer.compat import ServiceManager

        assert ServiceManager.LAUNCHD_LABEL == "com.spellbook.mcp"
        assert ServiceManager.SERVICE_NAME == "spellbook-mcp"

    @patch("installer.compat.get_platform")
    def test_is_installed_macos_checks_plist(self, mock_plat, tmp_path):
        from installer.compat import Platform, ServiceManager

        mock_plat.return_value = Platform.MACOS
        mgr = ServiceManager(tmp_path, 8765, "127.0.0.1")
        # Plist doesn't exist, so should be False
        assert mgr.is_installed() is False

    @patch("installer.compat.get_platform")
    def test_is_installed_linux_checks_service_file(self, mock_plat, tmp_path):
        from installer.compat import Platform, ServiceManager

        mock_plat.return_value = Platform.LINUX
        mgr = ServiceManager(tmp_path, 8765, "127.0.0.1")
        assert mgr.is_installed() is False

    def test_is_running_checks_port(self, tmp_path):
        """is_running() should try to connect to host:port."""
        from installer.compat import ServiceManager

        mgr = ServiceManager(tmp_path, 9, "192.0.2.1")  # non-routable IP
        # Port 9 on a non-routable IP should not be running
        assert mgr.is_running() is False

    @patch("installer.compat.get_platform")
    def test_generate_task_xml_format(self, mock_plat, tmp_path):
        """Windows task XML should contain required elements."""
        from installer.compat import Platform, ServiceManager

        mock_plat.return_value = Platform.WINDOWS
        mgr = ServiceManager(tmp_path, 8765, "127.0.0.1")
        xml = mgr._generate_task_xml()
        assert "LogonTrigger" in xml
        assert "spellbook-watchdog.py" in xml
        assert str(tmp_path) in xml

    @patch("installer.compat.get_platform")
    def test_launchd_plist_path(self, mock_plat, tmp_path):
        from installer.compat import Platform, ServiceManager

        mock_plat.return_value = Platform.MACOS
        mgr = ServiceManager(tmp_path, 8765, "127.0.0.1")
        plist_path = mgr._launchd_plist_path()
        assert "LaunchAgents" in str(plist_path)
        assert "com.spellbook.mcp.plist" in str(plist_path)

    @patch("installer.compat.get_platform")
    def test_systemd_service_path(self, mock_plat, tmp_path):
        from installer.compat import Platform, ServiceManager

        mock_plat.return_value = Platform.LINUX
        mgr = ServiceManager(tmp_path, 8765, "127.0.0.1")
        service_path = mgr._systemd_service_path()
        assert "systemd" in str(service_path)
        assert "spellbook-mcp.service" in str(service_path)


# ---------------------------------------------------------------------------
# Task 0.6: Utility functions
# ---------------------------------------------------------------------------


class TestGetPythonExecutable:
    """get_python_executable() returns the current Python interpreter."""

    def test_returns_sys_executable(self):
        from installer.compat import get_python_executable

        assert get_python_executable() == sys.executable

    def test_returns_string(self):
        from installer.compat import get_python_executable

        assert isinstance(get_python_executable(), str)


class TestGetConfigDir:
    """get_config_dir() returns OS-appropriate config directory."""

    def test_default_app_name(self):
        from installer.compat import get_config_dir

        result = get_config_dir()
        assert "spellbook" in str(result)

    def test_custom_app_name(self):
        from installer.compat import get_config_dir

        result = get_config_dir("myapp")
        assert "myapp" in str(result)

    def test_returns_path_object(self):
        from installer.compat import get_config_dir

        assert isinstance(get_config_dir(), Path)

    @patch("installer.compat.get_platform")
    def test_unix_uses_dot_config(self, mock_plat):
        from installer.compat import Platform, get_config_dir

        mock_plat.return_value = Platform.LINUX
        result = get_config_dir()
        assert ".config" in str(result)

    @patch("installer.compat.get_platform")
    @patch.dict(os.environ, {"APPDATA": "/fake/appdata"})
    def test_windows_uses_appdata(self, mock_plat):
        from installer.compat import Platform, get_config_dir

        mock_plat.return_value = Platform.WINDOWS
        result = get_config_dir()
        assert "appdata" in str(result).lower()


# ---------------------------------------------------------------------------
# Task 0.7 supplement: _pid_exists()
# ---------------------------------------------------------------------------


class TestPidExists:
    """_pid_exists() checks if a process is alive."""

    def test_current_process_exists(self):
        from installer.compat import _pid_exists

        assert _pid_exists(os.getpid()) is True

    def test_dead_pid_does_not_exist(self):
        from installer.compat import _pid_exists

        # PID 2147483647 is very unlikely to exist
        assert _pid_exists(2147483647) is False

    def test_init_process_exists(self):
        """PID 1 (init/launchd) should always exist on Unix."""
        from installer.compat import _pid_exists

        if sys.platform != "win32":
            assert _pid_exists(1) is True


# ---------------------------------------------------------------------------
# Task 0.3 supplement: _create_junction
# ---------------------------------------------------------------------------


class TestCreateJunction:
    """_create_junction() only operates on Windows."""

    def test_returns_false_on_non_windows(self, tmp_path):
        from installer.compat import _create_junction

        with patch("installer.compat.sys") as mock_sys:
            mock_sys.platform = "linux"
            result = _create_junction(tmp_path / "src", tmp_path / "tgt")
        assert result is False


# ---------------------------------------------------------------------------
# Integration: round-trip create + remove
# ---------------------------------------------------------------------------


class TestCreateRemoveRoundTrip:
    """create_link followed by remove_link should leave no artifacts."""

    def test_symlink_round_trip(self, tmp_path):
        from installer.compat import create_link, remove_link

        source = tmp_path / "source"
        source.mkdir()
        (source / "file.txt").write_text("hello")
        target = tmp_path / "link"

        create_result = create_link(source, target)
        assert create_result.success
        assert target.is_symlink()

        remove_result = remove_link(target)
        assert remove_result is True
        assert not target.exists()
        assert not target.is_symlink()
        # Source should be untouched
        assert source.exists()
        assert (source / "file.txt").read_text() == "hello"
