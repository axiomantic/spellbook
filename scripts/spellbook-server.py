#!/usr/bin/env python3
"""Spellbook MCP Server daemon management.

Runs the spellbook MCP server as a persistent HTTP service instead of
spawning a new process for each Claude session (which takes 10+ seconds).

Usage:
    # Install as system service (starts on boot)
    python3 scripts/spellbook-server.py install

    # Uninstall system service
    python3 scripts/spellbook-server.py uninstall

    # Manual start (if not using system service)
    python3 scripts/spellbook-server.py start

    # Stop the server
    python3 scripts/spellbook-server.py stop

    # Check status
    python3 scripts/spellbook-server.py status

    # Show connection URL for Claude
    python3 scripts/spellbook-server.py url

Configuration:
    Port: 8765 (default) or set SPELLBOOK_MCP_PORT
    Host: 127.0.0.1 (localhost only for security)

macOS: Uses launchd (~/Library/LaunchAgents/com.spellbook.mcp.plist)
Linux: Uses systemd user service (~/.config/systemd/user/spellbook-mcp.service)
"""

import argparse
import os
import platform
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

# Default configuration
DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"
SERVICE_NAME = "spellbook-mcp"
LAUNCHD_LABEL = "com.spellbook.mcp"


def get_platform() -> str:
    """Get the current platform: 'darwin', 'linux', or 'windows'."""
    return platform.system().lower()


def get_config_dir() -> Path:
    """Get the spellbook config directory."""
    config_dir = Path(os.environ.get(
        "SPELLBOOK_CONFIG_DIR",
        Path.home() / ".local" / "spellbook"
    ))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_pid_file() -> Path:
    return get_config_dir() / f"{SERVICE_NAME}.pid"


def get_log_file() -> Path:
    return get_config_dir() / f"{SERVICE_NAME}.log"


def get_err_log_file() -> Path:
    return get_config_dir() / f"{SERVICE_NAME}.err.log"


def get_port() -> int:
    return int(os.environ.get("SPELLBOOK_MCP_PORT", DEFAULT_PORT))


def get_host() -> str:
    return os.environ.get("SPELLBOOK_MCP_HOST", DEFAULT_HOST)


def get_server_url() -> str:
    return f"http://{get_host()}:{get_port()}/mcp"


def get_spellbook_dir() -> Path:
    """Get the spellbook installation directory."""
    if "SPELLBOOK_DIR" in os.environ:
        return Path(os.environ["SPELLBOOK_DIR"])
    return Path(__file__).parent.parent.resolve()


def get_server_script() -> Path:
    """Get path to the server script."""
    return get_spellbook_dir() / "spellbook_mcp" / "server.py"


def get_uv_path() -> str | None:
    """Get path to uv, or None if not installed."""
    import shutil
    return shutil.which("uv")


def check_dependencies() -> bool:
    """Check all required dependencies and prompt to install if missing.

    Returns True if all dependencies are present.
    """
    import shutil

    missing = []

    # Check uv
    if not shutil.which("uv"):
        missing.append({
            "name": "uv",
            "description": "Fast Python package manager (required)",
            "install": [
                "curl -LsSf https://astral.sh/uv/install.sh | sh",
                "brew install uv",
                "pipx install uv",
            ],
            "docs": "https://docs.astral.sh/uv/getting-started/installation/",
        })

    # Check git (optional but recommended)
    if not shutil.which("git"):
        missing.append({
            "name": "git",
            "description": "Version control (recommended for full functionality)",
            "install": [
                "brew install git",
                "apt install git",
                "xcode-select --install  # macOS",
            ],
            "docs": "https://git-scm.com/downloads",
            "optional": True,
        })

    if not missing:
        return True

    # Report missing dependencies
    required_missing = [d for d in missing if not d.get("optional")]
    optional_missing = [d for d in missing if d.get("optional")]

    if required_missing:
        print("Error: Missing required dependencies:", file=sys.stderr)
        print("", file=sys.stderr)
        for dep in required_missing:
            print(f"  {dep['name']}: {dep['description']}", file=sys.stderr)
            print("  Install with one of:", file=sys.stderr)
            for cmd in dep["install"]:
                print(f"    {cmd}", file=sys.stderr)
            print(f"  More info: {dep['docs']}", file=sys.stderr)
            print("", file=sys.stderr)

    if optional_missing:
        print("Warning: Missing optional dependencies:", file=sys.stderr)
        for dep in optional_missing:
            print(f"  {dep['name']}: {dep['description']}", file=sys.stderr)
        print("", file=sys.stderr)

    return len(required_missing) == 0


