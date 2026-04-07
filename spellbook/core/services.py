"""Cross-platform service management for spellbook.

ServiceConfig, ServiceManager, and service config builders live here so
that both the spellbook package and the installer package can use them
without circular dependencies.

Re-exported by installer.compat for backward compatibility.
"""

import getpass
import json
import logging
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

from spellbook.core.paths import get_config_dir, get_data_dir, get_log_dir

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform detection
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
# Process utilities
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
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Service configuration
# ---------------------------------------------------------------------------


@dataclass
class ServiceConfig:
    """Platform-agnostic service configuration.

    Encapsulates all parameters needed to install, run, and manage a service
    across macOS (launchd), Linux (systemd), and Windows (Task Scheduler).

    health_check_port: When set, is_running() uses a TCP probe on this
        port (preserving the existing MCP behavior of checking port health).
        When None, is_running() falls back to platform-specific process
        status checks (launchctl list / systemctl is-active).
    health_check_host: Host for TCP health probe (default "127.0.0.1").
    """

    launchd_label: str
    service_name: str
    schtasks_name: str
    description: str
    executable: Path
    args: list[str]
    working_directory: Path
    environment: dict[str, str]
    log_stdout: Path
    log_stderr: Path
    pid_file: Optional[Path] = None
    keep_alive: bool = True
    health_check_port: Optional[int] = None
    health_check_host: str = "127.0.0.1"


# ---------------------------------------------------------------------------
# Service config builders
# ---------------------------------------------------------------------------


def tts_service_config(
    tts_venv_dir: Path,
    port: int = 10200,
    device: str = "cpu",
    voice: str = "af_heart",
    data_dir: Optional[Path] = None,
) -> ServiceConfig:
    """Build ServiceConfig for the TTS server.

    Args:
        tts_venv_dir: Path to the TTS venv directory.
        port: Wyoming server port (default 10200).
        device: Compute device ("mps", "cuda", "cpu").
        voice: Voice name for kokoro engine.
        data_dir: Model data directory (default ~/.local/spellbook/tts-data).

    Returns:
        ServiceConfig with TTS server parameters.
    """
    if sys.platform == "win32":
        python = tts_venv_dir / "Scripts" / "python.exe"
    else:
        python = tts_venv_dir / "bin" / "python"

    if data_dir is None:
        data_dir = get_data_dir() / "tts-data"

    log_dir = get_log_dir()

    return ServiceConfig(
        launchd_label="com.spellbook.tts",
        service_name="spellbook-tts",
        schtasks_name="SpellbookTTS",
        description="Spellbook TTS Server",
        executable=python,
        args=[
            "-m", "wyoming_kokoro_torch",
            "--uri", f"tcp://127.0.0.1:{port}",
            "--device", device,
            "--voice", voice,
            "--data-dir", str(data_dir),
        ],
        working_directory=get_data_dir(),
        environment={},
        log_stdout=log_dir / "tts.log",
        log_stderr=log_dir / "tts.err.log",
        pid_file=None,
        keep_alive=True,
        health_check_port=port,
        health_check_host="127.0.0.1",
    )


# ---------------------------------------------------------------------------
# Service management
# ---------------------------------------------------------------------------


