"""Cross-platform compatibility layer for spellbook.

All OS-specific logic converges into this single module. Callers ask for
capabilities ("create a link", "acquire a lock", "get config directory")
and this module handles the OS-specific implementation.

No external dependencies beyond the Python standard library.
"""

import errno
import json
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task 0.1: Platform enum + get_platform()
# ---------------------------------------------------------------------------


class Platform(Enum):
    """Supported operating systems."""

    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"


class UnsupportedPlatformError(Exception):
    """Raised when running on an unsupported OS."""

    pass


class LockHeldError(Exception):
    """Raised when a lock cannot be acquired because another process holds it."""

    pass


def get_platform() -> Platform:
    """Return the current OS as a Platform enum.

    Returns:
        Platform enum value for the current OS.

    Raises:
        UnsupportedPlatformError: If the OS is not macOS, Linux, or Windows.
    """
    system = platform.system().lower()
    if system == "darwin":
        return Platform.MACOS
    elif system == "linux":
        return Platform.LINUX
    elif system == "windows":
        return Platform.WINDOWS
    raise UnsupportedPlatformError(f"Unsupported OS: {system}")


# ---------------------------------------------------------------------------
# Task 0.2: LinkResult + create_link()
# ---------------------------------------------------------------------------


@dataclass
class LinkResult:
    """Result of a link creation operation."""

    source: Path
    target: Path
    success: bool
    action: str  # "created", "updated", "failed"
    link_mode: str  # "symlink", "junction", "copy", "none"
    message: str


def _create_junction(source: Path, target: Path) -> bool:
    """Create a Windows NTFS junction.

    Args:
        source: The directory the junction points TO (the actual content).
        target: WHERE the junction is created (the link location).

    Note: Parameter order matches create_link() convention.
        _winapi.CreateJunction(junction_path, target_path) creates a
        junction AT junction_path POINTING TO target_path.

    Tries _winapi.CreateJunction first, falls back to mklink /J.
    Always returns False on non-Windows platforms.
    """
    if sys.platform != "win32":
        return False
    try:
        import _winapi

        _winapi.CreateJunction(str(target), str(source))
        return True
    except (OSError, AttributeError):
        try:
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(target), str(source)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False


def _is_dir_empty(path: Path) -> bool:
    """Check if a directory is empty."""
    try:
        return not any(path.iterdir())
    except (OSError, PermissionError):
        return False


# ---------------------------------------------------------------------------
# Task 0.3: is_junction(), remove_link(), normalize_path_for_comparison()
# ---------------------------------------------------------------------------