def check_uv_installed() -> bool:
    """Check if uv is installed and prompt to install if not."""
    return check_dependencies()


def get_python_path() -> str:
    """Get path to Python interpreter."""
    return sys.executable


# =============================================================================
# macOS launchd support
# =============================================================================

def get_launchd_plist_path() -> Path:
    """Get path to launchd plist file."""
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def get_daemon_path() -> str:
    """Get PATH for daemon environment.

    launchd doesn't inherit shell PATH, so we need to explicitly set it.
    Includes Homebrew paths for both Apple Silicon and Intel Macs.
    """
    import platform

    paths = []

    # Homebrew paths (platform-specific)
    if platform.machine() == "arm64":
        paths.append("/opt/homebrew/bin")
        paths.append("/opt/homebrew/sbin")
    else:
        paths.append("/usr/local/bin")
        paths.append("/usr/local/sbin")

    # User local bin
    home = Path.home()
    if (home / ".local" / "bin").exists():
        paths.append(str(home / ".local" / "bin"))

    # Common tool managers
    if (home / ".cargo" / "bin").exists():
        paths.append(str(home / ".cargo" / "bin"))

    # System paths
    paths.extend(["/usr/bin", "/bin", "/usr/sbin", "/sbin"])

    return os.pathsep.join(paths)


