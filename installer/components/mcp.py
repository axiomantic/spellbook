"""
MCP server registration, daemon management, and verification.
"""

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from installer.compat import Platform, get_platform, get_python_executable

# Daemon configuration
# TODO: Consolidate service management with installer.compat.ServiceManager
# to eliminate duplicated launchd/systemd/schtasks logic.
DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"
SERVICE_NAME = "spellbook-mcp"
LAUNCHD_LABEL = "com.spellbook.mcp"


@dataclass
class MCPStatus:
    """Status of an MCP server."""

    name: str
    registered: bool
    connected: Optional[bool]  # None if registration check failed
    command: str
    error: Optional[str] = None


def check_claude_cli_available() -> bool:
    """Check if claude CLI is available."""
    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def list_registered_mcp_servers() -> List[MCPStatus]:
    """Get list of registered MCP servers from claude CLI."""
    if not check_claude_cli_available():
        return []

    try:
        result = subprocess.run(
            ["claude", "mcp", "list"], capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            return []

        servers = []
        # Parse the output (format varies, look for server names)
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("-"):
                continue

            # Try to parse "name: command" or just "name"
            if ":" in line:
                parts = line.split(":", 1)
                name = parts[0].strip()
                command = parts[1].strip() if len(parts) > 1 else ""
            else:
                name = line
                command = ""

            if name:
                servers.append(
                    MCPStatus(
                        name=name,
                        registered=True,
                        connected=None,  # We can't easily check this
                        command=command,
                    )
                )

        return servers
    except (subprocess.TimeoutExpired, OSError):
        return []


def is_mcp_registered(name: str) -> bool:
    """Check if an MCP server is registered."""
    servers = list_registered_mcp_servers()
    return any(s.name == name for s in servers)


def register_mcp_server(
    name: str, command: List[str], dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Register an MCP server with claude CLI.

    Args:
        name: Server name
        command: Command to run the server
        dry_run: If True, don't actually register

    Returns: (success, message)
    """
    if not check_claude_cli_available():
        return (False, "claude CLI not available")

    if dry_run:
        return (True, f"Would register MCP server: {name}")

    try:
        # Always try to remove first (ignore errors)
        subprocess.run(
            ["claude", "mcp", "remove", name],
            capture_output=True,
            timeout=10,
        )

        # Add the MCP server with user scope (global, not per-project)
        cmd = ["claude", "mcp", "add", "--scope", "user", name, "--"] + command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return (True, "registered successfully")
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            # Check if it's an "already exists" error - that's actually fine
            if "already exists" in error_msg.lower():
                return (True, "already registered")
            return (False, f"registration failed: {error_msg}")

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))


def unregister_mcp_server(name: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Remove an MCP server registration.

    Args:
        name: Server name
        dry_run: If True, don't actually unregister

    Returns: (success, message)
    """
    if not check_claude_cli_available():
        return (False, "claude CLI not available")

    if dry_run:
        if is_mcp_registered(name):
            return (True, f"Would unregister MCP server: {name}")
        return (True, "MCP server not registered")

    try:
        if not is_mcp_registered(name):
            return (True, "was not registered")

        result = subprocess.run(
            ["claude", "mcp", "remove", name],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return (True, "unregistered successfully")
        elif "not found" in result.stderr.lower():
            return (True, "was not registered")
        else:
            return (False, result.stderr.strip())

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))


def verify_mcp_connectivity(server_path: Path, timeout: int = 10) -> Tuple[bool, str]:
    """
    Verify MCP server can start and respond.

    This does a basic check that the server can be imported/started.

    Args:
        server_path: Path to the server script
        timeout: Timeout in seconds

    Returns: (success, message)
    """
    if not server_path.exists():
        return (False, f"Server not found: {server_path}")

    try:
        # Try to import and check the server can at least be loaded
        result = subprocess.run(
            [get_python_executable(), "-c", f"import sys; sys.path.insert(0, '{server_path.parent}'); import server"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=server_path.parent,
        )

        if result.returncode == 0:
            return (True, "server module loads successfully")
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return (False, f"server failed to load: {error}")

    except subprocess.TimeoutExpired:
        return (False, "server load timed out")
    except OSError as e:
        return (False, str(e))


def restart_mcp_server(name: str, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Restart an MCP server by killing its process.

    Claude Code will respawn the MCP server on next use.

    Args:
        name: Server name (used to find the process)
        dry_run: If True, don't actually kill the process

    Returns: (success, message)
    """
    import signal

    if dry_run:
        return (True, f"Would restart MCP server: {name}")

    try:
        # Find processes matching the MCP server
        # Look for processes running the spellbook_mcp server
        plat = get_platform()
        if plat == Platform.WINDOWS:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process | "
                 "Where-Object {$_.CommandLine -like '*spellbook_mcp*server*'} | "
                 "Select-Object -ExpandProperty ProcessId"],
                capture_output=True, text=True, timeout=5,
            )
        else:
            result = subprocess.run(
                ["pgrep", "-f", f"{name}.*server\\.py|spellbook_mcp.*server"],
                capture_output=True,
                text=True,
                timeout=5,
            )

        if result.returncode != 0 or not result.stdout.strip():
            return (True, "no running process found (will start on next use)")

        pids = [int(pid) for pid in result.stdout.strip().split("\n") if pid.strip()]

        if not pids:
            return (True, "no running process found (will start on next use)")

        killed = 0
        for pid in pids:
            try:
                if plat == Platform.WINDOWS:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid)],
                        capture_output=True,
                    )
                    killed += 1
                else:
                    os.kill(pid, signal.SIGTERM)
                    killed += 1
            except (ProcessLookupError, PermissionError):
                # Process already gone or we can't kill it
                pass

        if killed > 0:
            return (True, f"terminated {killed} process(es), will respawn on next use")
        else:
            return (True, "processes already stopped")

    except subprocess.TimeoutExpired:
        return (False, "process search timed out")
    except (OSError, ValueError) as e:
        return (False, str(e))


def check_gemini_cli_available() -> bool:
    """Check if gemini CLI is available."""
    try:
        result = subprocess.run(
            ["gemini", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# =============================================================================
# Daemon Management
# =============================================================================

def get_spellbook_server_url() -> str:
    """Get the spellbook MCP server URL."""
    return f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/mcp"


def get_launchd_plist_path() -> Path:
    """Get path to launchd plist file."""
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def get_systemd_service_path() -> Path:
    """Get path to systemd user service file."""
    return Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"


def is_daemon_installed() -> bool:
    """Check if the spellbook daemon is installed as a system service."""
    plat = get_platform()
    if plat == Platform.MACOS:
        return get_launchd_plist_path().exists()
    elif plat == Platform.LINUX:
        return get_systemd_service_path().exists()
    elif plat == Platform.WINDOWS:
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", "SpellbookMCP"],
                capture_output=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    return False


def is_daemon_running() -> bool:
    """Check if the spellbook daemon is running."""
    import socket

    try:
        with socket.create_connection((DEFAULT_HOST, DEFAULT_PORT), timeout=2):
            return True
    except (OSError, TimeoutError):
        return False


def stop_daemon(dry_run: bool = False) -> Tuple[bool, str]:
    """
    Stop the spellbook daemon if running.

    Args:
        dry_run: If True, don't actually stop

    Returns: (success, message)
    """
    if dry_run:
        if is_daemon_running():
            return (True, "Would stop daemon")
        return (True, "Daemon not running")

    plat = get_platform()

    try:
        if plat == Platform.MACOS:
            plist_path = get_launchd_plist_path()
            if plist_path.exists():
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True
                )
        elif plat == Platform.LINUX:
            subprocess.run(
                ["systemctl", "--user", "stop", SERVICE_NAME],
                capture_output=True
            )
    except FileNotFoundError:
        # systemctl/launchctl not available (e.g., in Docker without systemd)
        pass

    # Give it a moment to stop
    time.sleep(1)

    if is_daemon_running():
        # Graceful stop failed, force kill
        try:
            if plat == Platform.WINDOWS:
                # Find and kill spellbook_mcp processes on Windows
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Process | "
                     "Where-Object {$_.CommandLine -like '*spellbook_mcp*server*'} | "
                     "Select-Object -ExpandProperty ProcessId"],
                    capture_output=True, text=True, timeout=10,
                )
                for pid_str in result.stdout.strip().split("\n"):
                    if pid_str.strip():
                        subprocess.run(
                            ["taskkill", "/F", "/PID", pid_str.strip()],
                            capture_output=True,
                        )
            else:
                subprocess.run(
                    ["pkill", "-f", "spellbook_mcp/server.py"],
                    capture_output=True
                )
        except FileNotFoundError:
            # pkill/powershell/taskkill not available
            pass
        time.sleep(1)

        if is_daemon_running():
            if plat != Platform.WINDOWS:
                # Last resort: SIGKILL (Unix only)
                try:
                    subprocess.run(
                        ["pkill", "-9", "-f", "spellbook_mcp/server.py"],
                        capture_output=True
                    )
                except FileNotFoundError:
                    pass
                time.sleep(1)

            if is_daemon_running():
                return (False, "Daemon still running after force kill attempt")

        return (True, "Daemon stopped (force killed)")

    return (True, "Daemon stopped")


def uninstall_daemon(dry_run: bool = False) -> Tuple[bool, str]:
    """
    Uninstall the spellbook daemon service.

    Args:
        dry_run: If True, don't actually uninstall

    Returns: (success, message)
    """
    if dry_run:
        if is_daemon_installed():
            return (True, "Would uninstall daemon service")
        return (True, "Daemon service not installed")

    plat = get_platform()

    # Stop first
    stop_daemon(dry_run=False)

    if plat == Platform.MACOS:
        plist_path = get_launchd_plist_path()
        if plist_path.exists():
            try:
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    capture_output=True
                )
            except FileNotFoundError:
                pass
            plist_path.unlink(missing_ok=True)
            return (True, "Daemon service uninstalled")
        return (True, "Daemon service was not installed")

    elif plat == Platform.LINUX:
        service_path = get_systemd_service_path()
        if service_path.exists():
            try:
                subprocess.run(
                    ["systemctl", "--user", "stop", SERVICE_NAME],
                    capture_output=True
                )
                subprocess.run(
                    ["systemctl", "--user", "disable", SERVICE_NAME],
                    capture_output=True
                )
            except FileNotFoundError:
                pass
            service_path.unlink(missing_ok=True)
            try:
                subprocess.run(
                    ["systemctl", "--user", "daemon-reload"],
                    capture_output=True
                )
            except FileNotFoundError:
                pass
            return (True, "Daemon service uninstalled")
        return (True, "Daemon service was not installed")

    elif plat == Platform.WINDOWS:
        try:
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", "SpellbookMCP", "/F"],
                capture_output=True, text=True,
            )
            if result.returncode == 0 or "does not exist" in result.stderr.lower():
                return (True, "Daemon service uninstalled")
            return (False, f"Failed to uninstall: {result.stderr}")
        except FileNotFoundError:
            return (True, "Daemon service was not installed")

    return (False, f"Unsupported platform: {plat.value}")


def install_daemon(spellbook_dir: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Install and start the spellbook daemon service.

    Args:
        spellbook_dir: Path to spellbook installation
        dry_run: If True, don't actually install

    Returns: (success, message)
    """
    if dry_run:
        return (True, "Would install daemon service")

    # First, stop and uninstall any existing daemon
    uninstall_daemon(dry_run=False)

    # Use the spellbook-server.py script to install
    server_script = spellbook_dir / "scripts" / "spellbook-server.py"

    if not server_script.exists():
        return (False, f"Server script not found: {server_script}")

    try:
        result = subprocess.run(
            [get_python_executable(), str(server_script), "install"],
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **os.environ,
                "SPELLBOOK_DIR": str(spellbook_dir),
            }
        )

        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            return (False, f"Install failed: {error}")

        # Wait for daemon to start
        for _ in range(10):
            time.sleep(1)
            if is_daemon_running():
                return (True, f"Daemon installed and running on {get_spellbook_server_url()}")

        return (False, "Daemon installed but not responding")

    except subprocess.TimeoutExpired:
        return (False, "Install timed out")
    except OSError as e:
        return (False, str(e))


def register_mcp_http_server(
    name: str, url: str, dry_run: bool = False
) -> Tuple[bool, str]:
    """
    Register an MCP server with HTTP transport using claude CLI.

    Args:
        name: Server name
        url: HTTP URL for the server
        dry_run: If True, don't actually register

    Returns: (success, message)
    """
    if not check_claude_cli_available():
        return (False, "claude CLI not available")

    if dry_run:
        return (True, f"Would register HTTP MCP server: {name} -> {url}")

    try:
        # Always try to remove first (ignore errors)
        subprocess.run(
            ["claude", "mcp", "remove", name],
            capture_output=True,
            timeout=10,
        )

        # Add the MCP server with HTTP transport and user scope (global, not per-project)
        cmd = ["claude", "mcp", "add", "--transport", "http", "--scope", "user", name, url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return (True, "registered successfully")
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            if "already exists" in error_msg.lower():
                return (True, "already registered")
            return (False, f"registration failed: {error_msg}")

    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    except OSError as e:
        return (False, str(e))