def is_junction(path: Path) -> bool:
    """Check if path is a Windows junction point.

    Returns False on non-Windows platforms. On Windows, uses
    GetFileAttributesW to check the reparse point attribute.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs == -1:
            return False
        return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT) and not path.is_symlink()
    except (OSError, AttributeError):
        return False


def remove_link(target: Path) -> bool:
    """Remove a symlink, junction, or copied directory/file.

    Handles all link types created by create_link():
    - Symlinks: unlink()
    - Junctions: os.rmdir() (junctions are removed with rmdir)
    - Copied dirs: shutil.rmtree()
    - Copied files: unlink()

    Returns:
        True if removed, False if target did not exist or removal failed.
    """
    try:
        if target.is_symlink():
            target.unlink()
            return True
        elif is_junction(target):
            os.rmdir(str(target))
            return True
        elif target.is_dir():
            shutil.rmtree(str(target))
            return True
        elif target.is_file():
            target.unlink()
            return True
        return False
    except OSError:
        return False


def normalize_path_for_comparison(path: Path) -> str:
    """Normalize a path for cross-platform string comparison.

    On Windows: case-folded, forward slashes.
    On Unix: resolved path as-is.

    Args:
        path: Path to normalize.

    Returns:
        Normalized path string suitable for comparison.
    """
    result = str(path.resolve())
    if get_platform() == Platform.WINDOWS:
        return result.casefold().replace("\\", "/")
    return result


# ---------------------------------------------------------------------------
# Task 0.2 continued: create_link()
# ---------------------------------------------------------------------------


def create_link(
    source: Path,
    target: Path,
    dry_run: bool = False,
    remove_empty_dirs: bool = False,
) -> LinkResult:
    """Create a link from target pointing to source.

    On macOS/Linux: always uses os.symlink().
    On Windows: tries symlink -> junction (dirs only) -> copy.

    Args:
        source: The actual file/directory to link to.
        target: Where the link will be created.
        dry_run: If True, don't actually create the link.
        remove_empty_dirs: If True, remove empty directories blocking link creation.

    Returns:
        LinkResult with status, link_mode, and message.
    """
    if not source.exists():
        return LinkResult(
            source=source,
            target=target,
            success=False,
            action="failed",
            link_mode="none",
            message=f"Source does not exist: {source}",
        )

    if dry_run:
        action = "updated" if (target.exists() or target.is_symlink()) else "created"
        return LinkResult(
            source=source,
            target=target,
            success=True,
            action=action,
            link_mode="symlink",
            message=f"Would {action} link: {target.name}",
        )

    try:
        # Ensure parent directory exists
        target.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing (file, dir, or symlink)
        action = "created"
        if target.is_symlink() or is_junction(target) or target.exists():
            if target.is_dir() and not target.is_symlink() and not is_junction(target):
                if remove_empty_dirs and _is_dir_empty(target):
                    target.rmdir()
                    action = "updated"
                else:
                    return LinkResult(
                        source=source,
                        target=target,
                        success=False,
                        action="failed",
                        link_mode="none",
                        message=f"Target is a non-empty directory: {target}. Remove it manually.",
                    )
            else:
                remove_link(target)
                action = "updated"

        # Attempt symlink first (all platforms)
        try:
            target.symlink_to(source)
            return LinkResult(
                source=source,
                target=target,
                success=True,
                action=action,
                link_mode="symlink",
                message=f"{action.capitalize()} symlink: {target.name}",
            )
        except OSError as e:
            if get_platform() != Platform.WINDOWS:
                raise  # On Unix, symlink failure is fatal
            if e.errno not in (errno.EPERM, errno.EACCES, 1314):
                raise

        # Windows fallback: junction (directories only)
        if source.is_dir() and _create_junction(source, target):
            return LinkResult(
                source=source,
                target=target,
                success=True,
                action=action,
                link_mode="junction",
                message=f"{action.capitalize()} junction: {target.name}",
            )

        # Windows fallback: copy
        if source.is_dir():
            shutil.copytree(str(source), str(target), dirs_exist_ok=True)
        else:
            shutil.copy2(str(source), str(target))
        return LinkResult(
            source=source,
            target=target,
            success=True,
            action=action,
            link_mode="copy",
            message=(
                f"{action.capitalize()} copy: {target.name}. "
                "Symlinks unavailable; changes require re-running installer."
            ),
        )

    except OSError as e:
        return LinkResult(
            source=source,
            target=target,
            success=False,
            action="failed",
            link_mode="none",
            message=f"Failed to create link: {e}",
        )


# ---------------------------------------------------------------------------
# Task 0.4: CrossPlatformLock
# ---------------------------------------------------------------------------


def _pid_exists(pid: int) -> bool:
    """Check if a process with given PID exists.

    Uses os.kill(pid, 0) on Unix, OpenProcess on Windows.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except (OSError, AttributeError):
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            # Process exists but we lack permission to signal it
            return True
        except OSError:
            return False


