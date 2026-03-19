"""``spellbook admin`` command.

Opens the admin dashboard in the default browser by exchanging the
bearer token for a one-time browser auth token.
"""

from __future__ import annotations

import argparse
import sys


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``admin`` subcommand."""
    parser = subparsers.add_parser(
        "admin",
        help="Manage the spellbook web admin interface",
        description="Open or manage the spellbook web admin dashboard.",
    )
    parser.set_defaults(func=run)

    admin_subs = parser.add_subparsers(dest="admin_command")

    open_p = admin_subs.add_parser("open", help="Open admin dashboard in browser")
    open_p.add_argument(
        "--port",
        type=int,
        default=None,
        help="MCP server port (default: 8765 or SPELLBOOK_MCP_PORT)",
    )


def run(args: argparse.Namespace) -> None:
    """Execute the admin command."""
    subcmd = getattr(args, "admin_command", None)

    if subcmd is None:
        print("Usage: spellbook admin {open}")
        sys.exit(2)

    if subcmd == "open":
        from spellbook.admin.cli import admin_open

        port = getattr(args, "port", None)
        exit_code = admin_open(port=port)
        if exit_code != 0:
            sys.exit(exit_code)
