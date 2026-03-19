"""Core daemon operations: start, stop, restart, status, logs.

Provides the high-level functions for managing the spellbook MCP server
daemon, plus the CLI entry point (``main``).
"""

from __future__ import annotations

import argparse
import collections
import os
import signal
import subprocess
import sys
import time
from typing import Any

from spellbook.core.compat import _pid_exists
from spellbook.daemon._paths import (
    SERVICE_NAME,
    get_daemon_python,
    get_host,
    get_log_file,
    get_pid_file,
    get_platform,
    get_port,
    get_server_script,
    get_server_url,
    get_spellbook_dir,
    get_uv_path,
)
from spellbook.daemon.pid import read_pid, remove_pid, write_pid
from spellbook.daemon.service import (
    check_server_health,
    check_uv_installed,
    get_launchd_plist_path,
    get_systemd_service_path,
    install_service,
    is_service_installed,
    is_service_running,
    uninstall_service,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_daemon(foreground: bool = False) -> None:
    """Start the MCP server daemon.

    If a system service is installed and running, reports that instead.
    In background mode, daemonizes the server process and writes a PID file.

    Args:
        foreground: If True, run in the foreground (blocks until interrupted).
    """
    if is_service_installed() and is_service_running():
        print("Server is running via system service.")
        print(f"URL: {get_server_url()}")
        print("\nUse 'spellbook-server stop' to stop, or manage via system service.")
        return

    if check_server_health():
        print("Server already running")
        print(f"URL: {get_server_url()}")
        return

    spellbook_dir = get_spellbook_dir()
    server_script = get_server_script()

    daemon_python = get_daemon_python()
    uv_path: str | None = None
    if not daemon_python:
        if not check_uv_installed():
            sys.exit(1)
        uv_path = get_uv_path()

    if not server_script.exists():
        print(f"Error: Server script not found: {server_script}", file=sys.stderr)
        sys.exit(1)

    port = get_port()
    host = get_host()
    log_file = get_log_file()

    env = os.environ.copy()
    env["SPELLBOOK_MCP_TRANSPORT"] = "streamable-http"
    env["SPELLBOOK_MCP_HOST"] = host
    env["SPELLBOOK_MCP_PORT"] = str(port)
    env["SPELLBOOK_DIR"] = str(spellbook_dir)

    if daemon_python:
        cmd = [daemon_python, "-m", "spellbook.mcp.server"]
    else:
        cmd = [uv_path, "run", str(server_script)]  # type: ignore[list-item]

    if foreground:
        print(f"Starting server on {host}:{port} (foreground mode)")
        print(f"URL: {get_server_url()}")
        print("Press Ctrl+C to stop")
        try:
            proc = subprocess.run(cmd, env=env)
            sys.exit(proc.returncode)
        except KeyboardInterrupt:
            print("\nStopped")
            return
    else:
        print(f"Starting server on {host}:{port}")

        with open(log_file, "a") as log:
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=(sys.platform != "win32"),
                creationflags=(
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    if sys.platform == "win32"
                    else 0
                ),
            )

        write_pid(proc.pid)

        time.sleep(2)
        if proc.poll() is not None:
            print(
                f"Error: Server failed to start. Check log: {log_file}",
                file=sys.stderr,
            )
            get_pid_file().unlink(missing_ok=True)
            sys.exit(1)

        print(f"Server started (PID {proc.pid})")
        print(f"URL: {get_server_url()}")
        print(f"Log: {log_file}")


def stop_daemon() -> None:
    """Stop the MCP server daemon.

    Handles both service-managed and manually-started daemons.
    """
    plat = get_platform()

    if is_service_installed():
        print("Stopping system service...")
        try:
            if plat == "darwin":
                subprocess.run(
                    ["launchctl", "unload", str(get_launchd_plist_path())],
                    capture_output=True,
                )
                subprocess.run(
                    ["launchctl", "load", str(get_launchd_plist_path())],
                    capture_output=True,
                )
                print("Service stopped (will restart due to KeepAlive)")
                print("To permanently stop, run: spellbook-server uninstall")
            elif plat == "linux":
                subprocess.run(
                    ["systemctl", "--user", "stop", SERVICE_NAME],
                    capture_output=True,
                )
                print("Service stopped (will restart on next boot)")
                print("To permanently stop, run: spellbook-server uninstall")
            elif plat == "windows":
                subprocess.run(
                    ["schtasks", "/End", "/TN", "SpellbookMCP"],
                    capture_output=True,
                )
                print("Service stopped (will restart on next logon)")
                print("To permanently stop, run: spellbook-server uninstall")
        except FileNotFoundError:
            print("Service manager command not found", file=sys.stderr)
            sys.exit(1)
        return

    pid = read_pid()
    if pid is None:
        print("Server not running")
        return

    print(f"Stopping server (PID {pid})")

    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)
        time.sleep(1)
        if _pid_exists(pid):
            print("Force killing...")
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)], capture_output=True
            )
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

    remove_pid()
    print("Server stopped")