def generate_launchd_plist() -> str:
    """Generate launchd plist content.

    Uses `uv run python -m spellbook_mcp.server` to run the server as a module,
    which ensures the package is properly installed via pyproject.toml.
    """
    uv_path = get_uv_path()
    spellbook_dir = get_spellbook_dir()
    log_file = get_log_file()
    err_log_file = get_err_log_file()
    port = get_port()
    host = get_host()
    daemon_path = get_daemon_path()

    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{LAUNCHD_LABEL}</string>

            <key>ProgramArguments</key>
            <array>
                <string>{uv_path}</string>
                <string>run</string>
                <string>python</string>
                <string>-m</string>
                <string>spellbook_mcp.server</string>
            </array>

            <key>EnvironmentVariables</key>
            <dict>
                <key>PATH</key>
                <string>{daemon_path}</string>
                <key>SPELLBOOK_MCP_TRANSPORT</key>
                <string>streamable-http</string>
                <key>SPELLBOOK_MCP_HOST</key>
                <string>{host}</string>
                <key>SPELLBOOK_MCP_PORT</key>
                <string>{port}</string>
                <key>SPELLBOOK_DIR</key>
                <string>{spellbook_dir}</string>
            </dict>

            <key>RunAtLoad</key>
            <true/>

            <key>KeepAlive</key>
            <true/>

            <key>StandardOutPath</key>
            <string>{log_file}</string>

            <key>StandardErrorPath</key>
            <string>{err_log_file}</string>

            <key>WorkingDirectory</key>
            <string>{spellbook_dir}</string>
        </dict>
        </plist>
    """)


def install_launchd() -> tuple[bool, str]:
    """Install launchd service on macOS."""
    plist_path = get_launchd_plist_path()

    # Create LaunchAgents directory if needed
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    # Unload existing service if present
    if plist_path.exists():
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True
        )

    # Write plist
    plist_content = generate_launchd_plist()
    plist_path.write_text(plist_content)

    # Load service
    result = subprocess.run(
        ["launchctl", "load", str(plist_path)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return False, f"Failed to load service: {result.stderr}"

    return True, f"Installed launchd service: {plist_path}"


def uninstall_launchd() -> tuple[bool, str]:
    """Uninstall launchd service on macOS."""
    plist_path = get_launchd_plist_path()

    if not plist_path.exists():
        return True, "Service not installed"

    # Unload service
    result = subprocess.run(
        ["launchctl", "unload", str(plist_path)],
        capture_output=True,
        text=True
    )

    # Remove plist file
    plist_path.unlink(missing_ok=True)

    return True, "Uninstalled launchd service"


def is_launchd_running() -> bool:
    """Check if launchd service is running."""
    result = subprocess.run(
        ["launchctl", "list", LAUNCHD_LABEL],
        capture_output=True
    )
    return result.returncode == 0


# =============================================================================
# Linux systemd support
# =============================================================================

def get_systemd_service_path() -> Path:
    """Get path to systemd user service file."""
    return Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"


def get_linux_daemon_path() -> str:
    """Get PATH for Linux daemon environment."""
    paths = []

    home = Path.home()

    # User local bin
    if (home / ".local" / "bin").exists():
        paths.append(str(home / ".local" / "bin"))

    # Common tool managers
    if (home / ".cargo" / "bin").exists():
        paths.append(str(home / ".cargo" / "bin"))

    # Linuxbrew
    if Path("/home/linuxbrew/.linuxbrew/bin").exists():
        paths.append("/home/linuxbrew/.linuxbrew/bin")

    # System paths
    paths.extend(["/usr/local/bin", "/usr/bin", "/bin", "/usr/local/sbin", "/usr/sbin", "/sbin"])

    return os.pathsep.join(paths)


def generate_systemd_service() -> str:
    """Generate systemd user service content.

    Uses `uv run python -m spellbook_mcp.server` to run the server as a module,
    which ensures the package is properly installed via pyproject.toml.
    """
    uv_path = get_uv_path()
    spellbook_dir = get_spellbook_dir()
    port = get_port()
    host = get_host()
    daemon_path = get_linux_daemon_path()

    return textwrap.dedent(f"""\
        [Unit]
        Description=Spellbook MCP Server
        After=network.target

        [Service]
        Type=simple
        ExecStart={uv_path} run python -m spellbook_mcp.server
        WorkingDirectory={spellbook_dir}
        Restart=always
        RestartSec=5

        Environment=PATH={daemon_path}
        Environment=SPELLBOOK_MCP_TRANSPORT=streamable-http
        Environment=SPELLBOOK_MCP_HOST={host}
        Environment=SPELLBOOK_MCP_PORT={port}
        Environment=SPELLBOOK_DIR={spellbook_dir}

        [Install]
        WantedBy=default.target
    """)


def install_systemd() -> tuple[bool, str]:
    """Install systemd user service on Linux."""
    service_path = get_systemd_service_path()

    # Create systemd user directory if needed
    service_path.parent.mkdir(parents=True, exist_ok=True)

    # Stop existing service if running
    subprocess.run(
        ["systemctl", "--user", "stop", SERVICE_NAME],
        capture_output=True
    )

    # Write service file
    service_content = generate_systemd_service()
    service_path.write_text(service_content)

    # Reload systemd
    result = subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return False, f"Failed to reload systemd: {result.stderr}"

    # Enable service (start on boot)
    result = subprocess.run(
        ["systemctl", "--user", "enable", SERVICE_NAME],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return False, f"Failed to enable service: {result.stderr}"

    # Start service now
    result = subprocess.run(
        ["systemctl", "--user", "start", SERVICE_NAME],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return False, f"Failed to start service: {result.stderr}"

    # Enable lingering so user services run without login
    subprocess.run(
        ["loginctl", "enable-linger", os.environ.get("USER", "")],
        capture_output=True
    )

    return True, f"Installed systemd service: {service_path}"


def uninstall_systemd() -> tuple[bool, str]:
    """Uninstall systemd user service on Linux."""
    service_path = get_systemd_service_path()

    if not service_path.exists():
        return True, "Service not installed"

    # Stop service
    subprocess.run(
        ["systemctl", "--user", "stop", SERVICE_NAME],
        capture_output=True
    )

    # Disable service
    subprocess.run(
        ["systemctl", "--user", "disable", SERVICE_NAME],
        capture_output=True
    )

    # Remove service file
    service_path.unlink(missing_ok=True)

    # Reload systemd
    subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        capture_output=True
    )

    return True, "Uninstalled systemd service"


def is_systemd_running() -> bool:
    """Check if systemd service is running."""
    result = subprocess.run(
        ["systemctl", "--user", "is-active", SERVICE_NAME],
        capture_output=True
    )
    return result.returncode == 0


# =============================================================================
# Platform-agnostic functions
# =============================================================================

def read_pid() -> int | None:
    """Read PID from pid file, return None if not exists or invalid."""
    from installer.compat import _pid_exists

    pid_file = get_pid_file()
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        if _pid_exists(pid):
            return pid
        pid_file.unlink(missing_ok=True)
        return None
    except (ValueError, OSError):
        pid_file.unlink(missing_ok=True)
        return None


def write_pid(pid: int) -> None:
    """Write PID to pid file."""
    get_pid_file().write_text(str(pid))


def check_server_health(timeout: float = 5.0) -> bool:
    """Check if server is responding by testing if the port is open."""
    import socket

    host = get_host()
    port = get_port()

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def is_service_installed() -> bool:
    """Check if the system service is installed."""
    plat = get_platform()
    if plat == "darwin":
        return get_launchd_plist_path().exists()
    elif plat == "linux":
        return get_systemd_service_path().exists()
    elif plat == "windows":
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", "SpellbookMCP"],
            capture_output=True,
        )
        return result.returncode == 0
    return False


def is_service_running() -> bool:
    """Check if the system service is running."""
    plat = get_platform()
    if plat == "darwin":
        return is_launchd_running()
    elif plat == "linux":
        return is_systemd_running()
    elif plat == "windows":
        return check_server_health(timeout=2.0)
    return False


# =============================================================================
# Commands
# =============================================================================

def cmd_install() -> int:
    """Install as system service."""
    plat = get_platform()

    # Check for uv
    if not check_uv_installed():
        return 1

    # Verify server script exists
    server_script = get_server_script()
    if not server_script.exists():
        print(f"Error: Server script not found: {server_script}", file=sys.stderr)
        return 1

    print(f"Installing spellbook MCP server as system service...")
    print(f"  Platform: {plat}")
    print(f"  Server: {server_script}")
    print(f"  URL: {get_server_url()}")

    if plat == "darwin":
        success, msg = install_launchd()
    elif plat == "linux":
        success, msg = install_systemd()
    elif plat == "windows":
        from installer.compat import ServiceManager
        mgr = ServiceManager(get_spellbook_dir(), get_port(), get_host())
        success, msg = mgr.install()
    else:
        print(f"Error: Unsupported platform: {plat}", file=sys.stderr)
        return 1

    if success:
        print(f"\n{msg}")
        print(f"\nServer will start automatically on boot.")
        print(f"Log file: {get_log_file()}")

        # Wait for server to start
        print("\nWaiting for server to start...", end=" ", flush=True)
        for _ in range(10):
            time.sleep(1)
            if check_server_health():
                print("OK")
                break
        else:
            print("(may still be starting)")

        print(f"\nTo configure Claude Code to use the HTTP server:")
        print(f"  claude mcp add --transport http spellbook {get_server_url()}")
        return 0
    else:
        print(f"\nError: {msg}", file=sys.stderr)
        return 1


def cmd_uninstall() -> int:
    """Uninstall system service."""
    plat = get_platform()

    print(f"Uninstalling spellbook MCP server system service...")

    if plat == "darwin":
        success, msg = uninstall_launchd()
    elif plat == "linux":
        success, msg = uninstall_systemd()
    elif plat == "windows":
        from installer.compat import ServiceManager
        mgr = ServiceManager(get_spellbook_dir(), get_port(), get_host())
        success, msg = mgr.uninstall()
    else:
        print(f"Error: Unsupported platform: {plat}", file=sys.stderr)
        return 1

    print(msg)
    return 0 if success else 1


def cmd_start(foreground: bool = False) -> int:
    """Start the server manually (without system service)."""
    if is_service_installed() and is_service_running():
        print("Server is running via system service.")
        print(f"URL: {get_server_url()}")
        print("\nUse 'spellbook-server stop' to stop, or manage via system service.")
        return 0

    if check_server_health():
        print("Server already running")
        print(f"URL: {get_server_url()}")
        return 0

    # Check for uv
    if not check_uv_installed():
        return 1

    spellbook_dir = get_spellbook_dir()
    server_script = get_server_script()
    uv_path = get_uv_path()

    if not server_script.exists():
        print(f"Error: Server script not found: {server_script}", file=sys.stderr)
        return 1

    port = get_port()
    host = get_host()
    log_file = get_log_file()

    env = os.environ.copy()
    env["SPELLBOOK_MCP_TRANSPORT"] = "streamable-http"
    env["SPELLBOOK_MCP_HOST"] = host
    env["SPELLBOOK_MCP_PORT"] = str(port)
    env["SPELLBOOK_DIR"] = str(spellbook_dir)

    # Use uv run to automatically install dependencies
    cmd = [uv_path, "run", str(server_script)]

    if foreground:
        print(f"Starting server on {host}:{port} (foreground mode)")
        print(f"URL: {get_server_url()}")
        print("Press Ctrl+C to stop")
        try:
            proc = subprocess.run(cmd, env=env)
            return proc.returncode
        except KeyboardInterrupt:
            print("\nStopped")
            return 0
    else:
        print(f"Starting server on {host}:{port}")

        with open(log_file, "a") as log:
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=(sys.platform != "win32"),
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if sys.platform == "win32" else 0,
            )

        write_pid(proc.pid)

        time.sleep(2)
        if proc.poll() is not None:
            print(f"Error: Server failed to start. Check log: {log_file}", file=sys.stderr)
            get_pid_file().unlink(missing_ok=True)
            return 1

        print(f"Server started (PID {proc.pid})")
        print(f"URL: {get_server_url()}")
        print(f"Log: {log_file}")
        return 0


def cmd_stop() -> int:
    """Stop the server."""
    plat = get_platform()

    # If running via system service, stop it that way
    if is_service_installed():
        print("Stopping system service...")
        if plat == "darwin":
            result = subprocess.run(
                ["launchctl", "unload", str(get_launchd_plist_path())],
                capture_output=True
            )
            # Reload to restart
            subprocess.run(
                ["launchctl", "load", str(get_launchd_plist_path())],
                capture_output=True
            )
            print("Service stopped (will restart due to KeepAlive)")
            print("To permanently stop, run: spellbook-server uninstall")
        elif plat == "linux":
            subprocess.run(
                ["systemctl", "--user", "stop", SERVICE_NAME],
                capture_output=True
            )
            print("Service stopped (will restart on next boot)")
            print("To permanently stop, run: spellbook-server uninstall")
        elif plat == "windows":
            subprocess.run(
                ["schtasks", "/End", "/TN", "SpellbookMCP"],
                capture_output=True
            )
            print("Service stopped (will restart on next logon)")
            print("To permanently stop, run: spellbook-server uninstall")
        return 0

    # Manual stop via PID
    pid = read_pid()
    if pid is None:
        print("Server not running")
        return 0

    print(f"Stopping server (PID {pid})")
    from installer.compat import _pid_exists

    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)
        time.sleep(1)
        if _pid_exists(pid):
            print("Force killing...")
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(10):
                time.sleep(0.5)
                if not _pid_exists(pid):
                    break
            else:
                print("Force killing...")
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    get_pid_file().unlink(missing_ok=True)
    print("Server stopped")
    return 0


def cmd_restart() -> int:
    """Restart the server."""
    plat = get_platform()

    if is_service_installed():
        print("Restarting system service...")
        if plat == "darwin":
            plist_path = get_launchd_plist_path()
            subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
            subprocess.run(["launchctl", "load", str(plist_path)], capture_output=True)
        elif plat == "linux":
            subprocess.run(
                ["systemctl", "--user", "restart", SERVICE_NAME],
                capture_output=True
            )
        elif plat == "windows":
            subprocess.run(["schtasks", "/End", "/TN", "SpellbookMCP"], capture_output=True)
            time.sleep(1)
            subprocess.run(["schtasks", "/Run", "/TN", "SpellbookMCP"], capture_output=True)
        print("Service restarted")
        return 0

    cmd_stop()
    time.sleep(1)
    return cmd_start()


def cmd_status() -> int:
    """Show server status."""
    plat = get_platform()
    installed = is_service_installed()
    running = is_service_running() if installed else read_pid() is not None
    healthy = check_server_health()

    print(f"Platform: {plat}")
    print(f"Service installed: {'yes' if installed else 'no'}")
    print(f"Server running: {'yes' if running else 'no'}")
    print(f"Health check: {'OK' if healthy else 'not responding'}")
    print(f"URL: {get_server_url()}")
    print(f"Log: {get_log_file()}")

    if installed:
        if plat == "darwin":
            print(f"Service file: {get_launchd_plist_path()}")
        elif plat == "linux":
            print(f"Service file: {get_systemd_service_path()}")

    return 0 if healthy else 1


def cmd_url() -> int:
    """Show the server URL."""
    print(get_server_url())
    return 0


def cmd_logs(follow: bool = False, lines: int = 50) -> int:
    """Show server logs."""
    import collections

    log_file = get_log_file()

    if not log_file.exists():
        print("No log file found")
        return 1

    if follow:
        if sys.platform == "win32":
            # Windows: seek-to-end + polling loop
            with open(log_file) as f:
                f.seek(0, 2)  # Seek to end
                try:
                    while True:
                        line = f.readline()
                        if line:
                            print(line, end="")
                        else:
                            time.sleep(0.5)
                except KeyboardInterrupt:
                    pass
        else:
            subprocess.run(["tail", "-f", str(log_file)])
    else:
        # Cross-platform: read last N lines using deque
        with open(log_file) as f:
            last_lines = collections.deque(f, maxlen=lines)
        for line in last_lines:
            print(line, end="")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Manage the spellbook MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # install
    subparsers.add_parser("install", help="Install as system service (starts on boot)")

    # uninstall
    subparsers.add_parser("uninstall", help="Uninstall system service")

    # start
    start_parser = subparsers.add_parser("start", help="Start server manually")
    start_parser.add_argument("-f", "--foreground", action="store_true",
                              help="Run in foreground (don't daemonize)")

    # stop
    subparsers.add_parser("stop", help="Stop the server")

    # restart
    subparsers.add_parser("restart", help="Restart the server")

    # status
    subparsers.add_parser("status", help="Show server status")

    # url
    subparsers.add_parser("url", help="Show server URL")

    # logs
    logs_parser = subparsers.add_parser("logs", help="Show server logs")
    logs_parser.add_argument("-f", "--follow", action="store_true",
                             help="Follow log output")
    logs_parser.add_argument("-n", "--lines", type=int, default=50,
                             help="Number of lines to show (default: 50)")

    args = parser.parse_args()

    if args.command == "install":
        return cmd_install()
    elif args.command == "uninstall":
        return cmd_uninstall()
    elif args.command == "start":
        return cmd_start(foreground=args.foreground)
    elif args.command == "stop":
        return cmd_stop()
    elif args.command == "restart":
        return cmd_restart()
    elif args.command == "status":
        return cmd_status()
    elif args.command == "url":
        return cmd_url()
    elif args.command == "logs":
        return cmd_logs(follow=args.follow, lines=args.lines)

    return 1


if __name__ == "__main__":
    sys.exit(main())