class ServiceManager:
    """Manage an OS service. Platform-agnostic via ServiceConfig.

    Delegates to launchd (macOS), systemd (Linux), or
    Task Scheduler (Windows).

    Args:
        config: ServiceConfig with all service parameters.
    """

    def __init__(self, config: ServiceConfig):
        self.config = config

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
        try:
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
                    ["systemctl", "--user", "start", self.config.service_name],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return True, "systemd service started"
                return False, f"Failed to start: {result.stderr}"
            elif plat == Platform.WINDOWS:
                result = subprocess.run(
                    ["schtasks", "/Run", "/TN", self.config.schtasks_name],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return True, "Task Scheduler task started"
                return False, f"Failed to start: {result.stderr}"
        except FileNotFoundError as e:
            return False, f"Service manager not available: {e}"
        return False, f"Unsupported platform: {plat.value}"

    def stop(self) -> tuple[bool, str]:
        """Stop the service. Primary: PID-based. Fallback: platform-specific."""
        # Primary: PID-based stop
        if self.config.pid_file and self.config.pid_file.exists():
            try:
                pid = int(self.config.pid_file.read_text(encoding="utf-8").strip())
                if _pid_exists(pid):
                    self._kill_process(pid)
                    self.config.pid_file.unlink(missing_ok=True)
                    return True, f"Stopped process {pid}"
            except (ValueError, OSError):
                pass

        # Fallback: platform-specific
        plat = get_platform()
        try:
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
                    ["systemctl", "--user", "stop", self.config.service_name],
                    capture_output=True,
                )
                return True, "systemd service stopped"
        except FileNotFoundError:
            return True, "Service manager not available, service assumed stopped"
        if plat == Platform.WINDOWS:
            # Use the executable path for a specific match, avoiding killing
            # unrelated processes that happen to contain "spellbook".
            pattern = str(self.config.executable)
            pids = self._find_process_windows(pattern)
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
            try:
                result = subprocess.run(
                    ["schtasks", "/Query", "/TN", self.config.schtasks_name],
                    capture_output=True,
                )
                return result.returncode == 0
            except FileNotFoundError:
                return False
        return False

    def is_running(self) -> bool:
        """Check if the service is running (synchronous).

        When health_check_port is set on the ServiceConfig, performs a TCP
        probe to confirm the port is actually listening (service healthy).
        This preserves the existing MCP behavior where is_running() checks
        port health, not just process status.

        When health_check_port is None, falls back to platform-specific
        process/service status checks (launchctl list / systemctl is-active).

        Note: This method uses blocking I/O (socket.create_connection). Callers
        in async contexts should wrap with ``asyncio.to_thread(manager.is_running)``
        or use a dedicated async health probe (see provisioner._health_probe).
        """
        import socket

        # TCP health probe when health_check_port is configured
        if self.config.health_check_port is not None:
            try:
                with socket.create_connection(
                    (self.config.health_check_host, self.config.health_check_port),
                    timeout=2,
                ):
                    return True
            except (OSError, TimeoutError):
                return False

        # Fallback: platform-specific service status check
        plat = get_platform()
        if plat == Platform.MACOS:
            try:
                result = subprocess.run(
                    ["launchctl", "list", self.config.launchd_label],
                    capture_output=True,
                )
                return result.returncode == 0
            except FileNotFoundError:
                return False
        elif plat == Platform.LINUX:
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "is-active", self.config.service_name],
                    capture_output=True,
                )
                return result.returncode == 0
            except FileNotFoundError:
                return False
        return False

    # -- Private helpers --

    def _launchd_plist_path(self) -> Path:
        return (
            Path.home()
            / "Library"
            / "LaunchAgents"
            / f"{self.config.launchd_label}.plist"
        )

    def _systemd_service_path(self) -> Path:
        return (
            Path.home()
            / ".config"
            / "systemd"
            / "user"
            / f"{self.config.service_name}.service"
        )

    def _install_macos(self) -> tuple[bool, str]:
        """Install launchd service from ServiceConfig."""
        plist_path = self._launchd_plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)

        # Unload existing if present
        if plist_path.exists():
            try:
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True,
                )
            except FileNotFoundError:
                pass

        # Build ProgramArguments array
        prog_args = [str(self.config.executable)] + self.config.args
        args_xml = "\n".join(
            f"        <string>{xml_escape(a)}</string>" for a in prog_args
        )

        # Build EnvironmentVariables dict
        env_xml = ""
        if self.config.environment:
            env_entries = "\n".join(
                f"            <key>{xml_escape(k)}</key>\n"
                f"            <string>{xml_escape(v)}</string>"
                for k, v in self.config.environment.items()
            )
            env_xml = (
                "\n    <key>EnvironmentVariables</key>\n"
                "    <dict>\n"
                f"{env_entries}\n"
                "    </dict>"
            )

        keep_alive = "<true/>" if self.config.keep_alive else "<false/>"

        plist_content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"'
            ' "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            '<dict>\n'
            '    <key>Label</key>\n'
            f'    <string>{xml_escape(self.config.launchd_label)}</string>\n'
            '\n'
            '    <key>ProgramArguments</key>\n'
            '    <array>\n'
            f'{args_xml}\n'
            '    </array>\n'
            f'{env_xml}\n'
            '\n'
            '    <key>RunAtLoad</key>\n'
            '    <true/>\n'
            '\n'
            '    <key>KeepAlive</key>\n'
            f'    {keep_alive}\n'
            '\n'
            '    <key>StandardOutPath</key>\n'
            f'    <string>{xml_escape(str(self.config.log_stdout))}</string>\n'
            '\n'
            '    <key>StandardErrorPath</key>\n'
            f'    <string>{xml_escape(str(self.config.log_stderr))}</string>\n'
            '\n'
            '    <key>WorkingDirectory</key>\n'
            f'    <string>{xml_escape(str(self.config.working_directory))}</string>\n'
            '</dict>\n'
            '</plist>\n'
        )

        try:
            plist_path.write_text(plist_content, encoding="utf-8")

            result = subprocess.run(
                ["launchctl", "load", str(plist_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, f"Failed to load: {result.stderr}"
            return True, "Installed launchd service"
        except OSError as e:
            return False, f"Failed: {e}"

    def _install_linux(self) -> tuple[bool, str]:
        """Install systemd user service from ServiceConfig."""
        service_path = self._systemd_service_path()
        service_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                ["systemctl", "--user", "stop", self.config.service_name],
                capture_output=True,
            )
        except FileNotFoundError:
            pass

        exec_start = shlex.join(
            [str(self.config.executable)] + self.config.args
        )

        env_lines = "\n".join(
            f"Environment={k}={v}"
            for k, v in self.config.environment.items()
        )

        restart_line = "Restart=always\nRestartSec=5" if self.config.keep_alive else ""

        log_lines = (
            f'StandardOutput=append:"{self.config.log_stdout}"\n'
            f'StandardError=append:"{self.config.log_stderr}"'
        )

        service_content = (
            "[Unit]\n"
            f"Description={self.config.description}\n"
            "After=network.target\n"
            "\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={exec_start}\n"
            f"WorkingDirectory={self.config.working_directory}\n"
            f"{restart_line}\n"
            f"{env_lines}\n"
            f"{log_lines}\n"
            "\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )

        try:
            service_path.write_text(service_content, encoding="utf-8")

            result = subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, f"Failed to reload systemd: {result.stderr}"

            result = subprocess.run(
                ["systemctl", "--user", "enable", self.config.service_name],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, f"Failed to enable service: {result.stderr}"

            result = subprocess.run(
                ["systemctl", "--user", "start", self.config.service_name],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False, f"Failed to start service: {result.stderr}"

            # Enable linger so user services survive logout
            try:
                subprocess.run(
                    ["loginctl", "enable-linger", getpass.getuser()],
                    capture_output=True,
                )
            except FileNotFoundError:
                pass

            return True, "Installed systemd service"
        except OSError as e:
            return False, f"Failed: {e}"

    def _install_windows(self) -> tuple[bool, str]:
        """Install Windows Task Scheduler task from ServiceConfig."""
        xml_content = self._generate_task_xml()
        xml_path = self.config.working_directory / ".task-scheduler.xml"
        try:
            xml_path.parent.mkdir(parents=True, exist_ok=True)
            xml_path.write_text(xml_content, encoding="utf-16")
            result = subprocess.run(
                [
                    "schtasks",
                    "/Create",
                    "/TN",
                    self.config.schtasks_name,
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
            try:
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True,
                )
            except FileNotFoundError:
                pass
            plist_path.unlink(missing_ok=True)
            return True, "Uninstalled launchd service"
        return True, "Service was not installed"

    def _uninstall_linux(self) -> tuple[bool, str]:
        service_path = self._systemd_service_path()
        if service_path.exists():
            try:
                subprocess.run(
                    ["systemctl", "--user", "stop", self.config.service_name],
                    capture_output=True,
                )
                subprocess.run(
                    ["systemctl", "--user", "disable", self.config.service_name],
                    capture_output=True,
                )
            except FileNotFoundError:
                pass
            service_path.unlink(missing_ok=True)
            try:
                subprocess.run(
                    ["systemctl", "--user", "daemon-reload"],
                    capture_output=True,
                )
            except FileNotFoundError:
                pass
            return True, "Uninstalled systemd service"
        return True, "Service was not installed"

    def _uninstall_windows(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", self.config.schtasks_name, "/F"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 or "does not exist" in result.stderr.lower():
                return True, "Task Scheduler task removed"
            return False, f"Failed: {result.stderr}"
        except FileNotFoundError:
            return True, "Task Scheduler not available"

    def _generate_task_xml(self) -> str:
        exe = xml_escape(str(self.config.executable))
        args = xml_escape(subprocess.list2cmdline(self.config.args))
        working_dir = xml_escape(str(self.config.working_directory))
        return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
  </Triggers>
  <Actions>
    <Exec>
      <Command>{exe}</Command>
      <Arguments>{args}</Arguments>
      <WorkingDirectory>{working_dir}</WorkingDirectory>
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
        """Find PIDs matching a pattern on Windows using PowerShell.

        Args:
            pattern: A filesystem path or simple name to match against
                process command lines. Path separators, colons, and spaces
                are permitted. PowerShell wildcard characters are escaped.
        """
        if not re.match(r'^[\w.\-\\/:() ]+$', pattern):
            raise ValueError(f"Invalid process pattern: {pattern}")
        # Escape PowerShell -like wildcard characters to match literally
        safe = pattern.replace("[", "`[").replace("]", "`]")
        if sys.platform != "win32":
            return []
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-CimInstance Win32_Process | "
                    f"Where-Object {{$_.CommandLine -like '*{safe}*'}} | "
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