class CrossPlatformLock:
    """Cross-platform file locking with stale lock detection.

    Uses fcntl.flock() on Unix, msvcrt.locking() on Windows.
    Supports context manager protocol.

    Args:
        lock_path: Path to the lock file.
        stale_seconds: Seconds after which a lock is considered stale.
        shared: If True, acquire a shared (read) lock. Only effective on Unix.
        blocking: If True, context manager retries until lock is acquired or
            timeout is reached. If False, raises LockHeldError immediately.
        timeout: Maximum seconds to wait when blocking (default 10.0).
    """

    def __init__(
        self,
        lock_path: Path,
        stale_seconds: int = 3600,
        shared: bool = False,
        blocking: bool = False,
        timeout: float = 10.0,
    ):
        self.lock_path = lock_path
        self.stale_seconds = stale_seconds
        self.shared = shared
        self.blocking = blocking
        self.timeout = timeout
        self._fd: Optional[int] = None

    def acquire(self) -> bool:
        """Acquire the lock.

        In blocking mode, waits until the lock becomes available (up to
        self.timeout seconds). In non-blocking mode, returns immediately.

        Returns:
            True on success, False if lock is held by another live process.
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)

        try:
            if sys.platform == "win32":
                import msvcrt

                # Note: msvcrt does not support shared locks.
                # On Windows, shared=True degrades to exclusive lock.
                if self.shared:
                    logger.debug(
                        "Windows: shared lock degrades to exclusive (msvcrt limitation)"
                    )
                if self.blocking:
                    # msvcrt.LK_LOCK blocks until available
                    msvcrt.locking(self._fd, msvcrt.LK_LOCK, 1)
                else:
                    msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                flag = fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX
                if not self.blocking:
                    flag |= fcntl.LOCK_NB
                fcntl.flock(self._fd, flag)
        except (BlockingIOError, OSError):
            # Lock held - check if stale (only in non-blocking mode)
            try:
                os.lseek(self._fd, 0, os.SEEK_SET)
                content = os.read(self._fd, 1024).decode()
                lock_info = json.loads(content)
                pid = lock_info.get("pid")
                timestamp = lock_info.get("timestamp", 0)

                is_stale = False
                if pid and not _pid_exists(pid):
                    is_stale = True
                elif time.time() - timestamp > self.stale_seconds:
                    is_stale = True

                if is_stale:
                    # Try to acquire again (stale lock)
                    try:
                        if sys.platform == "win32":
                            import msvcrt

                            msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl

                            flag = fcntl.LOCK_SH if self.shared else fcntl.LOCK_EX
                            fcntl.flock(self._fd, flag | fcntl.LOCK_NB)
                    except (BlockingIOError, OSError):
                        os.close(self._fd)
                        self._fd = None
                        return False
                else:
                    os.close(self._fd)
                    self._fd = None
                    return False
            except (json.JSONDecodeError, OSError):
                os.close(self._fd)
                self._fd = None
                return False

        # Write our lock info
        os.ftruncate(self._fd, 0)
        os.lseek(self._fd, 0, os.SEEK_SET)
        lock_data = json.dumps({"pid": os.getpid(), "timestamp": time.time()})
        os.write(self._fd, lock_data.encode())
        return True

    def release(self) -> None:
        """Release the lock and clean up.

        In non-blocking mode, removes the lock file after release.
        In blocking mode, keeps the lock file to avoid race conditions
        with other threads/processes waiting on the same inode.
        """
        if self._fd is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    os.lseek(self._fd, 0, os.SEEK_SET)
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
            self._fd = None
            if not self.blocking:
                try:
                    self.lock_path.unlink()
                except OSError:
                    pass

    def __enter__(self) -> "CrossPlatformLock":
        if not self.acquire():
            raise LockHeldError(f"Lock held by another process: {self.lock_path}")
        return self

    def __exit__(self, *args) -> None:
        self.release()


# ---------------------------------------------------------------------------
# Task 0.5: ServiceManager
# ---------------------------------------------------------------------------


class ServiceManager:
    """Manage spellbook daemon as an OS service.

    Delegates to launchd (macOS), systemd (Linux), or
    Task Scheduler + watchdog (Windows).

    Args:
        spellbook_dir: Path to the spellbook installation.
        port: Port for the MCP server.
        host: Host for the MCP server.
    """

    LAUNCHD_LABEL = "com.spellbook.mcp"
    SERVICE_NAME = "spellbook-mcp"

    def __init__(self, spellbook_dir: Path, port: int, host: str):
        self.spellbook_dir = spellbook_dir
        self.port = port
        self.host = host

    def install(self) -> tuple[bool, str]:
        """Install the daemon as a system service."""
        plat = get_platform()
        if plat == Platform.MACOS:
            return self._install_macos()
        elif plat == Platform.LINUX:
            return self._install_linux()
        elif plat == Platform.WINDOWS:
            return self._install_windows()
        return False, f"Unsupported platform: {plat.value}"

    def uninstall(self) -> tuple[bool, str]:
        """Uninstall the system service."""
        plat = get_platform()
        if plat == Platform.MACOS:
            return self._uninstall_macos()
        elif plat == Platform.LINUX:
            return self._uninstall_linux()
        elif plat == Platform.WINDOWS:
            return self._uninstall_windows()
        return False, f"Unsupported platform: {plat.value}"

    def start(self) -> tuple[bool, str]:
        """Start the service."""
        plat = get_platform()
        if plat == Platform.MACOS:
            plist_path = self._launchd_plist_path()
            result = subprocess.run(
                ["launchctl", "load", str(plist_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True, "launchd service loaded"
            return False, f"Failed to load: {result.stderr}"
        elif plat == Platform.LINUX:
            result = subprocess.run(
                ["systemctl", "--user", "start", self.SERVICE_NAME],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True, "systemd service started"
            return False, f"Failed to start: {result.stderr}"
        elif plat == Platform.WINDOWS:
            result = subprocess.run(
                ["schtasks", "/Run", "/TN", "SpellbookMCP"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True, "Task Scheduler task started"
            return False, f"Failed to start: {result.stderr}"
        return False, f"Unsupported platform: {plat.value}"

    def stop(self) -> tuple[bool, str]:
        """Stop the service. Primary: PID-based. Fallback: platform-specific."""
        # Primary: PID-based stop
        config_dir = Path(
            os.environ.get(
                "SPELLBOOK_CONFIG_DIR",
                str(Path.home() / ".local" / "spellbook"),
            )
        )
        pid_file = config_dir / f"{self.SERVICE_NAME}.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
                if _pid_exists(pid):
                    self._kill_process(pid)
                    pid_file.unlink(missing_ok=True)
                    return True, f"Stopped process {pid}"
            except (ValueError, OSError):
                pass

        # Fallback: platform-specific
        plat = get_platform()
        if plat == Platform.MACOS:
            plist_path = self._launchd_plist_path()
            if plist_path.exists():
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True,
                )
            return True, "launchd service unloaded"
        elif plat == Platform.LINUX:
            subprocess.run(
                ["systemctl", "--user", "stop", self.SERVICE_NAME],
                capture_output=True,
            )
            return True, "systemd service stopped"
        elif plat == Platform.WINDOWS:
            pids = self._find_process_windows("spellbook_mcp")
            for pid in pids:
                self._kill_process(pid)
            return True, f"Stopped {len(pids)} process(es)"
        return False, f"Unsupported platform: {plat.value}"

    def is_installed(self) -> bool:
        """Check if the service is installed."""
        plat = get_platform()
        if plat == Platform.MACOS:
            return self._launchd_plist_path().exists()
        elif plat == Platform.LINUX:
            return self._systemd_service_path().exists()
        elif plat == Platform.WINDOWS:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", "SpellbookMCP"],
                capture_output=True,
            )
            return result.returncode == 0
        return False

    def is_running(self) -> bool:
        """Check if the service is running."""
        import socket

        try:
            with socket.create_connection((self.host, self.port), timeout=2):
                return True
        except (OSError, TimeoutError):
            return False

    # -- Private helpers --

    def _launchd_plist_path(self) -> Path:
        return (
            Path.home()
            / "Library"
            / "LaunchAgents"
            / f"{self.LAUNCHD_LABEL}.plist"
        )

    def _systemd_service_path(self) -> Path:
        return (
            Path.home()
            / ".config"
            / "systemd"
            / "user"
            / f"{self.SERVICE_NAME}.service"
        )

    def _install_macos(self) -> tuple[bool, str]:
        """Install launchd service. Delegates plist generation to spellbook-server.py."""
        server_script = self.spellbook_dir / "scripts" / "spellbook-server.py"
        if not server_script.exists():
            return False, f"Server script not found: {server_script}"
        result = subprocess.run(
            [sys.executable, str(server_script), "install"],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "SPELLBOOK_DIR": str(self.spellbook_dir)},
        )
        if result.returncode == 0:
            return True, "Installed launchd service"
        return False, f"Failed: {result.stderr.strip()}"

    def _install_linux(self) -> tuple[bool, str]:
        """Install systemd service. Delegates to spellbook-server.py."""
        server_script = self.spellbook_dir / "scripts" / "spellbook-server.py"
        if not server_script.exists():
            return False, f"Server script not found: {server_script}"
        result = subprocess.run(
            [sys.executable, str(server_script), "install"],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "SPELLBOOK_DIR": str(self.spellbook_dir)},
        )
        if result.returncode == 0:
            return True, "Installed systemd service"
        return False, f"Failed: {result.stderr.strip()}"

    def _install_windows(self) -> tuple[bool, str]:
        """Install Windows Task Scheduler task running the watchdog."""
        xml_content = self._generate_task_xml()
        xml_path = self.spellbook_dir / "scripts" / ".task-scheduler.xml"
        try:
            xml_path.parent.mkdir(parents=True, exist_ok=True)
            xml_path.write_text(xml_content, encoding="utf-16")
            result = subprocess.run(
                [
                    "schtasks",
                    "/Create",
                    "/TN",
                    "SpellbookMCP",
                    "/XML",
                    str(xml_path),
                    "/F",
                ],
                capture_output=True,
                text=True,
            )
            xml_path.unlink(missing_ok=True)
            if result.returncode == 0:
                return True, "Task Scheduler task created"
            return False, f"Failed: {result.stderr}"
        except OSError as e:
            xml_path.unlink(missing_ok=True)
            return False, f"Failed to write task XML: {e}"

    def _uninstall_macos(self) -> tuple[bool, str]:
        plist_path = self._launchd_plist_path()
        if plist_path.exists():
            subprocess.run(
                ["launchctl", "unload", str(plist_path)],
                capture_output=True,
            )
            plist_path.unlink(missing_ok=True)
            return True, "Uninstalled launchd service"
        return True, "Service was not installed"

    def _uninstall_linux(self) -> tuple[bool, str]:
        service_path = self._systemd_service_path()
        if service_path.exists():
            subprocess.run(
                ["systemctl", "--user", "stop", self.SERVICE_NAME],
                capture_output=True,
            )
            subprocess.run(
                ["systemctl", "--user", "disable", self.SERVICE_NAME],
                capture_output=True,
            )
            service_path.unlink(missing_ok=True)
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
            )
            return True, "Uninstalled systemd service"
        return True, "Service was not installed"

    def _uninstall_windows(self) -> tuple[bool, str]:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", "SpellbookMCP", "/F"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or "does not exist" in result.stderr.lower():
            return True, "Task Scheduler task removed"
        return False, f"Failed: {result.stderr}"

    def _generate_task_xml(self) -> str:
        return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>{sys.executable}</Command>
      <Arguments>{self.spellbook_dir}/scripts/spellbook-watchdog.py</Arguments>
      <WorkingDirectory>{self.spellbook_dir}</WorkingDirectory>
    </Exec>
  </Actions>
  <Settings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
  </Settings>
</Task>"""

    def _kill_process(self, pid: int) -> None:
        """Kill a process by PID, cross-platform."""
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid)],
                capture_output=True,
            )
            time.sleep(1)
            if _pid_exists(pid):
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                )
        else:
            try:
                os.kill(pid, signal.SIGTERM)
                for _ in range(10):
                    time.sleep(0.5)
                    if not _pid_exists(pid):
                        return
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def _find_process_windows(self, pattern: str) -> list[int]:
        """Find PIDs matching a pattern on Windows using PowerShell."""
        if sys.platform != "win32":
            return []
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-CimInstance Win32_Process | "
                    f"Where-Object {{$_.CommandLine -like '*{pattern}*'}} | "
                    f"Select-Object -ExpandProperty ProcessId",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return [
                int(pid) for pid in result.stdout.strip().split("\n") if pid.strip()
            ]
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return []


# ---------------------------------------------------------------------------
# Task 0.6: Utility functions
# ---------------------------------------------------------------------------


def get_python_executable() -> str:
    """Get the Python executable path.

    Handles the python3 vs python naming difference on Windows.
    Returns sys.executable which always works.
    """
    return sys.executable


def get_config_dir(app_name: str = "spellbook") -> Path:
    """Get OS-appropriate config directory.

    macOS:   ~/.config/{app_name}
    Linux:   ~/.config/{app_name}
    Windows: %APPDATA%/{app_name}

    Args:
        app_name: Application name for the config subdirectory.

    Returns:
        Path to the config directory.
    """
    if get_platform() == Platform.WINDOWS:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / app_name
        return Path.home() / "AppData" / "Roaming" / app_name
    return Path.home() / ".config" / app_name


def get_path_separator() -> str:
    """Get the PATH environment variable separator.

    Unix: ':'
    Windows: ';'
    """
    return ";" if get_platform() == Platform.WINDOWS else ":"