def restart_daemon() -> None:
    """Restart the MCP server daemon."""
    plat = get_platform()

    if is_service_installed():
        print("Restarting system service...")
        try:
            if plat == "darwin":
                plist_path = get_launchd_plist_path()
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)], capture_output=True
                )
                subprocess.run(
                    ["launchctl", "load", str(plist_path)], capture_output=True
                )
            elif plat == "linux":
                subprocess.run(
                    ["systemctl", "--user", "restart", SERVICE_NAME],
                    capture_output=True,
                )
            elif plat == "windows":
                subprocess.run(
                    ["schtasks", "/End", "/TN", "SpellbookMCP"],
                    capture_output=True,
                )
                time.sleep(1)
                subprocess.run(
                    ["schtasks", "/Run", "/TN", "SpellbookMCP"],
                    capture_output=True,
                )
        except FileNotFoundError:
            print("Service manager command not found", file=sys.stderr)
            sys.exit(1)
        print("Service restarted")
        return

    stop_daemon()
    time.sleep(1)
    start_daemon()


def daemon_status() -> dict[str, Any]:
    """Get current daemon status.

    Returns:
        A dict with keys:
        - ``running`` (bool): Whether the daemon is responding.
        - ``pid`` (int | None): The daemon PID, or None.
        - ``port`` (int): The configured port.
        - ``uptime`` (str | None): Placeholder for future uptime tracking.
    """
    installed = is_service_installed()
    running = is_service_running() if installed else read_pid() is not None
    healthy = check_server_health()
    pid = read_pid()

    return {
        "running": running or healthy,
        "pid": pid,
        "port": get_port(),
        "uptime": None,  # Future: track daemon start time
    }


def show_logs(follow: bool = False, lines: int = 50) -> None:
    """Show server logs.

    Args:
        follow: If True, tail the log file continuously.
        lines: Number of trailing lines to display (default 50).
    """
    log_file = get_log_file()

    if not log_file.exists():
        print("No log file found")
        return

    if follow:
        if sys.platform == "win32":
            with open(log_file) as f:
                f.seek(0, 2)
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
        with open(log_file) as f:
            last_lines = collections.deque(f, maxlen=lines)
        for line in last_lines:
            print(line, end="")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _cmd_status() -> int:
    """Show server status (CLI wrapper)."""
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


def _cmd_url() -> int:
    """Show the server URL."""
    print(get_server_url())
    return 0


def main() -> None:
    """CLI entry point for the spellbook-server command."""
    parser = argparse.ArgumentParser(
        description="Manage the spellbook MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("install", help="Install as system service (starts on boot)")
    subparsers.add_parser("uninstall", help="Uninstall system service")

    start_parser = subparsers.add_parser("start", help="Start server manually")
    start_parser.add_argument(
        "-f",
        "--foreground",
        action="store_true",
        help="Run in foreground (don't daemonize)",
    )

    subparsers.add_parser("stop", help="Stop the server")
    subparsers.add_parser("restart", help="Restart the server")
    subparsers.add_parser("status", help="Show server status")
    subparsers.add_parser("url", help="Show server URL")

    logs_parser = subparsers.add_parser("logs", help="Show server logs")
    logs_parser.add_argument(
        "-f", "--follow", action="store_true", help="Follow log output"
    )
    logs_parser.add_argument(
        "-n",
        "--lines",
        type=int,
        default=50,
        help="Number of lines to show (default: 50)",
    )

    args = parser.parse_args()

    if args.command == "install":
        install_service()
    elif args.command == "uninstall":
        uninstall_service()
    elif args.command == "start":
        start_daemon(foreground=args.foreground)
    elif args.command == "stop":
        stop_daemon()
    elif args.command == "restart":
        restart_daemon()
    elif args.command == "status":
        sys.exit(_cmd_status())
    elif args.command == "url":
        sys.exit(_cmd_url())
    elif args.command == "logs":
        show_logs(follow=args.follow, lines=args.lines)
