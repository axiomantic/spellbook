"""``spellbook server`` command.

Subcommands: start, stop, restart, status, install, uninstall, logs.
Delegates to :mod:`spellbook.daemon.manager` and
:mod:`spellbook.daemon.service`.
"""

from __future__ import annotations

import argparse
import sys

from spellbook.cli.formatting import output


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``server`` subcommand with its nested subcommands."""
    parser = subparsers.add_parser(
        "server",
        help="Manage the spellbook MCP server daemon",
        description="Start, stop, and manage the spellbook MCP server daemon.",
    )
    parser.set_defaults(func=run)

    server_subs = parser.add_subparsers(dest="server_command")

    # start
    start_p = server_subs.add_parser("start", help="Start the server daemon")
    start_p.add_argument(
        "--foreground", "-f",
        action="store_true",
        default=False,
        help="Run in foreground (don't daemonize)",
    )

    # stop
    server_subs.add_parser("stop", help="Stop the server daemon")

    # restart
    server_subs.add_parser("restart", help="Restart the server daemon")

    # status
    server_subs.add_parser("status", help="Show server status")

    # install
    server_subs.add_parser("install", help="Install as system service")

    # uninstall
    server_subs.add_parser("uninstall", help="Uninstall system service")

    # logs
    logs_p = server_subs.add_parser("logs", help="Show server logs")
    logs_p.add_argument(
        "--follow", "-f",
        action="store_true",
        default=False,
        help="Follow log output",
    )
    logs_p.add_argument(
        "-n", "--lines",
        type=int,
        default=50,
        help="Number of lines to show (default: 50)",
    )


def run(args: argparse.Namespace) -> None:
    """Execute the server command."""
    subcmd = getattr(args, "server_command", None)

    if subcmd is None:
        # No subcommand given; print help
        print("Usage: spellbook server {start|stop|restart|status|install|uninstall|logs}")
        sys.exit(2)

    if subcmd == "start":
        from spellbook.daemon.manager import start_daemon

        start_daemon(foreground=getattr(args, "foreground", False))

    elif subcmd == "stop":
        from spellbook.daemon.manager import stop_daemon

        stop_daemon()

    elif subcmd == "restart":
        from spellbook.daemon.manager import restart_daemon

        restart_daemon()

    elif subcmd == "status":
        from spellbook.daemon.manager import daemon_status

        status = daemon_status()
        json_mode = getattr(args, "json", False)

        if json_mode:
            output(status, json_mode=True)
        else:
            running = status.get("running", False)
            pid = status.get("pid")
            port = status.get("port", 8765)

            print(f"Running: {'yes' if running else 'no'}")
            if pid:
                print(f"PID: {pid}")
            print(f"Port: {port}")

    elif subcmd == "install":
        from spellbook.daemon.service import install_service

        install_service()

    elif subcmd == "uninstall":
        from spellbook.daemon.service import uninstall_service

        uninstall_service()

    elif subcmd == "logs":
        from spellbook.daemon.manager import show_logs

        show_logs(
            follow=getattr(args, "follow", False),
            lines=getattr(args, "lines", 50),
        )
